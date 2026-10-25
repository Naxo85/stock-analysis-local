"""Deterministic safeguards for Luna -> Sol review routing."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from src.local_runner.level_continuity import build_level_continuity_precheck
from src.common.analysis_validator import extract_range, _extract_line_value, _normalize_for_match
from src.local_runner.report_schema import parse_report


def load_policy(root: Path) -> dict:
    policy = json.loads((root / "config/codex_analysis.json").read_text(encoding="utf-8"))
    return validate_policy(policy)


def validate_policy(policy: dict) -> dict:
    """Validate file-loaded and explicitly supplied policies with identical rules."""
    for key in ("max_model_parallel", "priority_itv_sessions", "watchlist_itv_sessions",
                "max_snapshot_age_hours",
                "triage_timeout_seconds", "report_timeout_seconds"):
        if type(policy.get(key)) is not int or policy[key] <= 0:
            raise ValueError(f"invalid_adaptive_policy: {key}")
    if policy["report_effort"] != "high":
        raise ValueError("authoritative_report_requires_high")
    if policy.get('maintenance_context_transport') not in (None, 'pointer-diff-v1'):
        raise ValueError('unsupported_maintenance_context_transport')
    if policy.get('volume_calculation_guidance') not in (None, 'selected-sources-v1'):
        raise ValueError('unsupported_volume_calculation_guidance')
    if policy.get('maintenance_output_schema') not in (None, 'shared-defs-v1'):
        raise ValueError('unsupported_maintenance_output_schema')
    revision = policy.get("routing_revision", 1)
    if type(revision) is not int or revision not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41):
        raise ValueError("unsupported_routing_revision")
    if policy.get('volume_calculation_guidance') is not None and revision < 41:
        raise ValueError('volume_calculation_guidance_requires41')
    if policy.get('maintenance_output_schema') is not None and revision < 41:
        raise ValueError('maintenance_output_schema_requires41')
    if type(policy.get("luna_news_research_enabled", False)) is not bool:
        raise ValueError("invalid_luna_news_research_policy")
    if type(policy.get("luna_repair_version", 0)) is not int or policy.get("luna_repair_version", 0) not in (0, 1):
        raise ValueError("unsupported_luna_repair_version")
    if policy.get('publication_protocol', 'legacy') not in ('legacy', 'manifest-v1'):
        raise ValueError('unsupported_publication_protocol')
    if type(policy.get('latest_attempt_publication_enabled', False)) is not bool:
        raise ValueError('invalid_latest_attempt_publication_policy')
    if type(policy.get('technical_archive_enabled', False)) is not bool:
        raise ValueError('invalid_technical_archive_policy')
    if policy.get('technical_archive_enabled') is True and revision < 40:
        raise ValueError('technical_archive_requires_new_preparation40')
    from src.local_runner.publication_auth import validate_publication_auth
    validate_publication_auth(policy.get('publication_auth'))
    return policy


def timestamp(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        return None


def require_activation(policy: dict) -> None:
    if policy.get("production_enabled") is not True:
        raise RuntimeError("adaptive_production_not_enabled_validation_pending")


# One calendar for acquisition and ITV; holiday semantics unchanged.
from gcp_functions.support_resistances_raw.market_sessions import (
    _observed, _nth, _easter, market_session,
)


def session_age(start: datetime, end: datetime, extra=()) -> int:
    from zoneinfo import ZoneInfo
    a, b = start.astimezone(ZoneInfo("America/New_York")).date(), end.astimezone(ZoneInfo("America/New_York")).date()
    return sum(market_session(a + timedelta(days=i), extra) for i in range(1, max(0, (b-a).days)+1))


def itv_state(reference: dict, *, owned: bool, priority: bool, now: datetime, policy: dict) -> dict:
    model = str(reference.get("generation_model") or "")
    trusted = ("sol" in model and reference.get("reasoning_effort") == "high"
               and reference.get("analysis_status") == "ok")
    last = timestamp(reference.get("generated_at")) if trusted else None
    limit = policy["priority_itv_sessions" if owned or priority else "watchlist_itv_sessions"]
    age = session_age(last, now, policy.get("extra_market_closures", [])) if last else None
    return {"last_full_report_at": reference.get("generated_at"),
            "last_sol_high_at": last.isoformat() if last else None,
            "age_sessions": age, "limit_sessions": limit,
            "due": last is None or age >= limit,
            "reason": "unverified_reference" if last is None else "age"}


def number(value):
    return float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) else None


def legacy_safeguards(reference: dict, slim: dict) -> list[str]:
    md = str(reference.get("analysis_markdown") or "")
    if reference.get("analysis_status") != "ok" or not md.strip():
        return ["missing_valid_reference"]
    result = []
    if "missing_from_current_slim" in build_level_continuity_precheck(md, slim):
        result.append("prior_support_evidence_missing")
    old_levels = (reference.get("slim_snapshot") or {}).get("levels") or {}
    current_levels = slim.get("levels") or {}
    market_at = timestamp(slim.get("as_of"))
    for label in ("Entrada", "Entrada ambiciosa"):
        zone = extract_range(md, label)
        if zone is None:
            result.append("unparseable_prior_entry")
            continue
        tolerance = max(.01, (zone.lower + zone.upper) / 2 * .005)
        for kind in ("supports", "put_walls_top"):
            for old in old_levels.get(kind) or []:
                price = number(old.get("level")) if isinstance(old, dict) else None
                if price is None or not zone.lower-tolerance <= price <= zone.upper+tolerance:
                    continue
                matches = [new for new in current_levels.get(kind) or []
                           if isinstance(new, dict) and number(new.get("level")) is not None
                           and abs(new["level"]-price) <= tolerance
                           and (kind != "supports" or new.get("type") == old.get("type"))]
                if not matches:
                    result.append(f"prior_{kind}_origin_missing")
                elif kind == "supports" and number(old.get("strength_score")) is not None:
                    strengths = [number(new.get("strength_score")) for new in matches]
                    strengths = [s for s in strengths if s is not None]
                    if not strengths or max(strengths) < old["strength_score"]-15:
                        result.append("support_strength_deteriorated_or_unknown")
                if kind == "put_walls_top" and market_at:
                    expires = timestamp(old.get("expiration"))
                    if expires and expires.date() < market_at.date():
                        result.append("prior_support_option_expired")
    current = number(slim.get("latest_price"))
    plan = reference.get("plan") or parse_report(md, latest_price=current).get("plan", {})
    for key in ("management_stop", "structural_stop"):
        value = plan.get(key)
        if isinstance(value, dict):
            value = value.get("price", value.get("value"))
        stop = number(value)
        if stop is not None and current is not None and current <= stop:
            result.append(f"price_below_{key}")
    old_price = number(reference.get("latest_price"))
    if old_price and current is not None and abs(current/old_price-1) >= .08:
        result.append("price_move_ge_8pct_since_report")
    if not isinstance(slim.get("levels"), dict) or not slim["levels"].get("supports"):
        result.append("missing_current_supports")
    return list(dict.fromkeys(result))


def _live_put_matches(old: dict, levels: dict, market_at: datetime | None) -> list[dict]:
    """Same strike and live option origin, not merely another nearby support."""
    price = number(old.get("level"))
    if price is None or market_at is None:
        return []
    matches = []
    for kind in ("supports", "put_walls_top"):
        for new in levels.get(kind) or []:
            if not isinstance(new, dict) or not str(new.get("type") or "").startswith("put_wall"):
                continue
            level, expires = number(new.get("level")), timestamp(new.get("expiration"))
            if (level is not None and abs(level-price) <= max(.01, price*1e-8)
                    and expires is not None and expires.date() >= market_at.date()
                    and (number(new.get("oi")) or number(new.get("gamma_share_pct"))
                         or number(new.get("gamma_usd_millions")) or 0) > 0):
                matches.append(new)
    return matches


def routing_precheck(reference: dict, slim: dict, *, legacy_price_move_guard: bool = True, revision: int = 17) -> dict:
    """Separate confirmed invalidation from changes Luna must assess.

    Review flags never prove retention: Luna receives complete old/new evidence
    and may escalate on material loss of options, strength, thesis or setup.
    """
    if reference.get("analysis_status") != "ok" or not str(reference.get("analysis_markdown") or "").strip():
        return {"guards": ["missing_valid_reference"], "review_flags": []}
    md = reference["analysis_markdown"]
    typed_plan = None
    if revision >= 22 and reference.get('semantic_report'):
        from src.local_runner.semantic_report import reference_document
        typed_plan = reference_document(reference, verify_projection=True)['plan']
    old_levels = (reference.get("slim_snapshot") or {}).get("levels") or {}
    levels = slim.get("levels") or {}
    market_at = timestamp(slim.get("as_of"))
    guards, flags = [], []
    if "missing_from_current_slim" in build_level_continuity_precheck(md, slim):
        guards.append("prior_support_evidence_missing")
    for label in ("Entrada", "Entrada ambiciosa"):
        key = 'entry' if label == 'Entrada' else 'ambitious_entry'
        if typed_plan is not None:
            from src.common.analysis_validator import PriceRange
            level = typed_plan[key]
            if level['range'] is None and level['strength'] is None:
                flags.append({'code': 'prior_' + key + '_explicitly_absent', 'level_label': label})
                continue
            zone = PriceRange(**level['range']) if level['range'] else None
        else:
            zone = extract_range(md, label)
        if zone is None:
            declared = _normalize_for_match(_extract_line_value(md, label) or "").casefold()
            if label == "Entrada ambiciosa" and declared in {"sin zona verificable", "no aplicable"}:
                flags.append({"code": "prior_ambitious_entry_explicitly_absent", "level_label": label})
            else:
                guards.append("unparseable_prior_entry")
            continue
        tolerance = max(.01, (zone.lower+zone.upper)/2*.005)
        for kind in ("supports", "put_walls_top"):
            for old in old_levels.get(kind) or []:
                price = number(old.get("level")) if isinstance(old, dict) else None
                if price is None or not zone.lower-tolerance <= price <= zone.upper+tolerance:
                    continue
                matches = [new for new in levels.get(kind) or []
                           if isinstance(new, dict) and number(new.get("level")) is not None
                           and abs(new["level"]-price) <= tolerance
                           and (kind != "supports" or new.get("type") == old.get("type"))]
                option_origin = kind == "put_walls_top" or str(old.get("type") or "").startswith("put_wall")
                live = _live_put_matches(old, levels, market_at) if option_origin else []
                expires = timestamp(old.get("expiration")) if option_origin else None
                expired = bool(expires and market_at and expires.date() < market_at.date())
                if expired:
                    if live:
                        flags.append({"code": "option_origin_renewed_requires_review", "level_label": label,
                                      "level": price, "previous_expiration": old.get("expiration"),
                                      "current_expirations": sorted({m["expiration"] for m in live})})
                    else:
                        guards.append("prior_support_option_expired")
                if not matches:
                    if live:
                        flags.append({"code": "put_origin_moved_between_source_lists", "level_label": label,
                                      "level": price})
                    else:
                        guards.append(f"prior_{kind}_origin_missing")
                elif kind == "supports" and number(old.get("strength_score")) is not None:
                    strengths = [number(new.get("strength_score")) for new in matches]
                    strengths = [s for s in strengths if s is not None]
                    if not strengths or max(strengths) < old["strength_score"]-15:
                        guards.append("support_strength_deteriorated_or_unknown")
    current, previous_price = number(slim.get("latest_price")), number(reference.get("latest_price"))
    plan = reference.get("plan") or parse_report(md, latest_price=current).get("plan", {})
    for key in (() if revision >= 29 else ("management_stop", "structural_stop")):
        value = plan.get(key)
        if isinstance(value, dict):
            value = value.get("price", value.get("value"))
        stop = number(value)
        if stop is not None and current is not None and current <= stop:
            if previous_price is not None and previous_price <= stop:
                flags.append({"code": "price_already_below_stop_in_reference", "stop_kind": key,
                              "stop": stop, "previous_price": previous_price, "current_price": current})
            else:
                guards.append(f"price_below_{key}")
    if legacy_price_move_guard and previous_price and current is not None and abs(current/previous_price-1) >= .08:
        guards.append("price_move_ge_8pct_since_report")
    if not isinstance(slim.get("levels"), dict) or not slim["levels"].get("supports"):
        guards.append("missing_current_supports")
    # Same option can occur in both arrays. Preserve facts without duplicate flags.
    flags = list({json.dumps(flag, sort_keys=True): flag for flag in flags}.values())
    return {"guards": list(dict.fromkeys(guards)), "review_flags": flags}


def safeguards(reference: dict, slim: dict) -> list[str]:
    return routing_precheck(reference, slim)["guards"]


def maintenance_precheck(reference: dict, slim: dict, sol_reference: dict, *, owned: bool, revision: int = 17) -> dict:
    """Routine technical losses need judgment/maintenance, not automatic Sol.

    Only confirmed invalidation/invalid contracts bypass Luna. Missing sources
    are rejected by data_ready before either model; a small list is not proof
    that the whole defining support disappeared. Luna must justify an update,
    never retain an orphan or reconstruct a critical plan itself.
    """
    result = routing_precheck(reference, slim, legacy_price_move_guard=revision < 18, revision=revision)
    hard = {"missing_valid_reference", "unparseable_prior_entry",
            "price_below_structural_stop", "price_move_ge_8pct_since_report",
            "missing_current_supports"}
    if owned:
        hard.add("price_below_management_stop")
    guards = [g for g in result["guards"] if g in hard]
    flags = result["review_flags"] + [{"code": g, "requires_current_evidence": True}
        for g in result["guards"] if g not in hard]
    # Changes cannot be hidden by several apparently small Luna updates.
    # Frozen legacy receipts keep their exact routing contract. New work does
    # not evaluate a price-move cutoff against either report; risk guards remain.
    anchor = routing_precheck(sol_reference, slim, legacy_price_move_guard=revision < 18, revision=revision)
    for guard in anchor["guards"]:
        if guard in {"price_below_structural_stop", "price_move_ge_8pct_since_report"}:
            guards.append(guard)
        elif owned and guard == "price_below_management_stop":
            guards.append(guard)
    if revision >= 26 and owned is False:
        from src.local_runner.semantic_report import reference_document
        # Applicability comes from authenticated CURRENT typed authority, not
        # prose, list absence or the older full anchor's superseded entries.
        plan = (reference_document(reference, verify_projection=True)['plan']
                if reference.get('semantic_report') else None)
        suspended = plan is not None and all(
            plan.get(key, {}).get('range', 'unknown') is None and
            plan.get(key, {}).get('strength', 'unknown') is None
            for key in ('entry', 'ambitious_entry'))
        if suspended and 'price_below_structural_stop' in guards:
            guards = [g for g in guards if g != 'price_below_structural_stop']
            flags.append({'code': 'historical_structural_stop_on_suspended_plan',
                          'requires_current_evidence': True,
                          'meaning': 'No recorded position or active purchase. Assess new risk; '
                                     'not automatic retention, reactivation or permission to edit protected stops.'})
    return {"guards": list(dict.fromkeys(guards)), "review_flags": flags}


def daily_decision(payload: dict, guards: list[str], context: dict) -> str:
    if context.get("routing_revision", 1) >= 3:
        from src.local_runner.adaptive_maintenance import maintenance_decision
        return maintenance_decision(payload, guards, context)
    return triage_decision(payload, guards, context)


SECTIONS = ("thesis", "setup", "levels", "news", "analysts", "events")
TRIAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["retain", "escalate", "blocked"]},
        "uncertainty": {"type": "boolean"}, "reason": {"type": "string"},
        **{key: {"type": "object", "additionalProperties": False,
                 "properties": {"assessment": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}}},
                 "required": ["assessment", "evidence"]} for key in SECTIONS},
    },
    "required": ["decision", "uncertainty", "reason", *SECTIONS],
}


def triage_schema(context: dict) -> dict:
    """Constrain citations to real, bounded source sections, not invented paths.

    Full prose/arrays remain available; quote item IDs/facts in assessment.
    A shared definition avoids repeating a large enum in every section.
    """
    from copy import deepcopy
    schema = deepcopy(TRIAGE_SCHEMA)
    # These five source roots are always present in a production triage.
    # Do not bake ticker-dependent optional fields into the cached prefix.
    # Exact facts, item IDs and comparisons still belong in the assessment;
    # every citation is resolved locally against the complete logical context.
    pointers = ["/reference", "/slim", "/news", "/analyst_actions", "/guards"]
    schema["$defs"] = {"evidence_pointer": {"type": "string", "enum": pointers}}
    for key in SECTIONS:
        schema["properties"][key]["properties"]["evidence"]["items"] = {"$ref": "#/$defs/evidence_pointer"}
    return schema


def triage_decision(payload: dict, guards: list[str], evidence_context: dict | None = None) -> str:
    from src.local_runner.adaptive_context import resolve_evidence
    if (set(payload) != set(TRIAGE_SCHEMA["required"])
            or payload.get("decision") not in {"retain", "escalate", "blocked"}
            or type(payload.get("uncertainty")) is not bool
            or not isinstance(payload.get("reason"), str) or not payload["reason"].strip()):
        raise ValueError("invalid_triage_contract")
    for key in SECTIONS:
        item = payload[key]
        if (not isinstance(item, dict) or set(item) != {"assessment", "evidence"}
                or not isinstance(item["assessment"], str) or not item["assessment"].strip()
                or not isinstance(item["evidence"], list) or not item["evidence"]
                or not all(isinstance(x, str) and x.strip() for x in item["evidence"])):
            raise ValueError(f"triage_evidence_missing: {key}")
        if evidence_context is not None:
            for pointer in item["evidence"]:
                resolve_evidence(evidence_context, pointer)
    if payload["decision"] == "blocked":
        return "blocked"
    return "escalate" if guards or payload["uncertainty"] else payload["decision"]


def routes_for(records, root: Path, force_full: bool = False, *, resume_dir: Path | None = None):
    from src.local_runner.analysis_policy import RouteDecision, parse_reference_summary, resolve_tier
    from src.local_runner.analysis_state import load_reference_payload
    policy = load_policy(root)
    ranked = []
    for record in records:
        frozen = resume_dir / "adaptive" / record.ticker / "input.json" if resume_dir else None
        if frozen and frozen.exists():
            context = json.loads(frozen.read_text(encoding="utf-8"))
            ref = context.get("reference") or {}
        else:
            ref = load_reference_payload(record.ticker) or {}
        summary = parse_reference_summary(ref)
        tier = resolve_tier(owned=record.owned, reference_score=summary.score, previous_tier=summary.tier)
        route = RouteDecision(record.ticker, "run", "reference" if force_full else "adaptive",
                              tier, policy["triage_model"], policy["triage_effort"],
                              policy["report_model"], "adaptive_luna_sol_itv", record.owned)
        # Oldest first within priority tier. After successful ITV the ticker moves
        # to the back, spreading expensive reviews instead of a weekly stampede.
        ranked.append(((not record.owned, tier != "priority", str(ref.get("generated_at") or ""), record.ticker), route))
    return tuple(route for _, route in sorted(ranked, key=lambda pair: pair[0]))
