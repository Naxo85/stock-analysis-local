"""Fetch IBKR news article bodies for selected headlines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


DEFAULT_MAX_ARTICLES = 8
DEFAULT_MAX_CHARS = 2500


def fetch_ibkr_news_articles(
    *,
    articles: list[dict[str, Any]],
    host: str,
    port: int,
    client_id: int,
    timeout: float,
    readonly: bool,
    max_articles: int = DEFAULT_MAX_ARTICLES,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, Any]:
    """Fetch article bodies by provider/article id from TWS API."""

    try:
        from ib_insync import IB
    except ImportError as exc:
        raise RuntimeError(
            "ib_insync_not_installed: install ib_insync in this Python environment"
        ) from exc

    selected = [
        item
        for item in articles
        if isinstance(item, dict) and item.get("providerCode") and item.get("articleId")
    ][:max_articles]
    ib = IB()

    try:
        try:
            ib.connect(
                host,
                port,
                clientId=client_id,
                readonly=readonly,
                timeout=timeout,
            )
        except OSError as exc:
            raise RuntimeError(
                f"ibkr_article_connection_failed: {host}:{port} - {exc}"
            ) from exc

        fetched = []
        for item in selected:
            fetched.append(
                _fetch_one(
                    ib=ib,
                    item=item,
                    max_chars=max_chars,
                )
            )

        return {
            "status": "ok",
            "source": "IBKR_TWS_API",
            "kind": "news_article_bodies",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested_count": len(selected),
            "article_count": len(fetched),
            "max_chars": max_chars,
            "articles": fetched,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()


def _fetch_one(*, ib: Any, item: dict[str, Any], max_chars: int) -> dict[str, Any]:
    provider = str(item.get("providerCode") or "")
    article_id = str(item.get("articleId") or "")

    try:
        article = ib.reqNewsArticle(provider, article_id, [])
        article_type = getattr(article, "articleType", None)
        article_text = _clean_article_text(getattr(article, "articleText", None))
        status = "ok" if article_text else "empty"
        error = None
    except Exception as exc:  # noqa: BLE001 - one failed body should not hide others.
        article_type = None
        article_text = ""
        status = "failed"
        error = str(exc)[:500]

    return {
        "published_at": item.get("published_at"),
        "providerCode": provider,
        "articleId": article_id,
        "headline": item.get("headline"),
        "articleType": article_type,
        "status": status,
        "error": error,
        "articleText": article_text[:max_chars],
        "articleText_chars": len(article_text),
        "truncated": len(article_text) > max_chars,
    }


def _clean_article_text(value: Any) -> str:
    return " ".join(str(value or "").split())
