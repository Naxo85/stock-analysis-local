"""Aggregate recent IBKR headlines into compact events for the AI prompt."""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.local_runner.analyst_actions import parse_analyst_headline
from src.local_runner.analyst_ratings import _canonical_firm_name
from src.local_runner.codex_generator import require_codex
from src.local_runner.ibkr_recent_news import load_recent_news
from src.local_runner.local_env import get_local_env_value


DEFAULT_PROMPT_LIMIT = 20
DEFAULT_UNRESOLVED_PROMPT_LIMIT = 3
DEFAULT_LOCAL_HEADLINE_PROMPT_LIMIT = 12
DEFAULT_NEWS_AGGREGATOR_PROVIDER = "codex"
DEFAULT_CODEX_NEWS_REASONING_EFFORT = "low"
DEFAULT_CODEX_NEWS_TIMEOUT_SECONDS = 240.0
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_GEMINI_INPUT_USD_PER_1M = 0.10
DEFAULT_GEMINI_OUTPUT_USD_PER_1M = 0.40
DEFAULT_GEMINI_TIMEOUT_SECONDS = 90.0
DEFAULT_GEMINI_RETRIES = 3
DEFAULT_GEMINI_RETRY_SLEEP_SECONDS = 2.0
GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
LOCAL_DROP_HEADLINE_MARKERS = (
    " press release:",
    " biggest bottleneck ",
    " limps along",
    " earnings afterglow",
)


def build_recent_news_events(
    repo_root: Path,
    symbol: str,
    *,
    use_gemini: bool = True,
    gemini_dry_run: bool = False,
    aggregator_provider: str | None = None,
) -> dict[str, Any]:
    recent_news = load_recent_news(repo_root, symbol)
    if recent_news.get("status") != "ok":
        return {
            "status": "unavailable",
            "reason": recent_news.get("reason", "recent_news_unavailable"),
            "source": "IBKR_TWS_API",
            "ticker": symbol.strip().upper(),
            "events": [],
            "unresolved_headlines": [],
        }

    items = recent_news.get("items")
    if not isinstance(items, list):
        items = []

    analyst_events, used_article_ids = _aggregate_analyst_events(items)
    unresolved, local_dropped = _split_local_dropped_headlines(
        [
            _compact_headline(item)
            for item in items
            if item.get("articleId") not in used_article_ids
        ]
    )

    payload = {
        "status": "ok",
        "source": "IBKR_TWS_API",
        "kind": "recent_ibkr_news_events",
        "ticker": recent_news.get("ticker") or symbol.strip().upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "news_generated_at": recent_news.get("generated_at"),
        "window": recent_news.get("window"),
        "event_count": len(analyst_events),
        "unresolved_count": len(unresolved),
        "dropped_count": len(local_dropped),
        "events": analyst_events,
        "unresolved_headlines": unresolved,
        "dropped_headlines": local_dropped,
        "aggregator": {
            "status": "not_run",
        },
    }

    if use_gemini and unresolved:
        payload = _apply_gemini_aggregation(
            repo_root=repo_root,
            symbol=symbol,
            payload=payload,
            dry_run=gemini_dry_run,
            aggregator_provider=aggregator_provider,
        )

    return payload


def write_recent_news_events(
    repo_root: Path,
    symbol: str,
    *,
    use_gemini: bool = True,
    gemini_dry_run: bool = False,
    aggregator_provider: str | None = None,
) -> dict[str, Any]:
    payload = build_recent_news_events(
        repo_root,
        symbol,
        use_gemini=use_gemini,
        gemini_dry_run=gemini_dry_run,
        aggregator_provider=aggregator_provider,
    )
    filename = "dry_run_latest.json" if gemini_dry_run else "latest.json"
    _write_events_payload(repo_root, symbol, payload, filename=filename)
    return payload


def _write_events_payload(
    repo_root: Path,
    symbol: str,
    payload: dict[str, Any],
    *,
    filename: str = "latest.json",
) -> None:
    path = repo_root / "data" / "ibkr_news_events" / symbol.strip().upper() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_unresolved_with_article_bodies(
    *,
    repo_root: Path,
    symbol: str,
    payload: dict[str, Any],
    article_payload: dict[str, Any],
    aggregator_provider: str | None = None,
) -> dict[str, Any]:
    articles = article_payload.get("articles")
    articles = articles if isinstance(articles, list) else []
    usable_articles = [
        _ai_article_body_input(item)
        for item in articles
        if isinstance(item, dict) and item.get("status") == "ok"
    ]
    payload["body_resolution"] = {
        "status": "not_run_no_usable_articles" if not usable_articles else "running",
        "requested": article_payload.get("requested_count", 0),
        "fetched": article_payload.get("article_count", 0),
        "usable": len(usable_articles),
        "source": article_payload.get("source"),
        "generated_at": article_payload.get("generated_at"),
    }
    if not usable_articles:
        _write_events_payload(repo_root, symbol, payload)
        return payload

    request_payload = {
        "ticker": symbol.strip().upper(),
        "existing_article_ids": _payload_article_ids(payload.get("events") or []),
        "unresolved_articles": usable_articles,
        "instructions": (
            "Resolve only these still-unresolved IBKR headlines using their "
            "article bodies. Return strict JSON with keys: events, "
            "unresolved_headlines, dropped_headlines. Create events only when "
            "the body supports a ticker/sector-relevant market event. Put "
            "ambiguous but relevant items in unresolved_headlines. Put broad "
            "noise, ads, generic market commentary, fragments, and irrelevant "
            "items in dropped_headlines. Do not invent facts. Merge semantic "
            "duplicates and include all articleId values in source_article_ids."
        ),
    }
    provider = _news_aggregator_provider(repo_root, override=aggregator_provider)
    if provider == "codex":
        response = _call_codex_json(
            repo_root=repo_root,
            symbol=symbol,
            payload=request_payload,
            output_name="codex_body_resolution_latest.json",
            body_resolution=True,
        )
        usage_metadata: dict[str, Any] = {}
        model = "codex_cli"
    elif provider == "gemini":
        response, usage_metadata = _call_gemini_json(
            api_key=_require_gemini_api_key(repo_root),
            payload=request_payload,
            model=_gemini_model(repo_root),
            timeout_seconds=_gemini_timeout_seconds(repo_root),
            retries=_gemini_retries(repo_root),
            retry_sleep_seconds=_gemini_retry_sleep_seconds(repo_root),
        )
        model = _gemini_model(repo_root)
    else:
        raise RuntimeError(f"unsupported_news_aggregator_provider: {provider}")

    attempted_ids = {
        str(item.get("articleId"))
        for item in usable_articles
        if isinstance(item, dict) and item.get("articleId")
    }
    previous_unresolved = payload.get("unresolved_headlines")
    previous_unresolved = previous_unresolved if isinstance(previous_unresolved, list) else []
    remaining_unresolved = [
        item
        for item in previous_unresolved
        if not isinstance(item, dict) or str(item.get("articleId")) not in attempted_ids
    ]

    events = response.get("events")
    if isinstance(events, list):
        payload["events"] = _merge_gemini_events(payload.get("events") or [], events)
        payload["event_count"] = len(payload["events"])

    unresolved = response.get("unresolved_headlines")
    if isinstance(unresolved, list):
        payload["unresolved_headlines"] = remaining_unresolved + unresolved
        payload["unresolved_count"] = len(payload["unresolved_headlines"])

    dropped = response.get("dropped_headlines")
    if isinstance(dropped, list):
        existing_dropped = payload.get("dropped_headlines")
        existing_dropped = existing_dropped if isinstance(existing_dropped, list) else []
        payload["dropped_headlines"] = existing_dropped + dropped
        payload["dropped_count"] = len(payload["dropped_headlines"])

    payload["body_resolution"] = {
        "status": "ok",
        "provider": provider,
        "model": model,
        "requested": article_payload.get("requested_count", 0),
        "fetched": article_payload.get("article_count", 0),
        "usable": len(usable_articles),
        "resolved_to_events": len(events) if isinstance(events, list) else 0,
        "still_unresolved": len(unresolved) if isinstance(unresolved, list) else 0,
        "dropped": len(dropped) if isinstance(dropped, list) else 0,
        "usage_estimate": _estimate_gemini_usage(
            repo_root=repo_root,
            request_payload=request_payload,
            response_payload=response,
            usage_metadata=usage_metadata,
        ),
    }
    _write_events_payload(repo_root, symbol, payload)
    return payload


def load_recent_news_events(repo_root: Path, symbol: str) -> dict[str, Any]:
    path = repo_root / "data" / "ibkr_news_events" / symbol.strip().upper() / "latest.json"
    if not path.exists():
        return build_recent_news_events(repo_root, symbol)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return build_recent_news_events(repo_root, symbol)

    return payload if isinstance(payload, dict) else build_recent_news_events(repo_root, symbol)


def _apply_gemini_aggregation(
    *,
    repo_root: Path,
    symbol: str,
    payload: dict[str, Any],
    dry_run: bool = False,
    aggregator_provider: str | None = None,
) -> dict[str, Any]:
    request_payload = {
        "ticker": symbol.strip().upper(),
        "existing_article_ids": _payload_article_ids(payload.get("events") or []),
        "unresolved_headlines": [
            _ai_headline_input(item)
            for item in (payload.get("unresolved_headlines") or [])
            if isinstance(item, dict)
        ],
        "instructions": (
            "Aggregate unresolved IBKR headlines into compact market events. "
            "Merge duplicates and related headlines. Keep analyst actions if "
            "they are fresh events. Return strict JSON with keys: events, "
            "unresolved_headlines, dropped_headlines. Each event must include "
            "kind, date, summary, source_article_ids, and confidence. "
            "Use unresolved_headlines only for ticker-relevant headlines that "
            "may matter but cannot be aggregated reliably from the headline. "
            "Unresolved must be exceptional; if the headline is merely opinion, "
            "generic commentary, a press release, a weak readthrough, or does "
            "not state a new concrete catalyst, put it in dropped_headlines. "
            "Put broad market noise, watchlists, generic live coverage, "
            "fragments, and low-relevance headlines in dropped_headlines. "
            "Do not drop a headline just because it does not mention the "
            "ticker: sector, direct rivals, suppliers/customers, core "
            "technology, regulation, demand, pricing, capex, or market "
            "structure can be relevant. Merge semantic duplicates into one "
            "event and include all articleId and duplicate_article_ids in "
            "source_article_ids. Do not return two events for the same fact "
            "because wording, timestamp, publisher, or '-2-' fragments differ. "
            "Do not invent facts."
        ),
    }
    provider = _news_aggregator_provider(repo_root, override=aggregator_provider)
    usage_estimate = _estimate_gemini_usage(
        repo_root=repo_root,
        request_payload=request_payload,
    )
    if dry_run:
        payload["aggregator"] = {
            "status": "dry_run",
            "provider": provider,
            "model": _provider_model(repo_root, provider),
            "usage_estimate": usage_estimate,
        }
        return payload

    if provider == "codex":
        response = _call_codex_json(
            repo_root=repo_root,
            symbol=symbol,
            payload=request_payload,
        )
        usage_metadata: dict[str, Any] = {}
        model = "codex_cli"
    elif provider == "gemini":
        response, usage_metadata = _call_gemini_json(
            api_key=_require_gemini_api_key(repo_root),
            payload=request_payload,
            model=_gemini_model(repo_root),
            timeout_seconds=_gemini_timeout_seconds(repo_root),
            retries=_gemini_retries(repo_root),
            retry_sleep_seconds=_gemini_retry_sleep_seconds(repo_root),
        )
        model = _gemini_model(repo_root)
    else:
        raise RuntimeError(f"unsupported_news_aggregator_provider: {provider}")

    original_unresolved = payload.get("unresolved_headlines") or []
    events = response.get("events")
    unresolved = response.get("unresolved_headlines")
    if isinstance(events, list):
        payload["events"] = _merge_gemini_events(payload.get("events") or [], events)
        payload["event_count"] = len(payload["events"])
    if isinstance(unresolved, list):
        payload["unresolved_headlines"] = _restore_headline_metadata(
            unresolved,
            original_unresolved,
        )
        payload["unresolved_count"] = len(payload["unresolved_headlines"])
    dropped = response.get("dropped_headlines")
    if isinstance(dropped, list):
        existing_dropped = payload.get("dropped_headlines")
        existing_dropped = existing_dropped if isinstance(existing_dropped, list) else []
        restored_dropped = _restore_headline_metadata(
            dropped,
            original_unresolved,
        )
        payload["dropped_headlines"] = existing_dropped + restored_dropped
        payload["dropped_count"] = len(payload["dropped_headlines"])

    payload["aggregator"] = {
        "status": "ok",
        "provider": provider,
        "model": model,
        "usage_estimate": _estimate_gemini_usage(
            repo_root=repo_root,
            request_payload=request_payload,
            response_payload=response,
            usage_metadata=usage_metadata,
        ),
    }
    return payload


def _require_gemini_api_key(repo_root: Path) -> str:
    api_key = (
        get_local_env_value("GEMINI_API_KEY", repo_root=repo_root)
        or get_local_env_value("GOOGLE_API_KEY", repo_root=repo_root)
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not api_key:
        raise RuntimeError("gemini_api_key_missing: set GEMINI_API_KEY in .env.local")
    return api_key


def _call_codex_json(
    *,
    repo_root: Path,
    symbol: str,
    payload: dict[str, Any],
    output_name: str = "codex_aggregation_latest.json",
    body_resolution: bool = False,
) -> dict[str, Any]:
    codex_path = require_codex()
    output_path = (
        repo_root
        / "data"
        / "ibkr_news_events"
        / symbol.strip().upper()
        / output_name
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    task = (
        "Resuelve titulares ambiguos usando cuerpo de noticia para un analisis "
        "bursatil diario."
        if body_resolution
        else "Agrega titulares de mercado para un analisis bursatil diario."
    )
    prompt = (
        "TAREA CERRADA Y SIN HERRAMIENTAS.\n"
        "No busques en web. No leas ficheros. No ejecutes comandos. "
        "No inspecciones el repo. Usa exclusivamente el JSON incluido abajo.\n\n"
        f"{task}\n"
        "Devuelve SOLO JSON valido, sin markdown, con claves exactas: "
        "events, unresolved_headlines, dropped_headlines.\n"
        "No inventes hechos. Fusiona duplicados. Si un titular no basta para "
        "crear evento fiable pero parece relevante para el ticker, dejalo en "
        "unresolved_headlines.\n"
        "Si el titular es ruido amplio de mercado, watchlist generica, live "
        "coverage, fragmento, repeticion, o no parece material para el ticker, "
        "ponlo en dropped_headlines.\n"
        "unresolved_headlines debe ser excepcional. Si es opinion, press "
        "release, readthrough flojo, comentario generico o no declara un "
        "catalizador concreto nuevo, ponlo en dropped_headlines.\n"
        "No descartes un titular solo porque no mencione el ticker: sector, "
        "rivales directos, proveedores/clientes, tecnologia central, regulacion, "
        "demanda, pricing, capex o estructura de mercado pueden ser relevantes.\n"
        "Si varios titulares dicen sustancialmente lo mismo, crea un solo "
        "evento e incluye todos sus articleId y duplicate_article_ids en "
        "source_article_ids. No devuelvas dos eventos para el mismo hecho por "
        "cambios de redaccion, hora, medio o fragmentos tipo '-2-'.\n"
        "Cada event debe incluir kind, date, summary, source_article_ids y "
        "confidence.\n\n"
        "No expliques tu razonamiento. No incluyas notas. No hagas analisis "
        "del ticker; solo agregacion/clasificacion de titulares.\n\n"
        "Input:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    command = (
        codex_path,
        "exec",
        "-c",
        f'model_reasoning_effort="{DEFAULT_CODEX_NEWS_REASONING_EFFORT}"',
        "--output-last-message",
        str(output_path),
        "-",
    )
    try:
        subprocess.run(
            list(command),
            cwd=str(repo_root),
            check=True,
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=_codex_news_timeout_seconds(repo_root),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("codex_news_aggregation_timeout") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        detail = f": {stderr[:1000]}" if stderr else ""
        raise RuntimeError(
            f"codex_news_aggregation_failed: exit_code={exc.returncode}{detail}"
        ) from exc

    if not output_path.exists():
        raise RuntimeError(f"codex_news_aggregation_no_output: {output_path}")

    return _parse_json_model_output(output_path.read_text(encoding="utf-8"))


def _parse_json_model_output(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("news_aggregation_response_not_object")
    return parsed


def _call_gemini_json(
    *,
    api_key: str,
    payload: dict[str, Any],
    model: str,
    timeout_seconds: float,
    retries: int,
    retry_sleep_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    params = urlencode({"key": api_key})
    url = f"{GEMINI_URL_TEMPLATE.format(model=model)}?{params}"
    body = json.dumps(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Return only valid JSON. Input:\n"
                                + json.dumps(payload, ensure_ascii=False)
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    raw = ""
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in {500, 502, 503, 504} and attempt < retries:
                time.sleep(retry_sleep_seconds * (attempt + 1))
                continue
            raise RuntimeError(f"gemini_http_{exc.code}: {detail[:500]}") from exc
        except TimeoutError as exc:
            if attempt < retries:
                time.sleep(retry_sleep_seconds * (attempt + 1))
                continue
            raise RuntimeError(
                f"gemini_read_timeout_after_{timeout_seconds:g}s"
            ) from exc
        except URLError as exc:
            if attempt < retries:
                time.sleep(retry_sleep_seconds * (attempt + 1))
                continue
            raise RuntimeError(f"gemini_url_error: {exc}") from exc

    parsed = json.loads(raw)
    text = (
        parsed.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("gemini_empty_response")

    result = json.loads(text)
    if not isinstance(result, dict):
        raise RuntimeError("gemini_response_not_object")
    usage_metadata = parsed.get("usageMetadata")
    return result, usage_metadata if isinstance(usage_metadata, dict) else {}


def _estimate_gemini_usage(
    *,
    repo_root: Path,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any] | None = None,
    usage_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_text = "Return only valid JSON. Input:\n" + json.dumps(
        request_payload,
        ensure_ascii=False,
    )
    response_text = (
        json.dumps(response_payload, ensure_ascii=False)
        if response_payload is not None
        else ""
    )
    estimated_input_tokens = _rough_token_count(request_text)
    estimated_output_tokens = _rough_token_count(response_text) if response_text else 0
    input_tokens = _int_or_none((usage_metadata or {}).get("promptTokenCount"))
    output_tokens = _int_or_none((usage_metadata or {}).get("candidatesTokenCount"))
    input_tokens = input_tokens if input_tokens is not None else estimated_input_tokens
    output_tokens = output_tokens if output_tokens is not None else estimated_output_tokens
    input_rate = _env_float(
        "GEMINI_FLASH_INPUT_USD_PER_1M",
        repo_root=repo_root,
        default=DEFAULT_GEMINI_INPUT_USD_PER_1M,
    )
    output_rate = _env_float(
        "GEMINI_FLASH_OUTPUT_USD_PER_1M",
        repo_root=repo_root,
        default=DEFAULT_GEMINI_OUTPUT_USD_PER_1M,
    )
    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    return {
        "method": "api_usage_metadata_or_chars_div_4",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_usd_per_1m": input_rate,
        "output_usd_per_1m": output_rate,
        "cost_usd": round(cost, 8),
        "cost_eur_approx": round(cost * 0.93, 8),
        "estimated": not bool(usage_metadata),
    }


def _gemini_model(repo_root: Path) -> str:
    return (
        get_local_env_value("GEMINI_MODEL", repo_root=repo_root)
        or os.environ.get("GEMINI_MODEL")
        or DEFAULT_GEMINI_MODEL
    )


def _news_aggregator_provider(repo_root: Path, *, override: str | None = None) -> str:
    if override:
        return override.strip().lower()
    value = (
        get_local_env_value("NEWS_AGGREGATOR_PROVIDER", repo_root=repo_root)
        or os.environ.get("NEWS_AGGREGATOR_PROVIDER")
        or DEFAULT_NEWS_AGGREGATOR_PROVIDER
    )
    return value.strip().lower()


def _provider_model(repo_root: Path, provider: str) -> str:
    if provider == "codex":
        return f"codex_cli:{DEFAULT_CODEX_NEWS_REASONING_EFFORT}"
    if provider == "gemini":
        return _gemini_model(repo_root)
    return provider


def _codex_news_timeout_seconds(repo_root: Path) -> float:
    return _env_float(
        "CODEX_NEWS_TIMEOUT_SECONDS",
        repo_root=repo_root,
        default=DEFAULT_CODEX_NEWS_TIMEOUT_SECONDS,
    )


def _gemini_timeout_seconds(repo_root: Path) -> float:
    return _env_float(
        "GEMINI_TIMEOUT_SECONDS",
        repo_root=repo_root,
        default=DEFAULT_GEMINI_TIMEOUT_SECONDS,
    )


def _gemini_retries(repo_root: Path) -> int:
    raw = get_local_env_value("GEMINI_RETRIES", repo_root=repo_root)
    if raw is None:
        raw = os.environ.get("GEMINI_RETRIES")
    if not raw:
        return DEFAULT_GEMINI_RETRIES
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_GEMINI_RETRIES


def _gemini_retry_sleep_seconds(repo_root: Path) -> float:
    return _env_float(
        "GEMINI_RETRY_SLEEP_SECONDS",
        repo_root=repo_root,
        default=DEFAULT_GEMINI_RETRY_SLEEP_SECONDS,
    )


def _rough_token_count(value: str) -> int:
    return max(1, math.ceil(len(value) / 4))


def _env_float(key: str, *, repo_root: Path, default: float) -> float:
    raw = get_local_env_value(key, repo_root=repo_root)
    if raw is None:
        raw = os.environ.get(key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _merge_gemini_events(
    existing: list[Any],
    generated: list[Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = [
        item for item in existing if isinstance(item, dict)
    ]
    seen_article_ids = set()
    for item in output:
        seen_article_ids.update(_event_article_ids(item))

    seen = {
        (
            str(item.get("date") or ""),
            str(item.get("kind") or ""),
            str(item.get("summary") or ""),
        )
        for item in output
    }
    for item in generated:
        if not isinstance(item, dict):
            continue
        article_ids = _event_article_ids(item)
        if article_ids and seen_article_ids.intersection(article_ids):
            seen_article_ids.update(article_ids)
            continue
        key = (
            str(item.get("date") or ""),
            str(item.get("kind") or ""),
            str(item.get("summary") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        seen_article_ids.update(article_ids)
        output.append(item)
    output.sort(key=lambda item: str(item.get("date") or item.get("published_at") or ""), reverse=True)
    return output


def _event_article_ids(event: dict[str, Any]) -> set[str]:
    values = event.get("source_article_ids")
    if values is None:
        values = event.get("article_ids")
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if value}


def _payload_article_ids(events: list[Any]) -> list[str]:
    values: set[str] = set()
    for event in events:
        if isinstance(event, dict):
            values.update(_event_article_ids(event))
    return sorted(values)


def _ai_headline_input(item: dict[str, Any]) -> dict[str, Any]:
    output = {
        "published_at": item.get("published_at"),
        "articleId": item.get("articleId"),
        "headline": item.get("headline"),
    }
    duplicates = item.get("duplicate_article_ids")
    if isinstance(duplicates, list) and duplicates:
        output["duplicate_article_ids"] = duplicates
    return output


def _ai_article_body_input(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "published_at": item.get("published_at"),
        "articleId": item.get("articleId"),
        "headline": item.get("headline"),
        "articleText": item.get("articleText"),
        "truncated": item.get("truncated"),
    }


def _restore_headline_metadata(
    items: list[Any],
    originals: list[Any],
) -> list[dict[str, Any]]:
    by_article_id = {
        str(item.get("articleId")): item
        for item in originals
        if isinstance(item, dict) and item.get("articleId")
    }
    output: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        restored = dict(item)
        original = by_article_id.get(str(restored.get("articleId")))
        if isinstance(original, dict):
            for key in (
                "published_at",
                "providerCode",
                "articleId",
                "headline",
                "duplicate_article_ids",
            ):
                if restored.get(key) in (None, "") and original.get(key) not in (None, ""):
                    restored[key] = original.get(key)
        output.append(restored)
    return output


def format_recent_news_events_for_prompt(
    payload: dict[str, Any],
    *,
    limit: int = DEFAULT_PROMPT_LIMIT,
    unresolved_limit: int = DEFAULT_UNRESOLVED_PROMPT_LIMIT,
) -> str:
    if payload.get("status") != "ok":
        return (
            "No hay eventos recientes agregados de IBKR disponibles. "
            f"Motivo: {payload.get('reason', 'unknown')}."
        )

    lines: list[str] = []
    events = payload.get("events")
    unresolved = payload.get("unresolved_headlines")
    events = events if isinstance(events, list) else []
    unresolved = unresolved if isinstance(unresolved, list) else []

    window = payload.get("window") or {}
    start = _short_date(window.get("start"))
    end = _short_date(window.get("end"))

    prompt_events = [
        event
        for event in events
        if isinstance(event, dict) and event.get("kind") != "analyst_action"
    ]

    if prompt_events:
        suffix = f" ({start}->{end})" if start or end else ""
        lines.append(f"Noticias IBKR agregadas{suffix}:")
        for event in prompt_events[:limit]:
            lines.append(f"- {_compact_event_line(event)}")
        if len(prompt_events) > limit:
            lines.append(f"- +{len(prompt_events) - limit} eventos truncados.")

    if unresolved and unresolved_limit > 0:
        if lines:
            lines.append("")
        lines.append("Titulares ambiguos aun no agregados:")
        for item in unresolved[:unresolved_limit]:
            lines.append(f"- {_short_date(item.get('published_at'))}: {item.get('headline')}")
        if len(unresolved) > unresolved_limit:
            lines.append(f"- +{len(unresolved) - unresolved_limit} ambiguos truncados.")

    if not lines:
        window = payload.get("window") or {}
        return (
            "IBKR no devolvió eventos/titulares nuevos desde "
            f"{window.get('start', 'unknown')}."
        )

    return "\n".join(lines)


def format_recent_news_local_triage_for_prompt(
    payload: dict[str, Any],
    *,
    limit: int = DEFAULT_LOCAL_HEADLINE_PROMPT_LIMIT,
) -> str:
    if payload.get("status") != "ok":
        return (
            "No hay titulares recientes de IBKR disponibles. "
            f"Motivo: {payload.get('reason', 'unknown')}."
        )

    items = payload.get("items")
    items = items if isinstance(items, list) else []
    kept, dropped = _local_triage_headlines(items)
    window = payload.get("window") or {}
    start = _short_date(window.get("start"))
    end = _short_date(window.get("end"))

    if not kept:
        return f"IBKR no devolvió titulares recientes relevantes ({start}->{end})."

    lines = [f"Titulares IBKR filtrados localmente ({start}->{end}):"]
    for item in kept[:limit]:
        lines.append(f"- {_short_date(item.get('published_at'))}: {item.get('headline')}")
    if len(kept) > limit:
        lines.append(f"- +{len(kept) - limit} titulares filtrados truncados.")
    if dropped:
        lines.append(f"(Descartados localmente por ruido/duplicado: {len(dropped)})")
    return "\n".join(lines)


def _compact_event_line(event: dict[str, Any]) -> str:
    date = _short_date(event.get("date") or event.get("published_at"))
    kind = str(event.get("kind") or "event")
    confidence = event.get("confidence")
    confidence_text = ""
    if isinstance(confidence, (int, float)):
        confidence_text = f" c={confidence:.2g}"
    summary = str(event.get("summary") or "").strip()
    return " | ".join(part for part in (date, kind, f"{summary}{confidence_text}") if part)


def _short_date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def _aggregate_analyst_events(
    items: list[Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    used_article_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        headline = str(item.get("headline") or "")
        parsed = parse_analyst_headline(headline)
        if parsed.get("parse_status") != "parsed":
            continue

        firm = _canonical_firm_name(parsed.get("firm"))
        if not firm:
            continue

        published_at = str(item.get("published_at") or "")
        event_date = published_at[:10] if published_at else ""
        key = (firm, event_date)
        current = grouped.setdefault(
            key,
            {
                "kind": "analyst_action",
                "date": event_date,
                "published_at": published_at,
                "firm": firm,
                "event_types": [],
                "rating": None,
                "rating_bucket": "unknown",
                "target": None,
                "previous_target": None,
                "article_ids": [],
                "headlines": [],
            },
        )

        _append_unique(current["event_types"], parsed.get("event_type"))
        _append_unique(current["article_ids"], item.get("articleId"))
        _append_unique(current["headlines"], headline)
        current["published_at"] = max(str(current.get("published_at") or ""), published_at)

        if parsed.get("rating"):
            current["rating"] = parsed.get("rating")
            current["rating_bucket"] = parsed.get("rating_bucket") or "unknown"
        if parsed.get("target") is not None:
            current["target"] = parsed.get("target")
        if parsed.get("previous_target") is not None:
            current["previous_target"] = parsed.get("previous_target")

        if item.get("articleId"):
            used_article_ids.add(str(item.get("articleId")))

    events = [_finalize_analyst_event(event) for event in grouped.values()]
    events.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    return events, used_article_ids


def _finalize_analyst_event(event: dict[str, Any]) -> dict[str, Any]:
    event = dict(event)
    event["summary"] = _analyst_event_summary(event)
    return event


def _analyst_event_summary(event: dict[str, Any]) -> str:
    firm = event.get("firm") or "Analyst"
    rating = event.get("rating")
    target = event.get("target")
    previous_target = event.get("previous_target")
    event_types = set(event.get("event_types") or [])

    parts = []
    if rating:
        if "rating_maintained" in event_types:
            parts.append(f"mantiene {rating}")
        else:
            parts.append(f"rating {rating}")
    if isinstance(target, (int, float)):
        if isinstance(previous_target, (int, float)):
            direction = "sube" if target > previous_target else "baja"
            parts.append(f"{direction} PT {previous_target:g}->{target:g}")
        else:
            parts.append(f"PT {target:g}")

    detail = " y ".join(parts) if parts else "acción de analista"
    return f"{firm} {detail}"


def _event_line(event: dict[str, Any]) -> str:
    return " | ".join(
        part
        for part in (
            str(event.get("date") or event.get("published_at") or ""),
            str(event.get("kind") or ""),
            str(event.get("summary") or ""),
        )
        if part
    )


def _compact_headline(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "published_at": item.get("published_at"),
        "providerCode": item.get("providerCode"),
        "articleId": item.get("articleId"),
        "headline": item.get("headline"),
    }


def _dedupe_headlines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_headline: dict[str, dict[str, Any]] = {}
    output: list[dict[str, Any]] = []

    for item in items:
        key = _headline_key(item.get("headline"))
        if not key:
            continue
        existing = by_headline.get(key)
        if existing is not None:
            _append_duplicate_article_id(existing, item.get("articleId"))
            continue
        by_headline[key] = item
        output.append(item)

    return output


def _split_local_dropped_headlines(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unresolved = []
    dropped = []
    for item in _dedupe_headlines(items):
        if _is_local_drop_headline(item.get("headline")):
            dropped.append(item)
        else:
            unresolved.append(item)
    return unresolved, dropped


def _local_triage_headlines(
    items: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compact = [_compact_headline(item) for item in items if isinstance(item, dict)]
    kept, dropped = _split_local_dropped_headlines(compact)
    filtered_kept = []
    for item in kept:
        headline = str(item.get("headline") or "")
        if _is_low_signal_headline(headline) or not _is_medium_prompt_candidate(headline):
            dropped.append(item)
        else:
            filtered_kept.append(item)
    return filtered_kept, dropped


def _is_medium_prompt_candidate(value: str) -> bool:
    text = _headline_key(value)
    direct_terms = ("nvidia", "nvda")
    direct = any(term in text for term in direct_terms)
    if direct:
        return True
    strong_sector_terms = (
        "ai chip demand",
        "ai chip competition",
        "custom-chip race",
        "openai enters the custom-chip",
        "broadcom",
        "tsmc",
    )
    return any(term in text for term in strong_sector_terms)


def _is_low_signal_headline(value: str) -> bool:
    text = _headline_key(value)
    if not text:
        return True
    low_signal_markers = (
        "correction to ",
        "cfa technology:",
        "cfa high yield:",
        "insider review",
        "substantial insider sales",
        "surrenders ",
        " sells ",
        "nvidia-backed",
        "micron is the new nvidia",
        "softbank's son:",
        "stocks to watch:",
        "stock market today:",
        "dow jones futures",
        "s&p 500 futures",
        "dow rallies",
        "dow's ",
        "dow index",
        "and more stocks that explain today",
        "market weekly review",
        "live coverage",
        "review --",
    )
    price_only_markers = (
        "nvidia stock rises",
        "nvidia stock steadies",
        "nvidia stock gains",
        "nvidia stock continues slide",
        "nvidia stock keeps falling",
        "nvidia stock keeps sliding",
        "nvidia stock tests key price level",
        "nvidia tests key price level",
        "nvidia stock has a new floor",
    )
    if any(marker in text for marker in price_only_markers):
        return not any(signal in text for signal in ("ai chip demand", "rivals", "competition"))
    return any(marker in text for marker in low_signal_markers)


def _is_local_drop_headline(value: Any) -> bool:
    normalized = f" {_headline_key(value)} "
    return any(marker in normalized for marker in LOCAL_DROP_HEADLINE_MARKERS)


def _append_duplicate_article_id(item: dict[str, Any], article_id: Any) -> None:
    if not article_id or article_id == item.get("articleId"):
        return
    values = item.setdefault("duplicate_article_ids", [])
    if isinstance(values, list) and article_id not in values:
        values.append(article_id)


def _headline_key(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _append_unique(values: list[Any], value: Any) -> None:
    if value is None:
        return
    if value not in values:
        values.append(value)
