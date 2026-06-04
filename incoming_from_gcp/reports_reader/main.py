import os
import json
import logging
import functions_framework

from flask import jsonify, Response, make_response
from google.cloud import storage
from google.api_core.exceptions import NotFound


logging.basicConfig(level=logging.INFO)

GCS_BUCKET = os.environ.get(
    "GCS_BUCKET",
    "stock-analysis-reports-naxo85"
)

ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN",
    "*"
)

storage_client = storage.Client()


@functions_framework.http
def read_stock_report(request):
    # CORS preflight para frontend web
    if request.method == "OPTIONS":
        return _cors_response("", status=204)

    try:
        symbol = _get_symbol(request)

        if not symbol:
            return _json_response(
                {"error": "Missing 'symbol'"},
                status=400
            )

        fmt = (request.args.get("format") or "json").strip().lower()
        debug = _bool_param(request, "debug", default=False)

        if fmt == "md":
            markdown = _read_latest_md(symbol)

            return _text_response(
                markdown,
                content_type="text/markdown; charset=utf-8"
            )

        full_json = _read_latest_json(symbol)

        if debug:
            # Devuelve todo lo guardado: analysis, grounding, slim_snapshot, etc.
            return _json_response(full_json)

        # Respuesta limpia para la app
        clean = _to_app_response(full_json)

        return _json_response(clean)

    except NotFound:
        logging.exception("report_not_found")

        return _json_response(
            {
                "error": "report_not_found",
                "message": "No latest report found for this symbol"
            },
            status=404
        )

    except Exception as e:
        logging.exception("internal_error")

        return _json_response(
            {
                "error": "internal_error",
                "details": str(e)
            },
            status=500
        )


def _get_symbol(request):
    symbol = (request.args.get("symbol") or "").strip().upper()

    if not symbol:
        payload = request.get_json(silent=True) or {}

        symbol = (
            payload.get("symbol")
            or ((payload.get("tickers") or [None])[0])
            or ""
        )

        symbol = str(symbol).strip().upper()

    return symbol or None


def _bool_param(request, name: str, default: bool = False):
    raw = request.args.get(name)

    if raw is None:
        return default

    return str(raw).strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "si",
        "sí"
    )


def _read_latest_json(symbol: str):
    bucket = storage_client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{symbol}/latest.json")

    text = blob.download_as_text(
        encoding="utf-8"
    )

    return json.loads(text)


def _read_latest_md(symbol: str):
    bucket = storage_client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{symbol}/latest.md")

    return blob.download_as_text(
        encoding="utf-8"
    )


def _to_app_response(full_json: dict):
    grounding = full_json.get("grounding") or {}
    sources = grounding.get("sources") or []
    queries = grounding.get("web_search_queries") or []

    return {
        "symbol": full_json.get("symbol"),
        "generated_at": full_json.get("generated_at"),
        "model": full_json.get("model"),
        "slim_as_of": full_json.get("slim_as_of"),
        "latest_price": full_json.get("latest_price"),
        "analysis_markdown": full_json.get("analysis_markdown"),
        "grounded": bool(sources or queries),
        "sources_count": len(sources),
        "search_queries_count": len(queries),
    }


def _json_response(payload: dict, status: int = 200):
    response = make_response(
        jsonify(payload),
        status
    )

    _add_cors_headers(response)

    return response


def _text_response(
    text: str,
    status: int = 200,
    content_type: str = "text/plain; charset=utf-8"
):
    response = make_response(
        Response(
            text,
            status=status,
            content_type=content_type
        )
    )

    _add_cors_headers(response)

    return response


def _cors_response(body, status: int = 200):
    response = make_response(body, status)

    _add_cors_headers(response)

    return response


def _add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    return response