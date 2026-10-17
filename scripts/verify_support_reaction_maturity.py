"""Check deployed raw/slim evidence; no models or analysis publication.

The raw market-data service performs its normal technical-JSON mirror refresh.
Diagnostic responses are preserved separately from reports and frozen receipts.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests


def main():
    destination = Path(__file__).resolve().parents[1] / "logs/incidents/20261008-ccj-reaction-maturity"
    destination.mkdir(parents=True, exist_ok=True)
    payloads = {}
    for layer in ("raw", "slim"):
        response = requests.get(
            f"https://support-resistances-{layer}-qauoswkmwa-no.a.run.app",
            params={"symbol": "CCJ"}, timeout=115,
        )
        response.raise_for_status()
        payload = response.json()
        (destination / f"{layer}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        payloads[layer] = payload
        assert payload["volume_profile"]["status"] == "available", layer
        levels = payload if layer == "raw" else payload["levels"]
        checked = 0
        for kind in ("supports", "put_walls_top"):
            for item in levels[kind]:
                reaction = (
                    (item.get("meta") or {}).get("historical_reaction")
                    or item.get("historical_reaction")
                    or (item.get("evidence") or {}).get("historical_reaction")
                )
                assert reaction, (layer, kind, item.get("level"))
                if reaction.get("reason") == "insufficient_daily_history":
                    continue
                assert reaction["observation_policy"] == "complete_forward_window_only"
                assert reaction["forward_sessions"] == 5
                if reaction["pending_test_count"]:
                    assert 0 <= reaction["last_pending_observed_sessions"] < 5
                    if reaction["status"] == "available":
                        assert reaction["last_test_date"] < reaction["last_pending_test_date"]
                if reaction["status"] == "available":
                    assert 0 <= reaction["defense_count"] <= reaction["test_count"]
                checked += 1
        wall = next(row for row in levels["put_walls_top"] if row["level"] == 90.0)
        evidence = wall.get("historical_reaction") or wall["evidence"]["historical_reaction"]
        print(json.dumps({"layer": layer, "checked_levels": checked, "CCJ_90": evidence}), flush=True)
    print("OK: deployed complete-window evidence reaches slim; no model call.", flush=True)


if __name__ == "__main__":
    main()
