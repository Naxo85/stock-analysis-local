from __future__ import annotations

import json
import logging
import math
import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from stock_analysis.contracts.market import DailyBar, Quote, TickerMarketData
from stock_analysis.market_worker.metrics import day_change, market_has_no_session


TRADIER_BASE_URL = "https://api.tradier.com/v1/markets"
MAX_EXTENDED_QUOTE_AGE = timedelta(minutes=15)
MAX_EXTENDED_SPREAD_RATIO = 0.05
QUOTE_CACHE_NAME = "latest_quotes.json"
LOGGER = logging.getLogger(__name__)


class MarketDataError(RuntimeError):
    pass


def _default_http_json(
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers=headers)
    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                rate_limit = {
                    name: response.headers.get(name)
                    for name in (
                        "X-Ratelimit-Allowed",
                        "X-Ratelimit-Used",
                        "X-Ratelimit-Available",
                        "X-Ratelimit-Expiry",
                    )
                    if response.headers.get(name) is not None
                }
                if rate_limit:
                    LOGGER.info("Tradier rate limit: %s", rate_limit)
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            last_error = error
            if error.code != 429 and not 500 <= error.code < 600:
                break
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = float(retry_after) if retry_after else 2**attempt
            except ValueError:
                delay = 2**attempt
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            delay = 2**attempt
        if attempt < 2:
            time.sleep(min(delay, 30))
    raise MarketDataError(f"request failed for {url}: {last_error}") from last_error


class TradierMarketDataProvider:
    """Tradier-backed quotes with once-per-market-day historical caching.

    One batch quote call is made per refresh. Daily OHLC is downloaded once per
    ticker and ET date, then reused by every refresh. Premarket and postmarket
    prices use the live bid/ask midpoint because Tradier's ``last`` remains at
    the previous regular close outside the regular session.
    """

    def __init__(
        self,
        token: str,
        *,
        cache_dir: Path | None = None,
        http_json: Callable[..., dict[str, Any]] = _default_http_json,
        history_workers: int = 6,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not token.strip():
            raise ValueError("Tradier token is required")
        self._headers = {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
        }
        self._cache_dir = cache_dir or Path("artifacts/cache/tradier")
        self._http_json = http_json
        self._history_workers = history_workers
        self._now = now or (lambda: datetime.now(timezone.utc))

    def fetch_universe(
        self,
        tickers: Iterable[str],
        *,
        market_date: date,
        prefer_extended: bool = False,
    ) -> tuple[dict[str, TickerMarketData], dict[str, str]]:
        universe = tuple(dict.fromkeys(ticker.strip().upper() for ticker in tickers))
        cached_quotes = self._read_quote_cache()
        quotes = self._fetch_quotes(
            universe, prefer_extended=prefer_extended, cached_quotes=cached_quotes
        )
        histories: dict[str, tuple[DailyBar, ...]] = {}
        failures: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=self._history_workers) as executor:
            futures = {
                executor.submit(self._fetch_history, ticker, market_date): ticker
                for ticker in universe
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    histories[ticker] = future.result()
                except MarketDataError as error:
                    failures[ticker] = str(error)

        result: dict[str, TickerMarketData] = {}
        for ticker in universe:
            quote = quotes.get(ticker)
            history = histories.get(ticker)
            if quote is None:
                failures[ticker] = "quote missing from Tradier batch response"
            elif not history:
                failures.setdefault(ticker, "daily history unavailable")
            else:
                if not quote.cached:
                    represented_date = market_date
                    if market_has_no_session(market_date):
                        represented_date = history[-1].session_date
                    quote = replace(
                        quote,
                        day_change=day_change(quote.price, history, represented_date),
                    )
                    cached_quotes[ticker] = quote
                result[ticker] = TickerMarketData(quote=quote, daily_bars=history)
        if any(not item.quote.cached for item in result.values()):
            self._write_quote_cache(cached_quotes)
        return result, failures

    def _fetch_quotes(
        self,
        tickers: tuple[str, ...],
        *,
        prefer_extended: bool = False,
        cached_quotes: dict[str, Quote] | None = None,
    ) -> dict[str, Quote]:
        cached_quotes = cached_quotes if cached_quotes is not None else self._read_quote_cache()
        try:
            payload = self._http_json(
                f"{TRADIER_BASE_URL}/quotes",
                headers=self._headers,
                params={"symbols": ",".join(tickers), "greeks": "false"},
            )
        except MarketDataError:
            if not all(ticker in cached_quotes for ticker in tickers):
                raise
            LOGGER.warning("Tradier quote request failed; using conserved samples")
            payload = {}
        raw_quotes = ((payload.get("quotes") or {}).get("quote")) or []
        if isinstance(raw_quotes, dict):
            raw_quotes = [raw_quotes]

        fetched_at = self._now()
        quotes: dict[str, Quote] = {}
        for raw in raw_quotes:
            ticker = str(raw.get("symbol") or "").upper()
            if ticker not in tickers:
                continue
            price = None
            observed_at = fetched_at
            source = "tradier"
            if prefer_extended:
                try:
                    bid = float(raw.get("bid"))
                    ask = float(raw.get("ask"))
                except (TypeError, ValueError):
                    bid = ask = 0.0
                if bid > 0 and ask >= bid:
                    midpoint = (bid + ask) / 2.0
                    bid_at = _quote_timestamp(raw.get("bid_date"))
                    ask_at = _quote_timestamp(raw.get("ask_date"))
                    timestamps = (bid_at, ask_at)
                    is_recent = all(
                        timestamp is not None
                        and timedelta(0) <= fetched_at - timestamp <= MAX_EXTENDED_QUOTE_AGE
                        for timestamp in timestamps
                    )
                    spread_ratio = (ask - bid) / midpoint
                    if is_recent and spread_ratio <= MAX_EXTENDED_SPREAD_RATIO:
                        price = midpoint
                        observed_at = max(
                            timestamp for timestamp in timestamps if timestamp is not None
                        )
                        source = "tradier_extended_mid"
            if price is None:
                price = raw.get("last")
                trade_at = _quote_timestamp(raw.get("trade_date"))
                if trade_at is None and prefer_extended and ticker in cached_quotes:
                    price = None
                observed_at = trade_at or fetched_at
            try:
                numeric_price = float(price)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric_price) and numeric_price > 0:
                candidate = Quote(ticker, numeric_price, observed_at, source)
                previous = cached_quotes.get(ticker)
                if previous is None or candidate.observed_at >= previous.observed_at:
                    quotes[ticker] = candidate
        for ticker in tickers:
            if ticker not in quotes and ticker in cached_quotes:
                quotes[ticker] = replace(cached_quotes[ticker], cached=True)
        return quotes

    def _quote_cache_path(self) -> Path:
        return self._cache_dir / QUOTE_CACHE_NAME

    def _read_quote_cache(self) -> dict[str, Quote]:
        try:
            payload = json.loads(self._quote_cache_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            return {}
        result: dict[str, Quote] = {}
        for ticker, item in (payload.get("quotes") or {}).items():
            if not isinstance(ticker, str) or not isinstance(item, dict):
                continue
            try:
                price = float(item["price"])
                observed_at = datetime.fromisoformat(item["observed_at"])
                source = str(item["source"])
                stored_change = item.get("day_change")
                change = float(stored_change) if stored_change is not None else None
            except (KeyError, TypeError, ValueError):
                continue
            if (
                not math.isfinite(price)
                or price <= 0
                or observed_at.tzinfo is None
                or not source
                or (change is not None and not math.isfinite(change))
            ):
                continue
            result[ticker] = Quote(ticker, price, observed_at, source, change)
        return result

    def _write_quote_cache(self, quotes: dict[str, Quote]) -> None:
        path = self._quote_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "quotes": {
                ticker: {
                    "price": quote.price,
                    "observed_at": quote.observed_at.isoformat(),
                    "source": quote.source,
                    "day_change": quote.day_change,
                }
                for ticker, quote in sorted(quotes.items())
            },
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)

    def _fetch_history(self, ticker: str, market_date: date) -> tuple[DailyBar, ...]:
        cached = self._read_history_cache(ticker, market_date)
        if cached:
            return cached

        payload = self._http_json(
            f"{TRADIER_BASE_URL}/history",
            headers=self._headers,
            params={
                "symbol": ticker,
                "interval": "daily",
                "start": (market_date - timedelta(days=1280)).isoformat(),
                "end": market_date.isoformat(),
            },
        )
        raw_days = ((payload.get("history") or {}).get("day")) or []
        if isinstance(raw_days, dict):
            raw_days = [raw_days]

        bars = []
        for raw in raw_days:
            try:
                bars.append(
                    DailyBar(
                        session_date=date.fromisoformat(str(raw["date"])[:10]),
                        high=float(raw["high"]),
                        low=float(raw["low"]),
                        close=float(raw["close"]),
                        volume=float(raw["volume"]) if raw.get("volume") is not None else None,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        bars.sort(key=lambda item: item.session_date)
        if len(bars) < 21:
            raise MarketDataError(f"{ticker}: only {len(bars)} valid daily bars")

        result = tuple(bars)
        self._write_history_cache(ticker, market_date, result)
        return result

    def _cache_path(self, ticker: str) -> Path:
        return self._cache_dir / f"{ticker}.json"

    def _read_history_cache(
        self, ticker: str, market_date: date
    ) -> tuple[DailyBar, ...] | None:
        path = self._cache_path(ticker)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("cache_date") != market_date.isoformat():
                return None
            return tuple(
                DailyBar(
                    session_date=date.fromisoformat(item["date"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]) if item.get("volume") is not None else None,
                )
                for item in payload["bars"]
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_history_cache(
        self, ticker: str, market_date: date, bars: tuple[DailyBar, ...]
    ) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_date": market_date.isoformat(),
            "written_at": int(time.time()),
            "bars": [
                {
                    "date": bar.session_date.isoformat(),
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in bars
            ],
        }
        self._cache_path(ticker).write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )


def tradier_token_from_environment() -> str:
    token = os.environ.get("TRADIER_TOKEN", "").strip()
    if not token:
        raise MarketDataError(
            "TRADIER_TOKEN is not configured; no Yahoo-only fallback is used"
        )
    return token


def _quote_timestamp(value: object) -> datetime | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return datetime.fromtimestamp(numeric / 1000.0, tz=timezone.utc)
