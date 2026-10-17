from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from math import isfinite

from stock_analysis.contracts.market import (
    BenchmarkMetrics,
    DailyBar,
    TickerMarketData,
    TickerMetrics,
)
from stock_analysis.market_worker.session import standard_us_market_holidays


def market_has_no_session(market_date: date) -> bool:
    return (
        market_date.weekday() >= 5
        or market_date in standard_us_market_holidays(market_date.year)
    )


def completed_bars(bars: Iterable[DailyBar], market_date: date) -> list[DailyBar]:
    return [bar for bar in bars if bar.session_date < market_date]


def day_change(price: float, bars: Iterable[DailyBar], market_date: date) -> float | None:
    closed = completed_bars(bars, market_date)
    if price <= 0 or not closed or closed[-1].close <= 0:
        return None
    return price / closed[-1].close - 1.0


def session_return(
    price: float,
    bars: Iterable[DailyBar],
    sessions: int,
    market_date: date,
) -> float | None:
    closed = completed_bars(bars, market_date)
    if price <= 0 or sessions < 1 or len(closed) <= sessions:
        return None
    reference = closed[-1 - sessions].close
    if reference <= 0:
        return None
    return round(price / reference - 1.0, 4)


def robust_atr_percent(bars: Iterable[DailyBar], days: int = 20) -> float | None:
    rows = list(bars)
    if len(rows) < 10 or days < 1:
        return None

    true_ranges: list[float] = []
    for previous, current in zip(rows, rows[1:], strict=False):
        if previous.close <= 0:
            continue
        value = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        value = min(value, abs(previous.close) * 0.25)
        if isfinite(value) and value >= 0:
            true_ranges.append(value)

    window = true_ranges[-min(days, len(true_ranges)) :]
    if not window or rows[-1].close <= 0:
        return None

    ordered = sorted(window)
    trim = int(0.10 * len(ordered))
    trimmed = ordered[trim : len(ordered) - trim] if len(ordered) > 2 * trim else ordered
    if not trimmed:
        return None

    period = min(days, len(trimmed))
    atr = trimmed[0]
    for value in trimmed[1:]:
        atr = (atr * (period - 1) + value) / period
    return round(atr / rows[-1].close, 4)


def relative_drawdown_6m(
    price: float,
    bars: Iterable[DailyBar],
    *,
    lookback: int = 126,
    history_sessions: int = 756,
) -> tuple[float | None, int | None, int]:
    rows = [bar for bar in bars if bar.close > 0]
    if price <= 0 or not rows or lookback < 2:
        return None, None, 0

    current = rows[-lookback:]
    peak = max([price, *(bar.close for bar in current)])
    severity = max(0.0, 1.0 - price / peak)
    drawdown = -severity

    if len(rows) < lookback:
        return drawdown, None, 0

    closes = [bar.close for bar in rows]
    first = max(lookback - 1, len(closes) - history_sessions)
    historical = []
    for index in range(first, len(closes)):
        rolling_peak = max(closes[index - lookback + 1 : index + 1])
        historical.append(max(0.0, 1.0 - closes[index] / rolling_peak))

    if not historical:
        percentile = None
    elif severity <= 0:
        percentile = 0
    else:
        percentile = round(100 * sum(item < severity for item in historical) / len(historical))
    return drawdown, percentile, len(historical)


def distance_from_6m_low(
    price: float, bars: Iterable[DailyBar], *, lookback: int = 126
) -> float | None:
    rows = [bar for bar in bars if bar.close > 0]
    if price <= 0 or not rows or lookback < 1:
        return None
    period_low = min([price, *(bar.close for bar in rows[-lookback:])])
    return max(0.0, price / period_low - 1.0)


def drawdown_from_intraday_high(
    price: float, bars: Iterable[DailyBar], *, lookback: int = 126
) -> float | None:
    rows = [bar for bar in bars if bar.high > 0]
    if price <= 0 or not rows or lookback < 1:
        return None
    peak = max([price, *(bar.high for bar in rows[-lookback:])])
    return min(0.0, price / peak - 1.0)


def benchmark_session_return(
    price: float,
    bars: Iterable[DailyBar],
    sessions: int,
    market_date: date,
) -> float | None:
    rows = list(bars)
    if not rows:
        return None
    represented_date = (
        rows[-1].session_date if market_has_no_session(market_date) else market_date
    )
    prior = [bar for bar in rows if bar.session_date < represented_date]
    prior_sessions = sessions - 1
    if price <= 0 or sessions < 2 or len(prior) < prior_sessions:
        return None
    reference = prior[-prior_sessions].close
    if reference <= 0:
        return None
    return round(price / reference - 1.0, 4)


def percentile_rank_inclusive(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return 1.0
    if value <= ordered[0]:
        return 0.0
    if value >= ordered[-1]:
        return 1.0

    for index, upper in enumerate(ordered[1:], start=1):
        lower = ordered[index - 1]
        if value <= upper:
            if upper == lower:
                return index / (len(ordered) - 1)
            fraction = (value - lower) / (upper - lower)
            return (index - 1 + fraction) / (len(ordered) - 1)
    return 1.0


def global_strength(
    rows: Mapping[str, tuple[float | None, float | None, float | None]],
) -> dict[str, float]:
    ratios: dict[str, tuple[float, float]] = {}
    for ticker, (return_5d, return_20d, volatility) in rows.items():
        if volatility is None or volatility == 0:
            ratios[ticker] = (0.0, 0.0)
            continue
        short = 0.0 if return_5d is None else return_5d / volatility
        medium = 0.0 if return_20d is None else return_20d / volatility
        ratios[ticker] = (short, medium)

    short_values = [item[0] for item in ratios.values()]
    medium_values = [item[1] for item in ratios.values()]
    return {
        ticker: round(
            10
            * (
                0.8 * percentile_rank_inclusive(short_values, short)
                + 0.2 * percentile_rank_inclusive(medium_values, medium)
            ),
            2,
        )
        for ticker, (short, medium) in ratios.items()
    }


def calculate_universe_metrics(
    data: Mapping[str, TickerMarketData],
    *,
    market_date: date,
) -> tuple[TickerMetrics, ...]:
    partial: dict[str, tuple[float | None, float | None, float | None]] = {}
    calculated: dict[str, dict[str, object]] = {}

    for ticker, item in data.items():
        bars = item.daily_bars
        price = item.quote.price
        day_market_date = market_date
        if market_has_no_session(market_date) and bars:
            day_market_date = bars[-1].session_date
        return_5d = session_return(price, bars, 5, market_date)
        return_20d = session_return(price, bars, 20, market_date)
        volatility = robust_atr_percent(bars, 20)
        drawdown, percentile, samples = relative_drawdown_6m(price, bars)
        partial[ticker] = (return_5d, return_20d, volatility)
        calculated[ticker] = {
            "day_change": (
                item.quote.day_change
                if item.quote.cached and item.quote.day_change is not None
                else day_change(price, bars, day_market_date)
            ),
            "return_5d": return_5d,
            "return_20d": return_20d,
            "volatility": volatility,
            "drawdown": drawdown,
            "distance_from_6m_low": distance_from_6m_low(price, bars),
            "percentile": percentile,
            "samples": samples,
        }

    strengths = global_strength(partial)
    result = []
    for ticker, item in data.items():
        values = calculated[ticker]
        result.append(
            TickerMetrics(
                ticker=ticker,
                price=item.quote.price,
                day_change=values["day_change"],
                strength=strengths[ticker],
                return_5d=values["return_5d"],
                return_20d=values["return_20d"],
                volatility=values["volatility"],
                drawdown_6m=values["drawdown"],
                distance_from_6m_low=values["distance_from_6m_low"],
                drawdown_percentile=values["percentile"],
                drawdown_samples=values["samples"],
                observed_at=item.quote.observed_at,
                source=item.quote.source,
                cached=item.quote.cached,
            )
        )
    return tuple(result)


def calculate_benchmark_metrics(
    data: Mapping[str, TickerMarketData],
    *,
    tickers: Iterable[str],
    market_date: date,
    return_sessions: int = 20,
) -> tuple[BenchmarkMetrics, ...]:
    result = []
    for ticker in tickers:
        item = data.get(ticker)
        if item is None:
            continue
        bars = item.daily_bars
        day_market_date = market_date
        if market_has_no_session(market_date) and bars:
            day_market_date = bars[-1].session_date
        drawdown, percentile, samples = relative_drawdown_6m(item.quote.price, bars)
        result.append(
            BenchmarkMetrics(
                ticker=ticker,
                day_change=(
                    item.quote.day_change
                    if item.quote.cached and item.quote.day_change is not None
                    else day_change(item.quote.price, bars, day_market_date)
                ),
                drawdown=drawdown,
                return_20d=benchmark_session_return(
                    item.quote.price, bars, return_sessions, market_date
                ),
                observed_at=item.quote.observed_at,
                source=item.quote.source,
                cached=item.quote.cached,
                drawdown_percentile=percentile,
                drawdown_samples=samples,
            )
        )
    return tuple(result)
