"""Exact observations for maintenance, NOT a relevance classifier or retain gate.

Report/source payloads are immutable. A refreshed capture timestamp is not a
market move; an already supplied headline is not independently verified news.
All real differences and all current source items remain available, without
rounding, thresholds, list caps or suppression of uncertainty/critical guards.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from datetime import datetime, timezone


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _pointer(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def _diff(old, new, old_path, new_path):
    if isinstance(old, dict) and isinstance(new, dict):
        rows = []
        for key in sorted(set(old) | set(new)):
            a, b = old_path + "/" + _pointer(key), new_path + "/" + _pointer(key)
            if key not in old or key not in new:
                rows.append({"previous_pointer": a, "current_pointer": b,
                    "previous_present": key in old, "current_present": key in new,
                    "previous": deepcopy(old.get(key)), "current": deepcopy(new.get(key))})
            else:
                rows.extend(_diff(old[key], new[key], a, b))
        return rows
    # Arrays compared exactly; keep full values, including order and origins.
    if _sha(old) == _sha(new):
        return []
    return [{"previous_pointer": old_path, "current_pointer": new_path,
             "previous_present": True, "current_present": True,
             "previous": deepcopy(old), "current": deepcopy(new)}]


def _market(reference, slim, root):
    old = reference.get("slim_snapshot")
    if not isinstance(old, dict) or not old:
        return {"baseline_available": False, "same_market_values": None,
                "changed_groups": [], "changes": [], "capture_only_changes": []}
    # ONLY these two top-level transport fields are bookkeeping. Do not remove
    # expiry dates, option DTE, event dates, feed freshness or other timestamps.
    bookkeeping = {"as_of", "mirror_url"}
    a = {k: v for k, v in old.items() if k not in bookkeeping}
    b = {k: v for k, v in slim.items() if k not in bookkeeping}
    changes = _diff(a, b, root + "/slim_snapshot", "/slim")
    return {"baseline_available": True, "same_market_values": not changes,
        "changed_groups": sorted({row["current_pointer"].split("/")[2] for row in changes}),
        "changes": changes,
        "capture_only_changes": _diff({k: v for k, v in old.items() if k in bookkeeping},
            {k: v for k, v in slim.items() if k in bookkeeping}, root + "/slim_snapshot", "/slim")}


def _time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def _identity(item, kind):
    if kind == "news":
        value = item.get("articleId") or item.get("id")
        if value:
            return (str(item.get("providerCode") or item.get("source") or ""), str(value))
    # Analyst records without a canonical event ID get exact-payload identity,
    # never a guessed firm/date match that could hide changed target/guidance.
    elif item.get("id") or item.get("event_id"):
        return (str(item.get("source") or ""), str(item.get("id") or item.get("event_id")))
    return ("exact_payload", _sha(item))


def _source_items(reference, kind):
    field, items = ("ibkr_recent_news", "items") if kind == "news" else ("analyst_recent_actions", "actions")
    source = reference.get(field)
    source = source if isinstance(source, dict) else {}
    values = source.get(items)
    return values if isinstance(values, list) else []


def _source_observations(context, reference, root, kind):
    source_key, items_key = ("news", "items") if kind == "news" else ("analyst_actions", "actions")
    source = context.get(source_key) or {}
    current = source.get(items_key) or []
    previous = _source_items(reference, kind)
    known = {}
    for index, item in enumerate(previous):
        if isinstance(item, dict):
            known.setdefault(_identity(item, kind), []).append((index, item))
    baseline_at = _time(reference.get("generated_at"))
    rows = []
    for index, item in enumerate(current):
        matches = known.get(_identity(item, kind), [])
        exact = [(i, v) for i, v in matches if _sha(v) == _sha(item)]
        published = _time(item.get("published_at"))
        chronology = ("unknown" if published is None or baseline_at is None else
                      "after_report" if published > baseline_at else "at_or_before_report")
        rows.append({"current_pointer": f"/{source_key}/{items_key}/{index}",
            "identity": list(_identity(item, kind)),
            "baseline_presence": "identical" if exact else "same_id_changed" if matches else "not_supplied",
            "previous_indices": [i for i, _ in matches], "chronology": chronology})
    return {"baseline_root": root,
        "baseline_source_field": "ibkr_recent_news" if kind == "news" else "analyst_recent_actions",
        "current_source_complete": source.get("status") == "ok" and source.get("truncated") is not True,
        "previous_supplied_count": len(previous), "current_count": len(current),
        "identical_count": sum(row["baseline_presence"] == "identical" for row in rows),
        "changed_same_id_count": sum(row["baseline_presence"] == "same_id_changed" for row in rows),
        "newly_supplied_count": sum(row["baseline_presence"] == "not_supplied" for row in rows),
        "after_report_count": sum(row["chronology"] == "after_report" for row in rows),
        "observations": rows,
        "meaning": "Supplied before is NOT independently verified or necessarily assessed. Older newly supplied items may be omitted material risks; disappearance from a rolling window is NOT retraction."}


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _geometry(reference, slim):
    from src.local_runner.report_schema import parse_report
    md = reference.get("analysis_markdown")
    if not isinstance(md, str) or not md:
        return {"available": False}
    plan = parse_report(md, latest_price=None)["plan"]
    price, previous = slim.get("latest_price"), reference.get("latest_price")
    target = plan.get("target")
    return {"available": True, "current_price": price, "previous_report_price": previous,
        "same_reference_price": _finite(price) and _finite(previous) and price == previous,
        "target": target,
        "target_above_current_price": target > price if _finite(target) and _finite(price) else None,
        "meaning": "Numeric observation only. A target below live price does not by itself invalidate a lower-entry plan; stop/entry geometry and structural guards remain authoritative."}


def plan_quote_observations(context):
    """Separate quote location from plan validity; never infer a traded path.

    Endpoints can describe above/below/overlap, not a confirmed breakout,
    defense, executed entry/stop, or changed decision. All prices stay exact.
    Typed report authority wins over stale numeric mirrors. No routing gate,
    threshold, market-data replacement or synthesized confirmation is added.
    """
    from src.local_runner.semantic_report import reference_document

    reference = context.get('reference') or {}
    slim = context.get('slim') or {}
    baseline = reference.get('slim_snapshot') or {}
    document = reference_document(reference) if reference.get('analysis_markdown') else None

    def quote(snapshot, fallback=None):
        state = snapshot.get('market_state') or {}
        price = snapshot.get('latest_price', fallback)
        bid, ask = state.get('bid'), state.get('ask')
        valid = _finite(bid) and _finite(ask) and 0 < bid <= ask
        return {'as_of': snapshot.get('as_of'),
                'reference_price': price if _finite(price) and price > 0 else None,
                'bid': bid, 'ask': ask, 'valid_bid_ask': valid}

    def position(price, zone):
        if not _finite(price) or price <= 0 or zone is None:
            return None
        return 'below' if price < zone['lower'] else 'above' if price > zone['upper'] else 'within'

    def location(sample, zone):
        valid = sample['valid_bid_ask'] and zone is not None
        return {'reference_price_position': position(sample['reference_price'], zone),
                'bid_position': position(sample['bid'], zone) if valid else None,
                'ask_position': position(sample['ask'], zone) if valid else None,
                'bid_ask_overlaps_zone': (sample['bid'] <= zone['upper']
                    and sample['ask'] >= zone['lower']) if valid else None}

    previous = quote(baseline, reference.get('latest_price'))
    current = quote(slim)
    owned = context.get('owned') if type(context.get('owned')) is bool else None
    rows = {}
    plan = document['plan'] if document else {}
    for key, block in plan.items():
        zone = block['range']
        rows[key] = {'range': deepcopy(zone),
                     'previous_quote': location(previous, zone),
                     'current_quote': location(current, zone)}
        if key == 'management_stop':
            rows[key]['protects_recorded_position'] = owned
    target = (plan.get('target') or {}).get('range')
    entries = {key: block['range'] for key, block in plan.items()
               if key in ('entry', 'ambitious_entry') and block['range'] is not None}
    return {'contract': 'plan-quote-observations-v1', 'owned': owned,
            'previous_quote': previous, 'current_quote': current, 'levels': rows,
            'target_above_entries': {key: target['lower'] > zone['upper'] if target else None
                                     for key, zone in entries.items()},
            'meaning': 'Endpoint locations only, not the intraperiod traded path. '
                'No confirmed breakout, lost support, execution or action change is inferred. '
                'Bid/ask overlap is quote ambiguity, not proof that a level failed or held. '
                'A lower-entry target need not be above the current quote. '
                'With owned=false the management stop protects no recorded position; '
                'structural risk, guards and ITV remain independently authoritative.'}


def plan_source_inventory(context):
    """Exact source locations in existing zones, never a support-loss verdict.

    Do not guess a matching strike/expiry or treat historical evidence as live.
    The model still reads surrounding origins and judges the common full rubric.
    """
    from src.common.analysis_validator import extract_range
    reference = context.get("reference") or {}
    md = reference.get("analysis_markdown") or ""
    zones = []
    if context.get('routing_revision', 1) >= 29 and md:
        from src.local_runner.semantic_report import reference_document
        from src.local_runner.plan_scope import plan_labels
        from types import SimpleNamespace
        plan = reference_document(reference, verify_projection=True)['plan']
        selected = [(label, SimpleNamespace(**plan[key]['range']) if plan[key]['range'] else None)
                    for key, label in plan_labels(context['routing_revision']).items()]
    else:
        selected = [(label, extract_range(md, label)) for label in
                    ("Entrada", "Entrada ambiciosa", "Resistencia estructural")]
    for label, zone in selected:
        row = {"label": label, "range": {'lower': zone.lower, 'upper': zone.upper} if zone else None,
               "current": [], "historical": []}
        if zone:
            for state, snapshot, root in (
                    ("current", context.get("slim") or {}, "/slim/levels"),
                    ("historical", reference.get("slim_snapshot") or {}, "/reference/slim_snapshot/levels")):
                levels = snapshot.get("levels") or {}
                for kind in ("supports", "resistances", "put_walls_top", "call_walls_top"):
                    items = levels.get(kind) or []
                    if not isinstance(items, list):
                        continue
                    for index, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        level = item.get("level")
                        if not _finite(level) or not zone.lower <= level <= zone.upper:
                            continue
                        row[state].append({"pointer": f"{root}/{kind}/{index}",
                            "source_list": kind, "level": level,
                            "type": item.get("type"), "expiration": item.get("expiration")})
        zones.append(row)
    return {"contract": "plan-source-inventory-v1", "zones": zones,
        "meaning": "Exact in-range source presence only, NOT proof of strength, independent origin, live expiry or total support loss. Read each original item and surrounding full slim evidence. Duplicate option copies are not independent origins. Historical rows are NOT current backing; empty rows or an absent range are NOT a relevance verdict. No proximity tolerance, scoring, list cap or automatic routing."}


def deterministic_comparison(context):
    current = context.get("reference") or {}
    anchor = context.get("sol_reference") or {}
    slim = context.get("slim") or {}
    current_md, anchor_md = current.get("analysis_markdown"), anchor.get("analysis_markdown")
    return {"contract": "deterministic-maintenance-delta-v1",
        "same_current_and_sol_markdown": current_md == anchor_md if current_md and anchor_md else None,
        "since_current": _market(current, slim, "/reference"),
        "since_full_sol": _market(anchor, slim, "/sol_reference"),
        "news_since_current": _source_observations(context, current, "/reference", "news"),
        "news_since_full_sol": _source_observations(context, anchor, "/sol_reference", "news"),
        "analyst_actions_since_full_sol": _source_observations(context, anchor, "/sol_reference", "analyst_actions"),
        "current_plan_geometry": _geometry(current, slim),
        "authority": "Exact factual differences only. No automatic retain/escalate, no materiality judgement, no suppression of ITV/critical events/omitted risks or source completeness checks."}
