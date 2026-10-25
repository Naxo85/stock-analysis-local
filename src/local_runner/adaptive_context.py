"""Versioned model view; frozen source/publication payloads remain untouched."""
from __future__ import annotations

import re
import json
import hashlib
from copy import deepcopy


REFERENCE_FIELDS = (
    "symbol", "analysis_status", "generated_at", "generation_model",
    "reasoning_effort", "analysis_markdown", "slim_snapshot", "latest_price",
    "decision", "plan", "catalysts", "next_event",
)

MAINTENANCE_OVERRIDE = (
    "\n\nLUNA OVERRIDE: Technical input stays frozen. No tools except public-news web access when an explicit "
    "LUNA NEWS RESEARCH ENABLED footer authorizes it. Escalate when essential research remains unresolved. "
    "Return maintenance JSON, never a full report. On update, level continuity is relative to CURRENT reference, "
    "not historical comparisons already in its text. Rebase inherited Se reprioriza/Se corrige for unchanged "
    "technical levels to Se conserva with the exact CURRENT prior numbers, or leave an EXACT inherited motive "
    "for the runner to rebase. Structural-stop reason is EXEMPT: keep it EXACTLY unchanged. Narrativa actual "
    "is also EXACTLY protected, including embedded technical comparisons: put dated corrections in routine_note. "
    "Update affected technical facts including neighboring option shares. The runner calculates level percentages "
    "without changing numeric levels. Proximity alone to a known future event is not new event results. "
    "Missing headline detail alone is not essential uncertainty: identify the source-backed causal impact on an "
    "actual conclusion and why routine maintenance cannot address it. Do not invent competitor-to-ticker links. "
    "Inspect current versus historical origins before concluding support loss; duplicate walls are not independent. "
    "Critical evidence, lost defining support, hard guards and essential uncertainty still require Sol."
)

TRANSPORT_INSTRUCTIONS = """
Input transport is lossless: _context_aliases maps logical JSON Pointers to
identical values already present elsewhere in the input. A mapped value's
{"$same_as": "/path"} marker means read the COMPLETE referenced value, not
missing evidence. Resolve aliases before comparing or citing logical paths.
Only entries in _context_aliases are aliases; similar source text is literal.
All dates, news, actions and non-identical snapshots remain available.
"""


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def pack_model_context(context: dict) -> dict:
    """Share only byte-identical JSON objects/arrays when that saves space.

    No semantic summarization, removed fields, rounded numbers or list caps.
    Alias locations are explicit, so literal markers in evidence are safe.
    """
    if "_context_aliases" in context:
        raise ValueError("reserved_context_transport_field")
    aliases, seen = {}, {}
    def visit(value, pointer):
        if isinstance(value, (dict, list)):
            signature = compact_json(value)
            target = seen.get(signature)
            if target is not None:
                marker = {"$same_as": target}
                # Include alias-map overhead: never expand a small duplicate.
                overhead = len(compact_json({pointer: target})) + len(compact_json(marker))
                if overhead < len(signature):
                    aliases[pointer] = target
                    return marker
            else:
                seen[signature] = pointer
            if isinstance(value, dict):
                return {key: visit(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                        for key, child in value.items()}
            return [visit(child, pointer + "/" + str(i)) for i, child in enumerate(value)]
        return deepcopy(value)
    # Prefer current authoritative sources over baseline copies as targets.
    keys = sorted(context, key=lambda key: (key != "slim", key != "reference", key))
    result = {key: visit(context[key], "/" + key.replace("~", "~0").replace("/", "~1")) for key in keys}
    if aliases:
        result["_context_aliases"] = aliases
    return result


def unpack_model_context(packed: dict) -> dict:
    aliases = packed.get("_context_aliases", {})
    def expand(value, pointer, active):
        if pointer in aliases:
            if pointer in active:
                raise ValueError("cyclic_context_alias")
            target = aliases[pointer]
            return expand(resolve_evidence(packed, target), target, active | {pointer})
        if isinstance(value, dict):
            return {key: expand(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"), active)
                    for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child, pointer + "/" + str(i), active) for i, child in enumerate(value)]
        return deepcopy(value)
    result = {key: expand(value, "/" + key.replace("~", "~0").replace("/", "~1"), set())
              for key, value in packed.items() if key != "_context_aliases"}
    if '_context_transport' in result:
        from src.local_runner.diff_transport import VERSION, restore_diffs
        if result['_context_transport'] != VERSION:
            raise ValueError('unsupported_context_transport')
        result = restore_diffs(result)
    return result


def serialize_model_input(context: dict) -> str:
    from src.local_runner.financial_projection import model_input_view
    context = model_input_view(context)
    transport_context = context
    if '_context_transport' in context:
        from src.local_runner.diff_transport import VERSION, compact_diffs
        if context['_context_transport'] != VERSION:
            raise ValueError('unsupported_context_transport')
        transport_context = compact_diffs(context)
    packed = pack_model_context(transport_context)
    if unpack_model_context(packed) != context:
        raise ValueError("context_transport_roundtrip_failed")
    return compact_json(packed)


def validation_context(context: dict) -> str:
    """Adapt frozen JSON to the existing validator's previous-level/slim contract."""
    from src.local_runner.previous_analysis import _build_previous_prompt_markdown
    reference = context.get("reference") or {}
    if context.get('routing_revision', 1) >= 8:
        reference, _ = _project_reference_numbers(reference)
    previous = _build_previous_prompt_markdown(
        symbol=context.get("symbol", ""), source_uri="frozen_adaptive_reference",
        generated_at=reference.get("generated_at"), payload=reference,
        analysis_markdown=reference.get("analysis_markdown", ""))
    return previous + "\n\n## JSON Técnico Slim\n```json\n" + json.dumps(context.get("slim", {}), ensure_ascii=False) + "\n```\n"


def _project_reference_numbers(reference: dict) -> tuple[dict, list]:
    '''Reparse derived mirrors from unchanged authoritative Markdown in a COPY.

    Fixes legacy numeric-token decoding without rewriting the report, dates,
    snapshot, hashes, full Sol anchor or stored historical JSON.
    '''
    from src.local_runner.report_schema import parse_report
    from src.common.analysis_validator import extract_range
    result, corrections = deepcopy(reference), []
    if reference.get('semantic_report') is not None:
        # Typed published data is authoritative. Do not decode prose back into it.
        from src.local_runner.semantic_report import reference_document
        reference_document(reference)  # Check immutable data/Markdown binding.
        return result, corrections
    markdown = reference.get('analysis_markdown') or ''
    if reference.get('analysis_status') != 'ok' or not markdown:
        return result, corrections
    plan = parse_report(markdown, latest_price=None)['plan']
    for key in ('entry', 'ambitious_entry', 'management_stop', 'structural_stop', 'resistance', 'target'):
        old_plan = result.get('plan')
        if isinstance(old_plan, dict) and key in old_plan and old_plan[key] != plan.get(key):
            corrections.append({'field':'plan/'+key,'before':deepcopy(old_plan[key]),'after':deepcopy(plan.get(key)),
                                'source':'analysis_markdown'})
            old_plan[key] = deepcopy(plan.get(key))
    validation = result.get('validation')
    if isinstance(validation, dict):
        for key,label in (('entry_range','Entrada'),('ambitious_entry_range','Entrada ambiciosa'),
                          ('resistance_range','Resistencia estructural')):
            zone = extract_range(markdown,label)
            current = zone.to_dict() if zone else None
            if key in validation and validation[key] != current:
                corrections.append({'field':'validation/'+key,'before':deepcopy(validation[key]),
                                    'after':current,'source':'analysis_markdown'})
                validation[key] = current
    return result, corrections


def model_context(context: dict) -> dict:
    """Keep full report/snapshots/current sources, not historical change receipts.

    `changes` describes the transition INTO the baseline report, not changes
    after that report. Never truncate current headlines/actions.
    """
    result = deepcopy(context)
    reference = context.get("reference") or {}
    result["reference"] = {key: deepcopy(reference[key]) for key in REFERENCE_FIELDS if key in reference}
    if "sol_reference" in context:
        anchor = context["sol_reference"]
        result["sol_reference"] = {key: deepcopy(anchor[key]) for key in REFERENCE_FIELDS if key in anchor}
    result["comparison"] = {
        "contract": "adaptive-context-v2",
        "baseline_report_at": reference.get("generated_at"),
        "baseline_market_at": (reference.get("slim_snapshot") or {}).get("as_of"),
        "current_market_at": (context.get("slim") or {}).get("as_of"),
        "same_market_snapshot": bool(reference.get("slim_snapshot"))
        and reference["slim_snapshot"] == context.get("slim"),
    }
    if context.get("routing_revision", 1) >= 3:
        result["comparison"].update(contract="adaptive-maintenance-context-v3",
            current_markdown_sha256=hashlib.sha256(str(reference.get("analysis_markdown") or "").encode("utf-8")).hexdigest(),
            last_full_sol_report_at=(context.get("sol_reference") or {}).get("generated_at"),
            compare_cumulative_changes_against_sol=True)
    if context.get("routing_revision", 1) >= 4:
        from src.local_runner.adaptive_delta import deterministic_comparison
        result["comparison"].update(contract="adaptive-maintenance-context-v4",
            deterministic=deterministic_comparison(context))
        # Compared before projection: full baseline sources remain in frozen
        # input; the model gets exact presence/chronology, not duplicate feeds.
    if context.get("routing_revision", 1) >= 6:
        from src.local_runner.adaptive_delta import plan_source_inventory
        result["comparison"].update(contract="adaptive-maintenance-context-v6",
            plan_source_inventory=plan_source_inventory(context))
    if context.get('routing_revision', 1) >= 8:
        projections = {}
        for key in ('reference','sol_reference'):
            if key in result:
                result[key], changes = _project_reference_numbers(result[key])
                if changes:
                    projections[key] = changes
        result['comparison'].update(contract='adaptive-maintenance-context-v8',
                                    reference_numeric_projection=projections)
    if context.get('routing_revision', 1) >= 9:
        from src.local_runner.semantic_report import reference_document
        for key in ('reference', 'sol_reference'):
            if result.get(key, {}).get('analysis_markdown'):
                # The typed authority is projected from the FULL frozen input,
                # not from an incomplete mirror or the current model's response.
                result[key]['semantic_data'] = reference_document(context[key], verify_projection=context.get('routing_revision', 1) >= 11)
        result['comparison']['contract'] = 'adaptive-semantic-context-v9'
    if context.get('routing_revision', 1) >= 11:
        for key in ('reference', 'sol_reference'):
            if (context.get(key) or {}).get('semantic_report') is not None:
                # Repeated projections retain authenticated typed authority;
                # never reparse escaped Markdown as a different source.
                result[key]['semantic_report'] = deepcopy(context[key]['semantic_report'])
    if context.get('routing_revision', 1) >= 10:
        from src.local_runner.semantic_sources import source_catalog
        result['source_catalog'] = source_catalog(result)
        result['comparison']['contract'] = ('adaptive-semantic-context-v11' if context.get('routing_revision', 1) >= 11
                                            else 'adaptive-semantic-context-v10')
    if context.get('routing_revision', 1) >= 12:
        result['comparison']['contract'] = 'adaptive-semantic-context-v12'
    if context.get('routing_revision', 1) >= 13:
        from src.local_runner.adaptive_delta import plan_quote_observations
        result['comparison']['contract'] = 'adaptive-semantic-context-v13'
        result['comparison']['plan_quote_observations'] = plan_quote_observations(result)
    if context.get('routing_revision', 1) >= 14:
        from src.local_runner.maintenance_change import origin_observations
        result['comparison']['contract'] = 'adaptive-semantic-context-v14'
        result['comparison']['plan_origin_observations'] = origin_observations(result)
    if context.get('routing_revision', 1) >= 15:
        result['comparison']['contract'] = 'adaptive-semantic-context-v15'
    if context.get('routing_revision', 1) >= 16:
        from src.local_runner.review_memory import memory_view
        from src.local_runner.evidence_semantics import technical_observations
        if 'review_memory' in reference:
            # Keep original integrity envelope for repeated projections/binding.
            # serialize_model_input removes it after exposing the financial view.
            result['reference']['review_memory'] = deepcopy(reference['review_memory'])
        result['comparison']['contract'] = 'adaptive-semantic-context-v16'
        result['comparison']['technical_evidence_semantics'] = technical_observations(context)
        result.setdefault('news', {})['prior_reviews'] = memory_view(context)
    if context.get('routing_revision', 1) >= 18:
        from src.local_runner.review_contract import review_agenda, latest_review_view
        result['comparison']['contract'] = 'adaptive-semantic-context-v18'
        result['comparison']['latest_published_review'] = latest_review_view(context)
        # Exact content hashes are runner-owned; the model only selects the
        # supplied short IDs. Do not spend context on internal ledger keys.
        result.setdefault('news', {})['review_agenda'] = [
            {key: value for key, value in row.items() if key != 'key'}
            for row in review_agenda(context)]
    if context.get('routing_revision', 1) >= 19:
        result['comparison']['contract'] = 'adaptive-semantic-context-v19'
    if context.get('routing_revision', 1) >= 20:
        result['comparison']['contract'] = 'adaptive-semantic-context-v20'
    if context.get('routing_revision', 1) >= 21:
        from src.local_runner.text_provenance import origins
        result['comparison']['contract'] = 'adaptive-semantic-context-v21'
        result['comparison']['text_origins'] = origins(context)
    if context.get('routing_revision', 1) >= 23:
        from src.local_runner.volume_rubric import observations
        result['comparison']['contract'] = 'adaptive-semantic-context-v23'
        result['comparison']['volume_rubric'] = observations(result)
    if context.get('routing_revision', 1) >= 25:
        result['comparison']['contract'] = 'adaptive-semantic-context-v25'
    if context.get('routing_revision', 1) >= 26:
        from src.local_runner.reaction_comparison import observations
        result['comparison']['contract'] = 'adaptive-semantic-context-v26'
        result['comparison']['historical_measurements'] = observations(result)
    if context.get('routing_revision', 1) >= 27:
        result['comparison']['contract'] = 'adaptive-semantic-context-v27'
    if context.get('routing_revision', 1) >= 28:
        result['comparison']['contract'] = 'adaptive-semantic-context-v28'
    if context.get('routing_revision', 1) >= 29:
        result['comparison']['contract'] = 'adaptive-semantic-context-v29'
        result['comparison']['deterministic'].pop('current_plan_geometry', None)
        from src.local_runner.plan_scope import plan_keys
        BUY_PLAN_KEYS = plan_keys(context['routing_revision'])
        quote = result['comparison'].get('plan_quote_observations') or {}
        quote['levels'] = {k: v for k, v in quote.get('levels', {}).items() if k in BUY_PLAN_KEYS}
        quote.pop('target_above_entries', None)
        quote['meaning'] = ('Endpoint locations are not confirmed breaks, defenses or executions. '
                            'Assess buying supports and one operational resistance; no numeric stops or exit target.')
        if context['routing_revision'] >= 35:
            quote['meaning'] = ('Endpoint locations are not confirmed breaks or defenses. '
                                'Assess only buying supports; no resistance, stop or target calculation.')
        origins = result['comparison'].get('text_origins') or {}
        result['comparison']['text_origins'] = {k: v for k, v in origins.items()
                                               if k in (*BUY_PLAN_KEYS, 'setup_reason', 'conclusion')}
    if context.get('routing_revision', 1) >= 32:
        from src.local_runner.reader_report import catalog
        result['reader_catalog'] = catalog(context.get('reference') or {})
    return result


def resolve_evidence(context: dict, pointer: str):
    """Resolve a non-root RFC 6901 pointer, rejecting invented paths/indices."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("triage_evidence_requires_json_pointer")
    value = context
    for encoded in pointer[1:].split("/"):
        if re.search(r"~(?![01])", encoded):
            raise ValueError("triage_evidence_invalid_escape")
        key = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(value):
            value = value[int(key)]
        else:
            raise ValueError(f"triage_evidence_path_missing: {pointer}")
    return value
