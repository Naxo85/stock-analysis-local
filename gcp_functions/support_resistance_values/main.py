import functions_framework
import logging
import os
import requests
from flask import jsonify
from datetime import datetime, timedelta, time
import statistics
import xml.etree.ElementTree as ET
import math
import json
import time as time_module
from zoneinfo import ZoneInfo                       ### NEW

from daily_metrics import day_change_pct
from drawdown_metrics import relative_drawdown_6m

# Configura logging a nivel INFO
tlogger = logging.getLogger()
tlogger.setLevel(logging.DEBUG)

# Claves de API
#ALPHA_VANTAGE_KEY = 'RHDJQ2Q3M0BDZ9YO'
TRADIER_TOKEN = os.environ.get("TRADIER_TOKEN", "")

# Cloud Run reutiliza el proceso entre peticiones. El histórico cerrado no
# cambia durante el día, por lo que basta una descarga por ticker y fecha ET.
_DAILY_SERIES_CACHE = {}
_CNN_FEAR_GREED_CACHE = {
    "payload": None,
    "expires_at": 0.0,
}

_CNN_FEAR_GREED_URL = (
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
)
_CNN_FEAR_GREED_TTL_SECONDS = 15 * 60
_CNN_FEAR_GREED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.cnn.com",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def _cnn_fear_greed_response():
    now_monotonic = time_module.monotonic()
    cached = _CNN_FEAR_GREED_CACHE["payload"]

    if cached and now_monotonic < _CNN_FEAR_GREED_CACHE["expires_at"]:
        payload = dict(cached)
        payload["cache_status"] = "hit"
        return jsonify(payload), 200

    try:
        response = requests.get(
            _CNN_FEAR_GREED_URL,
            headers=_CNN_FEAR_GREED_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        fear_and_greed = data.get("fear_and_greed") or {}
        score = float(fear_and_greed.get("score"))

        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("CNN returned an invalid Fear & Greed score")

        payload = {
            "score": round(score, 1),
            "rating": fear_and_greed.get("rating"),
            "source": "CNN Fear & Greed",
            "source_timestamp": fear_and_greed.get("timestamp"),
            "fetched_at": datetime.now(ZoneInfo("UTC")).isoformat(),
            "cache_ttl_seconds": _CNN_FEAR_GREED_TTL_SECONDS,
            "cache_status": "miss",
        }
        _CNN_FEAR_GREED_CACHE["payload"] = payload
        _CNN_FEAR_GREED_CACHE["expires_at"] = (
            now_monotonic + _CNN_FEAR_GREED_TTL_SECONDS
        )
        return jsonify(payload), 200
    except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError):
        tlogger.exception("CNN Fear & Greed proxy request failed")

        if cached:
            payload = dict(cached)
            payload["cache_status"] = "stale"
            return jsonify(payload), 200

        return jsonify(
            error="CNN Fear & Greed unavailable",
            source="CNN Fear & Greed",
        ), 502


@functions_framework.http
def support_resistance(request):
    tlogger.error("Empezando support_resistance")

    if request.method in {"GET", "HEAD"} and (
        request.path.rstrip("/") == "/market/fear-greed/cnn"
    ):
        return _cnn_fear_greed_response()

    ET_TZ  = ZoneInfo("US/Eastern")                     ### NEW
    UTC_TZ = ZoneInfo("UTC")                            ### NEW

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify(error="Invalid JSON body"), 400

    symbol = payload.get('symbol') or (payload.get('tickers') or [None])[0]
    if not symbol:
        return jsonify(error="Missing 'symbol' or 'tickers'"), 400
    symbol = symbol.upper()

    # --- INTENTA Tradier primero ---
    today  = datetime.now(ZoneInfo("US/Eastern")).strftime('%Y-%m-%d')
    start  = f"{today} 04:00"
    end    = f"{today} 20:00"
    ts     = _fetch_time_series_tradier(symbol, start, end)
    if ts:
        tlogger.error(f"[TS] len={len(ts):4}  first={min(ts)}  last={max(ts)}")
    else:
        tlogger.warning("[TS] len=0 – Tradier vacío ⇒ reintento con último día hábil")
        # Reintento: último día hábil (salta fin de semana) en US/Eastern
        prev = datetime.now(ZoneInfo("US/Eastern")).date() - timedelta(days=1)
        while prev.weekday() >= 5:  # 5=sábado, 6=domingo
            prev -= timedelta(days=1)
        prev_str   = prev.strftime('%Y-%m-%d')
        start_prev = f"{prev_str} 04:00"
        end_prev   = f"{prev_str} 20:00"

        ts = _fetch_time_series_tradier(symbol, start_prev, end_prev)
        if ts:
            tlogger.error(f"[TS:prev] len={len(ts):4}  first={min(ts)}  last={max(ts)}")
        else:
            tlogger.error("[TS:prev] len=0 – sin datos en último día hábil")
            return jsonify(error="No intraday data from Tradier"), 502

    sorted_times = _sorted_timestamps(ts)
    last_ref     = sorted_times[-1]

    # --- PRICE: preferimos payload, si no fallback al cierre intradía ---
    latest_price = payload.get('price')
    if latest_price is not None:
        try:
            latest_price = float(latest_price)
            tlogger.error(f"Using passed-in latest_price = {latest_price:.2f}")
        except:
            return jsonify(error="Invalid 'price' parameter"), 400
    else:
        latest_price = float(ts[last_ref]['4. close'])
        tlogger.error(f"Using intraday close latest_price = {latest_price:.2f}")

    # Ahora ts, sorted_times y last_ref siempre existen:    
    # 1,280 días naturales aportan aproximadamente tres años comparables
    # más las 126 sesiones de calentamiento para el máximo móvil de 6 meses.
    daily_pts = _fetch_daily_series(symbol, lookback_days=1280)
    if not daily_pts or len(daily_pts) < 21:
        return jsonify(error="Insufficient daily history (Tradier)"), 502
    closes = [c for (_d, c, _h, _l) in daily_pts]
    atr_intra = _calculate_atr(ts, sorted_times, last_ref, period=10)
    atr_daily  =_atr_daily(daily_pts, period=10)
    ATR_MIN = 0.5
    atr_opts = max(atr_daily, ATR_MIN)
    atr_px   = max(atr_intra, 0.05)

    raw_last    = sorted_times[-1]                      ### NEW
    last_dt_et  = datetime.strptime(raw_last, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ET_TZ)
    last_dt_utc = last_dt_et.astimezone(UTC_TZ)
    last_ref    = raw_last

    now_et = datetime.now(ET_TZ)
    is_wkend = now_et.weekday() >= 5

    if is_wkend and daily_pts:
        latest_price = closes[-1]

    if is_wkend:
        # usa el viernes para el rango de descarga
        last_friday = now_et - timedelta(days=now_et.weekday() - 4)
        day_str = last_friday.strftime('%Y-%m-%d')
        start = f"{day_str} 04:00"
        end   = f"{day_str} 20:00"
    else:
        today = now_et.strftime('%Y-%m-%d')
        if now_et.time() >= time(20, 0):
            start = f"{today} 04:00"
            end   = f"{today} 20:00"
        elif now_et.time() < time(4, 0):
            yesterday = (now_et - timedelta(days=1)).strftime('%Y-%m-%d')
            start = f"{yesterday} 04:00"
            end   = f"{yesterday} 20:00"
        else:
            start = f"{today} 04:00"
            end   = now_et.strftime('%Y-%m-%d %H:%M')

    session_label, session_start = _determine_session_window(now_et)
    session_start = session_start.replace(tzinfo=None) 
    if session_label == 'closed':
        # la sesión que acabó fue la de la fecha de raw_last
        session_start = datetime.strptime(raw_last.split()[0] + " 09:30", "%Y-%m-%d %H:%M")

    vwap_session = _calculate_session_vwap(ts, sorted_times, session_start, raw_last, regular_only=(session_label=='regular')) 

    if vwap_session is None:
        # fuera de mercado o sin volumen ⇒ usa el último precio
        tlogger.warning("[VWAP] vwap_session=None → fallback a latest_price")
        vwap_session = latest_price

    tlogger.error(f"[WINDOW] now_et={now_et}  session_label={session_label} "
             f"session_start={session_start}  raw_last={last_ref}")
    
    # --- volumen sesión ---
    # session_vol = _calculate_session_volume(ts, sorted_times,
    #                                         session_start, last_ref)
    # tlogger.error(f"[VOL]  session_vol={session_vol}")

    # --- volumen "del día" (NO se resetea en postmarket) ---
    day_str = raw_last.split()[0]  # fecha del último timestamp real en ts
    day_start = datetime.strptime(day_str + " 04:00", "%Y-%m-%d %H:%M")  # extended

    session_vol = _calculate_session_volume(ts, sorted_times, day_start, last_ref)
    tlogger.error(f"[VOL] day_start={day_start}  session_vol={session_vol}")

    avg_vol_5d   = _fetch_daily_volume_avg(symbol)
    tlogger.error(f"[VOL]  avg_vol_5d={avg_vol_5d}")

    ref_dt = last_dt_et   # hora del último trade existente
    session_ended = (ref_dt.time() >= time(20,0)) or (session_label == 'closed')
    progress = 1.0 if session_ended else _expected_cdf(ref_dt)

    rel_volume_raw = (
        session_vol / (avg_vol_5d * progress)
        if (avg_vol_5d and progress)
        else None
    )
    tlogger.error(f"[REL]  rel_volume_raw={rel_volume_raw}")

    rel_volume = round(rel_volume_raw, 2) if rel_volume_raw is not None else None

    # Mínimos de últimos 2 días hábiles
    session_low, min3d_low = _fetch_lows_from_intraday(ts, days=3)
    tlogger.error(f"Session low today: {session_low}, Min 3d low: {min3d_low}")
    
    # 2. Expirations y cadena de opciones (MULTI-EXPIRY)
    expirations, error = _fetch_option_expirations(symbol)
    if error:
        return error

    exp_list = _pick_expirations(expirations, max_n=6, max_dte_days=60)

    # ---- MULTI-EXPIRY: guardamos también la cadena usada (opts) para métricas ----
    opts_data_any = None  # primera cadena válida que llegue

    best_put  = {"strike": None, "strength": None, "bucket": {}, "meta": {}, "opts": None, "exp": None}
    best_call = {"strike": None, "strength": None, "bucket": {}, "meta": {}, "opts": None, "exp": None}

    # --- P/C swing (OI) estable: agrega varias expiraciones
    PCR_PCT_WINDOW = 0.05   # ±5% spot
    PCR_MIN_DTE = 14        # ignora 0DTE/semana (ruido hedging)
    PCR_MAX_DTE = 60

    pcr_puts_oi = 0
    pcr_calls_oi = 0
    pcr_used_exps = 0

    for exp in exp_list:
        opts_data, error = _fetch_options_chain(symbol, exp)
        if error or not opts_data:
            continue
        
        # --- PCR swing: suma OI ATM-ish en ventana fija ±5% y DTE 14-60 ---
        dte = _dte_days(exp, now_et.date())
        if dte is not None and PCR_MIN_DTE <= dte <= PCR_MAX_DTE:
            puts_oi, calls_oi = _pcr_oi_sums(opts_data, latest_price, pct_window=PCR_PCT_WINDOW)
            if puts_oi > 0 and calls_oi > 0:
                pcr_used_exps += 1
            pcr_puts_oi  += puts_oi
            pcr_calls_oi += calls_oi

        if opts_data_any is None:
            opts_data_any = opts_data

        put_wall, call_wall, put_bkt, call_bkt, put_meta, call_meta = _calculate_gamma_walls(
            opts_data,
            spot=latest_price,
            atr_window=atr_opts,
            avg_vol_5d=avg_vol_5d
        )

        put_strength  = _wall_strength(put_wall,  put_bkt,  put_meta)
        call_strength = _wall_strength(call_wall, call_bkt, call_meta)

        if put_strength is not None and (best_put["strength"] is None or put_strength > best_put["strength"]):
            best_put = {"strike": put_wall, "strength": put_strength, "bucket": put_bkt, "meta": put_meta, "opts": opts_data, "exp": exp}

        if call_strength is not None and (best_call["strength"] is None or call_strength > best_call["strength"]):
            best_call = {"strike": call_wall, "strength": call_strength, "bucket": call_bkt, "meta": call_meta, "opts": opts_data, "exp": exp}

    pcr_oi_swing = (pcr_puts_oi / pcr_calls_oi) if pcr_calls_oi > 0 else None
    tlogger.error(f"[PCR_OI_SWING] used_exps={pcr_used_exps} puts_oi={pcr_puts_oi} calls_oi={pcr_calls_oi} pcr_oi={pcr_oi_swing}")

    put_wall  = best_put["strike"]
    call_wall = best_call["strike"]
    put_bkt   = best_put["bucket"]
    call_bkt  = best_call["bucket"]

    put_cluster  = best_put["strength"]  if put_wall  is not None else None
    call_cluster = best_call["strength"] if call_wall is not None else None

    tlogger.error(f"[CLUSTER DBG] put_bkt={put_bkt}")
    tlogger.error(f"[CLUSTER DBG] call_bkt={call_bkt}")

    # Cadena a usar para métricas (preferimos la del mejor put/call; si no, la primera válida)
    opts_for_metrics = (
        (best_put["opts"]  if best_put["strike"]  is not None else None) or
        (best_call["opts"] if best_call["strike"] is not None else None) or
        (opts_data_any or [])
    )

    zero_gamma = _calculate_zero_gamma(opts_for_metrics, latest_price, atr_opts) if opts_for_metrics else None

    # usamos min3d_low ya existente :contentReference[oaicite:0]{index=0}
    low_tol = 0.01             # 1 ¢ de holgura
    anchor_time = None
    if min3d_low is not None:
        anchor_time = next(
            (t for t in sorted_times
            if abs(float(ts[t]['3. low']) - min3d_low) <= low_tol),
            None
        )

    anch_vwap = (_calculate_anchored_vwap(ts, sorted_times,
                                        anchor_time, raw_last)
                if anchor_time else None)

    hvn_poc     = _calculate_hvn(ts, sorted_times, last_ref, days=5, bin_size=atr_daily/2)

    # 5. VWAP ± ATR
    support_vwap, resistance_vwap = _calculate_ranges(vwap_session, atr_daily)

    # 6. Soportes/resistencias “robustos” con muros a 1.5–2.5×ATR
    robust_support, robust_resistance = _select_robust_levels(
        opts_for_metrics, latest_price, atr_daily, vwap_session,
        low_mult=1.5, high_mult=2.5
    ) if opts_for_metrics else (vwap_session - 1.5*atr_daily, vwap_session + 1.5*atr_daily)


    # 7. Datos diarios: SMA20 y extremos de 5 días
    sma20 = _calculate_sma(closes, window=20)
    min5, max5 = _calculate_recent_extremes(closes, days=5)

    # EMA20 + pendiente sobre daily_pts que ya tienes :contentReference[oaicite:1]{index=1}
    ema20_today = _ema([c for (_d,c,_h,_l) in daily_pts][-20:])
    ema20_prev  = _ema([c for (_d,c,_h,_l) in daily_pts][-21:-1])
    ema20_slope = (ema20_today - ema20_prev) if (ema20_today and ema20_prev) else None

    # 8. Mínimo intradía + cluster de 30m
    low_price, vol_at_low, avg_vol = _fetch_intraday_low_and_volcluster(
        ts, sorted_times, last_ref, window_min=30
    )

    # 9. Candidatos para scoring
    support_cands = []
    
    if session_low is not None:
        support_cands.append({
            'level': session_low,
            'strength': 1.0,
            'type': 'session_low'
        })

    
    if min3d_low is not None:
        support_cands.append({
            'level': min3d_low,
            'strength': 1.0,
            'type': 'min3d_low'
        })

    if low_price is not None and avg_vol is not None and avg_vol > 0:
        strength = vol_at_low / avg_vol
        support_cands.append({
            'level': low_price,
            'strength': strength,
            'type': 'intraday_low_cluster'
        })
    if put_wall is not None:
        support_cands.append({'level': put_wall,  'strength': put_cluster or 0,                   'type':'put_wall'})
    support_cands.append({   'level': vwap_session-atr_daily, 'strength': 1.0,                                 'type':'vwap_atr'})
    if sma20 is not None:
        support_cands.append({'level': sma20,       'strength': 1.0,                                 'type':'sma20'})
    if min5 is not None:
        support_cands.append({'level': min5,        'strength': 1.0,                                 'type':'min5d'})

    # 1) Calcula el score crudo: fuerza / (1 + dist/ATR)
    resistance_cands = []
    if call_wall is not None:
        resistance_cands.append({'level': call_wall, 'strength': call_cluster or 0,                 'type':'call_wall'})
    resistance_cands.append({      'level': vwap_session+atr_daily,'strength': 1.0,                             'type':'vwap_atr'})
    if sma20 is not None:
        resistance_cands.append({'level': sma20,       'strength': 1.0,                                 'type':'sma20'})
    if max5 is not None:
        resistance_cands.append({'level': max5,        'strength': 1.0,                                 'type':'max5d'})

    for c in support_cands:
        dist = abs(latest_price - c['level'])
        c['raw_score'] = c['strength'] / (1 + dist/atr_daily) if atr_daily > 0 else c['strength']
    for c in resistance_cands:
        dist = abs(latest_price - c['level'])
        c['raw_score'] = c['strength'] / (1 + dist/atr_daily) if atr_daily > 0 else c['strength']

    # 2) Normaliza a [0,1] dividiendo por el máximo
    max_sup = max(c['raw_score'] for c in support_cands) or 1
    for c in support_cands:
        c['score'] = round(c['raw_score'] / max_sup, 3)

    max_res = max(c['raw_score'] for c in resistance_cands) or 1
    for c in resistance_cands:
        c['score'] = round(c['raw_score'] / max_res, 3)

    strong_support, support_type = _select_strongest(support_cands,    latest_price, atr_daily)
    strong_resistance, resistance_type = _select_strongest(resistance_cands, latest_price, atr_daily)

    day_pct = day_change_pct(
        latest_price,
        daily_pts,
        market_date=datetime.now(ZoneInfo("US/Eastern")).date(),
    )
    streak_dd = _compute_streak_drawdown_pct(latest_price, daily_pts, last_ref)
    drawdown_6m = relative_drawdown_6m(latest_price, daily_pts)
    pct_6m = drawdown_6m["pct_from_high"]
    peak_val = drawdown_6m["peak_value"]
    peak_date = drawdown_6m["peak_date"]
    pcr_oi = pcr_oi_swing 
    rsi14 = _rsi14(closes)

    # 10. Logging final
    tlogger.info(f"ATR-10: {atr_daily:.4f}")
    tlogger.info(f"VWAP {session_label}: {vwap_session:.4f}")
    tlogger.info(f"Latest price: {latest_price:.4f}")
    tlogger.info(f"Put wall: {put_wall}, cluster: {put_cluster}")
    tlogger.info(f"Call wall: {call_wall}, cluster: {call_cluster}")
    tlogger.info(f"Support VWAP: {support_vwap}")
    tlogger.info(f"Resistance VWAP: {resistance_vwap}")
    tlogger.info(f"Robust support: {robust_support:.2f}")
    tlogger.info(f"Robust resistance: {robust_resistance:.2f}")
    tlogger.info(f"SMA20: {sma20}, Min5d: {min5}, Max5d: {max5}")
    tlogger.info(f"Strong support: {strong_support:.2f} ({support_type})")
    tlogger.info(f"Strong resistance: {strong_resistance:.2f} ({resistance_type})")

    tlogger.info(f"[CLUSTER] put_cluster={put_cluster}  call_cluster={call_cluster}")

    # 11. Respuesta JSON
    return jsonify(
        status="OK",
        symbol=symbol,
        session=session_label,                        ### NEW
        latest_price=round(latest_price,4),
        streak_drawdown_pct=round(streak_dd, 2) if streak_dd is not None else None,  # racha acumulada
        pct_change=round(day_pct,   2) if day_pct   is not None else None,  # % diario “verdadero”
        ATR10=round(atr_daily,4),
        vwap_session=round(vwap_session,4),           ### NEW
        put_wall=put_wall,
        put_cluster=round(put_cluster,1) if put_cluster is not None else None,
        call_wall=call_wall,                          ### NEW
        call_cluster=round(call_cluster,1) if call_cluster is not None else None,
        zero_gamma=zero_gamma,
        anchored_vwap_swing=round(anch_vwap,2) if anch_vwap else None,
        hvn_poc=round(hvn_poc,2) if hvn_poc else None,
        ema20=round(ema20_today,4) if ema20_today else None,
        ema20_slope=round(ema20_slope,4) if ema20_slope else None,
        rsi14=round(rsi14,1),
        last_5_closes=_last_daily_closes(daily_pts, 5),
        pct_from_6m_high=round(pct_6m, 2) if pct_6m is not None else None,
        drawdown_6m_percentile=(
            round(drawdown_6m["percentile"])
            if drawdown_6m["percentile"] is not None
            else None
        ),
        drawdown_6m_samples=drawdown_6m["samples"],
        drawdown_6m_history_years=3,
        peak_ref=round(peak_val, 2) if peak_val is not None else None,
        peak_ref_date=peak_date,
        rel_volume=rel_volume,
        pcr_oi=round(pcr_oi,2) if pcr_oi is not None else None
    ), 200

# ----------------------- Helpers -----------------------

def _parse_request(request):
    if request.method != 'POST':
        return None, (jsonify(error="Only POST allowed"), 405)
    payload = request.get_json(silent=True)
    if not payload:
        return None, (jsonify(error="Invalid JSON body"), 400)
    symbol = None
    if 'symbol' in payload:
        symbol = payload['symbol']
    elif 'tickers' in payload:
        t = payload['tickers']
        symbol = t[0] if isinstance(t, list) and t else (t if isinstance(t, str) else None)
    if not symbol:
        return None, (jsonify(error="Missing 'symbol' or 'tickers' parameter"), 400)
    return symbol.upper(), None


def _fetch_time_series(symbol):
    url = (
        'https://www.alphavantage.co/query'
        f'?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min'
        f'&outputsize=full&extended_hours=true&apikey={ALPHA_VANTAGE_KEY}'
    )
    resp = requests.get(url)
    if resp.status_code != 200:
        return None, (jsonify(error="AlphaV API failed"), 502)
    return resp.json(), None


#def _parse_meta_and_series(data):
#    try:
#        meta = data['Meta Data']
#        series = data['Time Series (1min)']
#        return {
#            'information': meta['1. Information'],
#            'symbol': meta['2. Symbol'],
#            'last_refreshed': meta['3. Last Refreshed']
#        }, series, None
#    except KeyError:
#        return None, None, (jsonify(error="Invalid AlphaV response format"), 500)


def _sorted_timestamps(ts):
    return sorted(ts.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))


def _calculate_atr(ts, times, last_ref, period=10):
    true_ranges = []
    for i in range(1, min(period+1, len(times))):
        cur = ts[times[-i]]
        prev = ts[times[-i-1]]
        high = float(cur['2. high'])
        low = float(cur['3. low'])
        prev_close = float(prev['4. close'])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    return statistics.mean(true_ranges) if true_ranges else 0.0


def _determine_session_window(dt_et):
    # --- NUEVO: fin de semana = cerrado todo el día -----------------
    if dt_et.weekday() >= 5:                       # 5 = sábado, 6 = domingo
        last_friday = dt_et - timedelta(days=dt_et.weekday() - 4)
        return 'closed', last_friday.replace(hour=16, minute=0, second=0)

    t = dt_et.time()
    if t >= time(20,0) or t < time(4,0):
        return 'closed', dt_et.replace(hour=16, minute=0, second=0)
    if t >= time(16,0):
        return 'post-market', dt_et.replace(hour=16, minute=0, second=0)
    if t >= time(9,30):
        return 'regular', dt_et.replace(hour=9, minute=30, second=0)
    return 'pre-market', dt_et.replace(hour=4, minute=0, second=0)


def _calculate_session_vwap(ts, times, session_start, raw_last, regular_only=False): ### NEW
    cumul_vol=cumul_vp=0.0
    end_dt=datetime.strptime(raw_last,'%Y-%m-%d %H:%M:%S')
    for t in times:
        dt=datetime.strptime(t,'%Y-%m-%d %H:%M:%S')
        if regular_only and (dt.time()<datetime.strptime('09:30','%H:%M').time() or
                             dt.time()>datetime.strptime('16:00','%H:%M').time()):
            continue
        if session_start<=dt<=end_dt:
            p=(float(ts[t]['2. high'])+float(ts[t]['3. low'])+float(ts[t]['4. close']))/3
            v=float(ts[t]['5. volume'])
            cumul_vp+=p*v; cumul_vol+=v
    return cumul_vp/cumul_vol if cumul_vol else None


def _fetch_option_expirations(symbol):
    url = f'https://api.tradier.com/v1/markets/options/expirations?symbol={symbol}'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/xml'
    }

    # Logs para depurar la petición
    tlogger.error(f"[Tradier expirations] URL: {url}")
    tlogger.error(f"[Tradier expirations] Headers: {headers}")

    resp = requests.get(url, headers=headers)

    # Logs de la respuesta
    tlogger.error(f"[Tradier expirations] Status Code: {resp.status_code}")
    tlogger.error(f"[Tradier expirations] Response Headers: {resp.headers}")
    tlogger.error(f"[Tradier expirations] Body:\n{resp.text}")

    if resp.status_code != 200:
        try:
            err = resp.json().get('message', resp.text)
        except ValueError:
            err = resp.text
        tlogger.error(f"[Tradier expirations] Request failed: {err}")
        return None, (jsonify(error="Tradier expirations failed", details=err), resp.status_code)

    try:
        root = ET.fromstring(resp.text)
        dates = [d.text for d in root.findall('.//date')]
        if not dates:
            raise ValueError("No expiration dates found")
        tlogger.error(f"[Tradier expirations] Parsed dates: {dates}")
        return dates, None
    except Exception as e:
        tlogger.error(f"[Tradier expirations] XML parsing error: {e}", exc_info=True)
        return None, (jsonify(error="Tradier expirations parsing failed"), 502)


def _fetch_options_chain(symbol, expiration):
    url = (
        'https://api.tradier.com/v1/markets/options/chains'
        f'?symbol={symbol}&greeks=true&expiration={expiration}'
    )
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    resp = requests.get(url, headers=headers, timeout=8)
    if resp.status_code != 200:
        return None, (jsonify(error="Tradier options chain failed"), resp.status_code)

    try:
        data = resp.json() or {}
    except ValueError:
        return None, (jsonify(error="Tradier options chain JSON decode failed"), 502)

    opts = (((data.get("options") or {}).get("option")) or [])
    if isinstance(opts, dict):
        opts = [opts]

    contracts = []
    for o in opts:
        try:
            strike   = float(o.get('strike', 0))
            oi       = int(float(o.get('open_interest', 0) or 0))
            vol      = int(float(o.get('volume', 0) or 0))
            bid      = float(o.get('bid', 0) or 0)
            ask      = float(o.get('ask', 0) or 0)
            opt_type = (o.get('option_type') or '').lower()

            greeks = o.get('greeks') or {}
            gamma  = float(greeks.get('gamma', 0) or 0)

        except Exception:
            continue

        contracts.append({
            'strike': strike,
            'oi': oi,
            'vol': vol,
            'bid': bid,
            'ask': ask,
            'gamma': gamma,
            'option_type': opt_type
        })

    tlogger.info(f"[CHAIN] symbol={symbol} exp={expiration} total={len(contracts)}")
    return contracts, None


# ------------------------------------------------------------------
#  Gamma walls 2.0  ̶  filtra por γ-$, agrupa strikes contiguos
# ------------------------------------------------------------------

def _calculate_gamma_walls(contracts, spot, *, atr_window, avg_vol_5d):
    """
    Devuelve muros basados en gamma-$ REALMENTE fuertes:
      - usa OI * |gamma| (y spot^2) como base
      - filtra por liquidez: spread, volumen de contrato, OI mínimo
      - NO recorta por cercanía: si el muro fuerte está lejos, se deja
      - si no hay nada decente -> devuelve None
    """

    # ---- parámetros “solo fuertes” (ajustables) ---------------------------
    OI_MIN     = 250      # antes 150
    VOL_MIN    = 10       # antes 0
    SPREAD_MAX = 0.12     # antes 0.15
    DOM_MIN    = 0.15     # antes 0.12

    gamma_usd = {'put': {}, 'call': {}}
    meta      = {'put': {}, 'call': {}}

    for opt in contracts:
        s   = opt['strike']
        typ = opt['option_type']
        if typ not in ('put', 'call'):
            continue

        # “lado correcto”: puts bajo spot, calls sobre spot
        if typ == 'put' and s > spot:
            continue
        if typ == 'call' and s < spot:
            continue

        oi  = opt.get('oi', 0) or 0
        vol = opt.get('vol', 0) or 0
        bid = opt.get('bid', 0) or 0.0
        ask = opt.get('ask', 0) or 0.0
        spread_pct = None
        if bid > 0 and ask > 0 and ask >= bid:
            mid = (bid + ask) / 2
            if mid > 0:
                spread_pct = (ask - bid) / mid

        # filtro duro de liquidez (si no, “muro fantasma”)
        if oi < OI_MIN:
            continue
        if vol < VOL_MIN and oi < (4 * OI_MIN):
            continue
        if spread_pct is not None and spread_pct > SPREAD_MAX:
            continue

        g = abs(opt.get('gamma', 0.0)) * oi * (spot ** 2) * 0.01
        if g <= 0:
            continue

        gamma_usd[typ][s] = gamma_usd[typ].get(s, 0.0) + g

        # Para meta/strength necesitamos un número siempre:
        # si no hay bid/ask, no filtramos por spread, pero guardamos un "neutral" (0.10)
        SPREAD_REF = 0.10
        sp_for_meta = spread_pct if spread_pct is not None else SPREAD_REF

        # filtro duro de liquidez (si no, “muro fantasma”)
        if oi < OI_MIN:
            continue
        if vol < VOL_MIN and oi < (4 * OI_MIN):
            continue
        if spread_pct is not None and spread_pct > SPREAD_MAX:
            continue

        g = abs(opt.get('gamma', 0.0)) * oi * (spot ** 2) * 0.01
        if g <= 0:
            continue

        gamma_usd[typ][s] = gamma_usd[typ].get(s, 0.0) + g

        m = meta[typ].get(s, {"oi": 0, "vol": 0, "spread_pct": sp_for_meta})
        m["oi"] += oi
        m["vol"] += vol
        m["spread_pct"] = min(m.get("spread_pct", sp_for_meta), sp_for_meta)
        meta[typ][s] = m

    # si no queda nada, devolver vacío
    if not gamma_usd['put'] and not gamma_usd['call']:
        return None, None, {}, {}, {}, {}

    # clustering contiguo: agrupa strikes “cercanos” (paso ~ATR diario)
    def _cluster(side_dict, side_label):
        if not side_dict:
            return None, {}
        atr = atr_window or 1.0
        strikes = sorted(side_dict, reverse=(side_label == 'put'))

        clusters = []
        cur = [strikes[0]]
        for s in strikes[1:]:
            if abs(s - cur[-1]) <= atr:
                cur.append(s)
            else:
                clusters.append(cur)
                cur = [s]
        clusters.append(cur)

        best = max(clusters, key=lambda cl: sum(side_dict[x] for x in cl))
        top_strike = max(best, key=lambda x: side_dict[x])
        return top_strike, {x: side_dict[x] for x in best}

    put_wall,  put_bucket  = _cluster(gamma_usd['put'],  'put')
    call_wall, call_bucket = _cluster(gamma_usd['call'], 'call')

    # filtro de “dominancia”: si está demasiado repartido, NO hay muro “fuerte”
    def _enforce_dom(wall, bucket):
        if wall is None or not bucket:
            return None
        tot = sum(bucket.values()) or 1.0
        dom = bucket.get(wall, 0.0) / tot
        return wall if dom >= DOM_MIN else None

    put_wall  = _enforce_dom(put_wall, put_bucket)
    call_wall = _enforce_dom(call_wall, call_bucket)

    # si dominancia tumba el wall, vaciamos bucket (para que tu endpoint devuelva None)
    if put_wall is None:
        put_bucket = {}
    if call_wall is None:
        call_bucket = {}

    return put_wall, call_wall, put_bucket, call_bucket, meta['put'], meta['call']



def _apply_atr_filter(strike, spot_price, atr):
    if strike is None:
        return None
    return strike if abs(spot_price - strike) <= atr * 2 else None


def _calculate_volume_cluster(ts, times, last_ref,
                              wall_strike, atr, days=5, k=1.0):
    """Volumen medio de los candles cuyo precio está a ±k·ATR del muro."""
    if wall_strike is None:
        return 0

    last_dt  = datetime.strptime(last_ref, '%Y-%m-%d %H:%M:%S')
    start_dt = last_dt - timedelta(days=days)

    vols = []
    for t in times:
        dt = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
        if not (start_dt <= dt <= last_dt):
            continue

        # precio típico del candle
        price = (float(ts[t]['2. high'])
                 + float(ts[t]['3. low'])
                 + float(ts[t]['4. close'])) / 3

        if abs(price - wall_strike) <= k * atr:
            vols.append(int(ts[t]['5. volume']))
            
    tlogger.error(f"[VCL] strike={wall_strike}  k={k}  days={days} → {statistics.mean(vols) if vols else 0}")

    return statistics.mean(vols) if vols else 0


def _calculate_ranges(vwap, atr):
    lower = round(vwap - atr, 2)
    upper = round(vwap + atr, 2)
    return f"{lower}-{vwap:.2f}", f"{vwap:.2f}-{upper}"


def _select_robust_levels(contracts, spot_price, atr,
                          vwap, low_mult=1.5, high_mult=2.5):
    """
    Devuelve un par (support, resistance) buscando strikes de puts/calls
    cuya distancia al spot esté entre low_mult*ATR y high_mult*ATR.
    Si no hay ninguno, hace fallback a vwap ± low_mult*ATR.
    """
    put_cands = [
        opt['strike']
        for opt in contracts
        if opt['option_type']=='put'
           and low_mult*atr <= (spot_price - opt['strike']) <= high_mult*atr
    ]
    call_cands = [
        opt['strike']
        for opt in contracts
        if opt['option_type']=='call'
           and low_mult*atr <= (opt['strike'] - spot_price) <= high_mult*atr
    ]

    support = max(put_cands) if put_cands else (vwap - low_mult * atr)
    resistance = min(call_cands) if call_cands else (vwap + low_mult * atr)

    return support, resistance


def _fetch_daily_series(symbol, lookback_days=180):
    """
    Usa Tradier /v1/markets/history para obtener cierres diarios.
    Devuelve lista ordenada de (fecha 'YYYY-MM-DD', close_float).
    """
    cache_key = (symbol.upper(), int(lookback_days))
    cache_date = datetime.now(ZoneInfo("US/Eastern")).date().isoformat()
    cached = _DAILY_SERIES_CACHE.get(cache_key)
    if cached and cached[0] == cache_date:
        return list(cached[1])

    end_dt   = datetime.now(ZoneInfo("US/Eastern")).date()
    start_dt = end_dt - timedelta(days=lookback_days)

    url = 'https://api.tradier.com/v1/markets/history'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    params = {
        'symbol':   symbol,
        'interval': 'daily',
        'start':    start_dt.strftime('%Y-%m-%d'),
        'end':      end_dt.strftime('%Y-%m-%d')
    }

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        tlogger.error(f"Tradier history failed: {resp.status_code}  Body:\n{resp.text[:300]}")
        return []

    try:
        data = resp.json() or {}
    except ValueError:
        tlogger.error(f"Tradier history JSON decode error. Body:\n{resp.text[:300]}")
        return []

    days = (data.get('history') or {}).get('day') or []
    if isinstance(days, dict):  # Tradier puede devolver un único día como objeto
        days = [days]

    rows = []
    for d in days:
        date_str  = d.get('date')
        close_val = d.get('close')
        high_val  = d.get('high')
        low_val   = d.get('low')        
        if date_str is None or close_val is None or high_val is None or low_val is None:
            continue
        try:
            rows.append((date_str, float(close_val), float(high_val), float(low_val)))
        except Exception as e:
            tlogger.error(f"Bad daily row: {d} ({e})")

    rows = sorted(rows, key=lambda x: x[0])
    _DAILY_SERIES_CACHE[cache_key] = (cache_date, rows)
    return list(rows)



def _calculate_sma(prices, window=20):
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def _calculate_recent_extremes(prices, days=5):
    if len(prices) < days:
        return None, None
    window = prices[-days:]
    return min(window), max(window)

def _select_strongest(cands, latest_price, atr):
    if not cands:
        return None, None

    filtered = [c for c in cands if abs(latest_price - c['level']) <= 3*atr] or cands

    # Parámetros de penalización
    alpha = 1.0   # escala de ATR
    beta  = 0.5   # exponente de distancia
    lam   = 0.2   # factor lineal opcional

    total = 0.0
    for c in filtered:
        dist = abs(latest_price - c['level'])
        raw_strength = math.log10(c['strength'] + 1)

        # 1) penalización exponencial suave
        decay = math.exp(- (dist/(alpha*atr))**beta) if atr>0 else 1.0

        # 2) penalización lineal ligera (opcional)
        linear = max(0.0, raw_strength - lam*(dist/atr)) if atr>0 else raw_strength

        # Combina ambos
        raw_score = raw_strength * decay  
        # raw_score = linear  # o prueba esta otra variante

        c['raw_score'] = raw_score
        total += raw_score

    # Normaliza y escoge igual que antes...
    for c in filtered:
        c['score'] = round(c['raw_score']/total, 3) if total>0 else 0.0

    filtered.sort(
        key=lambda x: (x['score'], -abs(latest_price - x['level'])),
        reverse=True
    )
    best = filtered[0]
    return best['level'], best['type']


def _fetch_intraday_low_and_volcluster(ts, times, last_ref, window_min=30):
    """
    Devuelve (low_price, vol_at_low, avg_vol_window).
    - low_price: mínimo intradía
    - vol_at_low: volumen en el candle de ese mínimo
    - avg_vol: media de volumen de los últimos window_min minutos
    """
    end = datetime.strptime(last_ref, '%Y-%m-%d %H:%M:%S')
    start = end - timedelta(minutes=window_min)
    relevant = [(t, int(ts[t]['5. volume']), float(ts[t]['3. low'])) 
                for t in times 
                if start <= datetime.strptime(t, '%Y-%m-%d %H:%M:%S') <= end]
    if not relevant:
        return None, None, None
    low_candle = min(relevant, key=lambda x: x[2])
    vols = [v for (_, v, _) in relevant]
    return low_candle[2], low_candle[1], statistics.mean(vols)

def _fetch_realtime_price(symbol):
    url = 'https://api.tradier.com/v1/markets/quotes'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    params = {'symbols': symbol}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        tlogger.error(f"Tradier quotes failed: {resp.status_code}")
        return None

    qdata = resp.json().get('quotes', {}).get('quote')
    if not qdata:
        tlogger.error("Tradier quotes: empty")
        return None
    quote = qdata[0] if isinstance(qdata, list) else qdata

    bid = quote.get('bid')
    ask = quote.get('ask')
    if bid is not None and ask is not None:
        try:
            return (float(bid) + float(ask)) / 2
        except Exception as e:
            tlogger.error(f"Invalid bid/ask values: {bid}/{ask} ({e})")

    last = quote.get('last')
    if last is not None:
        try:
            return float(last)
        except Exception as e:
            tlogger.error(f"Invalid last price: {last} ({e})")

    tlogger.error("Tradier quotes: no usable price field")
    return None

def _fetch_session_low_via_tradier(symbol):
    """
    Obtiene directamente de Tradier el mínimo (low) de la sesión extendida
    usando el endpoint /markets/quotes JSON.
    """
    url = 'https://api.tradier.com/v1/markets/quotes'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    params = {'symbols': symbol}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        tlogger.error(f"Tradier quotes failed: {resp.status_code}")
        return None

    data = resp.json().get('quotes', {}).get('quote')
    if not data:
        tlogger.error("Tradier quotes: empty")
        return None

    quote = data[0] if isinstance(data, list) else data
    low = quote.get('low')
    try:
        return float(low) if low is not None else None
    except Exception:
        tlogger.error(f"Invalid low price: {low}")
        return None

def _fetch_min_last_days(daily_pts, days=2):
    """
    Devuelve el mínimo de cierres de los últimos `days` días hábiles,
    usando la serie diaria (Time Series Daily).
    """
    if len(daily_pts) < days:
        return None
    # daily_pts es lista ordenada de (fecha, close)
    closes = [c for (_d, c, _h, _l) in daily_pts[-days:]]
    return min(closes)

def _fetch_lows_from_intraday(ts, days=3):
    """
    ts: dict con todas las velas 1 min extendidas (clave='YYYY-MM-DD HH:MM:SS').
    days: cuántos días atrás queremos mirar (hoy incluido).
    Devuelve (min_session_low, min_n_days_low).
    """
    from datetime import datetime, timedelta, time

    # Ordenamos timestamps
    times = sorted(ts.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))

    # Último timestamp y su fecha
    last_dt = datetime.strptime(times[-1], '%Y-%m-%d %H:%M:%S')
    session_date = last_dt.date()

    # Defino inicio y fin de extended hours de cada día
    def session_bounds(date):
        start = datetime.combine(date, datetime.min.time()).replace(hour=4)
        end   = start.replace(hour=20)
        return start, end

    # 1) mínimo de la sesión extendida de hoy
    start0, end0 = session_bounds(session_date)
    session_lows = [
        float(ts[t]['3. low']) 
        for t in times
        if start0 <= datetime.strptime(t, '%Y-%m-%d %H:%M:%S') <= end0
    ]
    min_session_low = min(session_lows) if session_lows else None

    # 2) mínimo de los últimos N días (cierres intradía)
    min_n = None
    for d in range(days):
        date = session_date - timedelta(days=d)
        s, e = session_bounds(date)
        day_lows = [
            float(ts[t]['3. low']) 
            for t in times
            if s <= datetime.strptime(t, '%Y-%m-%d %H:%M:%S') <= e
        ]
        if day_lows:
            low = min(day_lows)
            min_n = low if (min_n is None or low < min_n) else min_n

    return min_session_low, min_n


# --- NUEVOS HELPERS -----------------------------------
def _calculate_zero_gamma(contracts, spot_price, atr_daily):
    """
    Devuelve el strike más próximo al precio spot donde la Γ neta
    cambia de signo (≈ “gamma-flip” real).
    Si no hay cruce, retorna None.
    """
    # 1) Acumula Γ neta por strike (puts = –Γ, calls = +Γ)
    gamma_net = {}
    for opt in contracts:
        s = opt['strike']
        g = opt['gamma'] * opt['oi'] * (1 if opt['option_type']=='call' else -1)
        gamma_net[s] = gamma_net.get(s, 0.0) + g

    # 2) Ordena strikes y localiza todos los cruces de signo
    strikes = sorted(gamma_net.keys())
    cumul = 0.0
    cross_candidates = []          # (strike, |strike-spot|)
    for s in strikes:
        prev_cumul = cumul
        cumul += gamma_net[s]
        if prev_cumul * cumul < 0:            # hay cambio de signo
            cross_candidates.append((s, abs(s - spot_price)))

    if not cross_candidates:
        return None

    # 3) Escoge el cruce cuya distancia al spot es mínima
    cross_candidates.sort(key=lambda x: x[1])
    best = cross_candidates[0][0]

    # 4) Sanity-check: descarta cruces demasiado lejos (>30 % del spot)
    return best if abs(best - spot_price) <= 2 * atr_daily else None

def _ema(values, window=20):
    k = 2/(window+1)
    ema = None
    for v in values:
        ema = v if ema is None else v*k + ema*(1-k)
    return ema

def _calculate_anchored_vwap(ts, times, anchor_time, last_ref):
    vol_sum = vp_sum = 0
    for t in times:
        if anchor_time <= t <= last_ref:
            p = (float(ts[t]['2. high']) + float(ts[t]['3. low']) + float(ts[t]['4. close']))/3
            v = float(ts[t]['5. volume'])
            vp_sum += p*v; vol_sum += v
    return vp_sum/vol_sum if vol_sum else None

def _calculate_hvn(ts, times, last_ref, days=5, bin_size=0.5):
    from collections import Counter
    end = datetime.strptime(last_ref,'%Y-%m-%d %H:%M:%S')
    start = end - timedelta(days=days)
    buckets = Counter()
    for t in times:
        dt = datetime.strptime(t,'%Y-%m-%d %H:%M:%S')
        if start<=dt<=end:
            price = float(ts[t]['4. close'])
            bucket = round(price/bin_size)*bin_size
            buckets[bucket]+=int(ts[t]['5. volume'])
    return max(buckets, key=buckets.get) if buckets else None


def _compute_streak_drawdown_pct(latest_price: float, daily_pts: list, last_ref=None):
    """Cumulative drawdown since the most recent positive‑close day.

    Parameters
    ----------
    latest_price : float
        Spot price to compare against (e.g. last trade or mid‑price).
    daily_pts : list[(str, float)]
        Daily closes ordered ascending: [("YYYY‑MM‑DD", close), …].
    last_ref : str | None, optional
        Kept only for backward compatibility. Ignored.

    Returns
    -------
    float | None
        Negative percentage (e.g. ‑2.7) if the market is in a
        continuous drawdown. ``None`` when no current down‑streak.
    """
    if not daily_pts:
        return None

    # --- 1. Vector de cierres (antiguo → reciente) ----------------------
    closes = [c for (_d, c, _h, _l) in daily_pts]
    n = len(closes)

    # --- 2. Localiza el inicio de la racha bajista ----------------------
    # Retrocede mientras cada cierre sea < cierre anterior.
    idx = n - 1  # índice del último cierre oficial
    while idx > 0 and closes[idx] < closes[idx - 1]:
        idx -= 1

    ref_close = closes[idx]

    # --- 3. ¿Hay drawdown activo? ---------------------------------------
    if latest_price >= ref_close:
        return None  # no hay bajada continua

    # --- 4. % acumulado --------------------------------------------------
    return (latest_price / ref_close - 1) * 100.0

def _rsi14(closes):
    gains = [max(0, c2-c1) for c1,c2 in zip(closes[:-1], closes[1:])]
    losses= [max(0, c1-c2) for c1,c2 in zip(closes[:-1], closes[1:])]
    avg_gain = sum(gains[-14:])/14
    avg_loss = sum(losses[-14:])/14 or 1e-9
    rs = avg_gain/avg_loss
    return 100 - 100/(1+rs)

def _safe_int(x):
    """Convierte a int; None, '', 'NaN' → 0."""
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0

def _calculate_session_volume(ts, times, session_start, last_ref):
    end_dt = datetime.strptime(last_ref, '%Y-%m-%d %H:%M:%S')
    total  = 0
    for t in times:
        dt = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
        if session_start <= dt <= end_dt:
            total += _safe_int(ts[t].get('5. volume'))
    return total          # puede ser 0, pero ya no levanta excepción

#def _fetch_daily_volume_avg(symbol, days=10):
#    url = 'https://www.alphavantage.co/query'
#    params = {
#        'function': 'TIME_SERIES_DAILY_ADJUSTED',
#        'symbol':   symbol,
#        'apikey':   ALPHA_VANTAGE_KEY,
#        'outputsize': 'compact'
#    }
#    data = requests.get(url, params=params).json().get('Time Series (Daily)', {})
#    vols = [int(day['6. volume']) for _, day in sorted(data.items())[-days:]]
#    return statistics.mean(vols) if vols else None

def _fetch_daily_volume_avg(symbol, days=10):
    """
    Media de volumen de los últimos `days` días hábiles usando Tradier.
    """
    url = 'https://api.tradier.com/v1/markets/history'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    params = {
        'symbol': symbol,
        'interval': 'daily'
    }
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        tlogger.error(f"Tradier history failed: {resp.status_code}")
        return None

    days_list = resp.json().get('history', {}).get('day')
    if not days_list:
        tlogger.error("Tradier history: empty")
        return None

    # Aseguramos orden por fecha y tomamos los últimos `days` registros
    rows = days_list if isinstance(days_list, list) else [days_list]
    rows = sorted(rows, key=lambda d: d.get('date'))[-days:]

    vols = []
    for r in rows:
        try:
            vols.append(int(float(r.get('volume', 0))))
        except (TypeError, ValueError):
            continue

    return statistics.mean(vols) if vols else None

def _calculate_rel_volume(session_vol, avg_vol):
    return session_vol / avg_vol if session_vol and avg_vol else None          ### NEW

def _calculate_pcr_oi(contracts, spot, atr_daily):                                 ### NEW
    puts = calls = 0
    for opt in contracts:
        if abs(opt['strike'] - spot) <= 2 * atr_daily:         # ventana ATM ±2 ATR
            if opt['option_type'] == 'put':
                puts  += opt['oi']
            else:
                calls += opt['oi']
    return puts / calls if calls else None

# tabla U-shape empírica (0-100 %); puedes afinarla más tarde
_INTRADAY_CDF = {
    10: 0.22, 11: 0.35, 12: 0.44, 13: 0.52, 14: 0.62, 15: 0.75, 16: 1.00
}

def _expected_cdf(dt_et):
    h = dt_et.hour if dt_et.minute < 30 else dt_et.hour + 1
    h = min(max(h, 10), 16)           # clamp 10-16
    return _INTRADAY_CDF[h]


def _fetch_time_series_tradier(symbol, start_iso, end_iso):
    url = 'https://api.tradier.com/v1/markets/timesales'
    headers = {
        'Authorization': f'Bearer {TRADIER_TOKEN}',
        'Accept': 'application/json'
    }
    params = {
        'symbol': symbol,
        'interval': '1min',
        'start':   start_iso,
        'end':     end_iso,
        'session_filter': 'all'
    }

    r = requests.get(url, headers=headers, params=params)

    # ---------- LOG BÁSICO DE LA RESPUESTA -------------
    tlogger.error(f"[Tradier TS] HTTP {r.status_code}  –  bytes={len(r.content)}")
    #   Solo si no es 200 o es muy corta imprimo el cuerpo completo
    if r.status_code != 200 or len(r.content) < 150:
        tlogger.error(f"[Tradier TS] Body:\n{r.text[:500]}")

    # ---------- 1) código HTTP distinto de 200 ----------
    if r.status_code != 200:
        return None

    # ---------- 2) intento de parseo JSON ---------------
    try:
        data = r.json() or {}
    except ValueError as e:
        tlogger.error(f"[Tradier TS] JSON decode error: {e}")
        tlogger.error(f"[Tradier TS] Raw body:\n{r.text[:500]}")
        return None

    # Tradier puede devolver {"series":null} fuera de horario
    series = data.get('series') or {}
    if not isinstance(series, dict):               # ← NUEVO ✔
        tlogger.error("[Tradier TS] ‘series’ no es dict – fuera de mercado")
        return None                                #    ⇒ devolverá 502

    rows = series.get('data') or []
    if not isinstance(rows, list):                 # ← el check que ya tenías
        tlogger.error("[Tradier TS] ‘data’ no es lista – fuera de mercado")
        return None

    ts = {}
    for row in rows:
        raw = row['time']                         # '09:30' o ISO
        date_part, time_part = (raw.split('T') if 'T' in raw
                                else (start_iso[:10], raw))
        if len(time_part) == 5:      # HH:MM → HH:MM:00
            time_part += ':00'
        key = f"{date_part} {time_part}"
        ts[key] = {
            '2. high':   row['high'],
            '3. low':    row['low'],
            '4. close':  row['close'],
            '5. volume': row['volume']
        }
    return ts

def _atr_daily(daily_pts, period=10):
    # daily_pts: [(date, close, high, low), ...]
    trs = []
    n = len(daily_pts)
    if n < 2:
        return 0.0

    for i in range(1, min(period+1, n)):
        _d, close, high, low = daily_pts[-i]
        _dp, prev_close, _hp, _lp = daily_pts[-i-1]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)

    return statistics.mean(trs) if trs else 0.0

def _discard_spent_wall(strike, spot_price, atr, side='put', thr=0.3):
    """
    Devuelve None si el precio ha roto el muro > thr·ATR.
      • side='put'  →  descarta si spot < strike – thr·ATR
      • side='call' →  descarta si spot > strike + thr·ATR
    """
    if strike is None or atr <= 0:
        return strike
    delta = spot_price - strike
    if side == 'put'  and delta < -thr*atr:
        return None
    if side == 'call' and delta >  thr*atr:
        return None
    return strike

def _find_valid_wall(wall, buckets, side,
                     spot_price, atr, top_strength,
                     thr_strength=0.70, thr_spent=0.30):
    """
    Devuelve el primer strike «usable»:
      • intacto (< thr_spent × ATR de penetración)
      • fuerza ≥ thr_strength × fuerza_top
    """

    # intenta el ganador original
    # w = _apply_atr_filter(wall, spot_price, atr)
    w = _discard_spent_wall(wall, spot_price, atr, side, thr_spent)
    if w is not None:
        return w

    # resto de strikes ordenados por fuerza ↓
    for s, strength in sorted(buckets.items(), key=lambda x: x[1], reverse=True):
        if strength < thr_strength * top_strength:
            break                      # todos los siguientes serán más débiles
        # w = _apply_atr_filter(s, spot_price, atr)
        w = _discard_spent_wall(s, spot_price, atr, side, thr_spent)
        if w is not None:
            return w
    return None  


def _pick_nearest_wall(
    buckets: dict,
    spot: float,
    atr: float,
    ts: dict,
    times: list,
    last_ref: str,
    side: str = "put",
    thr_spent: float = 0.30,
    near_thr: float = 1.0   # ← se mantiene para compat., ya no se usa
):
    """
    Devuelve el muro ganador basado **únicamente en la fuerza** dentro de ±1·ATR
      • fuerza = media geométrica (γ-USD normalizado × cluster_vol normalizado)
      • ignora strikes fuera de ese rango o “gastados” > thr_spent·ATR
      • si todos se descartan, fallback = strike con γ-USD más alto
    """
    import math

    if not buckets:
        tlogger.warning(f"[{side.upper()}] sin candidatos tras filtros → wall=None")
        return None

    # Normalizadores ---------------------------------------------------------
    gamma_max   = max(buckets.values())
    cluster_max = max(
        _calculate_volume_cluster(ts, times, last_ref, k, atr) for k in buckets
    ) or 1

    tlogger.error(
        f"[{side.upper()}] ► parámetros  ATR={atr:.2f}  thr_spent={thr_spent}"
    )

    scored = {}
    dbg_rows = []

    for strike, g_usd in buckets.items():
        dist = abs(spot - strike)

        # 2) fuerza = √(γ-norm × cluster-norm)
        g_norm = g_usd   / gamma_max  if gamma_max   else 0
        cluster = _calculate_volume_cluster(ts, times, last_ref, strike, atr)
        c_norm = cluster / cluster_max if cluster_max else 0

        # ③  ─── factor de distancia  --------------------------
        #if dist <= atr:                 # sin castigo dentro de 1·ATR
        d_pen = 1.0
        #else:                           # >1·ATR → penaliza suave
            # e^(-x / 0.5·ATR)  ⇒ a 2·ATR vale ≈ 0,14
        #    d_pen = max(0.0, 1 - (dist - atr) / (3 * atr))

        # ④  ─── fuerza final  ---------------------------------
        W_C, W_G = 0.30, 0.70
        strength = d_pen * (W_C * c_norm + W_G * g_norm)

        # 3) muro gastado
        spent = (spot < strike - thr_spent*atr) if side == "put" \
                else (spot > strike + thr_spent*atr)
        if spent:
            continue

        scored[strike] = strength

        # ---- log detallado por strike --------------------------------------
        tlogger.error(
            f"[{side.upper()}] {strike:6.1f}  γ$={g_usd/1e3:6.1f}k  "
            f"cl={cluster:6.0f}  gN={g_norm:.2f}  cN={c_norm:.2f}  "
            f"str={strength:.3f}"
        )
        # ----------  LOG TABLA COMPLETA --------------
        dbg_rows.append({
            "strike":   strike,
            "gamma_k":  g_usd / 1e3,
            "cluster":  cluster,
            "g_norm":   round(g_norm, 3),
            "c_norm":   round(c_norm, 3),
            "strength": round(strength, 3),
            "dist":     round(dist, 2),
            "spent":    spent
        })

    tlogger.error(f"[{side.upper()}] ***** SCORED *****")
    for row in sorted(dbg_rows, key=lambda r: r["strength"], reverse=True):
        tlogger.error(
            f"{side.upper():>3} {row['strike']:7.1f} | "
            f"str={row['strength']:.3f}  γ$={row['gamma_k']:6.1f}k  "
            f"cl={row['cluster']:6.0f}  gN={row['g_norm']:.2f}  "
            f"cN={row['c_norm']:.2f}  dist={row['dist']:.2f}  "
            f"spent={'Y' if row['spent'] else 'N'}"
        )

    # ---------- elección final ----------------------------------------------
    if scored:
        best = max(scored, key=scored.get)        # pura fuerza
        tlogger.error(f"[{side.upper()}] ► ganador = {best}")
        return best

    # fallback: todos gastados o fuera de rango → γ-USD más alto
    fallback = max(buckets, key=buckets.get)
    tlogger.warning(f"[{side.upper()}] fallback = {fallback} (sin candidatos)")
    return fallback


def _pct_from_6m_high(latest_price: float, daily_pts: list):
    """
    % desde el máximo de cierre de los últimos ~6 meses (180 días).
    Devuelve valor negativo si el precio está por debajo del máximo.
    """
    if not daily_pts:
        return None

    # daily_pts: [(date, close), ...] ordenado ascendente
    _, high_6m = max(daily_pts, key=lambda x: x[1])

    if high_6m == 0:
        return None

    return (latest_price / high_6m - 1.0) * 100.0

def _pick_expirations(expirations, max_n=4, max_dte_days=35):
    """
    Coge los próximos vencimientos, pero evitando irte demasiado lejos.
    expirations viene como ['YYYY-MM-DD', ...]
    """
    out = []
    now = datetime.now(ZoneInfo("US/Eastern")).date()
    for d in expirations:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except:
            continue
        dte = (dt - now).days
        if dte < 0:
            continue
        if dte <= max_dte_days:
            out.append(d)
        if len(out) >= max_n:
            break
    return out or expirations[:max_n]


def _wall_strength(wall_strike, bucket_gamma, meta_by_strike):
    """
    Devuelve un “strength” 0..100 para el muro (y None si no hay muro).
    Mezcla:
      - dominancia de gamma-$ dentro del bucket
      - liquidez (spread)
      - volumen relativo del contrato dentro del bucket
    """
    if wall_strike is None or not bucket_gamma:
        return None

    total = sum(bucket_gamma.values()) or 1.0
    dom = bucket_gamma.get(wall_strike, 0.0) / total  # 0..1

    m = (meta_by_strike or {}).get(wall_strike, {}) or {}
    # liquidez: 1.0 si spread muy bajo, 0 si spread muy alto
    SPREAD_REF = 0.10
    sp = m.get("spread_pct", 1.0)
    if sp is None:
        sp = SPREAD_REF

    liq = max(0.0, 1.0 - (sp / SPREAD_REF))
    
    vol = m.get("vol", 0)

    # volumen: relativo al mejor del bucket
    vmax = 0
    for s in bucket_gamma.keys():
        vmax = max(vmax, (meta_by_strike or {}).get(s, {}).get("vol", 0))
    vol_norm = (vol / vmax) if vmax else 0.0
    vol_norm = max(0.0, min(1.0, vol_norm))

    # combina (ajustable)
    score = 100.0 * dom * (0.65 * liq + 0.35 * vol_norm)
    return round(score, 1)

def _dte_days(expiration: str, now_date):
    try:
        return (datetime.strptime(expiration, "%Y-%m-%d").date() - now_date).days
    except Exception:
        return None

def _pcr_oi_sums(contracts, spot: float, pct_window: float = 0.05):
    lo = spot * (1.0 - pct_window)
    hi = spot * (1.0 + pct_window)

    puts = 0
    calls = 0

    for opt in contracts or []:
        try:
            s = float(opt.get("strike", 0) or 0)
        except Exception:
            continue
        if s < lo or s > hi:
            continue

        oi = int(opt.get("oi", 0) or 0)
        typ = opt.get("option_type")

        if typ == "put":
            puts += oi
        elif typ == "call":
            calls += oi

    return puts, calls

def _pct_from_rolling_high(latest_price: float, daily_pts: list, lookback: int = 63, use_close: bool = True):
    """
    % desde el máximo reciente (rolling) en una ventana.
    daily_pts: [(date, close, high, low), ...] ordenado ascendente
    lookback: número de velas diarias a mirar (63 ~ 3 meses de trading)
    use_close: True => máximo por cierres; False => máximo por high intradía
    Devuelve: (pct, peak_value, peak_date)
    """
    if not daily_pts:
        return None, None, None

    window = daily_pts[-lookback:] if len(daily_pts) > lookback else daily_pts

    if use_close:
        peak_row = max(window, key=lambda x: x[1])   # close
        peak_val = peak_row[1]
    else:
        peak_row = max(window, key=lambda x: x[2])   # high
        peak_val = peak_row[2]

    peak_date = peak_row[0]
    if not peak_val:
        return None, None, None

    pct = (latest_price / peak_val - 1.0) * 100.0
    return pct, peak_val, peak_date

def _last_daily_closes(daily_pts, limit=5):
    rows = []

    for date_value, close, _high, _low in daily_pts[-limit:]:
        rows.append({
            "date": date_value.isoformat() if hasattr(date_value, "isoformat") else str(date_value),
            "close": round(float(close), 4),
        })

    return rows
