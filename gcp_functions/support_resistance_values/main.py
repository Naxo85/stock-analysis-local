"""Local reference for the live `support-resistance-values` Cloud Function.

The live function currently contains the full implementation pasted during the
thread. This local copy intentionally does not include secrets. Keep the real
Tradier token configured only in the live Cloud Function until this function is
fully migrated to Secret Manager or environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Iterable


# The live Cloud Function has the real value configured there.
# Do not commit the real token to this repository.
TRADIER_TOKEN = "LIVE_VALUE_CONFIGURED_IN_CLOUD_FUNCTION"


def support_resistance(request):  # pragma: no cover - reference stub
    """Reference stub for the live endpoint.

    Live endpoint:
    https://support-resistance-values-714254943648.europe-southwest1.run.app/

    Request shape:
    {
      "symbol": "HOOD",
      "price": 93
    }

    Current live response includes fields such as:
    - ATR10
    - anchored_vwap_swing
    - call_cluster
    - call_wall
    - ema20
    - ema20_slope
    - hvn_poc
    - latest_price
    - pcr_oi
    - pct_change
    - pct_from_6m_high
    - peak_ref
    - peak_ref_date
    - put_cluster
    - put_wall
    - rel_volume
    - rsi14
    - session
    - status
    - streak_drawdown_pct
    - symbol
    - vwap_session
    - zero_gamma

    Suggested next response field:
    - last_5_closes: daily closes for the ticker, ordered oldest -> newest,
      for relative momentum checks against QQQ.

    Next migration step:
    replace this reference stub with the full live implementation, but read the
    Tradier token from Secret Manager or an environment variable instead of
    hardcoding it.
    """

    raise NotImplementedError(
        "Reference stub only. The full implementation is still live in GCP."
    )


def get_tradier_token() -> str:
    """Future-safe token accessor for the full migrated implementation."""

    return os.environ.get("TRADIER_TOKEN", TRADIER_TOKEN)


def last_daily_closes(daily_points: Iterable[tuple[Any, float, float, float]], limit: int = 5) -> list[dict[str, Any]]:
    """Return the last N daily closes from the live function's daily series.

    The live implementation builds daily points as tuples shaped like:
    `(date, close, high, low)`.
    """

    points = list(daily_points)[-limit:]
    rows: list[dict[str, Any]] = []

    for date_value, close, _high, _low in points:
        rows.append(
            {
                "date": date_value.isoformat() if hasattr(date_value, "isoformat") else str(date_value),
                "close": round(float(close), 4),
            }
        )

    return rows
