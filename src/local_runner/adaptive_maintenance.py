"""Exact, evidence-linked daily edits; Sol's fundamental anchor stays immutable.

This is a structural/contract gate, not a semantic fact checker. The model must
classify materiality and uncertainty, and the caller must validate the complete
candidate with the established arithmetic, origin and continuity validator.
Integrity failures never authorize another model call. Repairable rejected
updates can receive one explicit Luna correction under the frozen policy.
"""
from __future__ import annotations

from copy import deepcopy
import difflib
from datetime import datetime, timezone
import hashlib
import math
import re
import unicodedata

from src.common.analysis_validator import (
    _extract_line_value, _to_number, extract_range, format_exact_price,
)
from src.local_runner.adaptive_context import resolve_evidence
from src.local_runner.adaptive_policy import SECTIONS, TRIAGE_SCHEMA, triage_schema
from src.local_runner.level_continuity import build_level_continuity_precheck
from src.local_runner.report_dates import parse_report_date
from src.local_runner.report_schema import parse_report
from src.local_runner.source_urls import cited_urls
from src.local_runner.adaptive_patch_normalization import (
    contiguous_editable_spans, locate_report_date_edit, refresh_level_percentages, refresh_inherited_snapshot,
    quote_snapshot_field, validate_quote_snapshot, refresh_derived_market_fields,
    SNAPSHOT_LABELS, validate_typed_snapshot_fields,
)

EVIDENCE_ROOTS = ("/reference", "/slim", "/news", "/analyst_actions", "/sol_reference")
RISK_FIELDS = ("thesis_change", "critical_catalyst", "structural_invalidation", "requires_research")
LEVEL_LABELS = ("Entrada", "Entrada ambiciosa", "Stop de gestión", "Stop estructural",
                "Resistencia estructural", "Salida / objetivo principal")
NOTE_HEADER = "## Actualización diaria (Luna)"


def maintenance_schema(context: dict) -> dict:
    """Invariant schema across tickers, keeping the original six assessments."""
    if context.get('routing_revision', 1) >= 9:
        from src.local_runner.semantic_report import nullable, update_schema
        schema = maintenance_schema({**context, 'routing_revision': 8})
        del schema['properties']['edits']
        schema['required'].remove('edits')
        schema['properties']['update'] = nullable(update_schema(context.get('routing_revision', 9)))
        schema['required'].append('update')
        if context.get('routing_revision', 1) >= 11:
            del schema['properties']['base_markdown_sha256']
            schema['required'].remove('base_markdown_sha256')
        if context.get('routing_revision', 1) >= 12 and context.get('maintenance_repair'):
            # Only a correction needs input-specific constrained choices. The
            # ordinary schema/prefix remains identical across all tickers for
            # session and prompt-cache reuse. No fuzzy source substitutions.
            from src.local_runner.semantic_sources import source_catalog
            choices = list(source_catalog(context))
            if choices:
                plan = schema['properties']['update']['anyOf'][0]['properties']['plan']['properties']
                for entry in plan.values():
                    level = entry['anyOf'][0]['properties']
                    for field in ('evidence', 'facts'):
                        level[field]['items'] = {'type': 'string', 'enum': choices}
                    if context.get('routing_revision', 1) >= 14:
                        review = level['change_review']['properties']
                        for field in ('previous_evidence', 'current_evidence'):
                            review[field]['items'] = {'type': 'string', 'enum': choices}
        if context.get('routing_revision', 1) >= 18:
            from src.local_runner.review_contract import coverage_schema
            schema['properties']['news_review'] = coverage_schema()
            schema['required'].append('news_review')
        if context.get('routing_revision', 1) >= 20:
            del schema['properties']['routine_note']
            schema['required'].remove('routine_note')
        if context.get('routing_revision', 1) >= 32:
            from src.local_runner.reader_report import review_schema
            schema['properties']['reader_review'] = review_schema(context.get('routing_revision', 1))
            schema['required'].append('reader_review')
        if context.get('routing_revision', 1) >= 36:
            from src.local_runner.support_validity import review_schema
            schema['properties']['support_validity_review'] = review_schema()
            schema['required'].append('support_validity_review')
        return schema
    schema = triage_schema(context)
    schema["properties"]["decision"]["enum"] = ["retain", "update", "escalate", "blocked"]
    schema["$defs"]["evidence_pointer"]["enum"] = [*EVIDENCE_ROOTS, "/guards"]
    if context.get("routing_revision", 1) >= 4:
        schema["$defs"]["evidence_pointer"]["enum"].append("/comparison")
    schema["$defs"]["edit_evidence_pointer"] = {
        "type": "string", "pattern": r"^/(?:reference|slim|news|analyst_actions|sol_reference)(?:/|$)",
    }
    schema["properties"].update({
        "base_markdown_sha256": {"type": "string"},
        "edits": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"before": {"type": "string"}, "after": {"type": "string"},
                           "reason": {"type": "string"},
                           "evidence": {"type": "array", "items": {"$ref": "#/$defs/edit_evidence_pointer"}}},
            "required": ["before", "after", "reason", "evidence"],
        }},
        "risk": {"type": "object", "additionalProperties": False,
                 "properties": {key: {"type": "boolean"} for key in RISK_FIELDS},
                 "required": list(RISK_FIELDS)},
        "routine_note": {"type": "string"},
    })
    schema["required"] += ["base_markdown_sha256", "edits", "risk", "routine_note"]
    if context.get("routing_revision", 1) >= 5:
        schema["properties"]["evidence_gap"] = {"type": "string", "enum": ["none", "research", "essential_data"]}
        schema["required"].append("evidence_gap")
    return schema


def _evidence(context: dict, pointers: list, *, edits: bool) -> list:
    if not isinstance(pointers, list) or not pointers:
        raise ValueError("invalid_update_evidence_missing" if edits else "invalid_maintenance_evidence")
    roots = EVIDENCE_ROOTS if edits else (*EVIDENCE_ROOTS, "/guards")
    if not edits and context.get("routing_revision", 1) >= 4:
        roots = (*roots, "/comparison")
    values = []
    for pointer in pointers:
        if not isinstance(pointer, str) or not any(pointer == root or pointer.startswith(root + "/") for root in roots):
            raise ValueError("invalid_update_evidence_root")
        if context.get('routing_revision', 1) >= 11:
            from src.local_runner.semantic_sources import resolve_source
            values.append(resolve_source(context, pointer))
        else:
            values.append(resolve_evidence(context, pointer))
    return values


def maintenance_decision(payload: dict, guards: list[str], context: dict) -> str:
    """Validate maintenance output, distinguishing policy escalation from errors."""
    if context.get('routing_revision', 1) >= 9:
        from src.local_runner.semantic_report import check_schema
        routing_schema = maintenance_schema(context)
        # Financial update checks belong INSIDE the existing directed repair
        # loop, not before it. Routing/risk/integrity contracts remain strict.
        routing_schema['properties']['update'] = {'anyOf': [{'type': 'object'}, {'type': 'null'}]}
        if context.get('routing_revision', 1) >= 36:
            routing_schema['properties']['support_validity_review'] = {}
            routing_schema['required'].remove('support_validity_review')
        if context.get('routing_revision', 1) >= 32:
            # Presentation cannot block finance or buy a repair/escalation.
            # Exact selectors are checked conservatively when rendering.
            routing_schema['properties']['reader_review'] = {}
            routing_schema['required'].remove('reader_review')
        if context.get('routing_revision', 1) >= 18:
            # Missing coverage is a review omission, handled by the shared
            # directed repair, not a routing/integrity failure before it.
            routing_schema['properties']['news_review'] = {}
            routing_schema['required'].remove('news_review')
        check_schema(payload, routing_schema)
        if not payload['reason'].strip():
            raise ValueError('invalid_maintenance_contract')
        if (payload['decision'] == 'update') != (payload['update'] is not None):
            raise ValueError('invalid_maintenance_update_decision_contract')
        # A routing note is audit information, not an edit. Revision 9 has an
        # explicit update object as the sole authority to change the report;
        # do not pass its routing output through the old text-edit contract.
        for key in SECTIONS:
            if not payload[key]['assessment'].strip():
                raise ValueError('invalid_maintenance_assessment')
            _evidence(context, payload[key]['evidence'], edits=False)
        route = _maintenance_route(payload, guards, context)
        if (route != 'blocked' and context.get('routing_revision', 1) >= 18
                and isinstance(payload.get('news_review'), list)
                and any(isinstance(group, dict) and group.get('outcome') == 'critical_change'
                        for group in payload['news_review'])):
            route = 'escalate'
        if route == 'update' and context.get('routing_revision', 1) >= 12:
            change = payload['update']
            if context.get('routing_revision', 1) >= 21:
                from src.local_runner.maintenance_text import unchanged_text_update
                from src.local_runner.semantic_report import update_schema
                # Invalid edit shapes belong in the one shared repair, not here.
                try:
                    check_schema(change, update_schema(context['routing_revision'] if context['routing_revision'] >= 29 else 21))
                except ValueError:
                    pass
                else:
                    if unchanged_text_update(payload, context):
                        return 'retain'
            from src.local_runner.maintenance_text import note_text, explanation_texts
            revision = context.get('routing_revision', 1)
            explanation_present = (change.get('plan_explanation') is not None if revision < 20
                                   else bool(explanation_texts(change.get('plan_explanation'))))
            if (change.get('setup_score') is None and change.get('setup_reason') is None
                    and change.get('conclusion') is None and not explanation_present
                    and not note_text(payload, revision).strip()
                    and all(value is None for value in (change.get('plan') or {}).values())):
                # A truly empty proposal is retention, not a new dated report,
                # validation repair or paid full Sol. Check its exact shape.
                from src.local_runner.semantic_report import update_schema
                check_schema(change, update_schema(context.get('routing_revision', 12)))
                return 'retain'
        return route
    required = set(TRIAGE_SCHEMA["required"]) | {"base_markdown_sha256", "edits", "risk", "routine_note"}
    if context.get("routing_revision", 1) >= 5:
        required.add("evidence_gap")
    if (not isinstance(payload, dict) or set(payload) != required
            or payload.get("decision") not in {"retain", "update", "escalate", "blocked"}
            or type(payload.get("uncertainty")) is not bool
            or not isinstance(payload.get("reason"), str) or not payload["reason"].strip()
            or not isinstance(payload.get("base_markdown_sha256"), str)
            or not isinstance(payload.get("edits"), list)
            or not isinstance(payload.get("routine_note"), str)):
        raise ValueError("invalid_maintenance_contract")
    risk = payload.get("risk")
    if not isinstance(risk, dict) or set(risk) != set(RISK_FIELDS) or any(type(risk[key]) is not bool for key in RISK_FIELDS):
        raise ValueError("invalid_maintenance_risk_contract")
    for key in SECTIONS:
        item = payload[key]
        if (not isinstance(item, dict) or set(item) != {"assessment", "evidence"}
                or not isinstance(item["assessment"], str) or not item["assessment"].strip()):
            raise ValueError("invalid_maintenance_assessment")
        _evidence(context, item["evidence"], edits=False)
    for edit in payload["edits"]:
        if (not isinstance(edit, dict) or set(edit) != {"before", "after", "reason", "evidence"}
                or any(not isinstance(edit[key], str) or not edit[key].strip() for key in ("before", "after", "reason"))):
            raise ValueError("invalid_update_edit_contract")
        _evidence(context, edit["evidence"], edits=True)
    if payload["decision"] != "update" and (payload["edits"] or payload["routine_note"].strip()):
        raise ValueError("invalid_maintenance_edits_without_update")
    return _maintenance_route(payload, guards, context)


def _maintenance_route(payload: dict, guards: list[str], context: dict) -> str:
    """Route validated decisions; commentary never grants write authority."""
    risk = payload['risk']
    if context.get("routing_revision", 1) >= 5:
        gap = payload["evidence_gap"]
        if not isinstance(gap, str) or gap not in {"none", "research", "essential_data"}:
            raise ValueError("invalid_maintenance_evidence_gap")
        if gap == "essential_data":
            return "blocked"
        if gap == "research":
            return "escalate"
        if payload["decision"] == "blocked":
            raise ValueError("invalid_maintenance_blocked_without_data_gap")
    if payload["decision"] == "blocked":
        return "blocked"
    if guards or payload["uncertainty"] or any(risk.values()):
        return "escalate"
    if context.get('routing_revision', 1) >= 15:
        from src.local_runner.maintenance_change import commentary_requires_sol
        if commentary_requires_sol(payload):
            return 'escalate'
    return payload["decision"]


def _clean(line: str) -> str:
    return line.strip().lstrip("-*•# ").replace("**", "").replace("*", "").strip()


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold().split())


def _layout(markdown: str) -> dict:
    """Locate canonical sections and editable slots without reformatting bytes."""
    lines, offset = [], 0
    for line in markdown.splitlines(keepends=True):
        lines.append((offset, offset + len(line), line, _clean(line)))
        offset += len(line)
    sections = []
    for start, end, raw, clean in lines:
        match = re.match(r"^([0-4])\)\s+", clean)
        if match:
            sections.append((int(match[1]), start, end))
    if [section[0] for section in sections] != list(range(5)):
        raise ValueError("update_not_allowed_unrecognized_report_sections")
    starts = {key: start for key, start, _ in sections}
    ends = {key: end for key, _, end in sections}
    allowed = []
    # Exact fields in front matter, never arbitrary prose before summary.
    for start, end, raw, clean in lines:
        if start >= starts[0]:
            break
        if any(_norm(clean).startswith(prefix) for prefix in (
                "fecha del analisis:", "precio de referencia:", "snapshot tecnico congelado:")):
            allowed.append((start, end))
        elif _norm(clean).startswith(("snapshot tecnico:", "instantanea tecnica:")):
            allowed.append((start, end))
    summary_fields = []
    for start, end, raw, clean in lines:
        if ends[0] <= start < starts[1] and ":" in clean:
            prefix = _norm(clean.split(":", 1)[0])
            if prefix in {"tesis", "motivo de tesis", "setup", "motivo de setup", "narrativa actual"}:
                summary_fields.append((prefix, start, end))
    if [item[0] for item in summary_fields] != ["tesis", "motivo de tesis", "setup", "motivo de setup", "narrativa actual"]:
        raise ValueError("update_not_allowed_unrecognized_summary")
    setup_start, setup_end = summary_fields[2][1], summary_fields[4][1]
    allowed.append((setup_start, setup_end))
    note_positions = [(start, end) for start, end, raw, clean in lines if _norm(clean) == _norm("Actualización diaria (Luna)")]
    if len(note_positions) > 1:
        raise ValueError("update_not_allowed_duplicate_maintenance_note")
    note_start = note_positions[0][0] if note_positions else len(markdown)
    if note_start < ends[4]:
        raise ValueError("update_not_allowed_misplaced_maintenance_note")
    allowed += [(ends[3], starts[4]), (ends[4], note_start)]
    labels = {_norm(label): 0 for label in (*LEVEL_LABELS, "Tesis", "Motivo de Tesis", "Setup",
              "Motivo de Setup", "Narrativa actual", "Precio de referencia", "Fecha del análisis", "Estado actual")}
    for start, end, raw, clean in lines:
        if ":" in clean:
            label = _norm(clean.split(":", 1)[0])
            if label in labels:
                labels[label] += 1
    if any(count != 1 for count in labels.values()):
        raise ValueError("update_not_allowed_duplicate_or_missing_report_field")
    headings = tuple(raw for start, end, raw, clean in lines
                     if re.match(r"^\s*#{1,6}\s+", raw) and start < note_start)
    return {"allowed": allowed, "sections": sections, "lines": lines, "note_start": note_start,
            "protected": (markdown[starts[1]:starts[3]],
                          tuple(markdown[a:b] for _, a, b in sections),
                          markdown[ends[0]:setup_start], markdown[setup_end:starts[1]], headings)}


def _urls(value) -> set[str]:
    if isinstance(value, dict):
        if value.get("provenance") == "codex_web_result_not_independent_fact_check":
            # Only the URL actually returned by the tool is citation authority.
            # Links in titles/snippets are leads, not separately retrieved pages.
            url = value.get("url")
            return {url} if isinstance(url, str) and url.startswith(("https://", "http://")) else set()
        return set().union(*({child} if key == "url" and isinstance(child, str)
                            and child.startswith(("https://", "http://")) else _urls(child)
                            for key, child in value.items())) if value else set()
    if isinstance(value, list):
        return set().union(*(_urls(child) for child in value)) if value else set()
    return cited_urls(value)


def _check_urls(after: str, before: str, values: list, *, canonical=False) -> None:
    supported = _urls(before) | _urls(values)
    cited = _urls(after)
    if canonical:
        from src.local_runner.source_urls import url_identity
        supported, cited = {url_identity(u) for u in supported}, {url_identity(u) for u in cited}
    if not cited <= supported:
        raise ValueError("update_not_allowed_unsupported_url")


def _check_rendering(text: str) -> None:
    # A wrapper inserted in an editable paragraph could hide/turn into code
    # protected fundamental bytes while every plain-text equality still passes.
    if (re.search(r"(?m)^\s*(?:```|~~~)", text)
            or re.search(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?>|<!--", text)):
        raise ValueError("update_not_allowed_rendering_wrapper")


def _stop_explanation(markdown: str, label: str) -> str:
    """Protect the structural rationale while refreshing its percentage line."""
    lines = markdown.splitlines(keepends=True)
    start = None
    for index, line in enumerate(lines):
        clean = _clean(line)
        if ":" in clean and _norm(clean.split(":", 1)[0]) == _norm(label):
            if start is not None:
                raise ValueError("update_not_allowed_duplicate_stop")
            start = index
    if start is None:
        raise ValueError("update_not_allowed_missing_stop")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        clean = _clean(lines[index])
        if (re.match(r"^[0-4]\)\s", clean) or ":" in clean and
                _norm(clean.split(":", 1)[0]) in {_norm(level) for level in LEVEL_LABELS}):
            end = index
            break
    return "".join(lines[start + 1:end])


def _refresh_inherited_report_date(baseline: str, candidate: str, context: dict) -> tuple[str, list[dict]]:
    """Complete omitted maintenance metadata; never repair an authored wrong date.

    Only revision 4, an exact inherited valid past date, and the unique front
    matter field qualify. This does not touch the immutable Sol anchor or ITV.
    Missing/changed/malformed/future dates still fail the ordinary market gate.
    """
    if context.get("routing_revision", 1) < 4:
        return candidate, []
    before = (_extract_line_value(baseline, "Fecha del análisis") or "").strip()
    after = (_extract_line_value(candidate, "Fecha del análisis") or "").strip()
    if not before or after != before:
        return candidate, []
    prepared = str(context.get("prepared_at") or "")
    try:
        day = datetime.fromisoformat(prepared.replace("Z", "+00:00")).date()
    except ValueError:
        return candidate, []
    inherited_day = parse_report_date(before)
    if inherited_day is None or inherited_day >= day:
        return candidate, []
    # Narrow supported spellings. Do not replace dates in arbitrary prose.
    match = re.fullmatch(r"(?:\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}-\d{2}-\d{2})", before)
    if match is None:
        return candidate, []
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", before):
        replacement = day.isoformat()
    else:
        separator = "/" if "/" in before else "-"
        replacement = day.strftime("%d" + separator + "%m" + separator + "%Y")
    layout = _layout(candidate)
    summary_start = layout["sections"][0][1]
    for start, end, raw, clean in layout["lines"]:
        if start >= summary_start:
            break
        if _norm(clean.split(":", 1)[0]) == "fecha del analisis" and raw.count(before) == 1:
            updated = raw.replace(before, replacement, 1)
            return candidate[:start] + updated + candidate[end:], [{
                "method": "exact_inherited_maintenance_date_refresh",
                "field": "Fecha del análisis", "before": before, "after": replacement,
                "source": "/prepared_at", "source_value": prepared,
                "before_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            }]
    return candidate, []


def _candidate_market_gate(markdown: str, context: dict) -> None:
    slim = context.get("slim") or {}
    price = slim.get("latest_price")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        raise ValueError("update_not_allowed_current_price_unavailable")
    # A single separator followed by three digits is ambiguous across locales:
    # $847,475 can mean 847.475 or 847475. Resolve that ambiguity ONLY against
    # the frozen authoritative price, never a guessed decimal/thousands policy.
    price_line = _extract_line_value(markdown, "Precio de referencia") or ""
    price_match = re.match(r"\s*\$?\s*([+-]?\d+(?:[.,]\d+)*)", price_line)
    candidates = []
    if price_match:
        raw = price_match[1]
        legacy = _to_number(raw)
        if legacy is not None:
            candidates.append(legacy)
        if raw.count(".") + raw.count(",") == 1:
            candidates.append(float(raw.replace(",", ".")))
    if not any(math.isclose(value, price, rel_tol=1e-10, abs_tol=1e-8) for value in candidates):
        raise ValueError("update_not_allowed_stale_reference_price")
    prepared = str(context.get("prepared_at") or "")
    try:
        prepared_day = datetime.fromisoformat(prepared.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError("update_not_allowed_missing_prepared_at") from exc
    date_text = (_extract_line_value(markdown, "Fecha del análisis") or "").strip()
    if parse_report_date(date_text) != prepared_day:
        raise ValueError("update_not_allowed_stale_report_date")
    for label in LEVEL_LABELS:
        zone = extract_range(markdown, label)
        if zone is None:
            continue  # The established full validator checks allowed absences.
        value = _extract_line_value(markdown, label) or ""
        percentages = re.findall(r"([+-]?\d+(?:[.,]\d+)?)\s*%", value.replace("−", "-"))
        expected = [(zone.lower / price - 1) * 100]
        if zone.lower != zone.upper:
            expected.append((zone.upper / price - 1) * 100)
        if len(percentages) != len(expected):
            raise ValueError("update_not_allowed_missing_level_percentages")
        for raw, actual in zip(percentages, expected):
            precision = len(re.split(r"[.,]", raw)[1]) if re.search(r"[.,]", raw) else 0
            declared = _to_number(raw)
            if declared is None or abs(declared - actual) > 0.5 * 10 ** -precision + 1e-7:
                raise ValueError("update_not_allowed_stale_level_percentages")
    plan = parse_report(markdown, latest_price=price)["plan"]
    entry = plan.get("entry")
    ambitious = plan.get("ambitious_entry")
    entries = [zone for zone in (entry, ambitious) if isinstance(zone, dict)]
    target = plan.get("target")
    structural = plan.get("structural_stop")
    if not entries or target is None or target <= max(zone["upper"] for zone in entries):
        raise ValueError("update_not_allowed_invalid_long_only_target")
    if structural is None or structural >= min(zone["lower"] for zone in entries):
        raise ValueError("update_not_allowed_structural_stop_not_below_entries")
    if ambitious is not None and ambitious["upper"] >= entry["lower"]:
        raise ValueError("update_not_allowed_ambitious_not_distinct_below_entry")
    resistance = plan.get("resistance")
    if not isinstance(resistance, dict) or resistance["upper"] < price:
        raise ValueError("update_not_allowed_resistance_not_current_roof")
    state = _norm(_extract_line_value(markdown, "Estado actual") or "")
    expected_state = ("por encima" if price > entry["upper"] else
                      "por debajo" if price < entry["lower"] else "dentro")
    state_match = re.match(
        r"^(por encima|por debajo|dentro)(?: de la zona)?"
        r"(?: segun el mid(?: de \$?\d+(?:[.,]\d+)*)?)?(?:\s*[,.;:]|$)", state)
    mid_claim = re.search(r"\bsegun el mid de \$?(\d+(?:[.,]\d+)*)", state)
    if mid_claim and not _metric_matches_token(price, "price", mid_claim[1]):
        raise ValueError("update_not_allowed_stale_current_state")
    contradictions = {other for other in ("por encima", "por debajo", "dentro de la zona")
                      if other in state and not other.startswith(expected_state)}
    if state_match is None or state_match[1] != expected_state or contradictions:
        raise ValueError("update_not_allowed_stale_current_state")
    # A visible old-snapshot banner must not mislabel the maintained report.
    baseline = (context.get("reference") or {}).get("analysis_markdown", "")
    snapshot_label = next((label for label in SNAPSHOT_LABELS if label != "Snapshot"
                          and _extract_line_value(baseline, label)), "Snapshot técnico")
    old_snapshot = _extract_line_value(baseline, snapshot_label)
    old_price_line = _extract_line_value(baseline, "Precio de referencia") or ""
    inline_snapshot = any(marker in _norm(old_price_line) for marker in ("snapshot", "fotografia tecnica"))
    if not old_snapshot and inline_snapshot:
        old_snapshot = old_price_line
    if old_snapshot:
        snapshot = (price_line if inline_snapshot and not _extract_line_value(baseline, snapshot_label)
                    else _extract_line_value(markdown, snapshot_label)) or ""
        try:
            market_at = datetime.fromisoformat(str(slim.get("as_of") or "").replace("Z", "+00:00"))
            if market_at.tzinfo is not None:
                market_at = market_at.astimezone(timezone.utc)
        except ValueError as exc:
            raise ValueError("update_not_allowed_missing_snapshot_time") from exc
        date_formats = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")
        had_date = bool(re.search(r"\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2}", old_snapshot))
        time_format = "%H:%M:%S" if re.search(r"\d{2}:\d{2}:\d{2}", snapshot) else "%H:%M"
        if ((had_date and not any(market_at.strftime(fmt) in snapshot for fmt in date_formats))
                or market_at.strftime(time_format) not in snapshot):
            raise ValueError("update_not_allowed_stale_snapshot_banner")


def _current_origin_gate(baseline: str, candidate: str, context: dict) -> None:
    """Changed technical zones need present source origins, not invented prices.

    Existing continuity tolerance is reused; options whose origin is expired,
    missing a dated expiry or has no positive OI/gamma cannot be the substitute.
    This proves source presence, not that the model's materiality assessment is
    correct. Strength arithmetic and previous-level explanations remain the
    responsibility of the established full report validator.
    """
    slim = deepcopy(context.get("slim") or {})
    try:
        market_at = datetime.fromisoformat(str(slim.get("as_of") or context.get("prepared_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("update_not_allowed_origin_time_unavailable") from exc
    levels = slim.get("levels") or {}
    for kind in ("supports", "put_walls_top", "resistances", "call_walls_top"):
        live = []
        for item in levels.get(kind) or []:
            if not isinstance(item, dict) or item.get("active") is False:
                continue
            is_option = "wall" in str(item.get("type") or "") or kind.endswith("walls_top")
            if is_option:
                try:
                    expires = datetime.fromisoformat(str(item.get("expiration") or "").replace("Z", "+00:00"))
                except ValueError:
                    continue
                strength = [item.get(key) for key in ("oi", "gamma_share_pct", "gamma_usd_millions")]
                if (expires.date() < market_at.date() or not any(
                        not isinstance(value, bool) and isinstance(value, (int, float))
                        and math.isfinite(value) and value > 0 for value in strength)):
                    continue
            live.append(item)
        levels[kind] = live
    slim["levels"] = levels
    for label in ("Entrada", "Entrada ambiciosa"):
        previous, current = extract_range(baseline, label), extract_range(candidate, label)
        if current is not None and current != previous:
            # Check a single entry at a time, so another absent/unchanged
            # ambitious entry does not accidentally reject the new primary.
            line = 'Entrada: ' + format_exact_price(current.lower) + '-' + format_exact_price(current.upper)
            if "missing_from_current_slim" in build_level_continuity_precheck(line, slim):
                raise ValueError("update_not_allowed_unproven_current_entry_origin")
    candidates = []
    for kind in ("resistances", "call_walls_top"):
        for item in levels[kind]:
            value = item.get("level")
            if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value):
                candidates.append(value)
    technicals = slim.get("technicals") or {}
    for key in ("donchian20_high", "keltner_upper", "sma20", "sma50", "sma200"):
        value = technicals.get(key)
        if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value):
            candidates.append(value)
    atr = technicals.get("atr10")
    atr = atr if not isinstance(atr, bool) and isinstance(atr, (int, float)) and math.isfinite(atr) and atr > 0 else 0
    for label in ("Resistencia estructural", "Salida / objetivo principal"):
        previous, current = extract_range(baseline, label), extract_range(candidate, label)
        if current is not None and current != previous:
            tolerance = max((current.lower + current.upper) / 2 * .005, atr * .25)
            if not any(current.lower - tolerance <= value <= current.upper + tolerance for value in candidates):
                raise ValueError("update_not_allowed_unproven_current_resistance_or_target_origin")


def _motivo_span(markdown: str, label: str) -> tuple[int, int] | None:
    """A complete contiguous Motivo paragraph, not an arbitrary matching phrase."""
    lines = markdown.splitlines(keepends=True)
    offset, collecting, found = 0, False, None
    for raw in lines:
        clean = _clean(raw)
        prefix = _norm(clean.split(":", 1)[0]) if ":" in clean else ""
        if prefix in {_norm(value) for value in LEVEL_LABELS}:
            if found:
                return found[0], offset
            collecting = prefix == _norm(label)
        elif collecting and prefix == "motivo":
            if found:
                raise ValueError("update_not_allowed_ambiguous_inherited_motive")
            found = (offset, offset + len(raw))
        elif found:
            if not clean or prefix.startswith(("fortaleza de", "desglose de", "factores de")) or re.match(r"^[0-4]\)", clean):
                return found[0], offset
            found = (found[0], offset + len(raw))
        offset += len(raw)
    return found


def _rebase_inherited_motives(baseline: str, candidate: str, context: dict) -> tuple[str, list[dict]]:
    """Reattribute exact inherited transitions, never excuse today's changed ones.

    The source report must be validated. Both exact numeric range and complete
    raw Motivo paragraph must be identical. Only the historical continuity
    formula is rebased; its rationale is retained with explicit source date.
    The structural-stop rationale remains protected, even for this operation.
    """
    reference = context.get("reference") or {}
    if reference.get("analysis_status") != "ok":
        return candidate, []
    source_at = str(reference.get("generated_at") or "")
    try:
        source_day = datetime.fromisoformat(source_at.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return candidate, []
    changes = []
    for label in LEVEL_LABELS:
        if label == "Stop estructural":
            continue
        old_range, new_range = extract_range(baseline, label), extract_range(candidate, label)
        if old_range is None or old_range != new_range:
            continue
        old_span, new_span = _motivo_span(baseline, label), _motivo_span(candidate, label)
        if old_span is None or new_span is None:
            continue
        old_text = baseline[old_span[0]:old_span[1]]
        new_text = candidate[new_span[0]:new_span[1]]
        if old_text != new_text:
            continue
        clean = _clean(old_text)
        match = re.match(r'^Motivo:\s*Se\s+(?:reprioriza|corrige|retira)\b\s*:?\s*(.+)$', clean, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        zone = '$' + format_exact_price(new_range.lower)
        if new_range.lower != new_range.upper:
            zone += '-' + format_exact_price(new_range.upper)
        formula = re.search(r'Se\s+(?:reprioriza|corrige|retira)\b:?', old_text, re.IGNORECASE)
        if formula is None:
            continue
        attributed = (f"Se conserva: {zone}. Justificación histórica del informe técnico "
                      f"de {source_day}, no una nueva decisión de hoy:")
        # Only the literal transition formula changes. The entire rationale,
        # its original numbers, typography and wrapper remain byte-for-byte.
        after = old_text[:formula.start()] + attributed + old_text[formula.end():]
        candidate = candidate[:new_span[0]] + after + candidate[new_span[1]:]
        changes.append({"method": "exact_inherited_motive_rebase", "label": label,
                        "source_report_at": source_at, "before_sha256": hashlib.sha256(old_text.encode()).hexdigest(),
                        "before": old_text, "after": after})
    return candidate, changes


def _number_choices(raw: str) -> list[float]:
    values = []
    legacy = _to_number(raw)
    if legacy is not None:
        values.append(legacy)
    if raw.count(".") + raw.count(",") == 1:
        values.append(float(raw.replace(",", ".")))
    return list(dict.fromkeys(values))


def _wall_records(slim: dict, root: str) -> list[dict]:
    records = []
    for kind in ("supports", "put_walls_top", "resistances", "call_walls_top"):
        for index, item in enumerate((slim.get("levels") or {}).get(kind) or []):
            if not isinstance(item, dict):
                continue
            wall_type = str(item.get("type") or "")
            side = ("put" if wall_type.startswith("put_wall") or kind == "put_walls_top" else
                    "call" if wall_type.startswith("call_wall") or kind == "call_walls_top" else None)
            level = item.get("level")
            if side is None or isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(level):
                continue
            try:
                expiry = datetime.fromisoformat(str(item.get("expiration") or "").replace("Z", "+00:00")).date()
            except ValueError:
                continue
            records.append({"side": side, "level": level, "expiry": expiry, "item": item,
                            "pointer": f"{root}/levels/{kind}/{index}"})
    return records


_METRIC_PATTERNS = {
    "gamma_share_pct": r"(?P<number>\d+(?:[.,]\d+)*)\s*%\s*(?:(?:del?|de la)\s+)?gamma(?:\s+(?:put|call))?",
    "oi_share_pct": r"(?P<number>\d+(?:[.,]\d+)*)\s*%\s*(?:(?:del?|de la)\s+)?OI\b",
    "oi": r"\bOI\s*(?:de\s+|[:=]\s*)?(?P<number>\d+(?:[.,]\d+)*)|(?P<contracts>\d+(?:[.,]\d+)*)\s+contratos\b",
    "gamma_usd_millions": r"\bgamma\s*(?:de\s+|[:=]\s*)?\$\s*(?P<number>\d+(?:[.,]\d+)*)\s*M(?:illones)?\b",
}

# A wall's identity is NOT the numeric quantity that happens to follow 'put'.
# Require a price token, or bind an unpriced wall to its labelled plan zone.
_WALL_MENTION = re.compile(
    r"\b(?P<qualified_side>put|call)\s+wall\s+"
    r"(?:(?!(?:put|call|OI|gamma|contratos)\b)[^\W\d_]+\s+)*\$"
    r"(?P<qualified_level>\d+(?:[.,]\d+)*)(?!\d|[.,]\d)"
    r"|\b(?P<side>put|call)(?:\s+wall)?\s+(?:de\s+)?\$?\s*"
    r"(?P<level>\d+(?:[.,]\d+)*)(?!\d|[.,]\d|\s*(?:%|contratos\b))"
    r"|\b(?P<unpriced_side>put|call)\s+wall\b"
    r"|\bwall\s+(?:de\s+)?\$(?P<reverse_level>\d+(?:[.,]\d+)*)(?!\d|[.,]\d)",
    re.IGNORECASE,
)


def _claim_expiry(text: str, records: list[dict]):
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        return datetime.strptime(iso[1], "%Y-%m-%d").date()
    abbreviated_pattern = r"(\d{1,2})[- ](ene|jan|feb|mar|abr|apr|may|jun|jul|ago|aug|sep|oct|nov|dic|dec)\b"
    abbreviated = re.search(r"\b(?:del?|al|vence|vencimiento|expira|expiration)\s+" + abbreviated_pattern, text, re.IGNORECASE)
    if abbreviated is None:
        abbreviated = re.search(r"\b" + abbreviated_pattern, text, re.IGNORECASE)
    if abbreviated:
        months = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6,
                  "jul": 7, "ago": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}
        matching = {record["expiry"] for record in records if record["expiry"].day == int(abbreviated[1])
                    and record["expiry"].month == months[abbreviated[2].casefold()]}
        if len(matching) != 1:
            raise ValueError("update_not_allowed_unproven_wall_expiry")
        return next(iter(matching))
    # Numeric dates require an expiry introducer or a standalone date. A score
    # like durabilidad 1/10 is not the first of October.
    numeric_pattern = r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{4}))?\b"
    numeric = re.search(r"\b(?:del?|al|vence|vencimiento|expira|expiration)\s+" + numeric_pattern, text, re.IGNORECASE)
    if numeric is None:
        numeric = re.fullmatch(r"\s*" + numeric_pattern + r"[.\s]*", text)
    if numeric:
        matching = {record["expiry"] for record in records if record["expiry"].day == int(numeric[1])
                    and record["expiry"].month == int(numeric[2])
                    and (not numeric[3] or record["expiry"].year == int(numeric[3]))}
        if len(matching) != 1:
            raise ValueError("update_not_allowed_unproven_wall_expiry")
        return next(iter(matching))
    return None


def _matching_metric(records: list[dict], key: str) -> tuple[float, str] | None:
    # Duplicates are usable only when EVERY source copy proves the same metric.
    # Missing, bool and nonfinite copies are ambiguity, not permission to choose
    # the convenient value or accidentally attribute it to a bad JSON pointer.
    if not records or any(isinstance(record["item"].get(key), bool)
                          or not isinstance(record["item"].get(key), (int, float))
                          or not math.isfinite(record["item"][key]) for record in records):
        return None
    values = {float(record["item"][key]) for record in records}
    if len(values) != 1:
        return None
    record = records[0]
    return next(iter(values)), record["pointer"] + "/" + key


def _wall_market_day(context: dict):
    raw = (context.get("slim") or {}).get("as_of") or context.get("prepared_at")
    try:
        return datetime.fromisoformat(str(raw or "").replace("Z", "+00:00")).date()
    except ValueError:
        raise ValueError("update_not_allowed_unproven_wall_market_date") from None


def _wall_metric_claims(segment: str) -> list[tuple[str, re.Match]]:
    claims = [(key, match) for key, pattern in _METRIC_PATTERNS.items()
              for match in re.finditer(pattern, segment, re.IGNORECASE)
              if not (key == "oi" and match.groupdict().get("number")
                      and re.match(r"\s*%", segment[match.end():]))]
    claims += [("oi_share_pct", match) for match in re.finditer(
        r"\bOI\s*(?:de\s+|[:=]\s*)?(?P<number>\d+(?:[.,]\d+)*)\s*%", segment, re.IGNORECASE)]
    claims += [("gamma_share_pct", match) for match in re.finditer(
        r"\bgamma\s+(?:(?:share\s+)?(?:put|call)\s+)?(?P<number>\d+(?:[.,]\d+)*)\s*%", segment, re.IGNORECASE)]
    claims += [("oi_share_pct", match) for match in re.finditer(
        r"\bOI\s*(?:de\s+|[:=]\s*)?\d+(?:[.,]\d+)*\s*\(\s*(?P<number>\d+(?:[.,]\d+)*)\s*%\s*\)", segment, re.IGNORECASE)]
    return claims


def _metric_matches_token(value: float, key: str, token: str) -> bool:
    precision = len(re.split(r"[.,]", token)[-1]) if re.search(r"[.,]", token) else 0
    tolerance = (0.5 * 10 ** -precision + 1e-7) if key != "oi" else 1e-7
    return any(abs(choice - value) <= tolerance for choice in _number_choices(token))


def _historical_wall_marker(prefix: str, segment: str) -> bool:
    # Only local, explicit wall attribution counts. Historical rebounds in a
    # different factor must never turn a live wall metric into a historical one.
    normalized_prefix, normalized_segment = _norm(prefix), _norm(segment)
    return bool(re.search(r"\b(?:historico|expirado|vencido)\s*:?\s*$", normalized_prefix)
                or re.match(r"^\s*(?:del?\s+)?(?:\d{1,2}[- ]\w+|\d{4}-\d{2}-\d{2})?\s*[,(:-]?\s*"
                            r"(?:(?:ya|ahora)\s+)?(?:historico|expirado|vencido)\b", normalized_segment))


def _metric_format(value: float, key: str, original: str) -> str:
    if key == "oi" and value.is_integer():
        # Contracts are integral; do not carry an ambiguous thousands separator.
        return str(int(value))
    precision = len(re.split(r"[.,]", original)[-1]) if re.search(r"[.,]", original) else 0
    formatted = f"{value:.{precision}f}"
    # Never silently round away a real source change when copying a metric.
    if not math.isclose(float(formatted), value, rel_tol=1e-10, abs_tol=1e-8):
        formatted = str(value)
    return formatted.replace(".", ",") if "," in original and "." not in original else formatted


def _refresh_wall_facts(baseline: str, candidate: str, context: dict) -> tuple[str, list[dict]]:
    """Copy only proven current metrics in byte-identical inherited factors.

    A typed wall must have a unique same-strike/expiry origin in both snapshots;
    the stated old number must match that old source. Changed model paragraphs
    cannot be corrected by this helper: conflicting current claims escalate.
    This is not a general prose/number rewrite, nor permission to alter ratings.
    """
    old_records = _wall_records((context.get("reference") or {}).get("slim_snapshot") or {}, "/reference/slim_snapshot")
    current_records = _wall_records(context.get("slim") or {}, "/slim")
    changes, edits = [], []
    factor_labels = {"Factores de Entrada", "Factores de Entrada ambiciosa", "Factores de Resistencia"}
    offset = 0
    for raw in candidate.splitlines(keepends=True):
        clean = _clean(raw)
        label = clean.split(":", 1)[0] if ":" in clean else ""
        if label not in factor_labels:
            offset += len(raw)
            continue
        inherited = any(raw == line for line in baseline.splitlines(keepends=True))
        plain, mapping = "", []
        for index, character in enumerate(raw):
            if character != "*":
                plain += character
                mapping.append(index)
        mentions = list(_WALL_MENTION.finditer(plain))
        preceding_side = None
        for i, mention in enumerate(mentions):
            end = mentions[i + 1].start() if i + 1 < len(mentions) else len(plain)
            # Unpriced mentions include the following quantity (e.g. contracts).
            segment_start = mention.end()
            # Scope is the typed wall identity, not a prose delimiter. OI/gamma
            # after a semicolon are still claims about this wall until the next
            # wall or an explicit historical comparison.
            segment = plain[segment_start:end]
            # Comparisons explicitly marked as previous are not current claims.
            segment = re.split(r"\b(?:frente a|comparado con|versus|vs\.?|antes|previamente|(?:el\s+)?(?:informe|reporte|snapshot)\s+anterior)\b", segment, maxsplit=1, flags=re.IGNORECASE)[0]
            metric_matches = _wall_metric_claims(segment)
            if not metric_matches:
                continue
            side = mention["qualified_side"] or mention["side"] or mention["unpriced_side"]
            if side is None:
                sides = set(re.findall(r"\b(?:put|call)\b", segment, re.IGNORECASE))
                if not sides and preceding_side is not None:
                    sides = {preceding_side}
                if len({item.casefold() for item in sides}) != 1:
                    raise ValueError("update_not_allowed_ambiguous_current_wall_fact")
                side = next(iter(sides))
            side = side.casefold()
            preceding_side = side
            price_token = mention["qualified_level"] or mention["level"] or mention["reverse_level"]
            zone = extract_range(candidate, label.removeprefix("Factores de ") if label != "Factores de Resistencia" else "Resistencia estructural")
            possible_levels = (_number_choices(price_token) if price_token else
                sorted({record["level"] for record in current_records if record["side"] == side
                        and zone is not None and zone.lower <= record["level"] <= zone.upper}))
            clause_prefix = plain[:mention.start()].rsplit(";", 1)[-1]
            if _historical_wall_marker(clause_prefix, segment):
                historical = [record for record in old_records if record["side"] == side
                              and record["level"] in possible_levels]
                expiry = _claim_expiry(segment, historical)
                if expiry is not None:
                    historical = [record for record in historical if record["expiry"] == expiry]
                if len({(record["side"], record["level"], record["expiry"]) for record in historical}) != 1:
                    raise ValueError("update_not_allowed_unproven_historical_wall_fact")
                for key, match in metric_matches:
                    token = match.groupdict().get("number") or match["contracts"]
                    metric = _matching_metric(historical, key)
                    if metric is None or not _metric_matches_token(metric[0], key, token):
                        raise ValueError("update_not_allowed_unproven_historical_wall_metric")
                # Preserve explicit historical/expired facts; NEVER refresh them
                # into a current assertion merely because the strike still exists.
                continue
            current = [record for record in current_records if record["side"] == side and record["level"] in possible_levels]
            expiry_error = None
            try:
                expiry = _claim_expiry(segment, current)
            except ValueError as exc:
                expiry, expiry_error = None, str(exc)
            if expiry is not None:
                current = [record for record in current if record["expiry"] == expiry]
            identities = {(record["side"], record["level"], record["expiry"]) for record in current}
            if expiry_error or len(identities) != 1:
                problem = ValueError(expiry_error or "update_not_allowed_ambiguous_current_wall_fact")
                problem.maintenance_details = {"label": label, "claim": mention.group(0) + segment,
                    "side": side, "strikes": possible_levels,
                    "current_sources": [{"pointer": record["pointer"], "strike": record["level"],
                        "expiry": str(record["expiry"]), "oi": record["item"].get("oi"),
                        "gamma_share_pct": record["item"].get("gamma_share_pct")}
                        for record in current_records if record["side"] == side],
                    "historical_sources": [{"pointer": record["pointer"], "strike": record["level"],
                        "expiry": str(record["expiry"]), "oi": record["item"].get("oi")}
                        for record in old_records if record["side"] == side and record["level"] in possible_levels],
                    "instruction": "Use only proven CURRENT identity/metrics; absence from a toplist is not proof of total support loss. Historical facts must be explicitly dated as historical."}
                raise problem
            identity = next(iter(identities))
            if identity[2] < _wall_market_day(context):
                raise ValueError("update_not_allowed_expired_wall_fact")
            old = [record for record in old_records if (record["side"], record["level"], record["expiry"]) == identity]
            for key, match in metric_matches:
                group = "number" if match.groupdict().get("number") is not None else "contracts"
                token = match[group]
                current_metric = _matching_metric(current, key)
                if current_metric is None:
                    raise ValueError("update_not_allowed_unproven_current_wall_metric")
                new_value, current_pointer = current_metric
                if _metric_matches_token(new_value, key, token):
                    continue
                old_metric = _matching_metric(old, key)
                if (not inherited or old_metric is None
                        or not _metric_matches_token(old_metric[0], key, token)):
                    problem = ValueError("update_not_allowed_stale_or_unproven_wall_metric")
                    problem.maintenance_details = {
                        "field": key, "claimed": token, "current_value": new_value,
                        "current_source": current_pointer, "label": label,
                        "wall": {"side": identity[0], "level": identity[1],
                                 "expiration": identity[2].isoformat()},
                        "old_metric_proven": old_metric is not None,
                    }
                    raise problem
                start_plain = mention.end() + match.start(group)
                end_plain = mention.end() + match.end(group)
                start_raw, end_raw = mapping[start_plain], mapping[end_plain - 1] + 1
                replacement = _metric_format(new_value, key, token)
                edits.append((offset + start_raw, offset + end_raw, replacement))
                changes.append({"method": "exact_inherited_wall_metric_refresh", "label": label,
                                "wall": {"side": identity[0], "level": identity[1], "expiration": identity[2].isoformat()},
                                "field": key, "old": old_metric[0], "new": new_value,
                                "old_pointer": old_metric[1], "current_pointer": current_pointer,
                                "before_sha256": hashlib.sha256(raw.encode()).hexdigest()})
        offset += len(raw)
    for start, end, replacement in sorted(edits, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]
    return candidate, changes


def _normalize_wall_continuation(candidate: str, context: dict) -> tuple[str, list[dict]]:
    """Join only a proven shorthand continuation of the SAME options factor.

    Four real evidence families plus ``; el wall de $X marca P% y el de $Y Q%.``
    is one options family accidentally split in two, not a fifth family. Change
    just that delimiter. No content, arithmetic or common-validator rule changes.
    All other fifth factors remain untouched and fail the established validator.
    """
    records = _wall_records(context.get("slim") or {}, "/slim")
    factor_labels = {"Factores de Entrada", "Factores de Entrada ambiciosa", "Factores de Resistencia"}
    wall_pattern = r"\b(?P<side>put|call)\s+wall\s+\$?\s*(?P<level>\d+(?:[.,]\d+)*)"
    tail_pattern = (r"el\s+wall\s+de\s+\$?\s*(?P<first>\d+(?:[.,]\d+)*)\s+marca\s+"
                    r"(?P<first_pct>\d+(?:[.,]\d+)*)\s*%\s+y\s+el\s+de\s+\$?\s*"
                    r"(?P<second>\d+(?:[.,]\d+)*)\s+(?P<second_pct>\d+(?:[.,]\d+)*)\s*%\s*\.")
    edits, changes, offset = [], [], 0
    for raw in candidate.splitlines(keepends=True):
        clean = _clean(raw)
        parts = clean.split(";")
        if clean.split(":", 1)[0] not in factor_labels or len(parts) != 5:
            offset += len(raw)
            continue
        tail = re.fullmatch(tail_pattern, parts[-1].strip(), re.IGNORECASE)
        left_mentions = list(re.finditer(wall_pattern, parts[-2], re.IGNORECASE))
        if tail is None or len(left_mentions) != 1:
            offset += len(raw)
            continue
        left = left_mentions[0]
        if (_historical_wall_marker(parts[-2][:left.start()], parts[-2][left.end():])
                or not any(key == "gamma_share_pct" for key, _ in _wall_metric_claims(parts[-2]))):
            offset += len(raw)
            continue
        side = left["side"].casefold()
        origin = [record for record in records if record["side"] == side
                  and record["level"] in _number_choices(left["level"])]
        expiry = _claim_expiry(parts[-2], origin)
        # Shorthand may inherit expiry only from an explicit, uniquely grounded
        # full wall assertion directly before it, never from another factor.
        if expiry is None or expiry < _wall_market_day(context):
            raise ValueError("update_not_allowed_unproven_wall_continuation_expiry")
        origin = [record for record in origin if record["expiry"] == expiry]
        if len({(record["side"], record["level"], record["expiry"]) for record in origin}) != 1:
            raise ValueError("update_not_allowed_ambiguous_wall_continuation_origin")
        neighbors = []
        for level_key, percentage_key in (("first", "first_pct"), ("second", "second_pct")):
            matching = [record for record in records if record["side"] == side and record["expiry"] == expiry
                        and record["level"] in _number_choices(tail[level_key])]
            if len({(record["side"], record["level"], record["expiry"]) for record in matching}) != 1:
                raise ValueError("update_not_allowed_unproven_wall_continuation_neighbor")
            metric = _matching_metric(matching, "gamma_share_pct")
            if metric is None or not _metric_matches_token(metric[0], "gamma_share_pct", tail[percentage_key]):
                raise ValueError("update_not_allowed_unproven_wall_continuation_metric")
            neighbors.append({"level": matching[0]["level"], "value": metric[0], "pointer": metric[1]})
        if len({origin[0]["level"], *(item["level"] for item in neighbors)}) != 3:
            raise ValueError("update_not_allowed_ambiguous_wall_continuation_neighbor")
        delimiter = raw.rfind(";")
        edits.append(offset + delimiter)
        changes.append({"method": "proven_options_factor_delimiter", "label": clean.split(":", 1)[0],
                        "side": side, "expiration": expiry.isoformat(), "neighbors": neighbors,
                        "before": ";", "after": ",", "before_sha256": hashlib.sha256(raw.encode()).hexdigest()})
        offset += len(raw)
    for position in reversed(edits):
        candidate = candidate[:position] + "," + candidate[position + 1:]
    return candidate, changes


def _locate_emphasis_equivalent_edit(baseline: str, before: str):
    """Unique labelled full line differing ONLY in Markdown bold delimiters.

    No fuzzy application: every word, number, punctuation and whitespace matches.
    Hash, authority and overlap checks still use the original source span.
    """
    if not before.strip() or '\n' in before.rstrip('\r\n'):
        return None
    canonical = before.rstrip('\r\n').replace('**', '')
    if not re.match(r'^[^#<>`\n:]+:\s*\S', canonical):
        return None
    matches, offset = [], 0
    for line in baseline.splitlines(keepends=True):
        raw = line.rstrip('\r\n')
        if raw.replace('**', '') == canonical:
            matches.append((offset, offset + len(raw)))
        offset += len(line)
    return matches[0] if len(matches) == 1 else None


def apply_update(payload: dict, context: dict, *, audit: list[dict] | None = None, binding=None) -> str:
    """Apply simultaneous unique literal edits and verify the complete candidate."""
    if context.get('routing_revision', 1) >= 9:
        from src.local_runner.semantic_report import maintenance_document, render_document
        return render_document(maintenance_document(payload, context, binding=binding))
    decision = maintenance_decision(payload, [], context)
    if payload["decision"] != "update":
        raise ValueError("invalid_update_decision")
    if decision != "update":
        raise ValueError("update_not_allowed_uncertain_or_critical")
    baseline = (context.get("reference") or {}).get("analysis_markdown")
    if not isinstance(baseline, str) or not baseline.strip():
        raise ValueError("invalid_update_missing_base")
    if payload["base_markdown_sha256"] != hashlib.sha256(baseline.encode("utf-8")).hexdigest():
        raise ValueError("invalid_update_base_hash")
    if not payload["edits"] and not payload["routine_note"].strip():
        raise ValueError("invalid_update_empty_patch")
    layout = _layout(baseline)
    if context.get("routing_revision", 1) >= 4:
        quote_field = quote_snapshot_field(layout)
        if quote_field is not None:
            layout["allowed"].append(quote_field[:2])
    allowed = (contiguous_editable_spans(baseline, layout["allowed"])
               if context.get("routing_revision", 1) >= 4 else layout["allowed"])
    patch_changes = []
    located = []
    note = payload["routine_note"].strip()
    old_note_body = ""
    if layout["note_start"] < len(baseline):
        old_note_body = baseline[layout["note_start"]:].split("\n", 1)[-1].strip()
    for edit_index, edit in enumerate(payload["edits"]):
        before, after = edit["before"], edit["after"]
        if before == after and context.get("routing_revision", 1) >= 4 and baseline.count(before) == 1:
            patch_changes.append({"method": "exact_noop_edit_ignored",
                                  "before_sha256": hashlib.sha256(before.encode()).hexdigest()})
            continue
        if before == after:
            raise ValueError("invalid_update_noop_edit")
        count = baseline.count(before)
        if count != 1:
            date_span = locate_report_date_edit(baseline, before, after, context, layout) if count > 1 else None
            emphasis_match = False
            if date_span is None and count == 0 and context.get("routing_revision", 1) >= 4:
                date_span = _locate_emphasis_equivalent_edit(baseline, before)
                emphasis_match = date_span is not None
            if date_span is None:
                problem = ValueError("invalid_update_ambiguous_or_missing_match")
                lines = [line for line in baseline.splitlines() if line.strip()]
                problem.maintenance_details = {"edit_index": edit_index, "requested_before": before,
                    "occurrences": count,
                    "nearest_source_lines": difflib.get_close_matches(before, lines, n=3, cutoff=.5),
                    "instruction": "Copy the correct source span exactly. Suggestions are feedback ONLY, never automatically applied; preserve protected fields and do not guess numeric values."}
                raise problem
            start, end = date_span
            patch_changes.append({"method": "unique_labelled_field_emphasis_match" if emphasis_match else "field_scoped_report_date_edit", "field": "Markdown field" if emphasis_match else "Fecha del análisis",
                                   "before": before, "after": after, "actual_before": baseline[start:end],
                                   "source": "/reference/analysis_markdown" if emphasis_match else "/prepared_at",
                                   "occurrences_in_base": count})
        else:
            start = baseline.index(before)
            end = start + len(before)
        if (context.get("routing_revision", 1) >= 4 and old_note_body
                and before == old_note_body and start >= layout["note_start"]
                and not note):
            _check_rendering(after)
            _check_urls(after, before, _evidence(context, edit["evidence"], edits=True))
            note = after.strip()
            patch_changes.append({"method": "exact_existing_daily_note_replacement",
                                  "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                                  "after_sha256": hashlib.sha256(after.encode()).hexdigest()})
            continue
        if not any(left <= start and end <= right for left, right in allowed):
            raise ValueError("update_not_allowed_protected_span")
        _check_rendering(after)
        _check_urls(after, before, _evidence(context, edit["evidence"], edits=True))
        located.append((start, end, after))
    located.sort()
    if not located and not note:
        raise ValueError("invalid_update_empty_patch")
    if any(current[0] < previous[1] for previous, current in zip(located, located[1:])):
        raise ValueError("invalid_update_overlapping_edits")
    candidate = baseline
    for start, end, after in reversed(located):
        candidate = candidate[:start] + after + candidate[end:]
    if note:
        _check_rendering(note)
        if re.search(r"(?m)^\s*(?:#{1,6}\s|[0-4]\)\s)", note):
            raise ValueError("update_not_allowed_note_structure")
        revision4 = context.get("routing_revision", 1) >= 4
        note_roots = ("/news", "/analyst_actions", "/slim") if revision4 else ("/news", "/analyst_actions")
        note_sections = ("setup", "levels", "news", "analysts") if revision4 else ("news", "analysts")
        pointers = [pointer for key in note_sections for pointer in payload[key]["evidence"]
                    if any(pointer == root or pointer.startswith(root + "/") for root in note_roots)]
        current_news = (context.get("news") or {}).get("items") or []
        if context.get("routing_revision", 1) >= 7 and not current_news:
            current_news = any(row.get("sources") for row in
                ((context.get("news") or {}).get("luna_research") or {}).get("calls", []))
        current_actions = (context.get("analyst_actions") or {}).get("actions") or []
        technical_note = False
        if revision4 and any(p == "/slim" or p.startswith("/slim/") for p in pointers):
            from src.local_runner.adaptive_delta import deterministic_comparison
            technical_note = bool(deterministic_comparison(context)["since_current"]["changes"])
        if not pointers or not (current_news or current_actions or technical_note):
            raise ValueError("update_not_allowed_note_without_sources")
        values = _evidence(context, pointers, edits=True)
        if not any(value for value in values):
            raise ValueError("update_not_allowed_note_without_sources")
        _check_urls(note, "", values)
        candidate_layout = _layout(candidate)
        candidate = candidate[:candidate_layout["note_start"]].rstrip() + "\n\n" + NOTE_HEADER + "\n\n" + note + "\n"
    current_layout = _layout(candidate)
    if layout["protected"] != current_layout["protected"]:
        raise ValueError("update_not_allowed_protected_content_changed")
    before_plan = parse_report(baseline, latest_price=None)["plan"]
    after_plan = parse_report(candidate, latest_price=None)["plan"]
    for key in ("structural_stop", "management_stop"):
        if before_plan.get(key) is None or before_plan.get(key) != after_plan.get(key):
            raise ValueError(f"update_not_allowed_{key}_changed")
    if _stop_explanation(baseline, "Stop estructural") != _stop_explanation(candidate, "Stop estructural"):
        raise ValueError("update_not_allowed_structural_stop_rationale_changed")
    before = parse_report(baseline, latest_price=None)
    after = parse_report(candidate, latest_price=None)
    for key in ("score", "thesis_score", "thesis_reason", "narrative", "score_basis"):
        if before["decision"].get(key) != after["decision"].get(key):
            raise ValueError("update_not_allowed_thesis_changed")
    if before["catalysts"] != after["catalysts"] or before["next_event"] != after["next_event"]:
        raise ValueError("update_not_allowed_fundamental_sections_changed")
    # Cheap, explicit system edits preserve factual freshness and reattribute
    # inherited historical transitions before the caller's FULL validation.
    candidate, motive_changes = _rebase_inherited_motives(baseline, candidate, context)
    candidate, fact_changes = _refresh_wall_facts(baseline, candidate, context)
    candidate, date_changes = _refresh_inherited_report_date(baseline, candidate, context)
    candidate, market_changes = refresh_derived_market_fields(baseline, candidate, context, _layout(candidate))
    candidate, percentage_changes = refresh_level_percentages(candidate, context, LEVEL_LABELS)
    candidate, snapshot_changes = refresh_inherited_snapshot(baseline, candidate, context, layout, _layout(candidate))
    _candidate_market_gate(candidate, context)
    validate_typed_snapshot_fields(_layout(candidate), context)
    if context.get("routing_revision", 1) >= 4 and quote_snapshot_field(layout) is not None:
        if quote_snapshot_field(_layout(candidate)) is None:
            raise ValueError("update_not_allowed_missing_quote_snapshot")
        validate_quote_snapshot(_layout(candidate), context)
    _current_origin_gate(baseline, candidate, context)
    if audit is not None:
        audit.extend([*patch_changes, *motive_changes, *fact_changes, *date_changes,
                       *market_changes, *percentage_changes, *snapshot_changes])
    return candidate
