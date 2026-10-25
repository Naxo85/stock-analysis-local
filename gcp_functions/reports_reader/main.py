"""Serve the latest stock report stored in GCS."""

from __future__ import annotations

import json
import logging
import os
from html import escape
from publication_contract import (read_committed, read_attempt, with_attempt, attempt_notice,
                                  PublicationVersionNotFound, InvalidPublicationVersion)

import functions_framework
from flask import Response, jsonify, make_response
from google.api_core.exceptions import NotFound
from google.cloud import storage


logging.basicConfig(level=logging.INFO)

GCS_BUCKET = os.environ.get("GCS_BUCKET", "stock-analysis-reports-naxo85")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

storage_client = storage.Client()


@functions_framework.http
def read_stock_report(request):
    if request.method == "OPTIONS":
        return _cors_response("", status=204)

    try:
        symbol = _get_symbol(request)

        if not symbol:
            return _json_response({"error": "Missing 'symbol'"}, status=400)

        fmt = (request.args.get("format") or "json").strip().lower()
        debug = _bool_param(request, "debug", default=False)
        version = request.args.get("version")

        if fmt == "md":
            return _text_response(
                _read_latest_text(symbol, "md", version=version),
                content_type="text/markdown; charset=utf-8",
            )

        if fmt == "html":
            response = _text_response(
                _read_latest_text(symbol, "html", version=version),
                content_type="text/html; charset=utf-8",
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "img-src https: data:; base-uri 'none'; form-action 'none'"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        if fmt != "json":
            return _json_response(
                {"error": "Unsupported format", "allowed": ["json", "md", "html"]},
                status=400,
            )

        full_json = _read_latest_json(symbol, version=version)

        if debug:
            return _json_response(full_json)

        return _json_response(_to_app_response(full_json))

    except InvalidPublicationVersion as exc:
        return _json_response({"error": str(exc)}, status=400)
    except MissingCurrentReport as exc:
        return _json_response({"error": "report_not_found", "symbol": exc.symbol,
            "analysis_status": "unavailable", "generated_at": None,
            "latest_attempt": exc.attempt,
            "attempt_notice": attempt_notice(exc.attempt, has_report=False)}, status=404)
    except (NotFound, PublicationVersionNotFound):
        logging.exception("report_not_found")
        return _json_response(
            {
                "error": "report_not_found",
                "message": "No latest report found for this symbol",
            },
            status=404,
        )
    except Exception as exc:
        logging.exception("internal_error")
        return _json_response(
            {"error": "internal_error", "details": str(exc)},
            status=500,
        )


def _get_symbol(request):
    symbol = (request.args.get("symbol") or "").strip().upper()

    if not symbol:
        payload = request.get_json(silent=True) or {}
        symbol = payload.get("symbol") or ((payload.get("tickers") or [None])[0]) or ""
        symbol = str(symbol).strip().upper()

    return symbol or None


def _bool_param(request, name: str, default: bool = False):
    raw = request.args.get(name)

    if raw is None:
        return default

    return str(raw).strip().lower() in ("1", "true", "yes", "y", "si", "sí")


class MissingCurrentReport(NotFound):
    def __init__(self, symbol, attempt):
        super().__init__('report_not_found')
        self.symbol = symbol
        self.attempt = attempt


def _read_latest_json(symbol: str, *, version=None):
    text = _read_latest_text(symbol, "json", version=version)
    return json.loads(text)


def _read_latest_text(symbol: str, extension: str, *, version=None):
    bucket = storage_client.bucket(GCS_BUCKET)
    def read(name):
        try:
            return bucket.blob(name).download_as_text(encoding='utf-8', timeout=30)
        except NotFound:
            return None
    body, manifest = read_committed(read, symbol, extension, version=version)
    if manifest is None:
        body = read(f'{symbol}/latest.{extension}')
    attempt = read_attempt(read, symbol)
    if body is None:
        raise MissingCurrentReport(symbol, attempt)
    if extension == 'json':
        return json.dumps(with_attempt(json.loads(body), attempt, manifest), ensure_ascii=False)
    notice = attempt_notice(attempt)
    if notice and extension == 'md':
        return '> ' + notice + '\n\n' + body
    if notice and extension == 'html':
        banner = '<aside role="status">' + escape(notice) + '</aside>'
        import re
        match = re.search(r'<body\b[^>]*>', body, re.IGNORECASE)
        return body[:match.end()] + banner + body[match.end():] if match else banner + body
    return body


def _to_app_response(full_json: dict):
    grounding = full_json.get("grounding") or {}
    sources = grounding.get("sources") or []
    queries = grounding.get("web_search_queries") or []

    return {
        "symbol": full_json.get("symbol"),
        "analysis_status": full_json.get("analysis_status"),
        "publication_version": full_json.get("publication_version"),
        "latest_attempt": full_json.get("latest_attempt"),
        "attempt_notice": attempt_notice(full_json.get("latest_attempt")),
        "generated_at": full_json.get("generated_at"),
        "model": full_json.get("model"),
        "slim_as_of": full_json.get("slim_as_of"),
        "latest_price": full_json.get("latest_price"),
        "analysis_markdown": full_json.get("analysis_markdown"),
        "analyst_ratings_summary": full_json.get("analyst_ratings_summary") or {},
        "grounded": bool(sources or queries),
        "sources_count": len(sources),
        "search_queries_count": len(queries),
    }


def _json_response(payload: dict, status: int = 200):
    response = make_response(jsonify(payload), status)
    _add_cors_headers(response)
    return response


def _text_response(
    text: str,
    status: int = 200,
    content_type: str = "text/plain; charset=utf-8",
):
    response = make_response(Response(text, status=status, content_type=content_type))
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
