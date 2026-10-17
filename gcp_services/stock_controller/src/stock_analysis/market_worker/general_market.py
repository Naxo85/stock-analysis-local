from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

from stock_analysis.contracts.market import BenchmarkMetrics, GeneralMarketOverview


CNN_PROXY_URL = (
    "https://support-resistance-values-714254943648.europe-southwest1.run.app/"
    "market/fear-greed/cnn"
)
YAHOO_VXN_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVXN"
MADRID = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True)
class GeneralMarketInputs:
    cnn_score: float | None
    sentiment_observed_at: datetime | None
    sentiment_source: str | None
    vxn_value: float | None
    vxn_change: float | None
    vxn_observed_at: datetime | None
    vxn_source: str | None
    trading_date: date | None
    core_date: date | None
    trading_note: str
    core_note: str
    sources: tuple[str, ...]
    failures: dict[str, str]


_CACHE: dict[str, tuple[float, Any]] = {}


def _http_json(url: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _cached(key: str, ttl_seconds: int, loader: Callable[[], Any]) -> Any:
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < ttl_seconds:
        return cached[1]
    value = loader()
    _CACHE[key] = (now, value)
    return value


def vxn_regime(value: float) -> tuple[str, int]:
    if value < 20:
        return "tranquilo", 4
    if value < 25:
        return "normal", 0
    if value < 30:
        return "tension", -8
    if value < 35:
        return "risk-off", -15
    return "shock", -25


def adjusted_risk_score(
    cnn_score: float, vxn_value: float, vxn_change: float
) -> tuple[int, str, str]:
    vxn_label, adjustment = vxn_regime(vxn_value)
    if vxn_change >= 0.20:
        adjustment -= 18
    elif vxn_change >= 0.10:
        adjustment -= 10
    elif vxn_change <= -0.10:
        adjustment += 5

    score = round(max(0.0, min(100.0, cnn_score + adjustment)))
    if score >= 76:
        label = "Strong Risk-on"
    elif score >= 56:
        label = "Risk-on"
    elif score >= 45:
        label = "Mixto"
    elif score >= 25:
        label = "Risk-off"
    else:
        label = "Strong Risk-off"
    return score, label, vxn_label


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fetch_cnn_score(
    http_json: Callable[..., dict[str, Any]],
) -> tuple[float, datetime | None, str]:
    payload = http_json(CNN_PROXY_URL)
    source = str(payload.get("source") or "CNN").strip()
    if "CNN" in source.upper():
        source = "CNN"
    observed_at = _parse_datetime(
        payload.get("source_timestamp") or payload.get("fetched_at")
    )
    return float(payload["score"]), observed_at, source


def _fetch_vxn(
    http_json: Callable[..., dict[str, Any]],
) -> tuple[float, float, datetime | None]:
    payload = http_json(YAHOO_VXN_URL, params={"range": "5d", "interval": "1d"})
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError("VXN chart returned no result")
    meta = result.get("meta") or {}
    price = float(meta["regularMarketPrice"])
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    if previous in (None, 0, "0"):
        closes = (
            (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close")
            or []
        )
        valid = [float(value) for value in closes if value not in (None, 0, "0")]
        if len(valid) < 2:
            raise ValueError("VXN previous close is unavailable")
        previous = valid[-2]
    previous = float(previous)
    market_time = meta.get("regularMarketTime")
    observed_at = (
        datetime.fromtimestamp(float(market_time), tz=timezone.utc)
        if market_time is not None
        else None
    )
    return price, price / previous - 1.0, observed_at


def analysis_batch_note(label: str, model_usage: Any) -> str:
    lines = [f"Última actualización completa de {label}"]
    if not isinstance(model_usage, dict):
        return lines[0]

    def append_group(title: str, key: str) -> None:
        group = model_usage.get(key)
        if not isinstance(group, dict):
            return
        order = {"Luna": 0, "Tierra": 1, "Sol": 2}
        populated = [
            (str(name), tickers)
            for name, tickers in group.items()
            if isinstance(tickers, list) and tickers
        ]
        populated.sort(key=lambda item: (order.get(item[0], 99), item[0]))
        if not populated:
            return
        lines.extend(("", title))
        for name, tickers in populated:
            lines.append(f"{name} ({len(tickers)}): {', '.join(map(str, tickers))}")

    append_group("Ruta base", "base")
    append_group("Revisiones superiores", "reviews")

    published = model_usage.get("published")
    if isinstance(published, list) and published:
        detail = ", ".join(map(str, published))
        lines.extend(("", f"Publicados sin revisión ({len(published)}): {detail}"))

    reviewed = model_usage.get("reviewed_and_published")
    if isinstance(reviewed, list) and reviewed:
        lines.extend(("", f"Revisados y publicados ({len(reviewed)})"))
        for item in reviewed:
            if not isinstance(item, dict):
                continue
            suffix = f": {item['model']}" if item.get("model") else ""
            lines.append(f"- {item.get('ticker', '')}{suffix}")

    retained = model_usage.get("reference_retained")
    if isinstance(retained, list) and retained:
        lines.extend(("", f"Referencia conservada ({len(retained)})"))
        for item in retained:
            if not isinstance(item, dict):
                continue
            details = [str(item.get("ticker") or "")]
            confidence = item.get("confidence")
            if isinstance(confidence, (int, float)):
                details.append(f"{confidence:.0f}%")
            reasons = item.get("reasons")
            if isinstance(reasons, list) and reasons:
                details.append(", ".join(map(str, reasons)))
            lines.append(f"- {' · '.join(details)}")

    failed = model_usage.get("failed")
    if isinstance(failed, list) and failed:
        detail = ", ".join(map(str, failed))
        lines.extend(("", f"Fallidos ({len(failed)}): {detail}"))
    return "\n".join(lines)


def _analysis_status(payload: dict[str, Any], profile: str) -> tuple[date, str]:
    finished_at = datetime.fromisoformat(
        str(payload["finished_at"]).replace("Z", "+00:00")
    )
    label = "Trading" if profile == "trading" else "Core"
    return (
        finished_at.astimezone(MADRID).date(),
        analysis_batch_note(label, payload.get("model_usage")),
    )


def _analysis_status_from_bucket(
    bucket: Any, profile: str, status_prefix: str
) -> tuple[date, str]:
    payload = json.loads(
        bucket.blob(f"{status_prefix.rstrip('/')}/latest_{profile}.json")
        .download_as_bytes()
        .decode("utf-8")
    )
    return _analysis_status(payload, profile)


def _analysis_status_from_gcloud(
    bucket_name: str, profile: str, status_prefix: str
) -> tuple[date, str]:
    uri = (
        f"gs://{bucket_name}/{status_prefix.rstrip('/')}/latest_{profile}.json"
    )
    completed = subprocess.run(
        ["gcloud.cmd", "storage", "cat", uri],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    payload = json.loads(completed.stdout)
    return _analysis_status(payload, profile)


def fetch_general_market_inputs(
    reports_bucket: str,
    *,
    status_prefix: str = "runtime/analysis-status",
    http_json: Callable[..., dict[str, Any]] = _http_json,
    storage_client: storage.Client | None = None,
    use_cache: bool = True,
) -> GeneralMarketInputs:
    failures: dict[str, str] = {}
    sources: list[str] = []

    try:
        loader = lambda: _fetch_cnn_score(http_json)
        # The proxy already owns the 15-minute upstream cache. Caching its
        # response again here can leave the sheet one full window behind.
        cnn_score, sentiment_observed_at, sentiment_source = loader()
        sources.append("CNN Fear & Greed proxy")
    except (KeyError, TypeError, ValueError, OSError) as error:
        cnn_score = None
        sentiment_observed_at = None
        sentiment_source = None
        failures["cnn"] = f"{type(error).__name__}: {error}"

    try:
        loader = lambda: _fetch_vxn(http_json)
        vxn_value, vxn_change, vxn_observed_at = (
            _cached("vxn", 300, loader) if use_cache else loader()
        )
        vxn_source = "Yahoo Finance ^VXN"
        sources.append("Yahoo Finance ^VXN")
    except (KeyError, TypeError, ValueError, OSError) as error:
        vxn_value = None
        vxn_change = None
        vxn_observed_at = None
        vxn_source = None
        failures["vxn"] = f"{type(error).__name__}: {error}"

    statuses: dict[str, tuple[date, str] | None] = {}
    try:
        bucket = (storage_client or storage.Client()).bucket(reports_bucket)
    except GoogleAuthError as error:
        bucket = None
        for profile in ("trading", "core"):
            try:
                statuses[profile] = _analysis_status_from_gcloud(
                    reports_bucket, profile, status_prefix
                )
            except (
                KeyError,
                TypeError,
                ValueError,
                OSError,
                subprocess.SubprocessError,
            ) as fallback_error:
                statuses[profile] = None
                failures[profile] = (
                    f"{type(error).__name__}; "
                    f"gcloud {type(fallback_error).__name__}: {fallback_error}"
                )
    if bucket is not None:
        for profile in ("trading", "core"):
            try:
                loader = lambda profile=profile: _analysis_status_from_bucket(
                    bucket, profile, status_prefix
                )
                statuses[profile] = (
                    _cached(f"analysis-status:{profile}", 300, loader)
                    if use_cache
                    else loader()
                )
            except (KeyError, TypeError, ValueError, OSError, GoogleAPIError) as error:
                statuses[profile] = None
                failures[profile] = f"{type(error).__name__}: {error}"
    if statuses.get("trading") or statuses.get("core"):
        sources.append(f"gs://{reports_bucket}/{status_prefix.rstrip('/')}")

    trading_status = statuses.get("trading")
    core_status = statuses.get("core")

    return GeneralMarketInputs(
        cnn_score=cnn_score,
        sentiment_observed_at=sentiment_observed_at,
        sentiment_source=sentiment_source,
        vxn_value=vxn_value,
        vxn_change=vxn_change,
        vxn_observed_at=vxn_observed_at,
        vxn_source=vxn_source,
        trading_date=trading_status[0] if trading_status else None,
        core_date=core_status[0] if core_status else None,
        trading_note=trading_status[1] if trading_status else "",
        core_note=core_status[1] if core_status else "",
        sources=tuple(sources),
        failures=failures,
    )


def build_general_market_overview(
    qqq: BenchmarkMetrics | None,
    inputs: GeneralMarketInputs,
    *,
    observed_at: datetime | None = None,
) -> GeneralMarketOverview:
    score = None
    risk_label = None
    vxn_label = None
    if (
        inputs.cnn_score is not None
        and inputs.vxn_value is not None
        and inputs.vxn_change is not None
    ):
        score, risk_label, vxn_label = adjusted_risk_score(
            inputs.cnn_score, inputs.vxn_value, inputs.vxn_change
        )
    elif inputs.vxn_value is not None:
        vxn_label = vxn_regime(inputs.vxn_value)[0]

    failures = dict(inputs.failures)
    if qqq is None:
        failures["qqq"] = "QQQ market metrics unavailable"
    qqq_sources = ("Tradier QQQ",) if qqq else ()
    sources = tuple(dict.fromkeys((*inputs.sources, *qqq_sources)))
    return GeneralMarketOverview(
        risk_score=score,
        risk_label=risk_label,
        vxn_value=inputs.vxn_value,
        vxn_change=inputs.vxn_change,
        vxn_label=vxn_label,
        vxn_observed_at=inputs.vxn_observed_at,
        vxn_source=inputs.vxn_source,
        qqq_day_change=qqq.day_change if qqq else None,
        qqq_drawdown_6m=qqq.drawdown if qqq else None,
        qqq_return_20d=qqq.return_20d if qqq else None,
        trading_date=inputs.trading_date,
        core_date=inputs.core_date,
        sentiment_observed_at=inputs.sentiment_observed_at,
        sentiment_source=inputs.sentiment_source,
        trading_note=inputs.trading_note,
        core_note=inputs.core_note,
        observed_at=observed_at or datetime.now(timezone.utc),
        sources=sources,
        failures=failures,
    )
