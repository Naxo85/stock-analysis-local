import os
import math
import logging
import requests
import functions_framework
from flask import jsonify

logging.basicConfig(level=logging.INFO)

RAW_BASE_URL = os.environ.get(
    "RAW_BASE_URL",
    "https://support-resistances-raw-714254943648.europe-southwest1.run.app"
)

REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "45"))


@functions_framework.http
def support_resistances_slim(request):
    try:
        symbol = _get_symbol(request)
        if not symbol:
            return jsonify(error="Missing 'symbol'"), 400

        raw = _fetch_raw(symbol)
        slim = _build_slim(raw)

        return jsonify(slim), 200

    except requests.HTTPError as e:
        body = getattr(e.response, "text", None)
        logging.exception("raw_endpoint_http_error")
        return jsonify(
            error="raw_endpoint_http_error",
            details=str(e),
            body=body
        ), 502

    except Exception as e:
        logging.exception("internal_error")
        return jsonify(error="internal_error", details=str(e)), 500


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


def _fetch_raw(symbol: str) -> dict:
    url = RAW_BASE_URL.rstrip("/")
    r = requests.get(url, params={"symbol": symbol}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _build_slim(raw: dict) -> dict:
    symbol = raw.get("symbol")
    price = _num(raw.get("latest_price"))

    technicals = raw.get("technicals") or {}
    sma = technicals.get("sma") or {}
    trend = technicals.get("trend") or {}
    price_vs_sma = trend.get("price_vs_sma") or {}
    volume = technicals.get("volume") or {}

    options = raw.get("options") or {}
    dealer_gamma = options.get("dealer_gamma") or {}
    expected_move = options.get("expected_move_1w") or {}
    max_pain = options.get("max_pain") or {}

    options_overview = raw.get("options_overview") or {}
    pcr_block = options_overview.get("put_call_oi_ratio") or {}

    vols = raw.get("vols") or {}
    liquidity = raw.get("liquidity") or {}
    bid_ask = liquidity.get("bid_ask") or {}

    relative_strength = raw.get("relative_strength") or {}
    vs_spy = relative_strength.get("vs_spy") or {}

    forward_returns = raw.get("forward_returns") or {}

    supports = raw.get("supports") or []
    resistances = raw.get("resistances") or []
    call_walls = raw.get("call_walls_top") or []
    put_walls = raw.get("put_walls_top") or []

    slim = {
        "symbol": symbol,
        "as_of": raw.get("as_of"),
        "latest_price": price,
        "mirror_url": raw.get("mirror_url"),

        "market_state": {
            "bid": _num(bid_ask.get("bid")),
            "ask": _num(bid_ask.get("ask")),
            "mid": _num(bid_ask.get("mid")),
            "spread_pct": _num(bid_ask.get("spread_pct")),
            "adv20_usd": _num(liquidity.get("adv20_usd")),
            "relative_strength_vs_spy_20d": _num(vs_spy.get("20d_diff_pct")),
            "relative_strength_vs_spy_60d": _num(vs_spy.get("60d_diff_pct")),
        },

        "technicals": {
            "atr10": _num(technicals.get("atr10")),
            "rsi14": _num(technicals.get("rsi14")),

            "sma20": _num(sma.get("20")),
            "sma50": _num(sma.get("50")),
            "sma200": _num(sma.get("200")),

            "price_vs_sma20_pct": _num(price_vs_sma.get("20")),
            "price_vs_sma50_pct": _num(price_vs_sma.get("50")),
            "price_vs_sma200_pct": _num(price_vs_sma.get("200")),

            "price_20d_change_pct": _num(trend.get("price_20d_change_pct")),
            "price_50d_change_pct": _num(trend.get("price_50d_change_pct")),
            "above_sma200": trend.get("above_sma200"),
            "bollinger_pos_pct": _num(trend.get("bollinger_pos_pct")),

            "bollinger_width_pct": _num((technicals.get("bollinger20_2") or {}).get("width_pct")),

            "donchian20_high": _num((technicals.get("donchian20") or {}).get("high")),
            "donchian20_low": _num((technicals.get("donchian20") or {}).get("low")),

            "keltner_upper": _num((technicals.get("keltner_ema20_atr10") or {}).get("upper")),
            "keltner_center": _num((technicals.get("keltner_ema20_atr10") or {}).get("center")),
            "keltner_lower": _num((technicals.get("keltner_ema20_atr10") or {}).get("lower")),

            "volume_rel_20d": _num((volume.get("last_complete_day") or {}).get("rel_to_20d")),
            "volume_last_complete_day": volume.get("last_complete_day"),
        },

        "options": {
            "gamma_regime": dealer_gamma.get("gamma_regime"),
            "gex_total_usd_millions": _num(dealer_gamma.get("gex_total_usd_millions")),

            "expected_move_1w_abs": _num(expected_move.get("dollars")),
            "expected_move_1w_pct": _normalize_pct(expected_move.get("percent")),
            "expected_move_expiration": expected_move.get("expiration"),
            "expected_move_dte": _num(expected_move.get("dte")),

            "iv_to_rv_ratio": _num(vols.get("iv_to_rv_ratio")),
            "rv20_weekly_pct": _num(vols.get("rv20_weekly_pct")),
            "rv60_weekly_pct": _num(vols.get("rv60_weekly_pct")),
            "em_to_atr_ratio": _num(vols.get("em_to_atr_ratio")),

            "near_term_put_call_oi_ratio": _num(pcr_block.get("ratio")),
            "near_term_total_call_oi": _num(pcr_block.get("total_call_oi")),
            "near_term_total_put_oi": _num(pcr_block.get("total_put_oi")),

            "max_pain": _num(max_pain.get("strike")),
            "max_pain_expiration": max_pain.get("expiration"),

            "expirations": _slim_expirations(options),
        },

        "levels": {
            "supports": _slim_levels(supports, price),
            "resistances": _slim_levels(resistances, price),
            "call_walls_top": _slim_walls(call_walls, price, wall_type="call_wall"),
            "put_walls_top": _slim_walls(put_walls, price, wall_type="put_wall"),
        },

        "price_location": _price_location(
            price=price,
            supports=supports,
            resistances=resistances,
            call_walls=call_walls,
            put_walls=put_walls,
        ),

        "trend_1_2w": _slim_trend(raw.get("trend_1_2w") or {}),

        "forward_returns_summary": {
            "latest": forward_returns.get("latest"),
            "stats": forward_returns.get("stats"),
            "lookback_days": forward_returns.get("lookback_days"),
        },

        "slim_meta": {
            "source": "support_resistances_raw",
            "normalization": {
                "distance_pct": "signed_vs_price; above price positive, below price negative",
                "abs_distance_pct": "absolute distance from latest_price",
                "expected_move_pct": "always percent units, e.g. 10.29 not 0.1029"
            },
            "raw_fields_removed": [
                "forward_returns.series",
                "technicals.volume.series",
                "cluster_neighbors_full",
                "conventions",
                "verbose_meta_methods"
            ]
        }
    }

    return _clean(slim)


def _slim_expirations(options: dict) -> list:
    rows = []

    summary = options.get("summary_by_expiration") or []

    max_pain_by_exp = {
        x.get("date"): x.get("strike")
        for x in (options.get("max_pain_by_expiration") or [])
        if x.get("date")
    }

    for item in summary[:5]:
        em = item.get("expected_move") or {}
        date = item.get("date")

        rows.append({
            "date": date,
            "dte": _num(item.get("dte")),
            "atm_iv": _num(item.get("atm_iv")),
            "expected_move_abs": _num(em.get("dollars")),
            "expected_move_pct": _normalize_pct(em.get("percent")),
            "call_oi": _num(item.get("total_call_oi")),
            "put_oi": _num(item.get("total_put_oi")),
            "put_call_oi_ratio": _num(item.get("put_call_oi_ratio")),
            "max_pain": _num(max_pain_by_exp.get(date)),
        })

    return rows


def _slim_levels(levels: list, price: float | None) -> list:
    out = []

    for item in levels:
        meta = item.get("meta") or {}
        level = _num(item.get("level"))
        signed_distance = _signed_distance_pct(level, price)

        out.append({
            "type": item.get("type"),
            "level": level,
            "distance_pct": signed_distance,
            "abs_distance_pct": _abs(signed_distance),
            "raw_distance_pct": _num(item.get("distance")),
            "strength_score": _num(item.get("strength_score")),
            "prob_touch_1w_pct": _num(item.get("prob_touch_1w_pct")),
            "notes": item.get("notes"),
            "testing_now": meta.get("testing_now"),

            "date": (
                meta.get("level_date")
                or meta.get("gap_date")
                or meta.get("anchor_date")
                or meta.get("last_touch_date")
                or meta.get("expiration")
            ),

            "expiration": meta.get("expiration"),
            "gamma_usd_millions": _num(meta.get("gamma_usd")),
            "gamma_share_pct": _num(meta.get("gamma_usd_share_pct")),
            "oi": _num(meta.get("oi")),
            "oi_share_pct": _num(meta.get("oi_share_pct")),

            "touches": meta.get("touches"),
            "retests_since_origin": meta.get("retests_since_origin"),

            "cluster_low": _cluster_min(meta),
            "cluster_high": _cluster_max(meta),
        })

    return _sort_levels(out, price)


def _slim_walls(walls: list, price: float | None, wall_type: str) -> list:
    out = []

    for item in walls[:5]:
        level = _num(item.get("level"))
        signed_distance = _signed_distance_pct(level, price)

        out.append({
            "type": wall_type,
            "level": level,
            "distance_pct": signed_distance,
            "abs_distance_pct": _abs(signed_distance),

            "expiration": item.get("expiration"),

            "gamma_usd_millions": _num(item.get("gamma_usd_millions")),
            "gamma_share_pct": _num(item.get("gamma_share_pct")),
            "oi": _num(item.get("oi")),
            "oi_share_pct": _num(item.get("oi_share_pct")),

            "cluster_gamma_usd": _num(item.get("cluster_gamma_usd")),
            "cluster_share_pct": _num(item.get("cluster_share_pct")),
            "cluster_low": _list_min(item.get("cluster_neighbors")),
            "cluster_high": _list_max(item.get("cluster_neighbors")),
        })

    return _sort_levels(out, price)


def _slim_trend(trend: dict) -> dict:
    components = trend.get("components") or {}

    return {
        "horizon": trend.get("horizon"),
        "bias": _num(trend.get("bias")),
        "confidence": _num(trend.get("confidence")),
        "entry_threshold_bias": _num((trend.get("config") or {}).get("entry_threshold_bias")),

        "scores": {
            "technicals": _num((components.get("A_technicals") or {}).get("score")),
            "options": _num((components.get("B_options_7_21DTE") or {}).get("score")),
            "vol_risk": _num((components.get("C_vol_risk") or {}).get("score")),
            "volume_tape": _num((components.get("D_volume_tape") or {}).get("score")),
        },

        "features": trend.get("features_flat"),

        "rules_triggered": [
            {
                "code": r.get("code"),
                "side": r.get("side"),
                "weight": r.get("weight"),
            }
            for r in (trend.get("rules_triggered") or [])
        ],
    }


def _price_location(price, supports, resistances, call_walls, put_walls):
    if price is None:
        return {}

    support_candidates = []
    resistance_candidates = []

    for x in supports:
        y = dict(x)
        y["_source_type"] = x.get("type") or "support"
        lvl = _num(y.get("level"))
        if lvl is not None and lvl <= price:
            support_candidates.append(y)

    for x in put_walls:
        y = dict(x)
        y["_source_type"] = "put_wall"
        lvl = _num(y.get("level"))
        if lvl is not None and lvl <= price:
            support_candidates.append(y)

    for x in resistances:
        y = dict(x)
        y["_source_type"] = x.get("type") or "resistance"
        lvl = _num(y.get("level"))
        if lvl is not None and lvl >= price:
            resistance_candidates.append(y)

    for x in call_walls:
        y = dict(x)
        y["_source_type"] = "call_wall"
        lvl = _num(y.get("level"))
        if lvl is not None and lvl >= price:
            resistance_candidates.append(y)

    nearest_support = max(
        support_candidates,
        key=lambda x: _num(x.get("level")) or -math.inf,
        default=None
    )

    nearest_resistance = min(
        resistance_candidates,
        key=lambda x: _num(x.get("level")) or math.inf,
        default=None
    )

    s_level = _num((nearest_support or {}).get("level"))
    r_level = _num((nearest_resistance or {}).get("level"))

    s_dist = _signed_distance_pct(s_level, price)
    r_dist = _signed_distance_pct(r_level, price)

    return {
        "nearest_support": s_level,
        "nearest_support_type": (nearest_support or {}).get("_source_type"),
        "nearest_support_distance_pct": s_dist,
        "nearest_support_abs_distance_pct": _abs(s_dist),

        "nearest_resistance": r_level,
        "nearest_resistance_type": (nearest_resistance or {}).get("_source_type"),
        "nearest_resistance_distance_pct": r_dist,
        "nearest_resistance_abs_distance_pct": _abs(r_dist),

        "room_to_resistance_vs_support_ratio": _rr_ratio(price, s_level, r_level),
    }


def _signed_distance_pct(level, price):
    level = _num(level)
    price = _num(price)

    if level is None or price in (None, 0):
        return None

    return round(100.0 * (level - price) / price, 2)


def _rr_ratio(price, support, resistance):
    price = _num(price)
    support = _num(support)
    resistance = _num(resistance)

    if price is None or support is None or resistance is None:
        return None

    downside = abs(price - support)
    upside = abs(resistance - price)

    if downside <= 0:
        return None

    return round(upside / downside, 2)


def _sort_levels(levels: list, price: float | None):
    if price is None:
        return levels

    return sorted(
        levels,
        key=lambda x: abs((_num(x.get("level")) or price) - price)
    )


def _cluster_min(meta: dict):
    cluster = meta.get("cluster") or {}
    return _list_min(cluster.get("neighbors"))


def _cluster_max(meta: dict):
    cluster = meta.get("cluster") or {}
    return _list_max(cluster.get("neighbors"))


def _list_min(values):
    values = [_num(x) for x in (values or [])]
    values = [x for x in values if x is not None]
    return min(values) if values else None


def _list_max(values):
    values = [_num(x) for x in (values or [])]
    values = [x for x in values if x is not None]
    return max(values) if values else None


def _normalize_pct(x):
    """
    Normaliza porcentajes:
    - 0.1029 -> 10.29
    - 10.29  -> 10.29
    """
    v = _num(x)
    if v is None:
        return None

    if abs(v) <= 1:
        return round(v * 100.0, 4)

    return v


def _num(x):
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 4)
    except Exception:
        return None


def _abs(x):
    x = _num(x)
    return round(abs(x), 4) if x is not None else None


def _clean(obj):
    if isinstance(obj, dict):
        return {
            k: _clean(v)
            for k, v in obj.items()
            if v is not None
        }

    if isinstance(obj, list):
        return [_clean(v) for v in obj]

    return obj