import os
import logging
import requests
import functions_framework
from flask import jsonify, g, has_request_context
from datetime import date, datetime, timedelta, timezone
import xml.etree.ElementTree as ET  # Tradier expirations/chains devuelven XML
import statistics
import json
#from google.cloud import storage
# Gemini (Vertex AI)
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig
import base64
import math
import re
from decimal import Decimal, InvalidOperation

try:
    from .market_sessions import NY, market_session, session_close, latest_completed_session, is_completed_session
    from .price_path import horizontal_path_evidence
except ImportError:
    try:  # Local offline loaders may not set __package__.
        from gcp_functions.support_resistances_raw.market_sessions import NY, market_session, session_close, latest_completed_session, is_completed_session
        from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence
    except ImportError:  # Cloud Functions source directory.
        from market_sessions import NY, market_session, session_close, latest_completed_session, is_completed_session
        from price_path import horizontal_path_evidence

try:
    from .support_origins import (parse_support_origins as _parse_support_origins,
        build_pool as _support_origin_pool, observe_support_origins as _observe_dated_supports,
        source_identity as _support_source_identity, valid_bar as _support_valid_bar,
        continuous_history as _support_continuous_history,
        verified_origin_identity as _support_verified_identity)
except ImportError:
    try:
        from gcp_functions.support_resistances_raw.support_origins import (
            parse_support_origins as _parse_support_origins, build_pool as _support_origin_pool,
            observe_support_origins as _observe_dated_supports, source_identity as _support_source_identity,
            valid_bar as _support_valid_bar, continuous_history as _support_continuous_history,
            verified_origin_identity as _support_verified_identity)
    except ImportError:
        from support_origins import (parse_support_origins as _parse_support_origins,
            build_pool as _support_origin_pool, observe_support_origins as _observe_dated_supports,
            source_identity as _support_source_identity, valid_bar as _support_valid_bar,
            continuous_history as _support_continuous_history,
            verified_origin_identity as _support_verified_identity)

DATA_CONTRACT_REVISION = 41

# ---- Config Vertex AI (explícita; no dependemos de env vars) ----
VERTEX_PROJECT = "recipe-generator-429817"
VERTEX_LOCATION = "us-central1"  # si diera error, prueba 'us-central1' o 'europe-west4'
gemini_client = genai.Client(vertexai=True, project=VERTEX_PROJECT, location=VERTEX_LOCATION)
GEMINI_MODEL = "gemini-2.5-pro"  # estable en Vertex

# -------------------- Config & logging --------------------
tlogger = logging.getLogger()
tlogger.setLevel(logging.DEBUG)

TRADIER_TOKEN = os.environ.get("TRADIER_TOKEN", "")
tlogger.info("TRADIER token configured: %s", bool(TRADIER_TOKEN))
TRADIER_BASE  = "https://api.tradier.com"

HEADERS_JSON = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
}
HEADERS_XML = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/xml",
}
#BUCKET_NAME = "support-resistances-mirror-naxo85"
#_storage = storage.Client()

# ====== CONFIG GITHUB ======
GH_OWNER  = "Naxo85"                  # <- tu usuario/organización
GH_REPO   = "sr-public-mirror"        # <- tu repo público
GH_BRANCH = "main"
GH_TOKEN  = os.environ.get("GH_TOKEN", "")
GH_API    = "https://api.github.com"

# Umbrales (no toco los existentes de otras resistencias)
MIN_GAP_DISTANCE_PCT    = float(os.environ.get("MIN_GAP_DISTANCE_PCT", "0.05"))     # 5% gaps
MIN_RANGE_DISTANCE_PCT  = float(os.environ.get("MIN_RANGE_DISTANCE_PCT", "0.05"))   # 5% rango
MIN_AVWAP_DISTANCE_PCT  = float(os.environ.get("MIN_AVWAP_DISTANCE_PCT", "0.05"))   # 5% avwap

# Filtros AVWAP
AVWAP_GAP_MIN_VOL_FACTOR = float(os.environ.get("AVWAP_GAP_MIN_VOL_FACTOR", "1.5"))
AVWAP_GAP_MIN_SIZE_ATR   = float(os.environ.get("AVWAP_GAP_MIN_SIZE_ATR", "0.5"))

# Call-wall (γ-$)
CALLWALL_TOP_EXPIRATIONS   = int(os.environ.get("CALLWALL_TOP_EXPIRATIONS", "3"))   # nº expiraciones a considerar
CALLWALL_TOL_ATR_MULT      = float(os.environ.get("CALLWALL_TOL_ATR_MULT", "0.2"))  # tolerancia “en test” ≈ 0.2×ATR10
CALLWALL_CLUSTER_ATR       = float(os.environ.get("CALLWALL_CLUSTER_ATR", "1.0"))   # vecindario para cluster γ-$
CALLWALL_EXPORT_TOP_N      = int(os.environ.get("CALLWALL_EXPORT_TOP_N", "5"))      # cuántos call walls listar
CALLWALL_MIN_DISTANCE_PCT  = float(os.environ.get("CALLWALL_MIN_DISTANCE_PCT", "0.05"))  # ≥ +5% para entrar en resistances

# Parámetros técnicos
BB_WINDOW   = int(os.environ.get("BB_WINDOW", "20"))
BB_STDS     = float(os.environ.get("BB_STDS", "2.0"))
KC_MULT_ATR = float(os.environ.get("KC_MULT_ATR", "2.0"))
DONCHIAN_N  = int(os.environ.get("DONCHIAN_N", "20"))

# Expected Move / Max Pain
EM_TARGET_DTE_MIN = int(os.environ.get("EM_TARGET_DTE_MIN", "4"))   # días min para “1W”
EM_TARGET_DTE_MAX = int(os.environ.get("EM_TARGET_DTE_MAX", "9"))   # días max para “1W”

# Put/Call ratio - vistas
PUTCALL_MAX_DTE = int(os.environ.get("PUTCALL_MAX_DTE", "60"))  # para "thru_60d"
PUTCALL_INCLUDE_ALL = os.environ.get("PUTCALL_INCLUDE_ALL", "false").lower() in ("1", "true", "yes", "y")

# Forward returns (lookback para estadísticas/series)
FORWARD_RET_LOOKBACK = int(os.environ.get("FORWARD_RET_LOOKBACK", "252"))

SECTOR_BENCH = None
RS_LOOKBACKS = [20, 60]

# Put-wall (γ-$)
PUTWALL_MIN_DISTANCE_PCT  = float(os.environ.get("PUTWALL_MIN_DISTANCE_PCT", "0.05"))  # ≥ -5% para entrar en supports


# ==========================================================
#                    HANDLER PRINCIPAL
# ==========================================================
@functions_framework.http
def support_resistances_raw(request):
    """
    Devuelve resistencias "serias" en un JSON extensible.
    V1.1: 52-week high + clasificación de test (primer test / re-test #N).
    V1.2: Techo de rango 3–6 meses (≥2 toques, clusterizado).
    V1.3: Gap bajista (borde superior), filtrado por distancia mínima.
    V1.4: AVWAP anclado a evento, filtrado por distancia mínima.
    V1.5: Call-wall (γ-$) multi-expiración — listado top (sin filtro de distancia).
          En 'resistances' solo aparece si está ≥ +5% sobre el spot (configurable).
    V1.6: Technicals (RSI14, SMA20/50/200, Bollinger 20-2σ, Keltner EMA20±2·ATR10, Donchian 20D).
    V1.7: Options extras (Expected Move 1W por straddle ATM; Max Pain en esa expiración).
    """
    try:
        symbol, err = _get_symbol(request)
        if err: return err
        try:
            requested_anchors = _parse_anchor_dates(request.args.get('avwap_anchors', ''))
        except ValueError:
            return jsonify(error='invalid_avwap_anchor_dates'), 400
        try:
            requested_options = _parse_option_origins(request.args.get('option_origins', ''))
        except ValueError:
            return jsonify(error='invalid_option_origins'), 400
        try:
            requested_supports = (_parse_support_origins(request.args.get('support_origins'))
                                  if 'support_origins' in request.args else None)
        except (ValueError, TypeError):
            return jsonify(error='invalid_support_origins'), 400
        if not TRADIER_TOKEN.strip():
            return jsonify(error="Missing TRADIER_TOKEN"), 500

        g.evaluation_archive_enabled = (os.environ.get('EVALUATION_ARCHIVE_ENABLED', '').lower() in ('1', 'true')
                                        and request.args.get('evaluation_archive', '').lower() in ('1', 'true'))
        g.capture_as_of = datetime.now(timezone.utc)
        # 1) Quote: último precio y high del día
        q = _tradier_quote(symbol)
        if not q:
            return jsonify(error="No quote data from Tradier", symbol=symbol), 502
        quote_observation = _quote_observation(q, g.capture_as_of)
        last_price = quote_observation.get("price")
        if quote_observation.get("status") != "available":
            return jsonify(error="invalid_quote_capture", symbol=symbol, quote_observation=quote_observation), 502
        today_high = _to_float(q.get("high"))
        today_low = _to_float(q.get("low"))

        # 2) Histórico diario (~400 días calendario → ~252 barras)
        start = (datetime.utcnow() - timedelta(days=400)).strftime("%Y-%m-%d")
        end   = datetime.utcnow().strftime("%Y-%m-%d")
        days = _tradier_history_daily(symbol, start, end)  # lista ascendente
        history_received_at = (getattr(g, 'history_received_at', {}) or {}).get(symbol)
        primary_history_index = len(getattr(g, 'downloaded_daily_histories', [])) - 1

        if not days or last_price is None:
            return jsonify(error="missing_daily_history", symbol=symbol), 502
        history_capture = _recent_price_history(days, g.capture_as_of)
        if history_capture.get("status") != "available":
            return jsonify(error="incomplete_daily_history", symbol=symbol, price_history=history_capture), 502
        # 3) ATR(10) diario para tolerancias
        atr10 = _atr10_from_daily(days) or 0.0
        
        callwall = None
        resistances = []
        supports = []

        # --------------------------------------------------------------
        # Resistencia #1: Máximo de 52 semanas
        # --------------------------------------------------------------
        level, level_date = _find_52w_high(days, lookback=252)
        if level is not None:
            tol_52w = 0.2 * atr10 if atr10 > 0 else max(0.25, 0.002 * level)
            hits_after = _count_retests(level, level_date, days, tol_52w)
            testing_now = (today_high is not None and abs(today_high - level) <= tol_52w)
            if hits_after == 0:
                note = "Primer test (en curso)" if testing_now else "Primer test (pendiente)"
                strength = 9.5
            else:
                note_idx = hits_after if testing_now else hits_after + 1
                note = (f"Re-test #{hits_after} (en curso)"
                        if testing_now else f"Re-test #{note_idx} (pendiente)")
                strength = 8.5
            distance_pct = 100.0 * (level - last_price) / last_price

            # usa callwall si ya existe; si no, trata como 0
            cw_gamma_m = ((callwall or {}).get("gamma_usd_millions") or 0.0)
            cw_share   = ((callwall or {}).get("gamma_share_pct") or 0.0)
            low_signal = (cw_share < 5.0) or (cw_gamma_m < 1.0)  # <5% de share o < $1M
            if low_signal:
                strength = max(6.0, strength - 0.5)
                note += " — señal débil (γ-$ bajo)"

            resistances.append({
                "type": "52_week_high",
                "level": round(level, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": note,
                "meta": {
                    "level_date": level_date,
                    "atr10": round(atr10, 4) if atr10 else None,
                    "tolerance": round(tol_52w, 4),
                    "retests_since_origin": hits_after,
                    "testing_now": testing_now,
                    "low_signal": low_signal
                }
            })

        # ---------------- Soporte #1: Mínimo de 52 semanas ----------------
        low_52w, low_52w_date = _find_52w_low(days, lookback=252)
        if low_52w is not None:
            tol_52w_low = 0.2 * atr10 if atr10 > 0 else max(0.25, 0.002 * (low_52w or 1))
            hits_after_low = _count_retests_low(low_52w, low_52w_date, days, tol_52w_low)
            testing_now_low = (today_low is not None and abs(today_low - low_52w) <= tol_52w_low)
            if hits_after_low == 0:
                note = "Primer test (en curso)" if testing_now_low else "Primer test (pendiente)"
                strength = 9.5
            else:
                note_idx = hits_after_low if testing_now_low else hits_after_low + 1
                note = (f"Re-test #{hits_after_low} (en curso)"
                        if testing_now_low else f"Re-test #{note_idx} (pendiente)")
                strength = 8.5
            distance_pct = 100.0 * (last_price - low_52w) / last_price
            supports.append({
                "type": "52_week_low",
                "level": round(low_52w, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": note,
                "meta": {
                    "level_date": low_52w_date,
                    "atr10": round(atr10, 4) if atr10 else None,
                    "tolerance": round(tol_52w_low, 4),
                    "retests_since_origin": hits_after_low,
                    "testing_now": testing_now_low
                }
            })

        # --------------------------------------------------------------
        # Resistencia #2: Techo de rango 3–6 meses (≥2 toques)
        # --------------------------------------------------------------
        lookback_max = 126  # ~6 meses hábiles
        win_days = days[-lookback_max:] if len(days) >= lookback_max else days[:]
        tol_range = 0.2 * atr10 if atr10 > 0 else max(0.25, 0.002 * (level or last_price or 1))
        swings = _find_swing_highs(win_days, k=2)
        clusters = _cluster_swing_highs(swings, tol=tol_range)
        median_vol_range = _median([_to_float(d["volume"]) or 0 for d in win_days]) or 0
        range_top = _select_range_top_cluster(
            clusters=clusters,
            last_price=last_price,
            today_high=today_high,
            tol=tol_range,
            median_vol=median_vol_range,
            min_distance_pct=MIN_RANGE_DISTANCE_PCT
        )
        if range_top:
            lvl = range_top["level"]
            distance_pct = 100.0 * (lvl - last_price) / last_price
            touches = range_top["touches"]
            if touches >= 4:
                strength = 9.0
            elif touches == 3:
                strength = 8.5
            else:
                strength = 8.0
            if (range_top["vol_factor"] or 0) >= 1.2:
                strength += 0.2
            if range_top["testing_now"]:
                strength += 0.2
            strength = max(6.0, min(strength, 9.5))
            notes = (
                f"Techo de rango 3–6m con {touches} toques; "
                f"último {range_top['last_date']}" + (" (en curso)" if range_top["testing_now"] else " (pendiente)")
            )
            resistances.append({
                "type": "range_top_3_6m",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "first_touch_date": range_top["first_date"],
                    "last_touch_date":  range_top["last_date"],
                    "touches":          touches,
                    "vol_factor_vs_median": round(range_top["vol_factor"], 2) if range_top["vol_factor"] is not None else None,
                    "tolerance": round(tol_range, 4),
                    "testing_now": range_top["testing_now"]
                }
            })

        # ---------------- Soporte #2: Suelo de rango 3–6 meses ----------------
        swings_low = _find_swing_lows(win_days, k=2)
        clusters_low = _cluster_swing_lows(swings_low, tol=tol_range)
        range_bottom = _select_range_bottom_cluster(
            clusters=clusters_low,
            last_price=last_price,
            today_low=today_low,
            tol=tol_range,
            median_vol=median_vol_range,
            min_distance_pct=MIN_RANGE_DISTANCE_PCT
        )
        if range_bottom:
            lvl = range_bottom["level"]
            distance_pct = 100.0 * (last_price - lvl) / last_price
            touches = range_bottom["touches"]
            if touches >= 4:
                strength = 9.0
            elif touches == 3:
                strength = 8.5
            else:
                strength = 8.0
            if (range_bottom["vol_factor"] or 0) >= 1.2:
                strength += 0.2
            if range_bottom["testing_now"]:
                strength += 0.2
            strength = max(6.0, min(strength, 9.5))
            notes = (
                f"Suelo de rango 3–6m con {touches} toques; "
                f"último {range_bottom['last_date']}" + (" (en curso)" if range_bottom["testing_now"] else " (pendiente)")
            )
            supports.append({
                "type": "range_bottom_3_6m",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "first_touch_date": range_bottom["first_date"],
                    "last_touch_date":  range_bottom["last_date"],
                    "touches":          touches,
                    "vol_factor_vs_median": round(range_bottom["vol_factor"], 2) if range_bottom["vol_factor"] is not None else None,
                    "tolerance": round(tol_range, 4),
                    "testing_now": range_bottom["testing_now"]
                }
            })


        # --------------------------------------------------------------
        # Resistencia #3: Gap bajista (borde superior)
        # --------------------------------------------------------------
        lookback_gap = 252
        gap_days = days[-lookback_gap:] if len(days) >= lookback_gap else days[:]
        tol_gap = 0.2 * atr10 if atr10 > 0 else max(0.25, 0.002 * (last_price or 1))
        gaps = _find_bearish_gaps(gap_days)
        gap_pick = _select_bearish_gap_resistance(
            gaps=gaps,
            full_days=gap_days,
            last_price=last_price,
            today_high=today_high,
            tol=tol_gap,
            min_distance_pct=MIN_GAP_DISTANCE_PCT
        )
        if gap_pick:
            lvl = gap_pick["upper"]
            distance_pct = 100.0 * (lvl - last_price) / last_price
            size_vs_atr = (gap_pick["size"] / max(atr10, 1e-6)) if atr10 > 0 else 0.0
            if size_vs_atr >= 2.0:
                strength = 9.0
            elif size_vs_atr >= 1.0:
                strength = 8.5
            elif size_vs_atr >= 0.5:
                strength = 8.0
            else:
                strength = 7.5
            if (gap_pick["vol_factor"] or 0) >= 1.3:
                strength += 0.2
            if gap_pick["testing_now"]:
                strength += 0.2
            if gap_pick["filled"]:
                strength -= 0.5
            strength = max(6.0, min(strength, 9.5))
            notes = (
                f"Gap bajista del {gap_pick['date']} (tam. {round(gap_pick['size_pct'], 2)}%); "
                + ("relleno" if gap_pick["filled"] else "abierto")
                + (" (en curso)" if gap_pick["testing_now"] else " (pendiente)")
            )
            resistances.append({
                "type": "gap_down_upper",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "gap_date": gap_pick["date"],
                    "gap_upper": round(gap_pick["upper"], 4),
                    "gap_lower": round(gap_pick["lower"], 4),
                    "gap_size":  round(gap_pick["size"], 4),
                    "gap_size_pct_vs_price": round(gap_pick["size_pct"], 2),
                    "vol_factor_vs_median": round(gap_pick["vol_factor"], 2) if gap_pick["vol_factor"] is not None else None,
                    "touches_since_gap": gap_pick["touches_since"],
                    "last_touch_date": gap_pick["last_touch_date"],
                    "tolerance": round(tol_gap, 4),
                    "testing_now": gap_pick["testing_now"],
                    "filled": gap_pick["filled"]
                }
            })
        
        # ---------------- Soporte #3: Gap alcista (borde inferior) ----------------
        gaps_up = _find_bullish_gaps(gap_days)
        gap_supp = _select_bullish_gap_support(
            gaps=gaps_up,
            full_days=gap_days,
            last_price=last_price,
            today_low=today_low,
            tol=tol_gap,
            min_distance_pct=MIN_GAP_DISTANCE_PCT
        )
        if gap_supp:
            lvl = gap_supp["level"]
            distance_pct = 100.0 * (last_price - lvl) / last_price
            size_vs_atr = (gap_supp["size"] / max(atr10, 1e-6)) if atr10 > 0 else 0.0
            if size_vs_atr >= 2.0:
                strength = 9.0
            elif size_vs_atr >= 1.0:
                strength = 8.5
            elif size_vs_atr >= 0.5:
                strength = 8.0
            else:
                strength = 7.5
            if (gap_supp["vol_factor"] or 0) >= 1.3:
                strength += 0.2
            if gap_supp["testing_now"]:
                strength += 0.2
            if gap_supp["filled"]:
                strength -= 0.5
            strength = max(6.0, min(strength, 9.5))
            notes = (
                f"Gap alcista del {gap_supp['date']} (tam. {round(gap_supp['size_pct'], 2)}%); "
                + ("relleno" if gap_supp["filled"] else "abierto")
                + (" (en curso)" if gap_supp["testing_now"] else " (pendiente)")
            )
            supports.append({
                "type": "gap_up_lower",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "gap_date": gap_supp["date"],
                    "gap_upper": round(gap_supp["upper"], 4),
                    "gap_lower": round(gap_supp["lower"], 4),
                    "gap_size":  round(gap_supp["size"], 4),
                    "gap_size_pct_vs_price": round(gap_supp["size_pct"], 2),
                    "vol_factor_vs_median": round(gap_supp["vol_factor"], 2) if gap_supp["vol_factor"] is not None else None,
                    "touches_since_gap": gap_supp["touches_since"],
                    "last_touch_date": gap_supp["last_touch_date"],
                    "tolerance": round(tol_gap, 4),
                    "testing_now": gap_supp["testing_now"],
                    "filled": gap_supp["filled"]
                }
            })

        # --------------------------------------------------------------
        # Resistencia #4: AVWAP anclado a evento
        # --------------------------------------------------------------
        tol_avwap = 0.2 * atr10 if atr10 > 0 else max(0.25, 0.002 * (last_price or 1))
        avwap_pick = _select_avwap_event(
            days=days,
            gap_days=gap_days,
            gaps=gaps,
            atr10=atr10,
            last_price=last_price,
            tol=tol_avwap,
            level_52w_date=level_date,
            range_clusters=clusters,
            median_vol_range=median_vol_range,
            min_distance_pct=MIN_AVWAP_DISTANCE_PCT,
            gap_min_vol_factor=AVWAP_GAP_MIN_VOL_FACTOR,
            gap_min_size_atr=AVWAP_GAP_MIN_SIZE_ATR,
            today_high=today_high
        )
        if avwap_pick:
            lvl = avwap_pick["level"]
            distance_pct = 100.0 * (lvl - last_price) / last_price
            anchor_type = avwap_pick["anchor_type"]
            strength = 8.0
            if anchor_type == "gap":
                strength = 9.0
                if (avwap_pick.get("gap_size_atr") or 0) >= 1.0:
                    strength += 0.2
                if (avwap_pick.get("vol_factor") or 0) >= 2.0:
                    strength += 0.2
            elif anchor_type == "52w_high":
                strength = 8.5
                if (avwap_pick.get("vol_factor") or 0) >= 1.5:
                    strength += 0.2
            elif anchor_type == "ytd_open":
                strength = 8.0
                if (avwap_pick.get("vol_factor") or 0) >= 1.5:
                    strength += 0.2
            elif anchor_type == "range_top":
                strength = 8.0
                if (avwap_pick.get("touches") or 0) >= 3:
                    strength += 0.2
            if avwap_pick["testing_now"]:
                strength += 0.2
            strength = max(6.0, min(strength, 9.5))
            notes = f"AVWAP anclado a {avwap_pick['anchor_label']} " \
                    + ("(en curso)" if avwap_pick["testing_now"] else "(pendiente)")
            resistances.append({
                "type": "avwap_event",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "anchor_type": anchor_type,
                    "anchor_date": avwap_pick["anchor_date"],
                    "vol_factor_vs_median": round(avwap_pick["vol_factor"], 2) if avwap_pick["vol_factor"] is not None else None,
                    "gap_size_atr": round(avwap_pick["gap_size_atr"], 2) if avwap_pick.get("gap_size_atr") is not None else None,
                    "touches": avwap_pick.get("touches"),
                    "tolerance": round(tol_avwap, 4),
                    "testing_now": avwap_pick["testing_now"],
                    "min_distance_pct": MIN_AVWAP_DISTANCE_PCT,
                    "method": "daily_typical_price_vwap"
                }
            })

        # ---------------- Soporte #4: AVWAP anclado a evento (lado soporte) ----------------
        tol_avwap_low = tol_avwap  # misma tolerancia
        avwap_supp = _select_avwap_event_support(
            days=days,
            gap_days=gap_days,
            gaps_up=gaps_up,
            atr10=atr10,
            last_price=last_price,
            tol=tol_avwap_low,
            level_52w_low_date=low_52w_date,
            range_clusters_bottom=clusters_low,
            median_vol_range=median_vol_range,
            min_distance_pct=MIN_AVWAP_DISTANCE_PCT,
            gap_min_vol_factor=AVWAP_GAP_MIN_VOL_FACTOR,
            gap_min_size_atr=AVWAP_GAP_MIN_SIZE_ATR,
            today_low=today_low 
        )
        if avwap_supp:
            lvl = avwap_supp["level"]
            distance_pct = 100.0 * (last_price - lvl) / last_price
            anchor_type = avwap_supp["anchor_type"]
            strength = 8.0
            if anchor_type == "gap_up":
                strength = 9.0
                if (avwap_supp.get("gap_size_atr") or 0) >= 1.0:
                    strength += 0.2
                if (avwap_supp.get("vol_factor") or 0) >= 2.0:
                    strength += 0.2
            elif anchor_type == "52w_low":
                strength = 8.5
                if (avwap_supp.get("vol_factor") or 0) >= 1.5:
                    strength += 0.2
            elif anchor_type == "ytd_open":
                strength = 8.0
                if (avwap_supp.get("vol_factor") or 0) >= 1.5:
                    strength += 0.2
            elif anchor_type == "range_bottom":
                strength = 8.0
                if (avwap_supp.get("touches") or 0) >= 3:
                    strength += 0.2
            if avwap_supp["testing_now"]:
                strength += 0.2
            strength = max(6.0, min(strength, 9.5))
            notes = f"AVWAP anclado a {avwap_supp['anchor_label']} " \
                    + ("(en curso)" if avwap_supp["testing_now"] else "(pendiente)")
            supports.append({
                "type": "avwap_event_support",
                "level": round(lvl, 4),
                "distance": round(distance_pct, 2),
                "strength_score": round(strength, 1),
                "notes": notes,
                "meta": {
                    "anchor_type": anchor_type,
                    "anchor_date": avwap_supp["anchor_date"],
                    "vol_factor_vs_median": round(avwap_supp["vol_factor"], 2) if avwap_supp["vol_factor"] is not None else None,
                    "gap_size_atr": round(avwap_supp.get("gap_size_atr"), 2) if avwap_supp.get("gap_size_atr") is not None else None,
                    "touches": avwap_supp.get("touches"),
                    "tolerance": round(tol_avwap_low, 4),
                    "testing_now": avwap_supp["testing_now"],
                    "min_distance_pct": MIN_AVWAP_DISTANCE_PCT,
                    "method": "daily_typical_price_vwap"
                }
            })


        # --------------------------------------------------------------
        # Resistencia #5: Call-wall (γ-$) — en 'resistances' solo si ≥ +5%
        # --------------------------------------------------------------
        try:
            callwall = _compute_callwall_gamma(
                symbol=symbol,
                last_price=last_price,
                today_high=today_high,
                atr10=atr10,
                top_expirations=CALLWALL_TOP_EXPIRATIONS,
                tol_mult=CALLWALL_TOL_ATR_MULT,
                cluster_atr=CALLWALL_CLUSTER_ATR
            )
        except Exception as e:
            tlogger.error(f"[callwall] error: {e}", exc_info=True)
            return jsonify(error='options_capture_failed', component='callwall',
                           symbol=symbol, error_type=type(e).__name__), 502

        if callwall:
            lvl = callwall["level"]
            distance_pct = 100.0 * (lvl - last_price) / last_price  # puede ser negativa o muy grande
            thr_pct = 100.0 * CALLWALL_MIN_DISTANCE_PCT

            if distance_pct >= thr_pct:
                strength = _score_callwall_strength(callwall, last_price, atr10)

                exp_lbl = callwall["expiration"] or "mixta"
                dom_pct = callwall.get("gamma_share_pct")
                notes = f"Call wall (γ-$) exp {exp_lbl}; " \
                        + (f"dominante ({round(dom_pct,1)}% del lado call) — " if dom_pct is not None else "") \
                        + ("en curso" if callwall["testing_now"] else "pendiente")

                meta_cluster = {
                    "neighbors": callwall.get("cluster_neighbors"),
                    "cluster_gamma_usd": round(callwall["cluster_gamma_usd"], 3) if callwall.get("cluster_gamma_usd") is not None else None,
                    "cluster_share_pct": round(callwall["cluster_share_pct"], 1) if callwall.get("cluster_share_pct") is not None else None
                }

                resistances.append({
                    "type": "call_wall_gamma",
                    "level": round(lvl, 4),
                    "distance": round(distance_pct, 2),
                    "strength_score": round(strength, 1),
                    "notes": notes,
                    "meta": {
                        "expiration": callwall["expiration"],
                        "option_details": callwall["option_details"],
                        "gamma_usd": round(callwall["gamma_usd_millions"], 3) if callwall.get("gamma_usd_millions") is not None else None,
                        "gamma_usd_units": "millions",
                        "gamma_usd_total_calls": round(callwall["total_call_gamma_usd_millions"], 3) if callwall.get("total_call_gamma_usd_millions") is not None else None,
                        "gamma_usd_share_pct": round(callwall["gamma_share_pct"], 1) if callwall.get("gamma_share_pct") is not None else None,
                        "oi": callwall.get("oi"),
                        "oi_share_pct": round(callwall["oi_share_pct"], 1) if callwall.get("oi_share_pct") is not None else None,
                        "atr10": round(atr10, 4) if atr10 else None,
                        "tolerance": round(callwall["tolerance"], 4),
                        "window": f"calls agregadas en top {CALLWALL_TOP_EXPIRATIONS} expiraciones; sin filtro de distancia",
                        "testing_now": callwall["testing_now"],
                        "cluster": meta_cluster,
                        "method": "sum(|γ|·OI·spot²) por strike multi-exp (sin límites de distancia)"
                    }
                })
            else:
                tlogger.info(f"[callwall] omitido en 'resistances' por distancia {round(distance_pct,2)}% < {round(thr_pct,2)}% (se mostrará en 'call_walls_top')")

        # --------------------------------------------------------------
        # Lista de call walls TOP (referencias adicionales; sin filtro de distancia)
        # --------------------------------------------------------------
        try:
            callwalls_top = _compute_top_callwalls_gamma(
                symbol=symbol,
                last_price=last_price,
                atr10=atr10,
                top_expirations=CALLWALL_TOP_EXPIRATIONS,
                cluster_atr=CALLWALL_CLUSTER_ATR,
                top_n=CALLWALL_EXPORT_TOP_N
            )
        except Exception as e:
            tlogger.error(f"[call_walls_top] error: {e}", exc_info=True)
            return jsonify(error='options_capture_failed', component='call_walls_top',
                           symbol=symbol, error_type=type(e).__name__), 502

        # Soporte #5: Put-wall (γ-$) — en 'supports' solo si ≤ -5%
        try:
            putwall = _compute_putwall_gamma(
                symbol=symbol,
                last_price=last_price,
                today_low=today_low,
                atr10=atr10,
                top_expirations=CALLWALL_TOP_EXPIRATIONS,
                tol_mult=CALLWALL_TOL_ATR_MULT,
                cluster_atr=CALLWALL_CLUSTER_ATR
            )
        except Exception as e:
            tlogger.error(f"[putwall] error: {e}", exc_info=True)
            return jsonify(error='options_capture_failed', component='putwall',
                           symbol=symbol, error_type=type(e).__name__), 502

        if putwall:
            lvl = putwall["level"]
            distance_pct = 100.0 * (last_price - lvl) / last_price  # distancia hacia ABAJO (positiva)
            thr_pct = 100.0 * PUTWALL_MIN_DISTANCE_PCT
            if distance_pct >= thr_pct:
                strength = _score_putwall_strength(putwall, last_price, atr10)
                exp_lbl = putwall["expiration"] or "mixta"
                dom_pct = putwall.get("gamma_share_pct")
                notes = f"Put wall (γ-$) exp {exp_lbl}; " \
                        + (f"dominante ({round(dom_pct,1)}% del lado put) — " if dom_pct is not None else "") \
                        + ("en curso" if putwall["testing_now"] else "pendiente")
                meta_cluster = {
                    "neighbors": putwall.get("cluster_neighbors"),
                    "cluster_gamma_usd": round(putwall["cluster_gamma_usd"], 3) if putwall.get("cluster_gamma_usd") is not None else None,
                    "cluster_share_pct": round(putwall["cluster_share_pct"], 1) if putwall.get("cluster_share_pct") is not None else None
                }
                supports.append({
                    "type": "put_wall_gamma",
                    "level": round(lvl, 4),
                    "distance": round(distance_pct, 2),
                    "unit": "pct",
                    "strength_score": round(strength, 1),
                    "notes": notes,
                    "meta": {
                        "expiration": putwall["expiration"],
                        "option_details": putwall["option_details"],
                        "gamma_usd": round(putwall["gamma_usd_millions"], 3) if putwall.get("gamma_usd_millions") is not None else None,
                        "gamma_usd_units": "millions",
                        "gamma_usd_total_puts": round(putwall["total_put_gamma_usd_millions"], 3) if putwall.get("total_put_gamma_usd_millions") is not None else None,
                        "gamma_usd_share_pct": round(putwall["gamma_share_pct"], 1) if putwall.get("gamma_share_pct") is not None else None,
                        "oi": putwall.get("oi"),
                        "oi_share_pct": round(putwall.get("oi_share_pct"), 1) if putwall.get("oi_share_pct") is not None else None,
                        "atr10": round(atr10, 4) if atr10 else None,
                        "tolerance": round(putwall["tolerance"], 4),
                        "window": f"puts agregadas en top {CALLWALL_TOP_EXPIRATIONS} expiraciones; sin filtro de distancia",
                        "testing_now": putwall["testing_now"],
                        "cluster": meta_cluster,
                        "method": "sum(|γ|·OI·spot²) por strike multi-exp (sin límites de distancia)"
                    }
                })
            else:
                tlogger.info(f"[putwall] omitido en 'supports' por distancia {round(distance_pct,2)}% < {round(thr_pct,2)}% (se mostrará en 'put_walls_top')")

        # Lista de put walls TOP (referencias adicionales; sin filtro de distancia)
        try:
            putwalls_top = _compute_top_putwalls_gamma(
                symbol=symbol,
                last_price=last_price,
                atr10=atr10,
                top_expirations=CALLWALL_TOP_EXPIRATIONS,
                cluster_atr=CALLWALL_CLUSTER_ATR,
                top_n=CALLWALL_EXPORT_TOP_N
            )
        except Exception as e:
            tlogger.error(f"[put_walls_top] error: {e}", exc_info=True)
            return jsonify(error='options_capture_failed', component='put_walls_top',
                           symbol=symbol, error_type=type(e).__name__), 502


        # --------------------------------------------------------------
        #           TECHNICALS (RSI, MAs, Bollinger, Keltner, Donchian)
        # --------------------------------------------------------------
        closes = [_to_float(d.get("close")) for d in days]
        highs  = [_to_float(d.get("high"))  for d in days]
        lows   = [_to_float(d.get("low"))   for d in days]
        typical = _typical_prices(days)  # para EMA20 de Keltner
        volume20 = _volume_20d_package(days, quote=q)

        rsi14 = _rsi14_from_closes(closes)
        sma20 = _sma(closes, 20)
        sma50 = _sma(closes, 50)
        sma200= _sma(closes, 200)

        bb = _bollinger(closes, window=BB_WINDOW, num_std=BB_STDS)
        kc = _keltner(typical, atr10=atr10, mult=KC_MULT_ATR)
        dch = _donchian(highs, lows, n=DONCHIAN_N)

        technicals = {
            "rsi14": round(rsi14, 2) if rsi14 is not None else None,
            "sma": {
                "20": round(sma20, 4) if sma20 is not None else None,
                "50": round(sma50, 4) if sma50 is not None else None,
                "200": round(sma200, 4) if sma200 is not None else None
            },
            "bollinger20_2": {
                "upper": round(bb["upper"], 4) if bb and bb.get("upper") is not None else None,
                "middle": round(bb["middle"], 4) if bb and bb.get("middle") is not None else None,
                "lower": round(bb["lower"], 4) if bb and bb.get("lower") is not None else None,
                "width_pct": round(bb["width_pct"], 2) if bb and bb.get("width_pct") is not None else None,
                "method": "SMA20 ± 2·σ(cierre)"
            },
            "keltner_ema20_atr10": {
                "upper": round(kc["upper"], 4) if kc and kc.get("upper") is not None else None,
                "center": round(kc["center"], 4) if kc and kc.get("center") is not None else None,
                "lower": round(kc["lower"], 4) if kc and kc.get("lower") is not None else None,
                "mult": KC_MULT_ATR,
                "method": "EMA20(typical) ± mult·ATR10"
            },
            "donchian20": {
                "high": round(dch["high"], 4) if dch and dch.get("high") is not None else None,
                "low":  round(dch["low"], 4) if dch and dch.get("low") is not None else None
            },
            "atr10": round(atr10, 4) if atr10 is not None else None,
            "volume": volume20
        }

        # ---- Tendencia/estructura ligera ----
        trend = _trend_structure_package(closes=closes, sma20=sma20, sma50=sma50, sma200=sma200, bb=bb)
        technicals["trend"] = trend

        # --------------------------------------------------------------
        #           OPTIONS EXTRAS (Expected Move 1W, Max Pain)
        # --------------------------------------------------------------
        options = None
        em_abs_1w = None  # <- usaremos estos luego en vols
        em_pct_1w = None
        try:
            exp_1w = _pick_expiration_around_1w(symbol, EM_TARGET_DTE_MIN, EM_TARGET_DTE_MAX)
            em_raw = _expected_move_1w_via_straddle(symbol, exp_1w, last_price)
            mp = _max_pain_for_expiration(symbol, exp_1w) if exp_1w else None

            # Observed straddle over its actual expiry; no synthetic weekly scaling.
            dte = _days_to(exp_1w) if exp_1w else None
            options = {
                "status": "ok" if exp_1w else "no_future_expirations",
                "atm_straddle": dict(em_raw, expiration=exp_1w, dte_calendar=dte,
                                     horizon="actual_expiration", probability_interpretation="none") if em_raw else None,
                "capture": {"status": "complete", "scope": "sampled_expirations",
                            "sampled_expirations": (_tradier_option_expirations(symbol) or [])[:CALLWALL_TOP_EXPIRATIONS]},
                "max_pain": {
                    "expiration": exp_1w,
                    "strike": mp
                } if (exp_1w and mp is not None) else None,
                "dealer_gamma": _dealer_gamma_summary(symbol, last_price, CALLWALL_TOP_EXPIRATIONS),
                "summary_by_expiration": _summary_by_expiration(symbol, last_price, max_items=CALLWALL_TOP_EXPIRATIONS),
                "max_pain_by_expiration": _max_pain_by_expiration(symbol, max_items=CALLWALL_TOP_EXPIRATIONS)
            }
        except Exception as e:
            tlogger.error(f"[options extras] error: {e}", exc_info=True)
            # A failed capture is NOT a successful empty options market.
            # Fail before publishing/mirroring; normal preparation retry obtains
            # a new snapshot without freezing it or paying for a model verdict.
            return jsonify(error='options_capture_failed', symbol=symbol,
                           error_type=type(e).__name__), 502

        
        # Realized close-to-close variability; no implied/realized label for a straddle premium.
        vols = _realized_vols_package(days=days, atr10=atr10)
        for key in ("iv_to_rv_ratio", "em_to_atr_ratio", "em_pct_1w", "em_abs_1w"):
            vols.pop(key, None)

        # ---- Liquidez (ADV20$ + spread) ----
        liquidity = _liquidity_package(volume20_block=volume20, quote=q, last_price=last_price)

        # -------- Overview de OI puts/calls (agregado + buckets) --------
        options_overview = {}
        try:
            options_overview["put_call_oi_ratio"] = _put_call_oi_views(
                symbol=symbol,
                top_expirations=CALLWALL_TOP_EXPIRATIONS,
                max_dte=PUTCALL_MAX_DTE,
                include_all=PUTCALL_INCLUDE_ALL
            )
            if _contains_source_error(options_overview):
                raise ValueError('incomplete_options_overview')
        except Exception as e:
            tlogger.error(f"[options_overview] error: {e}", exc_info=True)
            return jsonify(error='options_capture_failed', component='options_overview',
                           symbol=symbol, error_type=type(e).__name__), 502

        # -------- Forward returns t+1 (serie + resumen) --------
        forward_returns = _forward_returns_t1_package(days, lookback=FORWARD_RET_LOOKBACK)

        conventions = {"returns": {"basis": "close_to_close", "t_is_trading_days": True},
                       "options": {"dealer_position_sign": "unobserved", "straddle_is_sigma": False},
                       "uncertainty": "No calibrated price-touch probabilities or directional confidence supplied."}

        # ---- Fuerza relativa vs SPY y, opcionalmente, vs sector ----
        relative_strength = {}
        try:
            relative_strength["vs_spy"] = _relative_strength_vs(
                symbol_days=days, bench_symbol="SPY", start=start, end=end, lookbacks=RS_LOOKBACKS
            )
            if SECTOR_BENCH:
                relative_strength["vs_sector"] = _relative_strength_vs(
                    symbol_days=days, bench_symbol=SECTOR_BENCH, start=start, end=end, lookbacks=RS_LOOKBACKS
                )
        except Exception as e:
            tlogger.error(f"[relative_strength] error: {e}", exc_info=True)

        # Asegura que toda distancia está marcada como porcentaje
        for _lst in (resistances, supports):
            for _it in _lst:
                if "distance" in _it and "unit" not in _it:
                    _it["unit"] = "pct"

        # Daily OHLCV is the finest history available from this service. Build
        # an explicit, reproducible approximation instead of asking the LLM to
        # infer volume-at-price or historical defenses from prose.
        volume_profile = _build_daily_volume_profile(days)
        option_origins = []
        if requested_options:
            try:
                option_origins = _observe_option_origins(requested_options, symbol, last_price)
                _annotate_support_evidence([], option_origins, days, atr10, volume_profile)
            except Exception as e:
                tlogger.error('[option_origins] capture failed: %s', type(e).__name__)
                return jsonify(error='options_capture_failed', component='option_origins',
                               symbol=symbol, error_type=type(e).__name__), 502
        observed_origins = _observe_avwap_anchors(requested_anchors, days)
        _annotate_support_evidence(observed_origins, [], days, atr10, volume_profile)
        _annotate_support_evidence(
            supports=supports,
            put_walls=putwalls_top,
            days=days,
            atr10=atr10,
            volume_profile=volume_profile,
        )
        support_origins = None
        if requested_supports is not None:
            support_origins, support_pool = _observe_support_origins(
                requested_supports, days, atr10, g.capture_as_of, volume_profile)
            # Add exact formation identity only for the revision41 opt-in.
            # Selection, coordinates and original score/evidence remain unchanged.
            for item in supports:
                if item.get('type') not in ('range_bottom_3_6m', 'gap_up_lower'):
                    continue
                identity = _support_source_identity(item)
                matches = [record for record in support_pool
                           if _support_source_identity(record) == identity]
                if len(matches) == 1:
                    item.setdefault('meta', {})['origin_identity'] = matches[0]['meta']['origin_identity']

        # -------- Salida JSON base (lo usamos como INPUT del LLM) --------
        out = {
            "symbol": symbol,
            "data_contract_revision": DATA_CONTRACT_REVISION,
            "latest_price": round(last_price, 4),
            "as_of": g.capture_as_of.isoformat(),
            "quote_observation": quote_observation,
            "resistances": resistances,
            "supports": supports,
            "observed_origins": observed_origins,
            "relative_strength": relative_strength,
            "call_walls_top": callwalls_top,
            "put_walls_top": putwalls_top,
            "technicals": technicals,
            "price_history": history_capture,
            "volume_profile": volume_profile,
            "options": options,
            "options_overview": options_overview,
            "vols": vols,
            "forward_returns": forward_returns,
            "conventions": conventions,
            "liquidity": liquidity
        }

        # -------- Llamada a Gemini con tu prompt + JSON --------
        if requested_options:
            out['option_origins'] = option_origins
        if support_origins is not None:
            out['support_origins'] = support_origins
        #try:
        #    advice_text = _advise_with_gemini(symbol, out, pt_media=127.0)
        #except Exception as e:
        #    logging.exception("[gemini] error")
        #    return jsonify(error="gemini_error", details=str(e)), 502

        #if not advice_text:
        #    advice_text = (
        #        f"🔖 {symbol} | Spot ${out['latest_price']} | {out['as_of']}\n"
        #        "No se pudo generar el análisis. Reintenta en unos minutos."
        #    )

        # -------- (Opcional) Guardar el texto en el bucket --------
        #advice_url = _publish_advice_text(symbol, advice_text)

        # -------- Responder (texto + url) --------
        #return jsonify({
        #    "symbol": symbol,
        #    "as_of": out["as_of"],
        #    "model": "gemini-2.5-pro",
        #    "advice": advice_text,
        #    "advice_url": advice_url
        #}), 200

        # -------- Devolver salida técnica directamente (sin IA) --------
        # (Opcional) publicar el JSON técnico al espejo GCS para consultarlo desde fuera.
        out = _measurement_contract(out)
        out["mirror_url"] = _publish_symbol_json(symbol, out)
        # Optional research archive: same downloads, excluded from public mirror.
        if g.evaluation_archive_enabled:
            try:
                try:
                    from .technical_archive import build_capture, text_sha256
                except ImportError:
                    try:
                        from gcp_functions.support_resistances_raw.technical_archive import build_capture, text_sha256
                    except ImportError:
                        from technical_archive import build_capture, text_sha256
                responses = []
                received = getattr(g, 'option_response_received_at', {})
                for (url, params), response in getattr(g, 'option_responses', {}).items():
                    endpoint = url.removeprefix(TRADIER_BASE)
                    responses.append({'endpoint': endpoint, 'params': dict(params),
                        'received_at': received.get((url, params)), 'body_text': response.text,
                        'body_sha256': text_sha256(response.text)})
                archive = build_capture(symbol, out['as_of'], days, responses,
                    expected_expirations=(options.get('capture') or {}).get('sampled_expirations', []),
                    source_status=options.get('status', 'unknown'),
                    history_received_at=history_received_at,
                    history_request_window={'start': start, 'end': end},
                    source_revision=DATA_CONTRACT_REVISION,
                    additional_histories=[item for index, item in enumerate(getattr(g, 'downloaded_daily_histories', [])) if index != primary_history_index])
                out = dict(out, _evaluation_archive=archive)
            except Exception as exc:
                tlogger.warning('evaluation_archive_unavailable: %s', exc)
                out = dict(out, _evaluation_archive_error={'status': 'failed',
                    'at': datetime.now(timezone.utc).isoformat(), 'error_type': type(exc).__name__, 'error': str(exc)})
        return jsonify(out), 200

    except requests.HTTPError as e:
        body = getattr(e.response, "text", None)
        tlogger.error(f"[Tradier] HTTPError {e} body={body}")
        return jsonify(error="tradier_http_error", details=str(e), body=body), 502
    except Exception as e:
        tlogger.exception("internal_error")
        return jsonify(error="internal_error", details=str(e)), 500


# ==========================================================
#                        HELPERS
# ==========================================================

# Obtiene el símbolo del request (GET ?symbol=… o POST con "symbol"/"tickers").
def _get_symbol(request):
    try:
        symbol = (request.args.get("symbol") or "").upper()
        if not symbol:
            payload = request.get_json(silent=True) or {}
            symbol = (payload.get("symbol")
                      or (payload.get("tickers") or [None])[0]
                      or "")
            symbol = (symbol or "").upper()
        if not symbol:
            return None, (jsonify(error="Missing 'symbol' or 'tickers'"), 400)
        return symbol, None
    except Exception:
        return None, (jsonify(error="Invalid request"), 400)


# Llama a Tradier /v1/markets/quotes y devuelve un dict único normalizado.
def _tradier_quote(symbol: str) -> dict:
    r = requests.get(
        f"{TRADIER_BASE}/v1/markets/quotes",
        headers=HEADERS_JSON,
        params={"symbols": symbol},
        timeout=10
    )
    r.raise_for_status()
    data = r.json().get("quotes", {}).get("quote")
    if isinstance(data, list):
        data = data[0] if data else None
    return data or {}


# Llama a Tradier /v1/markets/history para barras diarias [start, end] (ascendente).
def _tradier_history_daily(symbol: str, start: str, end: str):
    """
    Devuelve lista de dicts diarios ordenados por fecha ascendente:
    [{"date":"YYYY-MM-DD","open":..,"high":..,"low":..,"close":..,"volume":..}, ...]
    """
    r = requests.get(
        f"{TRADIER_BASE}/v1/markets/history",
        headers=HEADERS_JSON,
        params={"symbol": symbol, "interval": "daily", "start": start, "end": end},
        timeout=15
    )
    r.raise_for_status()
    raw = r.json().get("history", {}) or {}
    days = raw.get("day") or []
    if isinstance(days, dict):
        days = [days]
    days.sort(key=lambda d: d.get("date"))
    if has_request_context() and getattr(g, 'evaluation_archive_enabled', False):
        received_at = datetime.now(timezone.utc).isoformat()
        if not hasattr(g, 'history_received_at'):
            g.history_received_at = {}
            g.downloaded_daily_histories = []
        g.history_received_at[symbol] = received_at
        g.downloaded_daily_histories.append({'symbol': symbol, 'request_start': start,
            'request_end': end, 'received_at': received_at, 'rows': days})
    return days


# Calcula ATR(10) diario usando High/Low/Close (True Range clásico).
def _atr10_from_daily(days: list, period: int = 10) -> float | None:
    if not days or len(days) < period + 1:
        return None
    trs = []
    for i in range(1, len(days)):
        hi = _to_float(days[i]["high"])
        lo = _to_float(days[i]["low"])
        prev_close = _to_float(days[i-1]["close"])
        if hi is None or lo is None or prev_close is None:
            continue
        tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


# Encuentra el máximo de 52 semanas (lookback barras) y devuelve (nivel, fecha).
def _find_52w_high(days: list, lookback: int = 252):
    if not days:
        return None, None
    window = days[-lookback:] if len(days) >= lookback else days[:]
    best = None
    best_date = None
    for d in window:
        hi = _to_float(d.get("high"))
        if hi is None:
            continue
        if best is None or hi > best:
            best = hi
            best_date = d.get("date")
    return best, best_date


# Cuenta cuántos "toques" del nivel ha habido DESDE la fecha en que se formó (excluyéndola).
def _count_retests(level: float, level_date: str, days: list, tol: float) -> int:
    """
    Un "toque" se contabiliza si high del día está a |high - level| <= tol.
    Empieza a contar desde el día posterior a 'level_date' hasta HOY (excluye el origen).
    """
    if level is None or level_date is None:
        return 0
    count = 0
    started = False
    for d in days:
        date = d.get("date")
        if not started:
            if date == level_date:
                started = True
            continue
        hi = _to_float(d.get("high"))
        if hi is None:
            continue
        if abs(hi - level) <= tol:
            count += 1
    return count


# Extrae precio utilizable: mid(bid,ask) → last → close → prevclose.
def _quote_observation(quote, as_of):
    """Select a positive, dated observation; never timestamp a prior close as live."""
    def timestamp(value):
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError):
            return None
    day = as_of.astimezone(NY).date()
    expected = latest_completed_session(as_of)
    if market_session(day) and as_of.astimezone(NY).hour >= 9 and as_of.astimezone(NY).time().replace(tzinfo=None) >= datetime.strptime('09:30', '%H:%M').time():
        expected = day
    bid, ask = _to_float(quote.get('bid')), _to_float(quote.get('ask'))
    choices = []
    if bid is not None and ask is not None and 0 < bid <= ask:
        times = [timestamp(quote.get('bid_date')), timestamp(quote.get('ask_date'))]
        choices.append(('bid_ask_mid', (bid + ask) / 2, min(times) if all(times) else None))
    choices.append(('last_trade', _to_float(quote.get('last')), timestamp(quote.get('trade_date'))))
    for source, price, stamp in choices:
        if (price is not None and price > 0 and stamp is not None
                and stamp <= as_of + timedelta(seconds=5)
                and stamp.astimezone(NY).date() >= expected):
            return {'status': 'available', 'price': price, 'source': source,
                    'provider_timestamp': stamp.isoformat(), 'fetched_at': as_of.isoformat(),
                    'age_seconds': max(0.0, (as_of - stamp).total_seconds()),
                    'freshness_basis': 'current_open_session_or_latest_completed_session',
                    'expected_market_date': expected.isoformat()}
    return {'status': 'unavailable', 'reason': 'missing_invalid_or_stale_dated_quote',
            'fetched_at': as_of.isoformat(), 'expected_market_date': expected.isoformat()}


def _measurement_contract(out):
    """New captures expose measurements, not uncalibrated confidence or dealer inventory."""
    options = out.get('options') or {}
    legacy = options.pop('dealer_gamma', {})
    options['gamma_concentration'] = {
        'call_minus_put_notional_usd_millions': legacy.get('gex_total_usd_millions'),
        'eligible_contracts': legacy.get('eligible_contracts'),
        'unknown_metric_contracts': legacy.get('unknown_metric_contracts'),
        'assumed_standard_multiplier_contracts': legacy.get('assumed_standard_multiplier_contracts'),
        'sampled_expirations': legacy.get('sampled_expirations'),
        'dealer_position_sign': 'unknown',
        'method': 'sum_call_abs_gamma_OI_multiplier_S2_minus_puts',
        'units': 'USD_millions_per_unit_underlying_return',
        'scope': 'gamma_eligible_contracts_in_sampled_expirations; hypothetical_long_contract_exposure',
    }
    def strip(value):
        if isinstance(value, dict):
            for key in ('prob_touch_1w_pct', 'strength_score'):
                value.pop(key, None)
            for child in value.values():
                strip(child)
        elif isinstance(value, list):
            for child in value:
                strip(child)
    strip(out)
    out['measurement_policy'] = {
        'version': 40, 'removed_auxiliaries': ['prob_touch_1w_pct', 'strength_score', 'trend_1_2w', 'dealer_gamma_regime', 'atm_iv_straddle_heuristic', 'iv_to_rv_ratio'],
        'reason': 'No calibrated probability, independent strength or dealer position inferred from these measurements.'}
    return out


def _extract_latest_price(quote: dict):
    bid = _to_float(quote.get("bid"))
    ask = _to_float(quote.get("ask"))
    if bid is not None and ask is not None and 0 < bid <= ask:
        return (bid + ask) / 2.0
    for k in ("last", "close", "prevclose"):
        v = _to_float(quote.get(k))
        if v is not None and v > 0:
            return v
    return None


# Convierte a float de forma segura (None/“NaN”/texto → None).
def _to_float(x):
    try:
        value = float(x)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _snapshot_time():
    if has_request_context() and getattr(g, 'capture_as_of', None) is not None:
        return g.capture_as_of
    return datetime.now(timezone.utc)


def _complete_daily_bars(days: list, as_of=None) -> list:
    as_of = as_of or _snapshot_time()
    rows = []
    for row in days or []:
        try:
            if is_completed_session(date.fromisoformat(row['date']), as_of):
                rows.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda row: row['date'])


def _recent_price_history(days: list, as_of=None) -> dict:
    """Observed recent sessions, not a support verdict or a forward-return test."""
    as_of = as_of or _snapshot_time()
    closed = _complete_daily_bars(days, as_of)[-20:]
    rows = []
    for day in closed:
        row = {'date': day['date']}
        for field in ('open', 'high', 'low', 'close', 'volume'):
            value = _to_float(day.get(field))
            if value is None or value < 0 or (field != 'volume' and value == 0):
                return {'status': 'unavailable', 'reason': 'invalid_recent_ohlcv', 'sessions': []}
            row[field] = value
        if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
            return {'status': 'unavailable', 'reason': 'inconsistent_recent_ohlcv', 'sessions': []}
        rows.append(row)
    if not rows or len({row['date'] for row in rows}) != len(rows):
        return {'status': 'unavailable', 'reason': 'missing_or_duplicate_sessions', 'sessions': []}
    for previous, current in zip(rows, rows[1:]):
        following = date.fromisoformat(previous['date']) + timedelta(days=1)
        while not market_session(following):
            following += timedelta(days=1)
        if current['date'] != following.isoformat():
            return {'status': 'unavailable', 'reason': 'missing_recent_session', 'sessions': rows}
    expected = latest_completed_session(as_of).isoformat()
    if rows[-1]['date'] != expected:
        return {'status': 'unavailable', 'reason': 'stale_daily_history',
                'expected_last_session': expected, 'last_session': rows[-1]['date'], 'sessions': rows}
    return {'status': 'available', 'source': 'tradier_daily_history',
            'observation_policy': 'completed_nyse_sessions_at_snapshot',
            'expected_last_session': expected, 'observed_sessions': len(rows),
            'window_complete': len(rows) == 20,
            'window_sessions': 20, 'first_session': rows[0]['date'],
            'last_session': rows[-1]['date'], 'sessions': rows,
            'scope': 'Recent OHLCV only. Not intraday ordering, breakout confirmation, '
                     'a fixed close-count rule or the five-session rebound metric.'}


def _build_daily_volume_profile(days: list, lookback: int = 126, bins: int = 48) -> dict:
    """Approximate volume-at-price by spreading each daily bar over its range."""
    bars = _complete_daily_bars(days)[-lookback:]
    valid = []
    for day in bars:
        low = _to_float(day.get("low"))
        high = _to_float(day.get("high"))
        close = _to_float(day.get("close"))
        volume = _to_float(day.get("volume"))
        if low is None or high is None or volume is None or volume <= 0:
            continue
        if high < low:
            low, high = high, low
        valid.append((low, high, close, volume, day.get("date")))

    if len(valid) < 20:
        return {
            "status": "unavailable",
            "reason": "fewer_than_20_complete_ohlcv_bars",
            "method": "daily_ohlcv_uniform_range",
            "lookback_sessions": len(valid),
        }

    price_low = min(row[0] for row in valid)
    price_high = max(row[1] for row in valid)
    if price_high <= price_low:
        return {
            "status": "unavailable",
            "reason": "zero_price_range",
            "method": "daily_ohlcv_uniform_range",
            "lookback_sessions": len(valid),
        }

    bin_count = max(12, min(int(bins), 96))
    width = (price_high - price_low) / bin_count
    allocated = [0.0] * bin_count
    for low, high, close, volume, _ in valid:
        if high - low < width * 0.05:
            anchor = close if close is not None else (low + high) / 2.0
            index = min(bin_count - 1, max(0, int((anchor - price_low) / width)))
            allocated[index] += volume
            continue
        first = min(bin_count - 1, max(0, int((low - price_low) / width)))
        last = min(bin_count - 1, max(0, int((high - price_low) / width)))
        share = volume / (last - first + 1)
        for index in range(first, last + 1):
            allocated[index] += share

    total = sum(allocated)
    if total <= 0:
        return {
            "status": "unavailable",
            "reason": "zero_allocated_volume",
            "method": "daily_ohlcv_uniform_range",
            "lookback_sessions": len(valid),
        }

    def node(index: int, node_type: str) -> dict:
        return {
            "type": node_type,
            "level": round(price_low + (index + 0.5) * width, 4),
            "volume_share_pct": round(100.0 * allocated[index] / total, 2),
        }

    poc_index = max(range(bin_count), key=lambda index: allocated[index])
    peaks = [
        index for index in range(1, bin_count - 1)
        if allocated[index] >= allocated[index - 1]
        and allocated[index] >= allocated[index + 1]
    ]
    peaks.sort(key=lambda index: allocated[index], reverse=True)
    selected = []
    for index in peaks:
        if index == poc_index or abs(index - poc_index) < 2:
            continue
        if any(abs(index - chosen) < 2 for chosen in selected):
            continue
        selected.append(index)
        if len(selected) == 4:
            break

    return {
        "status": "available",
        "method": "daily_ohlcv_uniform_range_48_bins",
        "approximate": True,
        "lookback_sessions": len(valid),
        "start_date": valid[0][4],
        "end_date": valid[-1][4],
        "price_low": round(price_low, 4),
        "price_high": round(price_high, 4),
        "bin_width": round(width, 4),
        "poc": node(poc_index, "poc"),
        "hvn": [node(index, "hvn") for index in selected],
    }


def _profile_proximity(level: float, profile: dict) -> dict:
    if not profile or profile.get("status") != "available" or not level:
        return {"status": "unavailable", "reason": "volume_profile_unavailable"}
    poc = profile.get("poc") or {}
    hvn = profile.get("hvn") or []
    nodes = [poc] + list(hvn)
    nodes = [item for item in nodes if _to_float(item.get("level")) is not None]
    if not nodes:
        return {"status": "unavailable", "reason": "no_profile_nodes"}
    nearest = min(nodes, key=lambda item: abs(_to_float(item.get("level")) - level))
    nearest_level = _to_float(nearest.get("level"))
    poc_level = _to_float(poc.get("level"))
    nearest_hvn = min(
        hvn,
        key=lambda item: abs(_to_float(item.get("level")) - level),
        default=None,
    )
    hvn_level = _to_float((nearest_hvn or {}).get("level"))
    return {
        "status": "available",
        "nearest_type": nearest.get("type"),
        "nearest_level": nearest_level,
        "nearest_distance_pct": round(100.0 * (nearest_level - level) / level, 2),
        "nearest_abs_distance_pct": round(100.0 * abs(nearest_level - level) / level, 2),
        "poc_distance_pct": (
            round(100.0 * (poc_level - level) / level, 2)
            if poc_level is not None else None
        ),
        "nearest_hvn_distance_pct": (
            round(100.0 * (hvn_level - level) / level, 2)
            if hvn_level is not None else None
        ),
    }


def _historical_support_reactions(
    level: float,
    days: list,
    atr10: float | None,
    tolerance: float | None = None,
    forward_sessions: int = 5,
) -> dict:
    bars = _complete_daily_bars(days)[-252:]
    if not level or len(bars) < 20:
        return {"status": "unavailable", "reason": "insufficient_daily_history"}

    tolerance = tolerance or max(0.005 * level, 0.2 * (atr10 or 0.0))
    min_rebound_pct = max(1.0, 50.0 * (atr10 or 0.0) / level)
    event_indexes = []
    previous_touch = False
    for index, day in enumerate(bars):
        low = _to_float(day.get("low"))
        high = _to_float(day.get("high"))
        touched = (
            low is not None and high is not None
            and low <= level + tolerance
            and high >= level - tolerance
        )
        if touched and not previous_touch:
            event_indexes.append(index)
        previous_touch = touched

    completed_events = []
    pending_events = []
    incomplete_data_count = 0
    for index in event_indexes:
        future = bars[index + 1:index + 1 + forward_sessions]
        # Partial windows are pending, not completed failures or successes.
        # Exclude them from ALL historical statistics until the horizon matures.
        if len(future) < forward_sessions:
            pending_events.append({
                "date": bars[index].get("date"),
                "observed_sessions": len(future),
            })
            continue
        future_highs = [_to_float(day.get("high")) for day in future]
        future_highs = [value for value in future_highs if value is not None]
        touch_close = _to_float(bars[index].get("close"))
        if len(future_highs) != forward_sessions or touch_close is None:
            incomplete_data_count += 1
            continue
        rebound = 100.0 * (max(future_highs) - level) / level
        defended = (
            touch_close is not None
            and touch_close >= level - tolerance
            and rebound >= min_rebound_pct
        )
        completed_events.append({
            "date": bars[index].get("date"),
            "rebound_5d_pct": rebound,
            "defended": defended,
        })

    observation = {
        "observation_policy": "complete_forward_window_only",
        "forward_sessions": forward_sessions,
        "pending_test_count": len(pending_events),
        "last_pending_test_date": pending_events[-1]["date"] if pending_events else None,
        "last_pending_observed_sessions": (
            pending_events[-1]["observed_sessions"] if pending_events else None
        ),
        "excluded_incomplete_data_test_count": incomplete_data_count,
    }
    if not completed_events:
        return {
            "status": "unavailable",
            "reason": "no_completed_tests_in_lookback",
            "lookback_sessions": len(bars),
            **observation,
        }

    rebounds = [event["rebound_5d_pct"] for event in completed_events]
    defenses = sum(1 for event in completed_events if event["defended"])
    last = completed_events[-1]
    return {
        "status": "available",
        "method": "daily_level_tests_collapsed_then_max_high_5_sessions",
        "lookback_sessions": len(bars),
        "tolerance_abs": round(tolerance, 4),
        "test_count": len(completed_events),
        "defense_count": defenses,
        "defense_rate_pct": round(100.0 * defenses / len(completed_events), 1),
        "last_test_date": last["date"],
        "last_test_rebound_5d_pct": round(last["rebound_5d_pct"], 2),
        "median_rebound_5d_pct": round(statistics.median(rebounds), 2),
        "max_rebound_5d_pct": round(max(rebounds), 2),
        "defense_min_rebound_pct": round(min_rebound_pct, 2),
        **observation,
    }


def _annotate_support_evidence(
    supports: list,
    put_walls: list,
    days: list,
    atr10: float | None,
    volume_profile: dict,
) -> None:
    # Historical tests and their calibration must observe the SAME completed
    # daily data. Live ATR/meta tolerance changed old defenses intraday even
    # though today's bar was excluded from the measured reaction window.
    import hashlib
    closed = _complete_daily_bars(days)
    history_atr = _atr10_from_daily(closed)
    history = [{k: day.get(k) for k in ('date', 'high', 'low', 'close')}
               for day in closed[-252:]]
    history_key = hashlib.sha256(json.dumps(history, sort_keys=True,
                               separators=(',', ':')).encode()).hexdigest()
    def reaction_for(level):
        basis = {'calibration': 'completed_daily_atr10_v1',
                 'history_sha256': history_key,
                 'history_end': closed[-1].get('date') if closed else None,
                 'atr10': history_atr}
        if history_atr is None:
            return {'status': 'unavailable', 'reason': 'incomplete_historical_atr',
                    'measurement_basis': basis}
        result = _historical_support_reactions(level, closed, history_atr)
        basis['parameters_sha256'] = hashlib.sha256(json.dumps(
            [level, history_atr, max(0.005 * level, 0.2 * history_atr)],
            separators=(',', ':')).encode()).hexdigest()
        result['measurement_basis'] = basis
        result['path_evidence'] = horizontal_path_evidence(
            level, closed, max(0.005 * level, 0.2 * history_atr))
        return result
    for item in supports or []:
        level = _to_float(item.get("level"))
        if level is None:
            continue
        meta = item.setdefault("meta", {})
        meta["volume_profile_proximity"] = _profile_proximity(level, volume_profile)
        meta["historical_reaction"] = reaction_for(level)

    for item in put_walls or []:
        level = _to_float(item.get("level"))
        if level is None:
            continue
        item["volume_profile_proximity"] = _profile_proximity(level, volume_profile)
        item["historical_reaction"] = reaction_for(level)


# --------------------- Helpers Rango 3–6m ---------------------

def _find_swing_highs(days: list, k: int = 2):
    swings = []
    n = len(days)
    if n < 2*k + 1:
        return swings
    for i in range(k, n - k):
        hi = _to_float(days[i]["high"])
        if hi is None:
            continue
        is_peak = True
        for j in range(1, k + 1):
            hi_prev = _to_float(days[i - j]["high"])
            hi_next = _to_float(days[i + j]["high"])
            if hi_prev is None or hi_next is None or hi < hi_prev or hi < hi_next:
                is_peak = False
                break
        if is_peak:
            swings.append({
                "date":   days[i]["date"],
                "price":  hi,
                "volume": _to_float(days[i]["volume"]) or 0.0
            })
    return swings


def _cluster_swing_highs(swings: list, tol: float):
    if not swings:
        return []
    swings_sorted = sorted(swings, key=lambda x: x["price"])
    clusters = []
    cur = [swings_sorted[0]]

    def _level_of(cluster):
        return _median([s["price"] for s in cluster])

    for s in swings_sorted[1:]:
        center = _level_of(cur)
        if abs(s["price"] - center) <= tol:
            cur.append(s)
        else:
            clusters.append(cur)
            cur = [s]
    clusters.append(cur)

    out = []
    for cl in clusters:
        prices = [s["price"] for s in cl]
        vols   = [s["volume"] for s in cl]
        dates  = [s["date"]   for s in cl]
        out.append({
            "level": _median(prices),
            "touches": len(cl),
            "first_date": min(dates),
            "last_date":  max(dates),
            "avg_volume": (sum(vols) / len(vols)) if vols else 0.0
        })
    return out


def _select_range_top_cluster(clusters: list, last_price: float, today_high: float, tol: float, median_vol: float, min_distance_pct: float = 0.05):
    if not clusters or last_price is None:
        return None
    threshold = last_price * (1.0 + max(0.0, min_distance_pct))
    cands = [c for c in clusters if c["touches"] >= 2 and c["level"] >= threshold]
    if not cands:
        return None
    def _score(c):
        dist  = abs(c["level"] - last_price)
        try:
            recency_days = (datetime.utcnow() - datetime.strptime(c["last_date"], "%Y-%m-%d")).days
            recency = max(0.0, 1.0 - min(recency_days, 90)/90.0)
        except Exception:
            recency = 0.0
        touches = c["touches"]
        vol_factor = (c["avg_volume"] / median_vol) if median_vol else 1.0
        return 1.5*touches + 1.0*recency + 0.5*min(vol_factor, 2.0) - 0.3*(dist / max(tol, 1e-6))
    cands.sort(key=_score, reverse=True)
    best = cands[0]
    testing_now = (today_high is not None and abs(today_high - best["level"]) <= tol)
    return {
        "level": best["level"],
        "touches": best["touches"],
        "first_date": best["first_date"],
        "last_date": best["last_date"],
        "vol_factor": (best["avg_volume"] / median_vol) if median_vol else None,
        "testing_now": testing_now
    }


def _median(vals: list):
    vals = [v for v in vals if v is not None]
    n = len(vals)
    if n == 0:
        return None
    vals = sorted(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


# ------------------------ Helpers Gaps ------------------------

def _find_bearish_gaps(days: list):
    gaps = []
    for i in range(1, len(days)):
        prev = days[i-1]
        cur  = days[i]
        hi_cur   = _to_float(cur.get("high"))
        lo_prev  = _to_float(prev.get("low"))
        vol_cur  = _to_float(cur.get("volume")) or 0.0
        if hi_cur is None or lo_prev is None:
            continue
        if hi_cur < lo_prev:  # gap-down estricto
            upper = lo_prev
            lower = hi_cur
            size  = upper - lower
            gaps.append({
                "date": cur.get("date"),
                "upper": upper,
                "lower": lower,
                "size":  size,
                "volume": vol_cur
            })
    return gaps


def _select_bearish_gap_resistance(gaps: list, full_days: list, last_price: float, today_high: float, tol: float, min_distance_pct: float = 0.05):
    if not gaps or last_price is None:
        return None
    median_vol = _median([_to_float(d.get("volume")) or 0.0 for d in full_days]) or 0.0
    threshold = last_price * (1.0 + max(0.0, min_distance_pct))
    cands = [g for g in gaps if g["upper"] >= threshold]
    if not cands:
        return None
    def _score(g):
        dist  = abs(g["upper"] - last_price)
        size  = g["size"]
        try:
            recency_days = (datetime.utcnow() - datetime.strptime(g["date"], "%Y-%m-%d")).days
            recency = max(0.0, 1.0 - min(recency_days, 120)/120.0)
        except Exception:
            recency = 0.0
        return (1.5*size - 0.3*(dist / max(tol, 1e-6)) + 1.0*recency)
    cands.sort(key=_score, reverse=True)
    best = cands[0]
    vol_factor = (best["volume"] / median_vol) if median_vol else None
    size_pct = 100.0 * best["size"] / last_price if last_price else 0.0
    filled = False
    touches_since = 0
    last_touch_date = None
    passed = False
    for d in full_days:
        if not passed:
            if d.get("date") == best["date"]:
                passed = True
            continue
        hi = _to_float(d.get("high"))
        cl = _to_float(d.get("close"))
        if hi is not None and abs(hi - best["upper"]) <= tol:
            touches_since += 1
            last_touch_date = d.get("date")
        if cl is not None and cl > best["upper"] + tol:
            filled = True
    testing_now = (today_high is not None and abs(today_high - best["upper"]) <= tol)
    return {
        "date": best["date"],
        "upper": best["upper"],
        "lower": best["lower"],
        "size":  best["size"],
        "size_pct": size_pct,
        "vol_factor": vol_factor,
        "touches_since": touches_since,
        "last_touch_date": last_touch_date,
        "testing_now": testing_now,
        "filled": filled
    }


# ---------------------- Helpers AVWAP evento ----------------------

def _parse_anchor_dates(value):
    dates = sorted(set(filter(None, str(value).split(','))))
    for value in dates:
        if datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') != value:
            raise ValueError('invalid_anchor_date')
    return dates


def _observe_avwap_anchors(anchors, days):
    """Observe prior origins outside ranking filters; never declare viability.

    Exact history coverage is required, not a later substitute anchor.
    """
    result = []
    for anchor in anchors:
        bars = [row for row in days if row.get('date', '') >= anchor]
        complete = (bars and bars[0].get('date') == anchor and all(
            all(_to_float(row.get(k)) is not None for k in ('high', 'low', 'close', 'volume'))
            and _to_float(row['volume']) >= 0 for row in bars))
        level = _avwap_from_date(bars, anchor) if complete else None
        result.append({'type': 'avwap_observation', 'level': round(level, 4) if level else None,
            'status': 'available' if level else 'unavailable',
            'reason': None if level else 'anchor_history_incomplete',
            'meta': {'anchor_date': anchor, 'anchor_type': 'requested_dated_origin',
                     'selection': 'continuity_observation_not_support_verdict'}})
    return result


def _avwap_from_date(days: list, anchor_date: str):
    if not anchor_date:
        return None
    start = False
    vp_sum = 0.0
    v_sum  = 0.0
    for d in days:
        if not start:
            if d.get("date") >= anchor_date:
                start = True
            else:
                continue
        hi = _to_float(d.get("high"))
        lo = _to_float(d.get("low"))
        cl = _to_float(d.get("close"))
        vol = _to_float(d.get("volume")) or 0.0
        if hi is None or lo is None or cl is None:
            continue
        p_typ = (hi + lo + cl) / 3.0
        vp_sum += p_typ * vol
        v_sum  += vol
    return (vp_sum / v_sum) if v_sum > 0 else None


def _first_trading_day_of_year(days: list, year: int):
    prefix = f"{year:04d}-"
    for d in days:
        if isinstance(d.get("date"), str) and d["date"].startswith(prefix):
            return d["date"]
    return None


def _select_avwap_event(
    days: list,
    gap_days: list,
    gaps: list,
    atr10: float,
    last_price: float,
    tol: float,
    level_52w_date: str,
    range_clusters: list,
    median_vol_range: float,
    min_distance_pct: float,
    gap_min_vol_factor: float,
    gap_min_size_atr: float,
    today_high: float | None
):
    if last_price is None:
        return None
    median_vol_gap_window = _median([_to_float(d.get("volume")) or 0.0 for d in gap_days]) or 0.0
    median_vol_all = _median([_to_float(d.get("volume")) or 0.0 for d in days[-126:]]) or 0.0
    threshold = last_price * (1.0 + max(0.0, min_distance_pct))
    best_gap_anchor = None
    if gaps:
        for g in sorted(gaps, key=lambda x: x["date"], reverse=True):
            vol_factor = (g["volume"] / median_vol_gap_window) if median_vol_gap_window else 0.0
            size_atr = (g["size"] / max(atr10, 1e-6)) if atr10 > 0 else 0.0
            if vol_factor >= gap_min_vol_factor and size_atr >= gap_min_size_atr:
                best_gap_anchor = {"date": g["date"], "vol_factor": vol_factor, "size_atr": size_atr}
                break
    if best_gap_anchor:
        avwap = _avwap_from_date(days, best_gap_anchor["date"])
        if avwap is not None and avwap >= threshold:
            testing_now = _is_testing_now(today_high, avwap, tol)
            return {
                "anchor_type": "gap",
                "anchor_label": f"gap del {best_gap_anchor['date']}",
                "anchor_date": best_gap_anchor["date"],
                "level": avwap,
                "vol_factor": best_gap_anchor["vol_factor"],
                "gap_size_atr": best_gap_anchor["size_atr"],
                "testing_now": testing_now
            }
    if level_52w_date:
        avwap = _avwap_from_date(days, level_52w_date)
        if avwap is not None and avwap >= threshold:
            vol_anchor = _volume_on_date(days, level_52w_date)
            vol_factor = (vol_anchor / median_vol_all) if median_vol_all else None
            testing_now = _is_testing_now(today_high, avwap, tol)
            return {
                "anchor_type": "52w_high",
                "anchor_label": f"52w high {level_52w_date}",
                "anchor_date": level_52w_date,
                "level": avwap,
                "vol_factor": vol_factor,
                "testing_now": testing_now
            }
    try:
        current_year = datetime.utcnow().year
    except Exception:
        current_year = int((days[-1]["date"] or "2000")[:4])
    ytd_date = _first_trading_day_of_year(days, current_year)
    if ytd_date:
        avwap = _avwap_from_date(days, ytd_date)
        if avwap is not None and avwap >= threshold:
            vol_anchor = _volume_on_date(days, ytd_date)
            vol_factor = (vol_anchor / median_vol_all) if median_vol_all else None
            testing_now = _is_testing_now(today_high, avwap, tol)
            return {
                "anchor_type": "ytd_open",
                "anchor_label": f"apertura YTD {ytd_date}",
                "anchor_date": ytd_date,
                "level": avwap,
                "vol_factor": vol_factor,
                "testing_now": testing_now
            }
    range_any = _select_range_top_cluster(
        clusters=range_clusters,
        last_price=last_price,
        today_high=None,
        tol=tol,
        median_vol=median_vol_range,
        min_distance_pct=0.0
    )
    if range_any:
        anchor_date = range_any["last_date"]
        avwap = _avwap_from_date(days, anchor_date)
        if avwap is not None and avwap >= threshold:
            testing_now = _is_testing_now(today_high, avwap, tol)
            return {
                "anchor_type": "range_top",
                "anchor_label": f"techo de rango {anchor_date}",
                "anchor_date": anchor_date,
                "level": avwap,
                "vol_factor": range_any.get("vol_factor"),
                "touches": range_any.get("touches"),
                "testing_now": testing_now
            }
    return None


def _volume_on_date(days: list, date_str: str):
    for d in days:
        if d.get("date") == date_str:
            return _to_float(d.get("volume")) or None
    return None


def _testing_today(days: list, level: float, tol: float):
    if not days:
        return False
    hi_today = _to_float(days[-1].get("high"))
    return (hi_today is not None and abs(hi_today - level) <= tol)


# ---------------------- Helpers Call-wall (γ-$) ----------------------

def _contains_source_error(value):
    if isinstance(value, dict):
        return bool(value.get('error')) or any(_contains_source_error(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_source_error(v) for v in value)
    return False


def _validate_option_chain_identity(root, requested_symbol, requested_expiration):
    """Reject explicit contradictions, without inferring adjusted-root mappings.

    Missing fields and unrecognized option-symbol formats remain unknown. This
    acquisition check is independent of the optional research archive.
    """
    if root.tag != 'options':
        raise ValueError('tradier_option_chain_structure_mismatch')
    symbol = str(requested_symbol or '').strip().upper()
    expiry = str(requested_expiration or '').strip()
    for option in root.findall('.//option'):
        def present(key):
            value = option.findtext(key)
            return value.strip() if isinstance(value, str) and value.strip() else None

        for key in ('underlying', 'underlying_symbol'):
            value = present(key)
            if symbol and value is not None and value.upper() != symbol:
                raise ValueError('tradier_option_underlying_mismatch')
        contract_expiry = present('expiration_date')
        if expiry and contract_expiry is not None and contract_expiry != expiry:
            raise ValueError('tradier_option_expiration_mismatch')

        # Recognize only a safely decoded compact/padded OCC identity. Compare
        # with explicit contract fields; a root different from the requested
        # underlying alone does not establish a contradiction (adjustments).
        contract_symbol = present('symbol')
        match = re.fullmatch(r'([A-Z][A-Z0-9.]{0,5}) *(\d{6})([CP])(\d{8})', contract_symbol or '')
        if match is None:
            continue
        try:
            encoded_expiry = date(2000 + int(match[2][:2]), int(match[2][2:4]), int(match[2][4:])).isoformat()
        except ValueError:
            continue
        root_symbol = present('root_symbol')
        side = present('option_type')
        strike_text = present('strike')
        if (root_symbol is not None and match[1] != root_symbol.upper()
                or expiry and encoded_expiry != expiry
                or contract_expiry is not None and encoded_expiry != contract_expiry
                or side is not None and side.lower() in ('put', 'call')
                   and match[3] != ('P' if side.lower() == 'put' else 'C')):
            raise ValueError('tradier_option_occ_identity_mismatch')
        if strike_text is not None:
            try:
                strike = Decimal(strike_text)
            except InvalidOperation:
                continue
            if strike.is_finite() and Decimal(match[4]) / 1000 != strike:
                raise ValueError('tradier_option_occ_identity_mismatch')


def _option_response(url, **kwargs):
    """Reuse successful wire data within ONE request, never across snapshots.

    Gamma/wall/EM consumers share identical chains. Failures are not cached;
    the existing batch preparation retry handles failed captures.
    """
    key = (url, tuple(sorted((kwargs.get('params') or {}).items())))
    cache = None
    if has_request_context():
        if not hasattr(g, 'option_responses'):
            g.option_responses = {}
        cache = g.option_responses
        if key in cache:
            return cache[key]
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    parsed = ET.fromstring(response.text)
    if parsed.tag in ('error', 'errors') or parsed.find('.//error') is not None:
        raise ValueError('tradier_option_response_error')
    if url.endswith('/v1/markets/options/chains'):
        params = kwargs.get('params') or {}
        _validate_option_chain_identity(parsed, params.get('symbol'), params.get('expiration'))
    if cache is not None:
        cache[key] = response
        if getattr(g, 'evaluation_archive_enabled', False):
            if not hasattr(g, 'option_response_received_at'):
                g.option_response_received_at = {}
            g.option_response_received_at[key] = datetime.now(timezone.utc).isoformat()
    return response



def _parse_option_origins(value):
    """Exact explicit identities, never inferred prices or executable input."""
    if not value:
        return []
    found = set()
    for token in value.split(','):
        side, sep, text = token.partition(':')
        if not sep or side not in ('put', 'call') or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', text):
            raise ValueError('invalid_option_origin')
        strike = float(text)
        if not math.isfinite(strike) or strike <= 0:
            raise ValueError('invalid_option_origin')
        found.add((side, strike))
    return sorted(found)


def _observe_option_origins(requested, symbol, spot):
    """Read exact identities from the SAME cached chain responses as the TOP.

    No extra expirations or network downloads. Preserve incomplete metrics and
    zero OI even when the ranking parser could not use that contract's gamma.
    Not observed is limited to this sample, never a global disappearance verdict.
    """
    expirations = (_tradier_option_expirations(symbol) or [])[:max(1, CALLWALL_TOP_EXPIRATIONS)]
    rows = {identity: [] for identity in requested}
    for expiry in expirations:
        response = _option_response(
            f'{TRADIER_BASE}/v1/markets/options/chains', headers=HEADERS_XML,
            params={'symbol': symbol, 'greeks': 'true', 'expiration': expiry}, timeout=15)
        root = ET.fromstring(response.text)
        contracts = {identity: [] for identity in requested}
        ambiguous = False
        for item in root.findall('.//option'):
            side = (item.findtext('option_type') or '').lower()
            strike = _to_float(item.findtext('strike'))
            if side not in ('put', 'call') or strike is None or strike <= 0:
                ambiguous = True
                continue
            identity = (side, strike)
            if identity not in contracts:
                continue
            contracts[identity].append(_parse_option_contract(item, expiry))
        for identity, observed in contracts.items():
            total_oi = sum(c['oi'] for c in observed) if observed and all(c['oi'] is not None for c in observed) else None
            total_gamma = (sum(abs(c['gamma']) * c['oi'] * _contract_multiplier(c) * spot**2 for c in observed) / 1e6
                           if observed and all(c['oi'] is not None and c['gamma'] is not None for c in observed) else None)
            rows[identity].append({
                'expiration': expiry,
                'status': 'unavailable' if ambiguous else 'observed' if observed else 'not_observed',
                'reason': 'incomplete_contract_identity' if ambiguous else
                          'requested_identity_observed' if observed else 'not_observed_in_sampled_chain',
                'aggregate_oi': total_oi, 'gamma_usd_millions': total_gamma,
                'observed_contracts': observed,
            })
    out = []
    for side, strike in requested:
        sampled = rows[(side, strike)]
        available = any(row['status'] == 'observed' for row in sampled)
        unavailable = any(row['status'] == 'unavailable' for row in sampled)
        out.append({
            'type': 'option_origin_observation', 'level': strike,
            'status': 'unavailable' if unavailable else 'available' if available else 'not_observed',
            'reason': 'incomplete_contract_identity' if unavailable else
                      'requested_identity_observed' if available else
                      'not_observed_in_sampled_expirations' if expirations else 'no_future_expirations',
            'option_details': {
                'scope': 'parsed_contracts_in_sampled_expirations',
                'option_type': side, 'strike': strike,
                'aggregate_oi_basis': 'all_observed_contracts_not_only_gamma_eligible',
                'sampled_expirations': expirations, 'by_expiration': sampled,
            },
        })
    return out


def _wall_option_details(strike, side, chains, spot):
    """Expose already downloaded evidence; never infer liquidity or persistence."""
    rows = []
    for expiry, chain in chains.items():
        contracts, aggregate_oi, aggregate_gamma = [], 0, 0.0
        for item in chain:
            if item.get("strike") != strike or item.get("option_type", "").lower() != side:
                continue
            oi, gamma = _to_float(item.get("oi")), _to_float(item.get("gamma"))
            contribution = abs(gamma) * oi * _contract_multiplier(item) * spot ** 2 if oi is not None and gamma is not None else None
            included = contribution is not None and contribution > 0
            if included:
                aggregate_oi += oi
                aggregate_gamma += contribution
            contracts.append({
                **item, "included_in_wall_aggregate": included,
                "bid": item.get("bid"), "ask": item.get("ask"),
                "bid_date": item.get("bid_date"), "ask_date": item.get("ask_date"),
            })
        rows.append({
            "expiration": expiry,
            "status": "observed" if contracts else "not_observed",
            "aggregate_oi": aggregate_oi if contracts else None,
            "gamma_usd_millions": aggregate_gamma / 1e6 if contracts else None,
            "observed_contracts": contracts,
        })
    return {
        "scope": "parsed_contracts_in_sampled_expirations",
        "option_type": side, "strike": strike,
        "aggregate_oi_basis": "gamma_eligible_contracts",
        "gamma_notional_units": "abs_gamma * OI * contract_multiplier * spot_squared / 1e6; no dealer sign",
        "sampled_expirations": list(chains), "by_expiration": rows,
    }

def _tradier_option_expirations(symbol: str):
    """
    Devuelve lista de fechas de expiración (YYYY-MM-DD) vía XML.
    """
    r = _option_response(
        f"{TRADIER_BASE}/v1/markets/options/expirations",
        headers=HEADERS_XML,
        params={"symbol": symbol},
        timeout=10
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return [el.text for el in root.findall(".//date")] or []


def _parse_option_contract(opt, expiration=None):
    strike = _to_float(opt.findtext("strike"))
    side = (opt.findtext("option_type") or "").lower()
    if strike is None or strike <= 0 or side not in ("put", "call"):
        return None
    oi = _to_float(opt.findtext("open_interest"))
    if oi is not None and (oi < 0 or not oi.is_integer()):
        oi = None
    size = _to_float(opt.findtext("contract_size"))
    if size is not None and size <= 0:
        size = None
    return {"strike": strike, "option_type": side,
            "oi": int(oi) if oi is not None else None,
            "gamma": _to_float(opt.findtext("greeks/gamma")),
            "bid": _to_float(opt.findtext("bid")), "ask": _to_float(opt.findtext("ask")),
            "last": _to_float(opt.findtext("last")),
            "bid_date": opt.findtext("bid_date"), "ask_date": opt.findtext("ask_date"),
            "trade_date": opt.findtext("trade_date"),
            "symbol": opt.findtext("symbol"), "root_symbol": opt.findtext("root_symbol"),
            "expiration_date": opt.findtext("expiration_date") or expiration,
            "contract_size": size,
            "multiplier_basis": "provider_contract_size" if size is not None else "assumed_standard_100",
            "greeks_updated_at": opt.findtext("greeks/updated_at"),
            "greeks_smv_vol": _to_float(opt.findtext("greeks/smv_vol"))}


def _contract_multiplier(contract):
    value = _to_float(contract.get("contract_size"))
    return value if value is not None and value > 0 else 100.0


def _oi_total(chain, side):
    contracts = [o for o in chain if o.get("option_type") == side]
    return sum(o["oi"] for o in contracts) if all(o.get("oi") is not None for o in contracts) else None


def _tradier_options_chain(symbol: str, expiration: str):
    """Parse identity first; OI, quotes and Greeks have independent eligibility."""
    response = _option_response(
        f"{TRADIER_BASE}/v1/markets/options/chains", headers=HEADERS_XML,
        params={"symbol": symbol, "greeks": "true", "expiration": expiration}, timeout=15)
    response.raise_for_status()
    out = []
    for opt in ET.fromstring(response.text).findall(".//option"):
        contract = _parse_option_contract(opt, expiration)
        if contract is None:
            raise ValueError("incomplete_option_contract_identity")
        out.append(contract)
    return out

def _compute_callwall_gamma(
    symbol: str,
    last_price: float,
    today_high: float,
    atr10: float,
    top_expirations: int,
    tol_mult: float,
    cluster_atr: float
):
    """
    Devuelve el call-wall dominante (γ-$ más alto) agregando varias expiraciones,
    SIN filtrar por distancia al precio.
    """
    if last_price is None:
        return None

    # 1) Expiraciones: coge las más próximas (hasta top_expirations)
    expirations = _tradier_option_expirations(symbol) or []
    if not expirations:
        return None
    expirations = expirations[:max(1, top_expirations)]

    # 2) Agrega γ-$ por strike de CALLS a través de esas expiraciones
    gamma_calls_by_strike = {}
    oi_calls_by_strike = {}
    gamma_total_calls = 0.0
    strike_exp_gamma = {}  # para identificar la expiración dominante del strike

    sampled_chains = {}
    for exp in expirations:
        chain = _tradier_options_chain(symbol, exp) or []
        sampled_chains[exp] = chain
        for c in chain:
            if (c.get("option_type") or "").lower() != "call":
                continue
            s = c.get("strike")
            oi = c.get("oi", 0)
            gam = c.get("gamma", 0.0)
            if s is None or oi is None or gam is None:
                continue
            CONTRACT = _contract_multiplier(c)
            g_usd = abs(gam) * oi * CONTRACT * (last_price ** 2)  # dólares
            if g_usd <= 0:
                continue
            gamma_calls_by_strike[s] = gamma_calls_by_strike.get(s, 0.0) + g_usd
            oi_calls_by_strike[s] = oi_calls_by_strike.get(s, 0) + oi
            gamma_total_calls += g_usd
            strike_exp_gamma.setdefault(s, {})
            strike_exp_gamma[s][exp] = strike_exp_gamma[s].get(exp, 0.0) + g_usd

    if not gamma_calls_by_strike:
        return None

    # 3) Elige el strike con γ-$ agregado más alto
    top_strike = max(gamma_calls_by_strike, key=lambda s: gamma_calls_by_strike[s])
    top_gamma = gamma_calls_by_strike[top_strike]
    gamma_share_pct = (100.0 * top_gamma / gamma_total_calls) if gamma_total_calls > 0 else None

    # Expiración dominante de ese strike
    exp_dom = None
    if top_strike in strike_exp_gamma:
        exp_dom = max(strike_exp_gamma[top_strike].items(), key=lambda kv: kv[1])[0]

    # 4) Cluster de confluencia ± (cluster_atr × ATR10) alrededor del strike top
    def _cluster_neighbors(center):
        radius = (cluster_atr * atr10) if atr10 and atr10 > 0 else 0.0
        nbrs = [k for k in gamma_calls_by_strike.keys() if abs(k - center) <= radius]
        return sorted(nbrs)

    neighbors = _cluster_neighbors(top_strike)
    cluster_gamma = sum(gamma_calls_by_strike[s] for s in neighbors) if neighbors else top_gamma
    cluster_share_pct = (100.0 * cluster_gamma / gamma_total_calls) if gamma_total_calls > 0 else None

    # 5) “En test” hoy si el high está dentro de la tolerancia
    tol = tol_mult * atr10 if atr10 and atr10 > 0 else max(0.25, 0.002 * last_price)
    testing_now = (today_high is not None and abs(today_high - top_strike) <= tol)

    return {
        "level": top_strike,
        "expiration": exp_dom,
        "option_details": _wall_option_details(top_strike, "call", sampled_chains, last_price),
        "gamma_usd_millions": top_gamma / 1e6,
        "total_call_gamma_usd_millions": gamma_total_calls / 1e6,
        "gamma_share_pct": gamma_share_pct,
        "oi": oi_calls_by_strike.get(top_strike),
        "oi_share_pct": (100.0 * (oi_calls_by_strike.get(top_strike, 0)) / max(1, sum(oi_calls_by_strike.values()))) if oi_calls_by_strike else None,
        "cluster_neighbors": neighbors,
        "cluster_gamma_usd": cluster_gamma / 1e6,
        "cluster_share_pct": cluster_share_pct,
        "tolerance": tol,
        "testing_now": testing_now
    }

def _days_to(date_str: str):
    """Devuelve días hasta la fecha 'YYYY-MM-DD' (puede ser 0/negativo si ya pasó)."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (dt - datetime.utcnow().date()).days
    except Exception:
        return None


def _score_callwall_strength(callwall: dict, last_price: float, atr10: float) -> float:
    """
    Score 6.0–9.8 que refleja fuerza real del call wall:
      • Dominancia γ-$ del strike (share %)  → hasta +1.2
      • Confluencia (cluster_share %)        → hasta +0.6
      • γ-$ absoluto en millones (log)       → hasta +0.5
      • Cuota de OI del strike               → hasta +0.3
      • DTE (<=7/21/45 días)                 → +0.3 / +0.2 / +0.1
      • En test hoy                          → +0.2
    """
    import math

    dom   = (callwall.get("gamma_share_pct") or 0.0) / 100.0           # 0–1
    clus  = (callwall.get("cluster_share_pct") or 0.0) / 100.0         # 0–1
    g_m   = max(0.0, callwall.get("gamma_usd_millions") or 0.0)        # millones
    oi_sh = (callwall.get("oi_share_pct") or 0.0) / 100.0              # 0–1
    testing = bool(callwall.get("testing_now"))
    dte   = _days_to(callwall.get("expiration"))

    # Base y contribuciones
    score = 7.8
    score += 1.2 * min(1.0, dom)                                       # dominancia γ-$
    score += 0.6 * min(1.0, clus)                                      # confluencia
    # γ-$ absoluto: log suave (γ_m=1M → ~+0.36; 0.2M → ~+0.28; cap +0.5)
    score += min(0.5, 0.12 * math.log10(1.0 + 1000.0 * g_m))
    # OI share: lineal hasta 30% (cap +0.3)
    score += 0.3 * min(1.0, oi_sh / 0.30)
    # DTE: más cerca, más impacto
    if dte is not None:
        if dte <= 7:
            score += 0.3
        elif dte <= 21:
            score += 0.2
        elif dte <= 45:
            score += 0.1
    # En test hoy
    if testing:
        score += 0.2

    return round(max(6.0, min(score, 9.8)), 1)


# ------------------------- TECHNICALS -------------------------

def _sma(vals: list, n: int):
    vals = [v for v in vals if v is not None]
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n

def _ema(vals: list, n: int):
    vals = [v for v in vals if v is not None]
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1.0)
    ema = vals[-n]
    for v in vals[-n+1:]:
        ema = v * k + ema * (1 - k)
    return ema

def _rsi14_from_closes(closes: list, n: int = 14):
    vals = [v for v in closes if v is not None]
    if len(vals) < n + 1:
        return None
    gains = []
    losses = []
    for c1, c2 in zip(vals[-(n+1):-1], vals[-n:]):
        ch = c2 - c1
        gains.append(max(0.0, ch))
        losses.append(max(0.0, -ch))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n if sum(losses) > 0 else 1e-9
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)

def _std(vals: list):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    return statistics.pstdev(vals)  # poblacional; para trading vale

def _bollinger(closes: list, window: int = 20, num_std: float = 2.0):
    if closes is None or len([c for c in closes if c is not None]) < window:
        return None
    last_window = [c for c in closes if c is not None][-window:]
    mid = sum(last_window) / window
    sd  = _std(last_window)
    if sd is None:
        return None
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    width_pct = (upper - lower) / mid * 100.0 if mid != 0 else None
    return {"upper": upper, "middle": mid, "lower": lower, "width_pct": width_pct}

def _typical_prices(days: list):
    out = []
    for d in days:
        hi = _to_float(d.get("high"))
        lo = _to_float(d.get("low"))
        cl = _to_float(d.get("close"))
        if hi is None or lo is None or cl is None:
            out.append(None)
        else:
            out.append((hi + lo + cl) / 3.0)
    return out

def _keltner(typical_prices: list, atr10: float, mult: float = 2.0):
    center = _ema(typical_prices, 20)
    if center is None or atr10 is None:
        return None
    upper = center + mult * atr10
    lower = center - mult * atr10
    return {"upper": upper, "center": center, "lower": lower}

def _donchian(highs: list, lows: list, n: int = 20):
    hs = [h for h in highs if h is not None]
    ls = [l for l in lows  if l is not None]
    if len(hs) < n or len(ls) < n:
        return None
    high_n = max(hs[-n:])
    low_n  = min(ls[-n:])
    return {"high": high_n, "low": low_n}


# ------------------- Expected Move / Max Pain -------------------

def _pick_expiration_around_1w(symbol: str, dte_min: int, dte_max: int):
    """
    Elige la expiración más cercana cuyo DTE esté entre [dte_min, dte_max].
    Si no hay, devuelve la expiración más próxima futura.
    """
    exps = _tradier_option_expirations(symbol) or []
    if not exps:
        return None
    today = datetime.utcnow().date()
    future = []
    for e in exps:
        try:
            dt = datetime.strptime(e, "%Y-%m-%d").date()
            dte = (dt - today).days
            if dte >= 0:
                future.append((e, dte))
        except Exception:
            continue
    if not future:
        return None
    # candidatos en rango
    in_band = [e for e in future if dte_min <= e[1] <= dte_max]
    if in_band:
        in_band.sort(key=lambda x: x[1])
        return in_band[0][0]
    # si no hay en banda, coge la menor DTE futura
    future.sort(key=lambda x: x[1])
    return future[0][0]

def _mid_price(bid, ask, last):
    ba = None
    if bid is not None and ask is not None and bid >= 0 and ask > 0 and ask >= bid:
        ba = 0.5 * (bid + ask)
    return ba if ba is not None else (last if last is not None else None)

def _expected_move_1w_via_straddle(symbol: str, expiration: str, spot: float):
    """
    EM ≈ precio del straddle ATM (call+put) usando mid (bid/ask) por strike más cercano al spot.
    Devuelve dict con move_abs (USD) y move_pct (fracción).
    """
    if not expiration or spot is None:
        return None
    chain = _tradier_options_chain(symbol, expiration) or []
    if not chain:
        return None
    # strike ATM
    strikes = sorted({c["strike"] for c in chain if c.get("strike") is not None})
    if not strikes:
        return None
    atm = min(strikes, key=lambda s: abs(s - spot))

    # extrae call/put del ATM
    call = next((c for c in chain if c["strike"] == atm and c["option_type"] == "call"), None)
    put  = next((c for c in chain if c["strike"] == atm and c["option_type"] == "put"),  None)
    if not call or not put:
        return None

    call_mid = _mid_price(call.get("bid"), call.get("ask"), call.get("last"))
    put_mid  = _mid_price(put.get("bid"),  put.get("ask"),  put.get("last"))
    if call_mid is None or put_mid is None:
        return None

    em_abs = call_mid + put_mid
    em_pct = em_abs / spot if spot else None
    return {"strike_atm": atm, "move_abs": em_abs, "move_pct": em_pct,
            "units": {"move_abs": "USD_per_share", "move_pct": "fraction"},
            "call_quote": call, "put_quote": put,
            "price_method": "valid_bid_ask_mid_or_last_fallback",
            "quote_timestamps_supplied": bool(call.get("bid_date") and call.get("ask_date") and put.get("bid_date") and put.get("ask_date")),
            "scope": "nearest_strike_in_sampled_chain; not calibrated volatility or probability"}

def _max_pain_for_expiration(symbol: str, expiration: str):
    """
    Calcula Max Pain minimizando la pérdida total teórica a vencimiento sobre todos los strikes.
    Pain(s*) = Σ_calls OI * max(0, s*-K) + Σ_puts OI * max(0, K-s*).
    Devuelve el strike (float) de mínimo pain.
    """
    if not expiration:
        return None
    chain = _tradier_options_chain(symbol, expiration) or []
    if not chain or any(o.get("oi") is None for o in chain) or not any(o.get("oi") for o in chain):
        return None

    # OI por strike y tipo
    strikes = sorted({c["strike"] for c in chain if c.get("strike") is not None})
    call_oi = {}
    put_oi  = {}
    for c in chain:
        s = c.get("strike")
        if s is None:
            continue
        if (c.get("option_type") or "").lower() == "call":
            call_oi[s] = call_oi.get(s, 0) + c["oi"] * _contract_multiplier(c)
        else:
            put_oi[s]  = put_oi.get(s, 0) + c["oi"] * _contract_multiplier(c)

    if not strikes:
        return None

    def pain_at(price):
        loss = 0.0
        for k in strikes:
            co = call_oi.get(k, 0)
            po = put_oi.get(k, 0)
            if co:
                loss += co * max(0.0, price - k)
            if po:
                loss += po * max(0.0, k - price)
        return loss

    # evalúa en todos los strikes y escoge mínimo
    best = min(strikes, key=pain_at)
    return float(best)
    
def _compute_top_callwalls_gamma(
    symbol: str,
    last_price: float,
    atr10: float,
    top_expirations: int,
    cluster_atr: float,
    top_n: int = 3
):
    """
    Devuelve los N call walls más fuertes por γ-$ agregado (multi-expiración),
    SIN filtrar por distancia. Incluye confluencia local (cluster) alrededor
    de cada strike.
    """
    if last_price is None:
        return []

    expirations = _tradier_option_expirations(symbol) or []
    if not expirations:
        return []
    expirations = expirations[:max(1, top_expirations)]

    gamma_calls_by_strike = {}
    oi_calls_by_strike = {}
    gamma_total_calls = 0.0
    strike_exp_gamma = {}

    sampled_chains = {}
    for exp in expirations:
        chain = _tradier_options_chain(symbol, exp) or []
        sampled_chains[exp] = chain
        for c in chain:
            if (c.get("option_type") or "").lower() != "call":
                continue
            s = c.get("strike")
            oi = c.get("oi", 0)
            gam = c.get("gamma", 0.0)
            if s is None or oi is None or gam is None:
                continue
            CONTRACT = _contract_multiplier(c)
            g_usd = abs(gam) * oi * CONTRACT * (last_price ** 2)
            if g_usd <= 0:
                continue
            gamma_calls_by_strike[s] = gamma_calls_by_strike.get(s, 0.0) + g_usd
            oi_calls_by_strike[s] = oi_calls_by_strike.get(s, 0) + oi
            gamma_total_calls += g_usd
            strike_exp_gamma.setdefault(s, {})
            strike_exp_gamma[s][exp] = strike_exp_gamma[s].get(exp, 0.0) + g_usd

    if not gamma_calls_by_strike:
        return []

    def _neighbors(center):
        radius = (cluster_atr * atr10) if atr10 and atr10 > 0 else 0.0
        return sorted([k for k in gamma_calls_by_strike.keys() if abs(k - center) <= radius])

    total_oi = sum(oi_calls_by_strike.values()) or 1

    top_strikes = sorted(gamma_calls_by_strike.keys(),
                         key=lambda s: gamma_calls_by_strike[s],
                         reverse=True)[:max(1, top_n)]

    out = []
    for s in top_strikes:
        g_s = gamma_calls_by_strike[s]
        exp_dom = None
        if s in strike_exp_gamma and strike_exp_gamma[s]:
            exp_dom = max(strike_exp_gamma[s].items(), key=lambda kv: kv[1])[0]
        nbrs = _neighbors(s)
        cluster_gamma = sum(gamma_calls_by_strike[n] for n in nbrs) if nbrs else g_s

        item = {
            "level": round(float(s), 4),
            "expiration": exp_dom,
            "option_details": _wall_option_details(s, "call", sampled_chains, last_price),
            "gamma_usd_millions": round(g_s / 1e6, 3),
            "gamma_share_pct": round(100.0 * g_s / gamma_total_calls, 1) if gamma_total_calls > 0 else None,
            "oi": oi_calls_by_strike.get(s),
            "oi_share_pct": round(100.0 * (oi_calls_by_strike.get(s, 0)) / total_oi, 1) if total_oi > 0 else None,
            "cluster_neighbors": nbrs,
            "cluster_gamma_usd": round(cluster_gamma / 1e6, 3),
            "cluster_share_pct": round(100.0 * cluster_gamma / gamma_total_calls, 1) if gamma_total_calls > 0 else None,
            "distance": round(100.0 * (float(s) - last_price) / last_price, 2) if last_price else None
        }
        out.append(item)

    return out

def _publish_symbol_json(symbol: str, payload: dict) -> str | None:
    """
    Sube tickers/{SYMBOL}.json al repo de GitHub y devuelve la URL RAW pública.
    (Reemplaza la versión anterior que escribía en GCS).
    """
    try:
        sym = (symbol or "UNKNOWN").upper()
        path = f"tickers/{sym}.json"
        url  = f"{GH_API}/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        # Si el fichero ya existe, necesitamos su 'sha' para actualizarlo
        sha = None
        r = requests.get(url, headers=headers, params={"ref": GH_BRANCH}, timeout=10)
        if r.status_code == 200:
            try:
                sha = r.json().get("sha")
            except Exception:
                sha = None

        content_b64 = base64.b64encode(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")

        body = {
            "message": f"mirror: update {sym}",
            "content": content_b64,
            "branch": GH_BRANCH
        }
        if sha:
            body["sha"] = sha  # requerido por GitHub para overwrite

        r = requests.put(url, headers=headers, json=body, timeout=15)
        r.raise_for_status()

        # URL RAW estable para leer desde fuera (incluido yo)
        return f"https://raw.githubusercontent.com/{GH_OWNER}/{GH_REPO}/{GH_BRANCH}/{path}"
    except Exception as e:
        tlogger.error(f"[mirror/github] publish failed: {e}", exc_info=True)
        return None


def _publish_symbol_json_old(symbol: str, payload: dict) -> str | None:
    """Guarda tickers/{SYMBOL}.json (overwrite) y devuelve URL pública."""
    try:
        sym = (symbol or "UNKNOWN").upper()
        key = f"tickers/{sym}.json"
        bucket = _storage.bucket(BUCKET_NAME)
        blob = bucket.blob(key)
        blob.cache_control = "no-store"
        blob.content_type = "application/json"
        blob.upload_from_string(json.dumps(payload), content_type="application/json")
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{key}"
    except Exception as e:
        tlogger.error(f"[mirror] publish failed: {e}", exc_info=True)
        return None

def _publish_advice_text(symbol: str, content: str) -> str | None:
    try:
        sym = (symbol or "UNKNOWN").upper()
        key = f"advice/{sym}.md"
        b = _storage.bucket(BUCKET_NAME)
        blob = b.blob(key)
        blob.cache_control = "no-store"

        # 👇 Fuerza el mismo Content-Type en el upload
        blob.upload_from_string(
            content.encode("utf-8"),
            content_type="text/markdown; charset=utf-8",
        )

        # opcional si quieres que el enlace sea público y no tienes bucket público:
        # blob.make_public()

        return f"https://storage.googleapis.com/{BUCKET_NAME}/{key}"
    except Exception as e:
        logging.error(f"[advice] publish failed: {e}", exc_info=True)
        return None

def _advise_with_gemini(symbol: str, payload: dict, pt_media: float = 127.0) -> str:
    # 1) Recorta entrada para no disparar tokens
    payload_shrunk = dict(payload)
    payload_shrunk["call_walls_top"] = (payload.get("call_walls_top") or [])[:2]
    payload_shrunk["resistances"] = (payload.get("resistances") or [])[:3]
    json_min = json.dumps(payload_shrunk, separators=(",", ":"), ensure_ascii=False)

    system_txt = (
        "Eres analista técnico. Devuelve SOLO texto plano en el formato pedido. "
        "Da 2–3 precios (B ≥ +5%, C ≥ +8%), condiciones de seguir/salir y una nota/10."
    )
    user_txt = (
        f"Formato:\n"
        f"🔖 {{SYMBOL}} | Spot ${{price}} | {{as_of}}\n"
        f"🧠 Análisis técnico actual: ...\n"
        f"🎯 Plan A: $... (...%) — ...\n"
        f"↘️ Plan B: $... (...%) — ...\n"
        f"↘️ Plan C: $... (...%) — ...\n"
        f"⚠️ Riesgos: ...\n\n"
        f"PT medio de analistas top: {pt_media}\n\n"
        f"JSON:\n{json_min}"
    )

    cfg = GenerateContentConfig(
        response_mime_type="text/plain",
        temperature=0.2,
        max_output_tokens=3000,  # sube margen de salida
        system_instruction=[{"text": system_txt}],
    )

    def _log_usage(resp):
        try:
            um = getattr(resp, "usage_metadata", None)
            frs = [getattr(c, "finish_reason", None) for c in (getattr(resp, "candidates", []) or [])]
            tlogger.info("[gemini] finish=%s usage=%s feedback=%s", frs, um, getattr(resp, "prompt_feedback", None))
        except Exception:
            pass

    def _finished_max_tokens(resp):
        try:
            return any(getattr(c, "finish_reason", None) == "MAX_TOKENS" for c in (getattr(resp, "candidates", []) or []))
        except Exception:
            return False

    def _text(resp):
        try:
            return (resp.text or "").strip()
        except Exception:
            return ""

    # Intento 1
    resp = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[{"role": "user", "parts": [{"text": user_txt}]}],
        config=cfg,
    )
    _log_usage(resp)
    text = _text(resp)

    # Fallback si se quedó sin tokens o vacío: input aún más pequeño
    if not text or _finished_max_tokens(resp):
        mini = {
            "symbol": payload["symbol"],
            "latest_price": payload["latest_price"],
            "as_of": payload["as_of"],
            "res": [{"type": r["type"], "level": r["level"], "distance": r["distance"]} for r in (payload.get("resistances") or [])[:2]],
            "cw": (payload.get("call_walls_top") or [])[:1],
            "rsi14": (payload.get("technicals") or {}).get("rsi14"),
            "sma": (payload.get("technicals") or {}).get("sma"),
            "em": (payload.get("options") or {}).get("expected_move_1w"),
        }
        user_txt2 = user_txt.rsplit("JSON:", 1)[0] + "JSON:\n" + json.dumps(mini, separators=(",", ":"), ensure_ascii=False)
        resp2 = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": user_txt2}]}],
            config=cfg,
        )
        _log_usage(resp2)
        text = _text(resp2)

    return text or f"🔖 {symbol} | Spot ${payload['latest_price']} | {payload['as_of']}\nNo se pudo generar el análisis. Reintenta en unos minutos."


def _volume_20d_package(days: list, quote: dict | None = None):
    """
    Devuelve un bloque listo para technicals.volume basado en los ÚLTIMOS 20 días COMPLETOS.
    - NO compara intradía con la media.
    - Si hay volumen intradía en el quote, lo expone solo como informativo.
    """
    try:
        # Filter the same completed NYSE sessions used by history and reactions.
        days = _complete_daily_bars(days)
        if not days or len(days) < 20:
            return {
                "note": "insufficient_history_20d",
                "avg_20d": None,
                "median_20d": None,
                "avg_dollar_20d": None,
                "last_complete_day": None,
                "series": None,
                "current_session": None
            }

        # Últimos 20 días COMPLETOS (history daily suele ser sesión cerrada)
        tail = days[-20:]
        vols = []
        dollar_vols = []
        for d in tail:
            v = _to_float(d.get("volume")) or 0.0
            c = _to_float(d.get("close"))
            vols.append(v)
            dollar_vols.append((c * v) if (c is not None) else None)

        # Resumen 20d
        avg_20d = (sum(vols) / 20.0) if vols else None
        med_20d = _median(vols)
        dv_vals = [x for x in dollar_vols if x is not None]
        avg_dv_20d = (sum(dv_vals) / len(dv_vals)) if dv_vals else None

        # Último día completo (el más reciente de history)
        last_day = days[-1]
        last_day_vol = _to_float(last_day.get("volume"))
        last_day_date = last_day.get("date")
        rel_to_20d = (last_day_vol / avg_20d) if (last_day_vol is not None and avg_20d) else None

        # Volumen intradía (del quote) SOLO informativo (no comparable)
        live_vol = None
        if isinstance(quote, dict):
            live_vol = _to_float(quote.get("volume"))
        current_session = {"shares": live_vol, "comparable_to_avg_20d": False} if live_vol is not None else None

        return {
            "avg_20d": round(avg_20d, 2) if avg_20d is not None else None,
            "median_20d": round(med_20d, 2) if med_20d is not None else None,
            "avg_dollar_20d": round(avg_dv_20d, 2) if avg_dv_20d is not None else None,
            "last_complete_day": {
                "date": last_day_date,
                "shares": int(last_day_vol) if last_day_vol is not None else None,
                "rel_to_20d": round(rel_to_20d, 3) if rel_to_20d is not None else None
            },
            # Serie completa (mejor para la IA que resúmenes cortos)
            "series": {
                "shares_20d": [int(v) for v in vols],
                "dollar_volume_20d": [round(x, 2) if x is not None else None for x in dollar_vols]
            },
            # Intradía: informativo; NO comparar con media
            "current_session": current_session,
            "note": "ratios calculados contra último día COMPLETO; intradía solo informativo"
        }
    except Exception as e:
        tlogger.error(f"[volume_20d_package] error: {e}", exc_info=True)
        return {
            "error": "volume_20d_failed",
            "avg_20d": None,
            "median_20d": None,
            "avg_dollar_20d": None,
            "last_complete_day": None,
            "series": None,
            "current_session": None
        }


def _put_call_oi_overview(symbol: str, top_expirations: int | None = None):
    expirations = _tradier_option_expirations(symbol) or []
    if top_expirations:
        expirations = expirations[:max(1, top_expirations)]
    return _put_call_oi_overview_for_exp_list(
        symbol, expirations, "top_expirations" if top_expirations else "all_available")

def _future_expirations_with_dte(symbol: str):
    """Devuelve [(exp_str, dte)] solo futuras, ordenadas por DTE asc."""
    exps = _tradier_option_expirations(symbol) or []
    today = datetime.utcnow().date()
    out = []
    for e in exps:
        try:
            dt = datetime.strptime(e, "%Y-%m-%d").date()
            dte = (dt - today).days
            if dte >= 0:
                out.append((e, dte))
        except Exception:
            continue
    out.sort(key=lambda x: x[1])
    return out


def _put_call_oi_overview_for_exp_list(symbol: str, expirations: list[str], scope_label: str):
    """Unknown OI is not zero; expose partial known totals only with explicit labels."""
    rows = []
    buckets = {key: [] for key in ("0_7", "8_30", "31_60", "61_plus")}
    def aggregate(items):
        puts = sum(row["puts"] for row in items) if all(row["puts"] is not None for row in items) else None
        calls = sum(row["calls"] for row in items) if all(row["calls"] is not None for row in items) else None
        return {"puts": puts, "calls": calls,
                "ratio": round(puts / calls, 3) if puts is not None and calls else None,
                "expirations": [row["expiration"] for row in items]}
    for exp in expirations:
        chain = _tradier_options_chain(symbol, exp) or []
        puts, calls = _oi_total(chain, "put"), _oi_total(chain, "call")
        dte = _days_to(exp)
        row = {"expiration": exp, "dte": dte, "puts": puts, "calls": calls,
               "ratio": round(puts / calls, 3) if puts is not None and calls else None,
               "unknown_oi_contracts": sum(o.get("oi") is None for o in chain),
               "known_put_oi": sum(o["oi"] for o in chain if o["option_type"] == "put" and o.get("oi") is not None),
               "known_call_oi": sum(o["oi"] for o in chain if o["option_type"] == "call" and o.get("oi") is not None)}
        rows.append(row)
        if dte is not None and dte >= 0:
            key = "0_7" if dte <= 7 else "8_30" if dte <= 30 else "31_60" if dte <= 60 else "61_plus"
            buckets[key].append(row)
    total = aggregate(rows)
    return {"scope": scope_label, "expirations_considered": expirations,
            "total_put_oi": total["puts"], "total_call_oi": total["calls"], "ratio": total["ratio"],
            "unknown_oi_contracts": sum(row["unknown_oi_contracts"] for row in rows),
            "dte_buckets": {key: aggregate(items) for key, items in buckets.items()},
            "per_expiration": rows}

def _put_call_oi_views(symbol: str, top_expirations: int, max_dte: int, include_all: bool):
    """
    Devuelve un objeto con varias vistas:
      - near_term: primeras N expiraciones (por DTE asc).
      - thru_60d: todas las expiraciones con DTE <= max_dte.
      - all: (opcional) todas las futuras.
    Expone además 'ratio' y totales del near_term a nivel superior (compatibilidad).
    """
    exps_dte = _future_expirations_with_dte(symbol)  # [(exp, dte)]
    if not exps_dte:
        return {"default_scope": "near_term", "near_term": {}, "thru_60d": {}}

    # near-term
    n = max(1, int(top_expirations or 1))
    near_list = [e for (e, _d) in exps_dte[:n]]

    # thru_60d (o el max_dte configurado)
    if max_dte and max_dte > 0:
        thru_list = [e for (e, d) in exps_dte if d <= max_dte]
    else:
        thru_list = []

    # all futuras (opcional)
    all_list = [e for (e, _d) in exps_dte]

    views = {
        "near_term": _put_call_oi_overview_for_exp_list(symbol, near_list, "near_term"),
        "thru_60d": _put_call_oi_overview_for_exp_list(symbol, thru_list, f"thru_{max_dte}d")
    }
    if include_all:
        views["all"] = _put_call_oi_overview_for_exp_list(symbol, all_list, "all_future")

    # Compatibilidad: publica el ratio y totales de near_term en el nivel superior
    default = views.get("near_term", {})
    views["default_scope"] = "near_term"
    views["ratio"] = default.get("ratio")
    views["total_put_oi"] = default.get("total_put_oi")
    views["total_call_oi"] = default.get("total_call_oi")
    return views


def _basic_stats(vals: list[float] | None):
    xs = [v for v in (vals or []) if v is not None]
    if not xs:
        return {"count": 0, "mean": None, "median": None, "up_rate_pct": None, "p05": None, "p95": None}
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    mean = sum(xs_sorted) / n
    median = xs_sorted[n//2] if n % 2 == 1 else 0.5*(xs_sorted[n//2 - 1] + xs_sorted[n//2])
    up_rate = 100.0 * sum(1 for v in xs_sorted if v > 0) / n
    def _percentile(p):
        if n == 1: return xs_sorted[0]
        k = (p/100.0)*(n-1)
        f = int(k)
        c = min(f+1, n-1)
        return xs_sorted[f] + (xs_sorted[c]-xs_sorted[f])*(k-f)
    return {
        "count": n,
        "mean": round(mean, 3),
        "median": round(median, 3),
        "up_rate_pct": round(up_rate, 2),
        "p05": round(_percentile(5), 3),
        "p95": round(_percentile(95), 3)
    }


def _forward_returns_t1_package(days: list, lookback: int = 252):
    """
    Calcula t+1:
      - close_from_close_pct = 100*(C[t+1]-C[t])/C[t]
      - high_from_close_pct  = 100*(H[t+1]-C[t])/C[t]
      - (alt) close_from_open_pct = 100*(C[t+1]-O[t+1])/O[t+1]
    Devuelve serie (recortada a 'lookback'), stats y el último dato ('latest').
    """
    try:
        if not days or len(days) < 2:
            return {
                "lookback_days": 0,
                "series": None,
                "stats": None,
                "latest": None,
                "note": "insufficient_history_t1"
            }

        n = len(days)
        # series completas (longitud n-1)
        t_dates = []
        t1_dates = []
        s_close_close = []
        s_high_close = []
        s_close_open = []

        for i in range(0, n - 1):
            d_t  = days[i]
            d_t1 = days[i + 1]
            c_t  = _to_float(d_t.get("close"))
            c_t1 = _to_float(d_t1.get("close"))
            h_t1 = _to_float(d_t1.get("high"))
            o_t1 = _to_float(d_t1.get("open"))
            t_dates.append(d_t.get("date"))
            t1_dates.append(d_t1.get("date"))

            # close_from_close
            if c_t is not None and c_t != 0 and c_t1 is not None:
                s_close_close.append(100.0 * (c_t1 - c_t) / c_t)
            else:
                s_close_close.append(None)

            # high_from_close
            if c_t is not None and c_t != 0 and h_t1 is not None:
                s_high_close.append(100.0 * (h_t1 - c_t) / c_t)
            else:
                s_high_close.append(None)

            # alt: close_from_open
            if o_t1 is not None and o_t1 != 0 and c_t1 is not None:
                s_close_open.append(100.0 * (c_t1 - o_t1) / o_t1)
            else:
                s_close_open.append(None)

        # recorte a lookback por el final (mantén alineadas las fechas)
        if lookback and lookback > 0:
            start = max(0, len(s_close_close) - lookback)
        else:
            start = 0

        series = {
            "anchor_dates": t_dates[start:],
            "t1_dates": t1_dates[start:],
            "t1_close_from_close_pct": [round(v, 3) if v is not None else None for v in s_close_close[start:]],
            "t1_high_from_close_pct":  [round(v, 3) if v is not None else None for v in s_high_close[start:]],
            "t1_close_from_open_pct":  [round(v, 3) if v is not None else None for v in s_close_open[start:]],
        }

        stats = {
            "close_from_close": _basic_stats(s_close_close[start:]),
            "high_from_close":  _basic_stats(s_high_close[start:]),
            "close_from_open":  _basic_stats(s_close_open[start:])
        }

        # último dato observable (si existe)
        latest = None
        if series["t1_close_from_close_pct"]:
            latest = {
                "anchor_date": series["anchor_dates"][-1],
                "t1_date": series["t1_dates"][-1],
                "close_from_close_pct": series["t1_close_from_close_pct"][-1],
                "high_from_close_pct":  series["t1_high_from_close_pct"][-1],
                "close_from_open_pct":  series["t1_close_from_open_pct"][-1]
            }

        return {
            "lookback_days": len(series["t1_dates"]),
            "series": series,
            "stats": stats,
            "latest": latest
        }
    except Exception as e:
        tlogger.error(f"[forward_returns_t1_package] error: {e}", exc_info=True)
        return {
            "lookback_days": 0,
            "series": None,
            "stats": None,
            "latest": None,
            "error": "forward_returns_failed"
        }

def _realized_vols_package(days: list, atr10: float | None = None, em_abs_1w: float | None = None, em_pct_1w: float | None = None):
    """
    Calcula volatilidad realizada (RV) a 20 y 60 días usando log-returns diarios:
      rvN_annual_pct = 100 * std( ln(C[t]/C[t-1]) , N ) * sqrt(252)
    Devuelve además equivalentes semanales (÷sqrt(52)) y ratios contra EM 1W y ATR10.
    """
    try:
        closes = [_to_float(d.get("close")) for d in _complete_daily_bars(days)]
        # Construye log-returns
        rets = []
        for i in range(1, len(closes)):
            c0, c1 = closes[i-1], closes[i]
            if c0 is None or c1 is None or c0 <= 0 or c1 <= 0:
                rets.append(None)
            else:
                rets.append(math.log(c1 / c0))

        def _rv_annual_pct(n: int):
            xs = [r for r in rets[-n:] if r is not None]
            if len(xs) != n:
                return None
            sd = statistics.pstdev(xs)  # poblacional está bien para este uso
            return 100.0 * sd * math.sqrt(252.0)

        rv20 = _rv_annual_pct(20)
        rv60 = _rv_annual_pct(60)

        def _wk(x):
            return (x / math.sqrt(52.0)) if x is not None else None

        rv20_w = _wk(rv20)
        rv60_w = _wk(rv60)

        # Ratios
        iv_to_rv = (em_pct_1w / rv20_w) if (em_pct_1w is not None and rv20_w and rv20_w > 0) else None
        em_to_atr = (em_abs_1w / atr10) if (em_abs_1w is not None and atr10 and atr10 > 0) else None

        return {
            "rv20_annual_pct": round(rv20, 3) if rv20 is not None else None,
            "rv60_annual_pct": round(rv60, 3) if rv60 is not None else None,
            "rv20_weekly_pct": round(rv20_w, 3) if rv20_w is not None else None,
            "rv60_weekly_pct": round(rv60_w, 3) if rv60_w is not None else None,
            "em_pct_1w": round(em_pct_1w, 3) if em_pct_1w is not None else None,
            "em_abs_1w": round(em_abs_1w, 4) if em_abs_1w is not None else None,
            "iv_to_rv_ratio": round(iv_to_rv, 3) if iv_to_rv is not None else None,
            "em_to_atr_ratio": round(em_to_atr, 3) if em_to_atr is not None else None,
            "windows": {"rv": [20, 60]},
            "units": {
                "rv_annual_pct": "percent",
                "rv_weekly_pct": "percent",
                "em_pct_1w": "percent",
                "em_abs_1w": "dollars"
            },
            "method": "std(log_returns_daily) * sqrt(252); weekly = annual/sqrt(52)"
        }
    except Exception as e:
        tlogger.error(f"[realized_vols_package] error: {e}", exc_info=True)
        return {
            "error": "realized_vol_failed"
        }

def _normal_cdf(x: float):
    try:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    except Exception:
        return None

def _annotate_resistances_touch_prob_1w(resistances: list, vols: dict | None):
    """
    Anota en cada resistencia:
      - prob_touch_1w_pct (0–100) si distance>0 y hay sigma.
      - meta.touch_prob_1w con sigma y z.
    Sigma: preferimos EM 1W (%); si falta, usamos RV20 semanal (%).
    """
    if not isinstance(resistances, list) or not resistances:
        return
    sigma_pct = None
    sigma_source = None
    try:
        if vols:
            if vols.get("em_pct_1w") is not None:
                sigma_pct = float(vols["em_pct_1w"])
                sigma_source = "em_pct_1w"
            elif vols.get("rv20_weekly_pct") is not None:
                sigma_pct = float(vols["rv20_weekly_pct"])
                sigma_source = "rv20_weekly_pct"
    except Exception:
        sigma_pct = None
        sigma_source = None

    for r in resistances:
        try:
            dist = r.get("distance")  # ya está en %
            z = None
            p = None
            if dist is not None and sigma_pct is not None and sigma_pct > 0 and dist > 0:
                z = dist / sigma_pct
                cdf = _normal_cdf(z)
                if cdf is not None:
                    p = max(0.0, min(100.0, 100.0 * (1.0 - cdf)))  # % prob de tocar

            if p is not None:
                r["prob_touch_1w_pct"] = round(p, 1)

            r.setdefault("meta", {})
            r["meta"]["touch_prob_1w"] = {
                "sigma_pct": round(sigma_pct, 3) if sigma_pct is not None else None,
                "sigma_source": sigma_source,
                "z": round(z, 3) if z is not None else None
            }
        except Exception as e:
            tlogger.error(f"[touch_prob_1w] error on {r.get('type')}: {e}", exc_info=True)

def _pct(a, b):
    try:
        if b is None or b == 0 or a is None:
            return None
        return 100.0 * (a - b) / abs(b)
    except Exception:
        return None


def _last_not_none(xs: list):
    if not xs:
        return None
    for v in reversed(xs):
        if v is not None:
            return v
    return None


def _trend_structure_package(closes: list, sma20: float | None, sma50: float | None, sma200: float | None, bb: dict | None):
    """
    Señales ligeras de tendencia/estructura:
      - above_sma200 (bool)
      - price_vs_sma{20,50,200} (pct)
      - price_20d_change_pct, price_50d_change_pct
      - bollinger_pos_pct: 0=lower, 50=middle, 100=upper
    """
    try:
        px = _last_not_none(closes)
        out = {}

        out["above_sma200"] = (px is not None and sma200 is not None and px > sma200)

        out["price_vs_sma"] = {
            "20": round(_pct(px, sma20), 2) if (px is not None and sma20 is not None) else None,
            "50": round(_pct(px, sma50), 2) if (px is not None and sma50 is not None) else None,
            "200": round(_pct(px, sma200), 2) if (px is not None and sma200 is not None) else None,
        }

        def _slope_price(n):
            if not closes or len([c for c in closes if c is not None]) < n+1:
                return None
            # Usa el último valor no-nulo y el valor n-periodos atrás
            # (buscamos índices desde el final hacia atrás)
            try:
                # índice del último close válido
                idx_last = next(i for i in range(len(closes)-1, -1, -1) if closes[i] is not None)
                # índice n-periodos atrás (mismo offset)
                idx_prev = idx_last - n
                if idx_prev < 0 or closes[idx_prev] is None:
                    return None
                return _pct(closes[idx_last], closes[idx_prev])
            except StopIteration:
                return None

        out["price_20d_change_pct"] = round(_slope_price(20), 2) if _slope_price(20) is not None else None
        out["price_50d_change_pct"] = round(_slope_price(50), 2) if _slope_price(50) is not None else None

        # Posición dentro de las bandas de Bollinger
        bb_pos = None
        if bb and bb.get("upper") is not None and bb.get("lower") is not None and px is not None:
            rng = (bb["upper"] - bb["lower"])
            if rng and rng > 0:
                bb_pos = 100.0 * (px - bb["lower"]) / rng
                bb_pos = max(0.0, min(100.0, bb_pos))
        out["bollinger_pos_pct"] = round(bb_pos, 1) if bb_pos is not None else None

        return out
    except Exception as e:
        tlogger.error(f"[trend_structure] error: {e}", exc_info=True)
        return {}


def _liquidity_package(volume20_block: dict | None, quote: dict | None, last_price: float | None):
    """
    Liquidez básica:
      - adv20_usd: average dollar volume 20d (si está disponible en technicals.volume)
      - bid_ask_spread_abs / pct (si hay bid/ask)
      - mid_price para referencia
    """
    try:
        adv20 = None
        if isinstance(volume20_block, dict):
            adv20 = volume20_block.get("avg_dollar_20d")

        bid = _to_float((quote or {}).get("bid"))
        ask = _to_float((quote or {}).get("ask"))
        mid = 0.5 * (bid + ask)
        spread_abs = ask - bid
        spread_pct = (spread_abs / mid) * 100.0 if mid else None
        if bid is not None and ask is not None and ask > 0 and bid >= 0 and ask >= bid:
            mid = 0.5 * (bid + ask)
            spread_abs = ask - bid
            base = mid if mid and mid > 0 else last_price
            spread_pct = _pct(ask, bid) if (ask and bid is not None) else None
            # spread_pct como (ask-bid)/base * 100
            if spread_pct is None and base:
                spread_pct = 100.0 * (spread_abs / base)

        return {
            "adv20_usd": round(adv20, 2) if adv20 is not None else None,
            "bid_ask": {
                "bid": bid,
                "ask": ask,
                "mid": round(mid, 4) if mid is not None else None,
                "spread_abs": round(spread_abs, 4) if spread_abs is not None else None,
                "spread_pct": round(spread_pct, 3) if spread_pct is not None else None
            }
        }
    except Exception as e:
        tlogger.error(f"[liquidity] error: {e}", exc_info=True)
        return {"error": "liquidity_failed"}


def _relative_strength_vs_spy(symbol_days: list, start: str, end: str, lookbacks: list[int] = [20, 60]):
    """
    Fuerza relativa simplificada vs SPY: devuelve diff de retorno (%) del símbolo menos SPY
    para ventanas en `lookbacks`, usando fechas alineadas por cierre.
    """
    try:
        spy = _tradier_history_daily("SPY", start, end) or []
        if not symbol_days or not spy:
            return {"vs_spy": {}}

        # Diccionarios fecha->close
        sym_map = {d.get("date"): _to_float(d.get("close")) for d in symbol_days}
        spy_map = {d.get("date"): _to_float(d.get("close")) for d in spy}

        # Fechas comunes ordenadas
        dates = sorted([dt for dt in sym_map.keys() if dt in spy_map and sym_map[dt] is not None and spy_map[dt] is not None])
        if len(dates) < 2:
            return {"vs_spy": {}}

        def _rel_ret(n):
            if len(dates) < n + 1:
                return None
            d0 = dates[-(n+1)]
            d1 = dates[-1]
            s0, s1 = sym_map[d0], sym_map[d1]
            p0, p1 = spy_map[d0], spy_map[d1]
            if not s0 or not s1 or not p0 or not p1:
                return None
            rsym = 100.0 * (s1 - s0) / s0
            rspy = 100.0 * (p1 - p0) / p0
            return round(rsym - rspy, 2)

        out = {"vs_spy": {}}
        for n in lookbacks:
            out["vs_spy"][f"{n}d_diff_pct"] = _rel_ret(n)
        return out
    except Exception as e:
        tlogger.error(f"[relative_strength_vs_spy] error: {e}", exc_info=True)
        return {"vs_spy": {}}

# ==================== SOPORTES: helpers simétricos ====================

def _find_52w_low(days: list, lookback: int = 252):
    if not days:
        return None, None
    window = days[-lookback:] if len(days) >= lookback else days[:]
    best = None
    best_date = None
    for d in window:
        lo = _to_float(d.get("low"))
        if lo is None:
            continue
        if best is None or lo < best:
            best = lo
            best_date = d.get("date")
    return best, best_date


def _count_retests_low(level: float, level_date: str, days: list, tol: float) -> int:
    if level is None or level_date is None:
        return 0
    count = 0
    started = False
    for d in days:
        date = d.get("date")
        if not started:
            if date == level_date:
                started = True
            continue
        lo = _to_float(d.get("low"))
        if lo is None:
            continue
        if abs(lo - level) <= tol:
            count += 1
    return count


def _find_swing_lows(days: list, k: int = 2):
    swings = []
    n = len(days)
    if n < 2*k + 1:
        return swings
    for i in range(k, n - k):
        lo = _to_float(days[i]["low"])
        if lo is None:
            continue
        is_trough = True
        for j in range(1, k + 1):
            lo_prev = _to_float(days[i - j]["low"])
            lo_next = _to_float(days[i + j]["low"])
            if lo_prev is None or lo_next is None or lo > lo_prev or lo > lo_next:
                is_trough = False
                break
        if is_trough:
            swings.append({
                "date":   days[i]["date"],
                "price":  lo,
                "volume": _to_float(days[i]["volume"]) or 0.0
            })
    return swings


def _cluster_swing_lows(swings: list, tol: float):
    if not swings:
        return []
    swings_sorted = sorted(swings, key=lambda x: x["price"])
    clusters = []
    cur = [swings_sorted[0]]

    def _level_of(cluster):
        return _median([s["price"] for s in cluster])

    for s in swings_sorted[1:]:
        center = _level_of(cur)
        if abs(s["price"] - center) <= tol:
            cur.append(s)
        else:
            clusters.append(cur)
            cur = [s]
    clusters.append(cur)

    out = []
    for cl in clusters:
        prices = [s["price"] for s in cl]
        vols   = [s["volume"] for s in cl]
        dates  = [s["date"]   for s in cl]
        out.append({
            "level": _median(prices),
            "touches": len(cl),
            "first_date": min(dates),
            "last_date":  max(dates),
            "member_dates": sorted(dates),
            "avg_volume": (sum(vols) / len(vols)) if vols else 0.0
        })
    return out


def _observe_support_origins(requested, days, atr10, as_of, volume_profile=None):
    """Reuses downloaded completed rows; no ranking, price-distance filter or I/O."""
    closed = _complete_daily_bars(days, as_of)
    history_atr = _atr10_from_daily(closed) or 0.0
    tol = 0.2 * history_atr if history_atr > 0 else 0.25
    clusters = _cluster_swing_lows(_find_swing_lows(closed[-126:], k=2), tol)
    gaps = _find_bullish_gaps(closed[-252:])
    pool = _support_origin_pool(closed, clusters, gaps)
    observations = _observe_dated_supports(requested, closed, pool, as_of.isoformat())
    records = [row['source_record'] for row in observations if row['status'] == 'available']
    expected_last = latest_completed_session(as_of).isoformat()
    for record in records:
        meta = record['meta']
        meta['tolerance'] = tol
        if record['type'] == 'gap_up_lower':
            following = [row for row in closed if row['date'] > meta['gap_date']]
            since_gap = [row for row in closed if row['date'] >= meta['gap_date']]
            if not _support_continuous_history(since_gap, expected_last):
                meta['gap_history_status'] = 'unavailable_missing_following_session'
            elif all(_support_valid_bar(row) for row in following):
                touches = [row['date'] for row in following if abs(row['low'] - record['level']) <= tol]
                meta['filled'] = any(row['close'] < record['level'] - tol for row in following)
                meta['touches_since_gap'] = len(touches)
                meta['last_touch_date'] = touches[-1] if touches else None
            else:
                meta['gap_history_status'] = 'unavailable_invalid_following_ohlcv'
    _annotate_support_evidence(records, [], closed, atr10, volume_profile or {})
    # Availability of an exact formation does not authenticate missing or malformed
    # remote bars elsewhere in the historical reaction window. Keep this guard in
    # the new directed lane; legacy candidate measurements remain unchanged.
    history = closed[-252:]
    history_reason = ('missing_historical_session' if not _support_continuous_history(history, expected_last)
                      else 'invalid_historical_ohlcv' if any(not _support_valid_bar(row) for row in history)
                      else None)
    if history_reason:
        for record in records:
            record['meta']['historical_reaction'] = {
                'status': 'unavailable', 'reason': history_reason,
                'lookback_sessions': min(252, len(closed))}
    # Metadata on ordinary candidates is also a verified dated formation, not
    # merely a selector's proposed grouping over possibly incomplete rows.
    return observations, [record for record in pool if _support_verified_identity(record, closed) is not None]


def _select_range_bottom_cluster(clusters: list, last_price: float, today_low: float, tol: float, median_vol: float, min_distance_pct: float = 0.05):
    if not clusters or last_price is None:
        return None
    threshold = last_price * (1.0 - max(0.0, min_distance_pct))
    cands = [c for c in clusters if c["touches"] >= 2 and c["level"] <= threshold]
    if not cands:
        return None
    def _score(c):
        dist  = abs(last_price - c["level"])
        try:
            recency_days = (datetime.utcnow() - datetime.strptime(c["last_date"], "%Y-%m-%d")).days
            recency = max(0.0, 1.0 - min(recency_days, 90)/90.0)
        except Exception:
            recency = 0.0
        touches = c["touches"]
        vol_factor = (c["avg_volume"] / median_vol) if median_vol else 1.0
        return 1.5*touches + 1.0*recency + 0.5*min(vol_factor, 2.0) - 0.3*(dist / max(tol, 1e-6))
    cands.sort(key=_score, reverse=True)
    best = cands[0]
    testing_now = (today_low is not None and abs(today_low - best["level"]) <= tol)
    return {
        "level": best["level"],
        "touches": best["touches"],
        "first_date": best["first_date"],
        "last_date": best["last_date"],
        "vol_factor": (best["avg_volume"] / median_vol) if median_vol else None,
        "testing_now": testing_now
    }


def _find_bullish_gaps(days: list):
    gaps = []
    for i in range(1, len(days)):
        prev = days[i-1]
        cur  = days[i]
        lo_cur  = _to_float(cur.get("low"))
        hi_prev = _to_float(prev.get("high"))
        vol_cur = _to_float(cur.get("volume")) or 0.0
        if lo_cur is None or hi_prev is None:
            continue
        if lo_cur > hi_prev:  # gap-up estricto
            upper = lo_cur
            lower = hi_prev
            size  = upper - lower
            gaps.append({
                "date": cur.get("date"),
                "upper": upper,
                "lower": lower,
                "size":  size,
                "volume": vol_cur
            })
    return gaps


def _select_bullish_gap_support(gaps: list, full_days: list, last_price: float, today_low: float, tol: float, min_distance_pct: float = 0.05):
    if not gaps or last_price is None:
        return None
    median_vol = _median([_to_float(d.get("volume")) or 0.0 for d in full_days]) or 0.0
    threshold = last_price * (1.0 - max(0.0, min_distance_pct))
    # Para soporte usamos el borde INFERIOR del gap-up (level = lower)
    cands = [g for g in gaps if g["lower"] <= threshold]
    if not cands:
        return None
    def _score(g):
        dist  = abs(last_price - g["lower"])
        size  = g["size"]
        try:
            recency_days = (datetime.utcnow() - datetime.strptime(g["date"], "%Y-%m-%d")).days
            recency = max(0.0, 1.0 - min(recency_days, 120)/120.0)
        except Exception:
            recency = 0.0
        return (1.5*size - 0.3*(dist / max(tol, 1e-6)) + 1.0*recency)
    cands.sort(key=_score, reverse=True)
    best = cands[0]
    vol_factor = (best["volume"] / median_vol) if median_vol else None
    size_pct = 100.0 * best["size"] / last_price if last_price else 0.0
    filled = False
    touches_since = 0
    last_touch_date = None
    passed = False
    for d in full_days:
        if not passed:
            if d.get("date") == best["date"]:
                passed = True
            continue
        lo = _to_float(d.get("low"))
        cl = _to_float(d.get("close"))
        if lo is not None and abs(lo - best["lower"]) <= tol:
            touches_since += 1
            last_touch_date = d.get("date")
        if cl is not None and cl < best["lower"] - tol:
            filled = True
    testing_now = (today_low is not None and abs(today_low - best["lower"]) <= tol)
    return {
        "date": best["date"],
        "level": best["lower"],   # soporte en borde inferior del gap-up
        "upper": best["upper"],
        "lower": best["lower"],
        "size":  best["size"],
        "size_pct": size_pct,
        "vol_factor": vol_factor,
        "touches_since": touches_since,
        "last_touch_date": last_touch_date,
        "testing_now": testing_now,
        "filled": filled
    }


def _testing_today_low(days: list, level: float, tol: float):
    if not days:
        return False
    lo_today = _to_float(days[-1].get("low"))
    return (lo_today is not None and abs(lo_today - level) <= tol)


def _select_avwap_event_support(
    days: list,
    gap_days: list,
    gaps_up: list,
    atr10: float,
    last_price: float,
    tol: float,
    level_52w_low_date: str,
    range_clusters_bottom: list,
    median_vol_range: float,
    min_distance_pct: float,
    gap_min_vol_factor: float,
    gap_min_size_atr: float,
    today_low: float | None
):
    if last_price is None:
        return None
    median_vol_gap_window = _median([_to_float(d.get("volume")) or 0.0 for d in gap_days]) or 0.0
    median_vol_all = _median([_to_float(d.get("volume")) or 0.0 for d in days[-126:]]) or 0.0
    threshold = last_price * (1.0 - max(0.0, min_distance_pct))

    # Preferencia 1: gap-up potente
    best_gap_anchor = None
    if gaps_up:
        for g in sorted(gaps_up, key=lambda x: x["date"], reverse=True):
            vol_factor = (g["volume"] / median_vol_gap_window) if median_vol_gap_window else 0.0
            size_atr = (g["size"] / max(atr10, 1e-6)) if atr10 > 0 else 0.0
            if vol_factor >= gap_min_vol_factor and size_atr >= gap_min_size_atr:
                best_gap_anchor = {"date": g["date"], "vol_factor": vol_factor, "size_atr": size_atr}
                break
    if best_gap_anchor:
        avwap = _avwap_from_date(days, best_gap_anchor["date"])
        if avwap is not None and avwap <= threshold:
            testing_now = _is_testing_now(today_low, avwap, tol)
            return {
                "anchor_type": "gap_up",
                "anchor_label": f"gap-up del {best_gap_anchor['date']}",
                "anchor_date": best_gap_anchor["date"],
                "level": avwap,
                "vol_factor": best_gap_anchor["vol_factor"],
                "gap_size_atr": best_gap_anchor["size_atr"],
                "testing_now": testing_now
            }

    # Preferencia 2: 52w low
    if level_52w_low_date:
        avwap = _avwap_from_date(days, level_52w_low_date)
        if avwap is not None and avwap <= threshold:
            vol_anchor = _volume_on_date(days, level_52w_low_date)
            vol_factor = (vol_anchor / median_vol_all) if median_vol_all else None
            testing_now = _is_testing_now(today_low, avwap, tol)
            return {
                "anchor_type": "52w_low",
                "anchor_label": f"52w low {level_52w_low_date}",
                "anchor_date": level_52w_low_date,
                "level": avwap,
                "vol_factor": vol_factor,
                "testing_now": testing_now
            }

    # Preferencia 3: YTD open
    try:
        current_year = datetime.utcnow().year
    except Exception:
        current_year = int((days[-1]["date"] or "2000")[:4])
    ytd_date = _first_trading_day_of_year(days, current_year)
    if ytd_date:
        avwap = _avwap_from_date(days, ytd_date)
        if avwap is not None and avwap <= threshold:
            vol_anchor = _volume_on_date(days, ytd_date)
            vol_factor = (vol_anchor / median_vol_all) if median_vol_all else None
            testing_now = _is_testing_now(today_low, avwap, tol)
            return {
                "anchor_type": "ytd_open",
                "anchor_label": f"apertura YTD {ytd_date}",
                "anchor_date": ytd_date,
                "level": avwap,
                "vol_factor": vol_factor,
                "testing_now": testing_now
            }

    # Preferencia 4: suelo de rango
    range_any = _select_range_bottom_cluster(
        clusters=range_clusters_bottom,
        last_price=last_price,
        today_low=None,
        tol=tol,
        median_vol=median_vol_range,
        min_distance_pct=0.0
    )
    if range_any:
        anchor_date = range_any["last_date"]
        avwap = _avwap_from_date(days, anchor_date)
        if avwap is not None and avwap <= threshold:
            testing_now = _is_testing_now(today_low, avwap, tol)
            return {
                "anchor_type": "range_bottom",
                "anchor_label": f"suelo de rango {anchor_date}",
                "anchor_date": anchor_date,
                "level": avwap,
                "vol_factor": range_any.get("vol_factor"),
                "touches": range_any.get("touches"),
                "testing_now": testing_now
            }
    return None


def _annotate_supports_touch_prob_1w(supports: list, vols: dict | None):
    if not isinstance(supports, list) or not supports:
        return
    sigma_pct = None
    sigma_source = None
    try:
        if vols:
            if vols.get("em_pct_1w") is not None:
                sigma_pct = float(vols["em_pct_1w"])
                sigma_source = "em_pct_1w"
            elif vols.get("rv20_weekly_pct") is not None:
                sigma_pct = float(vols["rv20_weekly_pct"])
                sigma_source = "rv20_weekly_pct"
    except Exception:
        sigma_pct = None
        sigma_source = None

    for s in supports:
        try:
            dist = s.get("distance")  # % distancia hacia ABAJO (definida positiva)
            z = None
            p = None
            if dist is not None and sigma_pct is not None and sigma_pct > 0 and dist > 0:
                z = dist / sigma_pct
                cdf = _normal_cdf(z)
                if cdf is not None:
                    p = max(0.0, min(100.0, 100.0 * (1.0 - cdf)))
            if p is not None:
                s["prob_touch_1w_pct"] = round(p, 1)
            s.setdefault("meta", {})
            s["meta"]["touch_prob_1w"] = {
                "sigma_pct": round(sigma_pct, 3) if sigma_pct is not None else None,
                "sigma_source": sigma_source,
                "z": round(z, 3) if z is not None else None
            }
        except Exception as e:
            tlogger.error(f"[touch_prob_1w support] error on {s.get('type')}: {e}", exc_info=True)


# ==================== Fuerza relativa sectorial (opcional) ====================

def _relative_strength_vs(symbol_days: list, bench_symbol: str, start: str, end: str, lookbacks: list[int] = [20, 60]):
    try:
        bench = _tradier_history_daily(bench_symbol, start, end) or []
        if not symbol_days or not bench:
            return {}

        sym_map = {d.get("date"): _to_float(d.get("close")) for d in symbol_days}
        ben_map = {d.get("date"): _to_float(d.get("close")) for d in bench}

        dates = sorted([dt for dt in sym_map.keys() if dt in ben_map and sym_map[dt] is not None and ben_map[dt] is not None])
        if len(dates) < 2:
            return {}

        def _rel_ret(n):
            if len(dates) < n + 1:
                return None
            d0 = dates[-(n+1)]
            d1 = dates[-1]
            s0, s1 = sym_map[d0], sym_map[d1]
            b0, b1 = ben_map[d0], ben_map[d1]
            if not s0 or not s1 or not b0 or not b1:
                return None
            rsym = 100.0 * (s1 - s0) / s0
            rben = 100.0 * (b1 - b0) / b0
            return round(rsym - rben, 2)

        out = {}
        for n in lookbacks:
            out[f"{n}d_diff_pct"] = _rel_ret(n)
        return out
    except Exception as e:
        tlogger.error(f"[relative_strength_vs {bench_symbol}] error: {e}", exc_info=True)
        return {}

def _compute_putwall_gamma(
    symbol: str,
    last_price: float,
    today_low: float,
    atr10: float,
    top_expirations: int,
    tol_mult: float,
    cluster_atr: float
):
    """
    Devuelve el put-wall dominante (γ-$ más alto en PUTS) agregando varias expiraciones,
    SIN filtrar por distancia al precio.
    """
    if last_price is None:
        return None

    expirations = _tradier_option_expirations(symbol) or []
    if not expirations:
        return None
    expirations = expirations[:max(1, top_expirations)]

    gamma_puts_by_strike = {}
    oi_puts_by_strike = {}
    gamma_total_puts = 0.0
    strike_exp_gamma = {}

    sampled_chains = {}
    for exp in expirations:
        chain = _tradier_options_chain(symbol, exp) or []
        sampled_chains[exp] = chain
        for p in chain:
            if (p.get("option_type") or "").lower() != "put":
                continue
            s = p.get("strike")
            oi = p.get("oi", 0)
            gam = p.get("gamma", 0.0)
            if s is None or oi is None or gam is None:
                continue
            CONTRACT = _contract_multiplier(p)
            g_usd = abs(gam) * oi * CONTRACT * (last_price ** 2)
            if g_usd <= 0:
                continue
            gamma_puts_by_strike[s] = gamma_puts_by_strike.get(s, 0.0) + g_usd
            oi_puts_by_strike[s] = oi_puts_by_strike.get(s, 0) + oi
            gamma_total_puts += g_usd
            strike_exp_gamma.setdefault(s, {})
            strike_exp_gamma[s][exp] = strike_exp_gamma[s].get(exp, 0.0) + g_usd

    if not gamma_puts_by_strike:
        return None

    top_strike = max(gamma_puts_by_strike, key=lambda s: gamma_puts_by_strike[s])
    top_gamma = gamma_puts_by_strike[top_strike]
    gamma_share_pct = (100.0 * top_gamma / gamma_total_puts) if gamma_total_puts > 0 else None

    exp_dom = None
    if top_strike in strike_exp_gamma:
        exp_dom = max(strike_exp_gamma[top_strike].items(), key=lambda kv: kv[1])[0]

    def _cluster_neighbors(center):
        radius = (cluster_atr * atr10) if atr10 and atr10 > 0 else 0.0
        return sorted([k for k in gamma_puts_by_strike.keys() if abs(k - center) <= radius])

    neighbors = _cluster_neighbors(top_strike)
    cluster_gamma = sum(gamma_puts_by_strike[s] for s in neighbors) if neighbors else top_gamma
    cluster_share_pct = (100.0 * cluster_gamma / gamma_total_puts) if gamma_total_puts > 0 else None

    tol = tol_mult * atr10 if atr10 and atr10 > 0 else max(0.25, 0.002 * last_price)
    testing_now = (today_low is not None and abs(today_low - top_strike) <= tol)

    total_oi = sum(oi_puts_by_strike.values()) or 1
    return {
        "level": float(top_strike),
        "expiration": exp_dom,
        "option_details": _wall_option_details(top_strike, "put", sampled_chains, last_price),
        "gamma_usd_millions": top_gamma / 1e6,
        "total_put_gamma_usd_millions": gamma_total_puts / 1e6,
        "gamma_share_pct": gamma_share_pct,
        "oi": oi_puts_by_strike.get(top_strike),
        "oi_share_pct": 100.0 * (oi_puts_by_strike.get(top_strike, 0)) / total_oi,
        "cluster_neighbors": neighbors,
        "cluster_gamma_usd": cluster_gamma / 1e6,
        "cluster_share_pct": cluster_share_pct,
        "tolerance": tol,
        "testing_now": testing_now
    }


def _compute_top_putwalls_gamma(
    symbol: str,
    last_price: float,
    atr10: float,
    top_expirations: int,
    cluster_atr: float,
    top_n: int = 5
):
    if last_price is None:
        return []
    expirations = _tradier_option_expirations(symbol) or []
    if not expirations:
        return []
    expirations = expirations[:max(1, top_expirations)]

    gamma_puts_by_strike = {}
    oi_puts_by_strike = {}
    gamma_total_puts = 0.0
    strike_exp_gamma = {}

    sampled_chains = {}
    for exp in expirations:
        chain = _tradier_options_chain(symbol, exp) or []
        sampled_chains[exp] = chain
        for p in chain:
            if (p.get("option_type") or "").lower() != "put":
                continue
            s = p.get("strike")
            oi = p.get("oi", 0)
            gam = p.get("gamma", 0.0)
            if s is None or oi is None or gam is None:
                continue
            CONTRACT = _contract_multiplier(p)
            g_usd = abs(gam) * oi * CONTRACT * (last_price ** 2)
            if g_usd <= 0:
                continue
            gamma_puts_by_strike[s] = gamma_puts_by_strike.get(s, 0.0) + g_usd
            oi_puts_by_strike[s] = oi_puts_by_strike.get(s, 0) + oi
            gamma_total_puts += g_usd
            strike_exp_gamma.setdefault(s, {})
            strike_exp_gamma[s][exp] = strike_exp_gamma[s].get(exp, 0.0) + g_usd

    if not gamma_puts_by_strike:
        return []

    def _neighbors(center):
        radius = (cluster_atr * atr10) if atr10 and atr10 > 0 else 0.0
        return sorted([k for k in gamma_puts_by_strike.keys() if abs(k - center) <= radius])

    total_oi = sum(oi_puts_by_strike.values()) or 1
    top_strikes = sorted(gamma_puts_by_strike.keys(),
                         key=lambda s: gamma_puts_by_strike[s],
                         reverse=True)[:max(1, top_n)]
    out = []
    for s in top_strikes:
        g_s = gamma_puts_by_strike[s]
        exp_dom = None
        if s in strike_exp_gamma and strike_exp_gamma[s]:
            exp_dom = max(strike_exp_gamma[s].items(), key=lambda kv: kv[1])[0]
        nbrs = _neighbors(s)
        cluster_gamma = sum(gamma_puts_by_strike[n] for n in nbrs) if nbrs else g_s
        item = {
            "level": round(float(s), 4),
            "expiration": exp_dom,
            "option_details": _wall_option_details(s, "put", sampled_chains, last_price),
            "gamma_usd_millions": round(g_s / 1e6, 3),
            "gamma_share_pct": round(100.0 * g_s / gamma_total_puts, 1) if gamma_total_puts > 0 else None,
            "oi": oi_puts_by_strike.get(s),
            "oi_share_pct": round(100.0 * (oi_puts_by_strike.get(s, 0)) / total_oi, 1) if total_oi > 0 else None,
            "cluster_neighbors": nbrs,
            "cluster_gamma_usd": round(cluster_gamma / 1e6, 3),
            "cluster_share_pct": round(100.0 * cluster_gamma / gamma_total_puts, 1) if gamma_total_puts > 0 else None,
            "distance": round(100.0 * (float(s) - last_price) / last_price, 2) if last_price else None
        }
        out.append(item)
    return out


def _dealer_gamma_summary(symbol: str, last_price: float, top_expirations: int):
    """Legacy helper name; observed call-minus-put long-contract notional only."""
    exps = (_tradier_option_expirations(symbol) or [])[:max(1, top_expirations)]
    sums = {"call": 0.0, "put": 0.0}
    eligible, unknown, assumed = 0, 0, 0
    for exp in exps:
        for option in _tradier_options_chain(symbol, exp) or []:
            oi, gamma = option.get("oi"), option.get("gamma")
            if oi is None or gamma is None:
                unknown += 1
                continue
            eligible += 1
            assumed += option.get("contract_size") is None
            sums[option["option_type"]] += abs(gamma) * oi * _contract_multiplier(option) * last_price ** 2 / 1e6
    return {"gex_total_usd_millions": round(sums["call"] - sums["put"], 3) if eligible else None,
            "eligible_contracts": eligible, "unknown_metric_contracts": unknown,
            "assumed_standard_multiplier_contracts": assumed,
            "sampled_expirations": exps, "gamma_regime": None,
            "method": "observed_call_minus_put_long_contract_notional"}

def _summary_by_expiration(symbol: str, spot: float, max_items: int | None = None):
    """
    Para cada expiración futura (limitada opcionalmente), calcula:
      - EM (straddle ATM mid)
      - IV ATM aprox (σ ≈ straddle / (0.8*S*sqrt(T))) — heurística
      - OI puts/calls y ratio
    """
    if spot is None:
        return []
    exps_dte = _future_expirations_with_dte(symbol) or []  # [(date, dte)]
    if not exps_dte:
        return []
    if max_items:
        exps_dte = exps_dte[:max(1, max_items)]
    out = []
    for exp, dte in exps_dte:
        chain = _tradier_options_chain(symbol, exp) or []
        if not chain:
            continue
        # ATM strike
        strikes = sorted({c["strike"] for c in chain if c.get("strike") is not None})
        if not strikes:
            continue
        atm = min(strikes, key=lambda s: abs(s - spot))
        call = next((c for c in chain if c["strike"] == atm and c["option_type"] == "call"), None)
        put  = next((c for c in chain if c["strike"] == atm and c["option_type"] == "put"),  None)
        em_abs = None; em_pct = None; iv_atm = None
        if call and put:
            call_mid = _mid_price(call.get("bid"), call.get("ask"), call.get("last"))
            put_mid  = _mid_price(put.get("bid"),  put.get("ask"),  put.get("last"))
            if call_mid is not None and put_mid is not None:
                em_abs = call_mid + put_mid
                em_pct = (em_abs / spot) if spot else None
                # IV ATM aprox (regla del 0.8) con T en años
                T = dte / 365.0 if dte and dte > 0 else None
                denom = 0.8 * spot * math.sqrt(T) if T else 0
                iv_atm = (em_abs / denom) if denom > 0 else None
        # OI totales
        puts = _oi_total(chain, "put")
        calls = _oi_total(chain, "call")
        ratio = (puts / calls) if puts is not None and calls else None
        out.append({
            "date": exp,
            "dte": dte,
            "strike_atm": atm,
            "call_quote": call, "put_quote": put,
            "unknown_oi_contracts": sum(o.get("oi") is None for o in chain),
            "expected_move": {
                "dollars": round(em_abs, 4) if em_abs is not None else None,
                "percent": round(em_pct, 4) if em_pct is not None else None,
                "method": "ATM straddle observed price; actual expiration; not sigma",
                "percent_unit": "fraction"
            },
            "total_call_oi": calls,
            "total_put_oi": puts,
            "put_call_oi_ratio": round(ratio, 3) if ratio is not None else None
        })
    return out


def _max_pain_by_expiration(symbol: str, max_items: int | None = None):
    """
    max_pain por expiración + 'confidence' (gap relativo entre el mínimo y el segundo mejor).
    """
    exps_dte = _future_expirations_with_dte(symbol) or []
    if not exps_dte:
        return []
    if max_items:
        exps_dte = exps_dte[:max(1, max_items)]
    out = []
    for exp, _dte in exps_dte:
        chain = _tradier_options_chain(symbol, exp) or []
        if not chain or any(o.get("oi") is None for o in chain) or not any(o.get("oi") for o in chain):
            continue
        strikes = sorted({c["strike"] for c in chain if c.get("strike") is not None})
        if not strikes:
            continue
        call_oi = {}; put_oi = {}
        for c in chain:
            s = c.get("strike")
            if s is None: continue
            if (c.get("option_type") or "").lower()=="call":
                call_oi[s] = call_oi.get(s,0) + c["oi"] * _contract_multiplier(c)
            else:
                put_oi[s]  = put_oi.get(s,0)  + c["oi"] * _contract_multiplier(c)
        def pain_at(price):
            loss = 0.0
            for k in strikes:
                co = call_oi.get(k, 0); po = put_oi.get(k, 0)
                if co: loss += co * max(0.0, price - k)
                if po: loss += po * max(0.0, k - price)
            return loss
        pains = [(k, pain_at(k)) for k in strikes]
        pains.sort(key=lambda kv: kv[1])
        best_k, best_p = pains[0]
        second_p = pains[1][1] if len(pains)>1 else best_p
        max_p = pains[-1][1]
        denom = max(1e-9, (max_p - best_p))
        confidence = max(0.0, min(1.0, (second_p - best_p) / denom))
        out.append({"date": exp, "strike": float(best_k), "objective_gap_fraction": round(confidence,3)})
    return out


def _score_putwall_strength(putwall: dict, last_price: float, atr10: float) -> float:
    # Reutiliza el mismo esquema de scoring que callwall
    return _score_callwall_strength({
        "gamma_share_pct": putwall.get("gamma_share_pct"),
        "cluster_share_pct": putwall.get("cluster_share_pct"),
        "gamma_usd_millions": putwall.get("gamma_usd_millions"),
        "oi_share_pct": putwall.get("oi_share_pct"),
        "expiration": putwall.get("expiration"),
        "testing_now": putwall.get("testing_now")
    }, last_price, atr10)

def _trend_bias_confidence_1_2w(
    last_price: float,
    technicals: dict | None,
    vols: dict | None,
    options: dict | None,
    callwalls_top: list | None,
    putwalls_top: list | None,
):
    """
    Devuelve un paquete compacto para que un LLM razone tendencias 1–2w sin texto natural.
    Campos:
      - bias ∈ [-100,100]  (negativo=bajista, positivo=alcista)
      - confidence ∈ [0,100]
      - components: {A_technicals, B_options_7_21DTE, C_vol_risk, D_volume_tape}
      - rules_triggered: [{code, weight, side}] (side +1/-1)
      - features_flat: dict llano de features relevantes
    """
    t = technicals or {}
    tr = (t.get("trend") or {})
    sma = (t.get("sma") or {})
    bb  = (t.get("bollinger20_2") or {})
    dch = (t.get("donchian20") or {})
    volpack = (t.get("volume") or {})

    # --- señales básicas ---
    rsi14 = t.get("rsi14")
    px_vs_sma20 = (tr.get("price_vs_sma") or {}).get("20")
    px_vs_sma50 = (tr.get("price_vs_sma") or {}).get("50")
    bb_width = bb.get("width_pct")
    # Donchian position 0–100
    dch_pos = None
    try:
        hi, lo = dch.get("high"), dch.get("low")
        if last_price is not None and hi is not None and lo is not None and hi > lo:
            dch_pos = 100.0 * (last_price - lo) / (hi - lo)
            dch_pos = max(0.0, min(100.0, dch_pos))
    except Exception:
        pass

    # Options / gamma regime
    dealer = (options or {}).get("dealer_gamma") or {}
    gamma_regime = dealer.get("gamma_regime")  # "positive" | "negative" | None

    # Distancias a paredes cercanas (en %). Arriba (call), abajo (put).
    nearest_call_up = None
    if callwalls_top:
        ups = [c for c in callwalls_top if c.get("distance") is not None and c["distance"] >= 0]
        if ups:
            nearest_call_up = min(x["distance"] for x in ups)

    nearest_put_down = None
    if putwalls_top:
        downs = [p for p in putwalls_top if p.get("distance") is not None and p["distance"] <= 0]
        if downs:
            nearest_put_down = min(abs(p["distance"]) for p in downs)

    # Volatilidad / riesgo
    iv_to_rv = (vols or {}).get("iv_to_rv_ratio")
    em_to_atr = (vols or {}).get("em_to_atr_ratio")
    em_pct_1w = (vols or {}).get("em_pct_1w")

    # Tape / volumen relativo último día completo
    vol_rel_last = None
    try:
        rel = (volpack.get("last_complete_day") or {}).get("rel_to_20d")
        vol_rel_last = float(rel) if rel is not None else None
    except Exception:
        pass

    # =============== scoring por componentes ===============
    A = 0.0
    B = 0.0
    C = 0.0
    D = 0.0
    rules = []

    def add_rule(code, cond, weight, side):
        if cond:
            rules.append({"code": code, "weight": int(weight), "side": int(side)})

    # --- TECHNICALS ---
    if rsi14 is not None:
        if rsi14 > 55: A += 20; add_rule("RSI_GT_55", True, 20, +1)
        elif rsi14 < 45: A -= 20; add_rule("RSI_LT_45", True, 20, -1)
    if px_vs_sma20 is not None:
        if px_vs_sma20 > 0: A += 10; add_rule("PX_GT_SMA20", True, 10, +1)
        elif px_vs_sma20 < 0: A -= 10; add_rule("PX_LT_SMA20", True, 10, -1)
    if px_vs_sma50 is not None:
        if px_vs_sma50 > 0: A += 10; add_rule("PX_GT_SMA50", True, 10, +1)
        elif px_vs_sma50 < 0: A -= 10; add_rule("PX_LT_SMA50", True, 10, -1)
    if dch_pos is not None:
        if dch_pos >= 70: A += 5; add_rule("DONCH_POS_GE_70", True, 5, +1)
        elif dch_pos <= 30: A -= 5; add_rule("DONCH_POS_LE_30", True, 5, -1)

    # --- OPTIONS (paredes + régimen) ---
    if nearest_call_up is not None:
        # si el call wall está muy cerca arriba y régimen γ positivo → freno bajista
        if nearest_call_up <= 8 and gamma_regime == "positive":
            B -= 5; add_rule("CALLWALL_NEAR_POS_GAMMA", True, 5, -1)
    if nearest_put_down is not None:
        if nearest_put_down <= 3:
            B += 5; add_rule("PUTWALL_NEAR", True, 5, +1)
    if gamma_regime == "positive":
        B += 5; add_rule("GAMMA_REGIME_POS", True, 5, +1)
    elif gamma_regime == "negative":
        B -= 5; add_rule("GAMMA_REGIME_NEG", True, 5, -1)

    # --- VOL / RIESGO ---
    if iv_to_rv is not None:
        if iv_to_rv > 1.8: C -= 10; add_rule("IV_RICH_GT_1_8", True, 10, -1)
        elif iv_to_rv < 1.0: C += 5; add_rule("IV_CHEAP_LT_1_0", True, 5, +1)
    if em_to_atr is not None:
        if em_to_atr > 1.6: C -= 10; add_rule("EM2W_ATR_GT_1_6", True, 10, -1)
        elif em_to_atr < 1.0: C += 5; add_rule("EM2W_ATR_LT_1_0", True, 5, +1)
    if bb_width is not None:
        # compresión ligera favorece breakouts neutrales; anchura muy alta = ruido/riesgo
        if bb_width >= 12: C -= 5; add_rule("BB_WIDTH_GE_12", True, 5, -1)
        elif bb_width <= 5: C += 3; add_rule("BB_WIDTH_LE_5", True, 3, +1)

    # --- VOLUMEN / TAPE ---
    if vol_rel_last is not None:
        if vol_rel_last >= 1.2: D += 10; add_rule("VOL_REL_GT_1_2", True, 10, +1)
        elif vol_rel_last <= 0.9: D -= 5; add_rule("VOL_REL_LT_0_9", True, 5, -1)

    # Bias total (cap a [-100,100], cada bloque se capea a ±40)
    def cap(x, m): return max(-m, min(m, x))
    A, B, C, D = cap(A, 40), cap(B, 40), cap(C, 40), cap(D, 40)
    bias = cap(A + B + C + D, 100)

    # Confidence heurística: cobertura de señales + coherencia
    present = sum(v is not None for v in [
        rsi14, px_vs_sma20, px_vs_sma50, dch_pos, nearest_call_up, nearest_put_down, iv_to_rv, em_to_atr, vol_rel_last
    ])
    coverage = min(1.0, present / 9.0)
    conf = int(round(35 + 45*coverage + 0.2*abs(bias)))  # 35–100 aprox
    conf = max(20, min(95, conf))
    # Si no hay casi señales, reduce
    if present <= 3:
        conf = min(conf, 60)

    features_flat = {
        "rsi14": rsi14,
        "price_vs_sma20_pct": px_vs_sma20,
        "price_vs_sma50_pct": px_vs_sma50,
        "donchian20_pos_pct": dch_pos,
        "bb_width_pct": bb_width,
        "nearest_call_wall_dist_pct": nearest_call_up,
        "nearest_put_wall_dist_pct": nearest_put_down,
        "gamma_regime": gamma_regime,
        "iv_to_rv": iv_to_rv,
        "em_2w_to_atr": em_to_atr,
        "em_pct_1w": em_pct_1w,
        "volume_rel_20d_last_close": vol_rel_last,
    }

    components = {
        "A_technicals": {
            "score": int(round(A)),
            "signals": {
                "rsi14": rsi14,
                "price_vs_sma20_pct": px_vs_sma20,
                "price_vs_sma50_pct": px_vs_sma50,
                "donchian20_pos_pct": round(dch_pos, 1) if dch_pos is not None else None,
                "bb_width_pct": bb_width
            }
        },
        "B_options_7_21DTE": {
            "score": int(round(B)),
            "signals": {
                "nearest_call_wall_dist_pct": nearest_call_up,
                "nearest_put_wall_dist_pct": nearest_put_down,
                "gamma_regime": gamma_regime
            }
        },
        "C_vol_risk": {
            "score": int(round(C)),
            "signals": {
                "iv_to_rv": iv_to_rv,
                "em_2w_to_atr": em_to_atr,
                "em_pct_1w": em_pct_1w
            }
        },
        "D_volume_tape": {
            "score": int(round(D)),
            "signals": {
                "volume_rel_20d_last_close": vol_rel_last
            }
        }
    }

    return {
        "horizon": "1-2w",
        "bias": int(round(bias)),
        "confidence": int(conf),
        "components": components,
        "rules_triggered": rules,
        "features_flat": {k:(round(v,4) if isinstance(v,(int,float)) and v is not None else v) for k,v in features_flat.items()},
        "config": {"entry_threshold_bias": 55}
    }

def _is_testing_now(today_px: float | None, level: float | None, tol: float) -> bool:
    return (today_px is not None and level is not None and abs(today_px - level) <= tol)
