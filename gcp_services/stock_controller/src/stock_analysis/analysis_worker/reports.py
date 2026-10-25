from __future__ import annotations

import hashlib
import json
import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from google.api_core.exceptions import NotFound
from stock_analysis.publication_contract import (validate_manifest, verify_artifact, with_attempt, attempt_notice, digest_json)
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.cloud import storage

from stock_analysis.contracts.analysis import AnalysisSheetRecord, PriceRange, support_validity_floor


@dataclass(frozen=True)
class ReportIndex:
    version: str
    blobs: dict[str, Any]
    publications: dict[str, Any] | None = None
    attempts: dict[str, Any] | None = None


class GcsAnalysisReportStore:
    def __init__(
        self,
        bucket_name: str,
        *,
        prefix: str = "runtime/analysis-reports",
        storage_client: storage.Client | None = None,
    ) -> None:
        client = storage_client or storage.Client()
        self._bucket = client.bucket(bucket_name)
        self._report_bucket = client.bucket(os.getenv('REPORT_BUCKET', 'stock-analysis-reports-naxo85'))
        self._prefix = prefix.rstrip("/")

    def index(self, tickers: tuple[str, ...]) -> ReportIndex:
        expected = {
            f"{self._prefix}/{ticker}.json": ticker for ticker in tickers
        }
        blobs = {
            blob.name: blob
            for blob in self._bucket.list_blobs(prefix=f"{self._prefix}/")
            if blob.name in expected
        }
        def metadata(ticker):
            def read(name):
                try:
                    return self._report_bucket.blob(name).download_as_bytes(timeout=20, retry=None).decode('utf-8')
                except NotFound:
                    return None
            raw = read(f'{ticker}/publication.json')
            publication = validate_manifest(json.loads(raw), ticker) if raw is not None else None
            if publication is not None and not publication.get('committed_at'):
                raise ValueError('publication_pointer_not_committed')
            from stock_analysis.publication_contract import read_attempt
            return ticker, publication, read_attempt(read, ticker)
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(tickers)))) as executor:
            metadata_rows = list(executor.map(metadata, tickers))
        publications = {ticker: publication for ticker, publication, _ in metadata_rows if publication}
        attempts = {ticker: attempt for ticker, _, attempt in metadata_rows if attempt}
        missing = [ticker for name, ticker in expected.items() if name not in blobs and ticker not in publications and ticker not in attempts]
        if missing:
            raise RuntimeError('analysis report mirror incomplete: ' + ', '.join(sorted(missing)))
        by_ticker = {ticker: blobs.get(name) for name, ticker in expected.items()}
        fingerprint = digest_json({ticker: {
            'generation': str(getattr(blob, 'generation', None)),
            'publication': publications.get(ticker), 'attempt': attempts.get(ticker)}
            for ticker, blob in by_ticker.items()})
        return ReportIndex(version=fingerprint, blobs=by_ticker, publications=publications, attempts=attempts)

    def load(self, index: ReportIndex) -> dict[str, dict[str, Any]]:
        def download(item: tuple[str, Any]) -> tuple[str, dict[str, Any]]:
            ticker, blob = item
            manifest = (index.publications or {}).get(ticker)
            if manifest:
                # Use the pointer frozen by index(), not aliases or a second pointer read.
                body = self._report_bucket.blob(manifest['files']['json']['name']).download_as_bytes(timeout=30).decode('utf-8')
                payload = json.loads(verify_artifact(manifest, 'json', body))
            elif blob is None:
                payload = {'symbol': ticker, 'analysis_status': 'unavailable', '_report_unavailable': True}
            else:
                payload = json.loads(blob.download_as_bytes().decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError(f'analysis report is not an object: {ticker}')
            return ticker, with_attempt(payload, (index.attempts or {}).get(ticker), manifest)
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(index.blobs)))) as executor:
            return dict(executor.map(download, index.blobs.items()))

    def last_synced_version(self) -> str | None:
        payload = self.sync_state()
        return str(payload.get("version") or "") or None

    def sync_state(self) -> dict[str, Any]:
        blob = self._bucket.blob(f"{self._prefix}/sync-state.json")
        if not blob.exists():
            return {}
        payload = json.loads(blob.download_as_bytes().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    def mark_synced(
        self,
        version: str,
        ticker_count: int,
        *,
        report_generations: dict[str, str] | None = None,
        score_presentations: dict[str, dict[str, str | None]] | None = None,
        support_validity: dict[str, Any] | None = None,
        earnings: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "schema_version": 2,
            "version": version,
            "ticker_count": ticker_count,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "report_generations": report_generations or {},
            "score_presentations": score_presentations or {},
            "score_presentation_version": 2,
            "support_validity": support_validity or {},
            "earnings": earnings or {},
        }
        self._bucket.blob(f"{self._prefix}/sync-state.json").upload_from_string(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            content_type="application/json; charset=utf-8",
        )


def parse_analysis_report(
    ticker: str,
    payload: dict[str, Any],
    *,
    report_url_template: str,
    previous_score_override: float | None = None,
) -> AnalysisSheetRecord:
    normalized = ticker.strip().upper()
    if str(payload.get("symbol") or "").strip().upper() != normalized:
        raise ValueError(f"report symbol mismatch: expected={normalized}")
    if (payload.get('_report_unavailable') is True and payload.get('analysis_status') == 'unavailable'
            and isinstance(payload.get('latest_attempt'), dict)):
        return AnalysisSheetRecord(ticker=normalized, score=None, entry=None, washout=None,
            entry_stop=None, washout_stop=None, resistance=None, entry_strength=None,
            washout_strength=None, resistance_strength=None, generated_at=None,
            report_url=report_url_template.format(ticker=normalized), score_background=None,
            score_note='Todavía no hay un informe válido disponible.',
            attempt_notice=attempt_notice(payload['latest_attempt'], has_report=False),
            last_attempt_status=payload['latest_attempt'].get('status'))
    if payload.get("analysis_status") != "ok":
        raise ValueError(f"analysis report is not valid: {normalized}")
    validation = payload.get("validation")
    if isinstance(validation, dict) and validation.get("ok") is False:
        raise ValueError(f"analysis validation failed: {normalized}")

    plan = payload.get("plan")
    decision = payload.get("decision")
    if not isinstance(plan, dict) or not isinstance(decision, dict):
        raise ValueError(f"structured report fields are missing: {normalized}")

    generated_at = _datetime(payload.get("generated_at"), normalized)
    if decision.get("score_basis") == "thesis" or any(decision.get(key) is not None for key in ("thesis_score", "setup_score")):
        for key in ("thesis_score", "setup_score"):
            if _dimension_score(decision, key) is None:
                raise ValueError(f"missing {key}: {normalized}")
        if decision.get("score") != decision.get("thesis_score"):
            raise ValueError(f"score must alias thesis_score: {normalized}")
    reference_price = (
        _number(decision.get("reference_price"))
        or _number(payload.get("latest_price"))
    )
    entry = _normalized_range(_price_range(plan.get("entry")), reference_price)
    washout = _normalized_range(
        _price_range(plan.get("ambitious_entry")),
        reference_price,
    )
    management_stop = _normalized_level(
        _number(plan.get("management_stop")),
        reference_price,
    )
    structural_stop = _normalized_level(
        _number(plan.get("structural_stop")),
        reference_price,
    )
    resistance = _normalized_range(
        _price_range(plan.get("resistance")),
        reference_price,
    )
    entry_strength = _strength(payload, "entry")
    washout_strength = _strength(payload, "washout")
    resistance_strength = _strength(payload, "resistance")
    entry_strength_category = _strength_category(payload, "entry", entry_strength)
    washout_strength_category = _strength_category(
        payload,
        "washout",
        washout_strength,
    )
    resistance_strength_category = _strength_category(
        payload,
        "resistance",
        resistance_strength,
    )
    entry_strength_factors = _strength_factors(payload, "entry")
    washout_strength_factors = _strength_factors(payload, "washout")
    resistance_strength_factors = _strength_factors(payload, "resistance")
    entry_strength_breakdown = _strength_breakdown(payload, "entry")
    washout_strength_breakdown = _strength_breakdown(payload, "washout")
    resistance_strength_breakdown = _strength_breakdown(payload, "resistance")
    schema_version = int(payload.get("report_schema_version") or 0)
    if schema_version >= 3:
        _require_strength(
            normalized,
            "entry",
            entry_strength,
            entry_strength_category,
            entry_strength_factors,
            entry_strength_breakdown,
            applicable=not _explicit_absent_entry(payload),
            require_breakdown=schema_version >= 4,
            require_current_rubric=schema_version >= 5,
        )
        _require_strength(
            normalized,
            "washout",
            washout_strength,
            washout_strength_category,
            washout_strength_factors,
            washout_strength_breakdown,
            applicable=washout is not None,
            require_breakdown=schema_version >= 4,
            require_current_rubric=schema_version >= 5,
        )
    metadata = ((payload.get('semantic_report') or {}).get('data') or {}).get('metadata') or {}
    support_only = max(metadata.get('source_contract_revision', 0),
                       metadata.get('reader_format_revision', 0)) >= 35
    if schema_version >= 6 and not support_only:
        if resistance is None:
            raise ValueError(f"invalid resistance range: {normalized}")
        _require_strength(
            normalized,
            "resistance",
            resistance_strength,
            resistance_strength_category,
            resistance_strength_factors,
            resistance_strength_breakdown,
            applicable=True,
            require_breakdown=True,
            require_current_rubric=True,
        )
    return AnalysisSheetRecord(
        ticker=normalized,
        attempt_notice=attempt_notice(payload.get("latest_attempt")),
        last_attempt_status=(payload.get("latest_attempt") or {}).get("status"),
        thesis_score=_dimension_score(decision, "thesis_score"),
        setup_score=_dimension_score(decision, "setup_score"),
        thesis_reason=str(decision.get("thesis_reason") or ""),
        setup_reason=str(decision.get("setup_reason") or ""),
        score=_number(decision.get("score")),
        entry=entry,
        washout=washout,
        entry_stop=_valid_stop(entry, management_stop, structural_stop),
        washout_stop=_valid_stop(washout, structural_stop),
        resistance=_valid_resistance(resistance, reference_price),
        entry_strength=entry_strength,
        washout_strength=washout_strength,
        resistance_strength=resistance_strength,
        generated_at=generated_at,
        report_url=_versioned_report_url(report_url_template.format(ticker=normalized), payload.get("publication_version")),
        score_background=_score_background(
            payload,
            decision.get("score"),
            previous_score_override=previous_score_override,
        ),
        score_note=_score_note(
            payload,
            decision.get("score"),
            previous_score_override=previous_score_override,
        ),
        entry_strength_category=entry_strength_category,
        entry_strength_factors=entry_strength_factors,
        washout_strength_category=washout_strength_category,
        washout_strength_factors=washout_strength_factors,
        resistance_strength_category=resistance_strength_category,
        resistance_strength_factors=resistance_strength_factors,
        resistance_strength_breakdown=resistance_strength_breakdown,
        entry_support_validity=_support_validity(payload, 'entry', entry),
        washout_support_validity=_support_validity(payload, 'ambitious_entry', washout),
    )


def _versioned_report_url(url: str, version: str | None) -> str:
    if not version:
        return url
    import re
    if not re.fullmatch('[0-9a-f]{64}', str(version)):
        raise ValueError('invalid_report_publication_version')
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != 'version']
    query.append(('version', version))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _support_validity(payload: dict[str, Any], key: str, normalized: PriceRange | None) -> dict[str, Any] | None:
    """Read the exact typed/mirrored estimate, not prices extracted from prose."""
    from copy import deepcopy
    plan = payload['plan']
    extent = plan.get(key + '_support_validity')
    source = (((payload.get('semantic_report') or {}).get('data') or {}).get('plan') or {}).get(key) or {}
    raw = _price_range(plan.get(key))
    if (normalized is None or raw is None or source.get('range') != plan.get(key)
            or extent != source.get('support_validity') or support_validity_floor(raw, extent) is None):
        return None
    result = {field: deepcopy(extent[field]) for field in ('lower_bound', 'range', 'reason', 'assessed_at')}
    # Existing report normalization may adjust a legacy price scale. Apply the
    # SAME transform to its bound, preserving the identity of this buying zone.
    result['lower_bound'] *= normalized.lower / raw.lower
    result['range'] = {'lower': normalized.lower, 'upper': normalized.upper}
    return result


def load_support_validity(bucket_name: str, prefix: str) -> dict[str, Any]:
    """One small projection read per quote refresh, without reading 46 reports."""
    return load_display_state(bucket_name, prefix).get('support_validity', {})


def load_display_state(bucket_name: str, prefix: str) -> dict[str, Any]:
    """Shared display data; source observation dates are retained exactly."""
    blob = storage.Client().bucket(bucket_name).blob(prefix.rstrip('/') + '/sync-state.json')
    payload = json.loads(blob.download_as_bytes(timeout=10, retry=None).decode('utf-8'))
    return {key: payload[key] for key in ('support_validity', 'earnings')
            if isinstance(payload, dict) and isinstance(payload.get(key), dict)}


def _explicit_absent_entry(payload: dict[str, Any]) -> bool:
    """Revision22 can deliberately publish no buyable support; missing data cannot."""
    stored = payload.get('semantic_report')
    data = stored.get('data') if isinstance(stored, dict) else None
    if not isinstance(data, dict):
        return False
    metadata = data.get('metadata')
    revision = metadata.get('source_contract_revision') if isinstance(metadata, dict) else None
    if not isinstance(revision, int) or revision < 22:
        return False
    semantic_plan = data.get('plan')
    level = semantic_plan.get('entry') if isinstance(semantic_plan, dict) else None
    plan = payload.get('plan')
    return (
        isinstance(plan, dict) and 'entry' in plan and plan['entry'] is None
        and isinstance(level, dict) and 'range' in level and level['range'] is None
        and 'strength' in level and level['strength'] is None
        and isinstance(level.get('reason'), str) and bool(level['reason'].strip())
    )


def _dimension_score(decision: dict[str, Any], key: str) -> float | None:
    value = _number(decision.get(key))
    if value is not None and not 0 <= value <= 10:
        raise ValueError(f"invalid {key}")
    return value


def _datetime(value: Any, ticker: str) -> datetime:
    if not value:
        raise ValueError(f"generated_at is missing: {ticker}")
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _price_range(value: Any) -> PriceRange | None:
    if not isinstance(value, dict):
        return None
    lower = _number(value.get("lower"))
    upper = _number(value.get("upper"))
    if lower is None or upper is None or lower <= 0 or upper < lower:
        return None
    return PriceRange(lower=lower, upper=upper)


def _normalized_range(
    level: PriceRange | None,
    reference_price: float | None,
) -> PriceRange | None:
    if level is None:
        return None
    lower = _normalized_level(level.lower, reference_price)
    upper = _normalized_level(level.upper, reference_price)
    if lower is None or upper is None or upper < lower:
        return None
    return PriceRange(lower=lower, upper=upper)


def _normalized_level(
    level: float | None,
    reference_price: float | None,
) -> float | None:
    if level is None or reference_price is None or reference_price <= 0:
        return level
    ratio = level / reference_price
    scaled_ratio = level * 1000 / reference_price
    if ratio < 0.01 and 0.1 <= scaled_ratio <= 10:
        level *= 1000
        ratio = scaled_ratio
    if not 0.02 <= ratio <= 10:
        return None
    return level


def _valid_stop(level: PriceRange | None, *candidates: float | None) -> float | None:
    if level is None:
        return None
    return next(
        (
            candidate
            for candidate in candidates
            if candidate is not None and candidate < level.lower
        ),
        None,
    )


def _valid_resistance(
    resistance: PriceRange | None,
    reference_price: float | None,
) -> PriceRange | None:
    if resistance is None:
        return None
    if reference_price is not None and resistance.upper < reference_price:
        return None
    return resistance


def _strength(payload: dict[str, Any], level: str) -> int | None:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    strengths = payload.get("level_strengths")
    candidates = (
        plan.get(f"{level}_strength"),
        plan.get(f"{level}_strength_score"),
        strengths.get(level) if isinstance(strengths, dict) else None,
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("score")
        number = _number(candidate)
        if number is not None and 0 <= number <= 100:
            return round(number)
    return None


def _strength_category(
    payload: dict[str, Any],
    level: str,
    score: int | None,
) -> str | None:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    strengths = payload.get("level_strengths")
    nested = strengths.get(level) if isinstance(strengths, dict) else None
    if score is not None:
        return _expected_strength_category(score)
    value = plan.get(f"{level}_strength_category")
    if value is None and isinstance(nested, dict):
        value = nested.get("category")
    if value:
        return str(value).strip().lower()
    return None


def _strength_factors(payload: dict[str, Any], level: str) -> str | None:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    strengths = payload.get("level_strengths")
    nested = strengths.get(level) if isinstance(strengths, dict) else None
    value = plan.get(f"{level}_strength_factors")
    if value is None and isinstance(nested, dict):
        value = nested.get("factors") or nested.get("reason")
    text = str(value or "").strip()
    return text or None


def _strength_breakdown(payload: dict[str, Any], level: str) -> dict[str, int] | None:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    value = plan.get(f"{level}_strength_breakdown")
    if not isinstance(value, dict):
        return None
    maxima = {
        "estructura": 25,
        "volumen": 20,
        "opciones": 25,
        "confluencia": 15,
        "durabilidad": 15,
    }
    result: dict[str, int] = {}
    for key, maximum in maxima.items():
        number = _number(value.get(key))
        if number is None or number != round(number) or not 0 <= number <= maximum:
            return None
        result[key] = round(number)
    return result if len(value) == len(maxima) else None


def _expected_strength_category(score: int | None) -> str | None:
    if score is None:
        return None
    if score < 40:
        return "débil"
    if score < 70:
        return "moderado"
    if score < 85:
        return "sólido"
    if score < 95:
        return "fuerte"
    return "excepcional"


def _strength_breakdown_qualifies(score: int, breakdown: dict[str, int]) -> bool:
    if score < 70:
        return True
    structure = breakdown["estructura"]
    volume = breakdown["volumen"]
    options = breakdown["opciones"]
    confluence = breakdown["confluencia"]
    durability = breakdown["durabilidad"]
    if structure < 13 or (volume < 10 and options < 12):
        return False
    if score < 85:
        return True
    primary_pillars = sum(
        (structure >= 18, volume >= 14, options >= 18)
    )
    if (
        primary_pillars < 2
        or (structure < 18 and volume < 14)
        or confluence < 10
        or durability < 9
    ):
        return False
    if score >= 95:
        return (
            structure >= 22
            and volume >= 17
            and confluence >= 13
            and durability >= 12
        )
    return True


def _require_strength(
    ticker: str,
    level: str,
    score: int | None,
    category: str | None,
    factors: str | None,
    breakdown: dict[str, int] | None,
    *,
    applicable: bool,
    require_breakdown: bool,
    require_current_rubric: bool,
) -> None:
    if not applicable:
        if (
            score is not None
            or category != "no_aplica"
            or not factors
            or (require_breakdown and breakdown not in ({}, None))
        ):
            raise ValueError(f"invalid {level} strength: {ticker}")
        return
    if (
        score is None
        or category != _expected_strength_category(score)
        or not factors
        or (
            require_breakdown
            and (
                breakdown is None
                or sum(breakdown.values()) != score
                or (
                    require_current_rubric
                    and not _strength_breakdown_qualifies(score, breakdown)
                )
            )
        )
    ):
        raise ValueError(f"invalid {level} strength: {ticker}")


def _score_change(
    payload: dict[str, Any],
    score: Any,
    *,
    previous_score_override: float | None = None,
) -> tuple[float, float] | None:
    changes = payload.get("changes")
    if isinstance(changes, dict) and changes.get("score_basis_changed"):
        return None
    previous = _number(previous_score_override)
    if previous is None and isinstance(changes, dict):
        previous = _number(changes.get("previous_score"))
    current = _number(score)
    if previous is None or current is None or abs(current - previous) < 0.5:
        return None
    return previous, current


def _reference_retained(payload: dict[str, Any]) -> dict[str, Any] | None:
    workflow = payload.get("analysis_workflow")
    if not isinstance(workflow, dict):
        return None
    if workflow.get("status") != "reference_retained_low_confidence":
        return None
    return workflow


def _score_background(
    payload: dict[str, Any],
    score: Any,
    *,
    previous_score_override: float | None = None,
) -> str | None:
    if _reference_retained(payload):
        return "#FFF2CC"
    change = _score_change(
        payload,
        score,
        previous_score_override=previous_score_override,
    )
    if change is None:
        return None
    return "#D9EAD3" if change[1] > change[0] else "#F4CCCC"


def _score_note(
    payload: dict[str, Any],
    score: Any,
    *,
    previous_score_override: float | None = None,
) -> str:
    workflow = _reference_retained(payload)
    if workflow:
        reference = _short_date(workflow.get("reference_generated_at"))
        followup = _short_date(
            workflow.get("followup_generated_at") or payload.get("generated_at")
        )
        confidence = _number(workflow.get("effective_confidence"))
        suffix = (
            f" Confianza del cambio propuesto: {confidence:.0f}%."
            if confidence is not None
            else ""
        )
        return (
            f"Seguimiento nuevo del {followup}. Se conserva la referencia oficial "
            f"del {reference}; la nota y los niveles pertenecen a esa referencia."
            f"{suffix}"
        )
    change = _score_change(
        payload,
        score,
        previous_score_override=previous_score_override,
    )
    if change is None:
        return ""
    previous, current = change
    direction = "subió" if current > previous else "bajó"
    delta = f"{current - previous:+.1f}".replace(".", ",")
    return (
        f"La nota {direction}: {_decimal(previous)} → {_decimal(current)} "
        f"({delta}). Umbral visual: 0,5 puntos."
    )


def _short_date(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(
            "%d/%m/%Y"
        )
    except (TypeError, ValueError):
        return "fecha desconocida"


def _decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")
