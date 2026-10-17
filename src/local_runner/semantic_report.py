"""Versioned financial data contract; Markdown is output, never model authority.

Revision 9 uses this for BOTH Luna updates and full Sol reports. Legacy inputs
keep their old receipt/schema; importing a published legacy report is a one-way
bridge, not a new requirement on the model's prose. This verifies typed financial
claims and source presence, not the semantic truth of arbitrary commentary.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import html
import json
import math
import re

from src.common.analysis_validator import (
    PriceRange, SupportStrength, ValidationResult, _strength_breakdown_qualifies,
    extract_range, extract_support_strength, format_exact_price, support_strength_category,
)
from src.local_runner.adaptive_context import resolve_evidence
from src.local_runner.source_urls import cited_urls
from src.local_runner.report_schema import (
    parse_report, compare_reports, build_analysis_alerts, score_category,
    _annotate_event_proximity,
)

MAXIMA = {'estructura': 25, 'volumen': 20, 'opciones': 25, 'confluencia': 15, 'durabilidad': 15}
LABELS = {'entry': 'Entrada', 'ambitious_entry': 'Entrada ambiciosa',
          'management_stop': 'Stop de gestión', 'structural_stop': 'Stop estructural',
          'resistance': 'Resistencia estructural', 'target': 'Salida / objetivo principal'}
EDITABLE = ('entry', 'ambitious_entry', 'resistance', 'target')
TRANSITIONS = ('keep', 'correct', 'reprioritize', 'remove', 'new')


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def level_schema(revision=9):
    schema = obj({'range': nullable(obj({'lower': {'type': 'number', 'exclusiveMinimum': 0},
                                       'upper': {'type': 'number', 'exclusiveMinimum': 0}})),
                'transition': {'type': 'string', 'enum': list(TRANSITIONS)},
                'reason': {'type': 'string'},
                'strength': nullable(obj({'components': obj({key: {'type': 'integer', 'minimum': 0, 'maximum': cap}
                                                             for key, cap in MAXIMA.items()}),
                                         'factors': {'type': 'string'}})),
                'evidence': {'type': 'array', 'items': {'type': 'string'}},
                # Source facts are pointers, NOT duplicated strike/OI/date strings.
                'facts': {'type': 'array', 'items': {'type': 'string'}}})
    if revision >= 10:
        del schema['properties']['transition']
        schema['required'].remove('transition')
    if revision >= 12:
        for field in ('evidence', 'facts'):
            schema['properties'][field]['items'] = {'type': 'string', 'pattern': r'^s[1-9][0-9]*$'}
    if revision >= 25:
        schema['properties']['volume_calculation'] = nullable(obj({
            'profile_source': {'type': 'string', 'pattern': r'^s[1-9][0-9]*$'},
            'reaction_source': {'type': 'string', 'pattern': r'^s[1-9][0-9]*$'}}))
        schema['required'].append('volume_calculation')
    return schema


def update_schema(revision=9):
    from src.local_runner.plan_scope import editable_keys
    if revision >= 12:
        # Null means inherit the authenticated block, not delete its zone or
        # ask the model to regenerate unchanged financial judgments.
        level = level_schema(revision)
        if revision >= 14:
            from src.local_runner.maintenance_change import review_schema
            level['properties']['change_review'] = review_schema(revision)
            level['required'].append('change_review')
        schema = obj({'setup_score': nullable({'type': 'number', 'minimum': 0, 'maximum': 10}),
                    'setup_reason': nullable({'type': 'string'}),
                    'plan': obj({key: nullable(deepcopy(level)) for key in editable_keys(revision)}),
                    'conclusion': nullable({'type': 'string'})})
        if revision >= 15:
            from src.local_runner.maintenance_change import commentary_review_schema
            schema['properties']['change_review'] = obj({key: nullable(commentary_review_schema())
                for key in ('setup', 'conclusion', 'routine_note')})
            schema['required'].append('change_review')
            if revision >= 19:
                reviews = schema['properties']['change_review']
                reviews['properties']['plan_explanation'] = nullable(commentary_review_schema())
                reviews['required'].append('plan_explanation')
        if revision >= 18:
            from src.local_runner.review_contract import plan_explanation_schema
            schema['properties']['plan_explanation'] = nullable(plan_explanation_schema(revision))
            schema['required'].append('plan_explanation')
        if revision >= 20:
            reviews = schema['properties']['change_review']
            del reviews['properties']['routine_note']
            reviews['required'].remove('routine_note')
            schema['properties']['public_note'] = nullable(obj({
                'text': {'type': 'string'}, 'review': commentary_review_schema()}))
            schema['required'].append('public_note')
        if revision >= 21:
            # No shared permission to overwrite unrelated paragraphs.
            reviews['properties']['plan_explanation'] = {'type': 'null'}
        return schema
    return obj({'setup_score': {'type': 'number', 'minimum': 0, 'maximum': 10},
                'setup_reason': {'type': 'string'},
                'plan': obj({key: level_schema(revision) for key in EDITABLE}),
                'conclusion': {'type': 'string'}})


def report_schema(revision=9):
    from src.local_runner.plan_scope import plan_labels
    schema = obj({'summary': obj({'thesis_score': {'type': 'number', 'minimum': 0, 'maximum': 10},
                               'thesis_reason': {'type': 'string'},
                               'setup_score': {'type': 'number', 'minimum': 0, 'maximum': 10},
                               'setup_reason': {'type': 'string'}, 'narrative': {'type': 'string'}}),
                'catalysts': {'type': 'array', 'items': obj({'date': nullable({'type': 'string'}),
                                'title': {'type': 'string'}, 'impact': {'type': 'integer', 'enum': [-10, -9, -8, -7, -6, -5, 5, 6, 7, 8, 9, 10]},
                                'description': {'type': 'string'}})},
                'next_event': nullable(obj({'date': nullable({'type': 'string'}), 'title': {'type': 'string'},
                                           'description': {'type': 'string'}})),
                'plan': obj({key: level_schema(revision) for key in plan_labels(revision)}), 'conclusion': {'type': 'string'}})
    if revision >= 32:
        for event in (schema['properties']['catalysts']['items'],
                      schema['properties']['next_event']['anyOf'][0]):
            event['properties']['show_in_report'] = {'type': 'boolean'}
            event['required'].append('show_in_report')
    if revision >= 33:
        from src.local_runner.catalyst_editorial import assessment_schema
        event = schema['properties']['catalysts']['items']
        del event['properties']['show_in_report']
        event['required'].remove('show_in_report')
        event['properties']['reader_assessment'] = assessment_schema()
        event['required'].append('reader_assessment')
    if revision >= 36:
        from src.local_runner.support_validity import review_schema
        schema['properties']['support_validity_review'] = review_schema()
        schema['required'].append('support_validity_review')
    return schema


def check_schema(value, schema, *, root=None, path=''):
    """Small strict checker for the exact JSON-schema subset we emit to Codex.

    No extra runtime dependency. Tests cover refs, unions, types, bounds and
    extra/missing keys; booleans and nonfinite floats never count as numbers.
    """
    root = root or schema
    if '$ref' in schema:
        target = root
        for part in schema['$ref'][2:].split('/'):
            target = target[part]
        return check_schema(value, target, root=root, path=path)
    if 'anyOf' in schema:
        for choice in schema['anyOf']:
            try:
                check_schema(value, choice, root=root, path=path)
                return
            except ValueError:
                pass
        raise ValueError(f'update_not_allowed_typed_data: {path}: invalid union value')
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'boolean': type(value) is bool, 'null': value is None,
             'number': type(value) in (int, float) and math.isfinite(value),
             'integer': type(value) is int}.get(kind, True)
    if not valid or ('enum' in schema and value not in schema['enum']):
        raise ValueError(f'update_not_allowed_typed_data: {path}: expected {kind}')
    if kind in ('number', 'integer'):
        if (('minimum' in schema and value < schema['minimum'])
                or ('maximum' in schema and value > schema['maximum'])
                or ('exclusiveMinimum' in schema and value <= schema['exclusiveMinimum'])):
            raise ValueError(f'update_not_allowed_typed_data: {path}: out of range')
    if kind == 'object':
        props = schema.get('properties', {})
        if any(key not in value for key in schema.get('required', [])) or (
                schema.get('additionalProperties') is False and not set(value) <= set(props)):
            raise ValueError(f'update_not_allowed_typed_data: {path}: missing or unknown data field')
        for key, child in value.items():
            if key in props:
                check_schema(child, props[key], root=root, path=path + '/' + key)
    if kind == 'array':
        for index, child in enumerate(value):
            check_schema(child, schema['items'], root=root, path=path + '/' + str(index))
    if kind == 'string' and 'pattern' in schema and not re.search(schema['pattern'], value):
        raise ValueError(f'update_not_allowed_typed_data: {path}: invalid source pointer')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('update_not_allowed_missing_reason: ' + field)


def _utc(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError) as exc:
        raise ValueError('update_not_allowed_missing_snapshot_time') from exc


def _metadata(context):
    price = (context.get('slim') or {}).get('latest_price')
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        raise ValueError('update_not_allowed_current_price_unavailable')
    return {'symbol': context['symbol'], 'analysis_date': _utc(context['prepared_at']).date().isoformat(),
            'reference_price': price, 'snapshot_at': _utc(context['slim']['as_of']).isoformat(),
            'quote': deepcopy(context['slim'].get('market_state') or {})}


def reference_document(reference, *, verify_projection=False):
    """Use persisted typed authority; only old published Markdown needs importing."""
    if verify_projection:
        reference = deepcopy(reference)
        reference.pop('semantic_data', None)  # A projected cache cannot authenticate itself.
    if 'semantic_data' in reference:
        # Created by model_context after validating the persisted binding.
        return deepcopy(reference['semantic_data'])
    stored = reference.get('semantic_report')
    if stored is not None:
        if (not isinstance(stored, dict) or stored.get('version') != 1 or not isinstance(stored.get('data'), dict)
                or stored.get('data_sha256') != digest(stored.get('data'))
                or stored.get('markdown_sha256') != hashlib.sha256(reference.get('analysis_markdown', '').encode()).hexdigest()):
            raise ValueError('invalid_update_semantic_base_integrity')
        return deepcopy(stored['data'])
    md = reference.get('analysis_markdown') or ''
    parsed = parse_report(md, latest_price=reference.get('latest_price'))
    # Import section boundaries ONCE. Not used on fresh model commentary.
    from src.local_runner.adaptive_maintenance import _layout
    layout = _layout(md)
    sections = layout['sections']
    fundamental = md[sections[1][1]:sections[3][1]]
    conclusion = md[sections[4][2]:layout['note_start']].strip()
    plan = {}
    for key, label in LABELS.items():
        zone = extract_range(md, label)
        strength_label = 'Resistencia' if key == 'resistance' else label
        strength = extract_support_strength(md, strength_label) if key in ('entry', 'ambitious_entry', 'resistance') else None
        plan[key] = {'range': zone.to_dict() if zone else None, 'transition': 'keep',
                     'reason': parsed['plan'].get(key + '_reason') or '',
                     'strength': {'components': strength.breakdown, 'factors': strength.factors}
                                 if strength and strength.applicable else None,
                     'evidence': [], 'facts': [], 'resolved_facts': [], 'continuity': None}
    decision = parsed['decision']
    return {'summary': {key: decision.get(key) for key in
                        ('thesis_score', 'thesis_reason', 'setup_score', 'setup_reason', 'narrative')},
            'plan': plan, 'fundamental_markdown': fundamental,
            'catalysts': deepcopy(parsed['catalysts']), 'next_event': deepcopy(parsed['next_event']),
            'conclusion': conclusion, 'routine_note': '', 'metadata': {}}


def _live_levels(context, kind):
    slim = context.get('slim') or {}
    market_day = _utc(slim['as_of']).date()
    for row in (slim.get('levels') or {}).get(kind) or []:
        if not isinstance(row, dict) or row.get('active') is False:
            continue
        if kind == 'observed_origins' and row.get('status') != 'available':
            continue
        if kind == 'option_origins':
            if context.get('routing_revision', 1) < 39 or row.get('status') != 'available':
                continue
            detail = row.get('option_details') or {}
            if detail.get('option_type') != 'put':
                continue
            def positive_current(observation):
                try:
                    expiry = date.fromisoformat(observation.get('expiration', ''))
                except (TypeError, ValueError):
                    return False
                return expiry >= market_day and observation.get('status') == 'observed' and any(
                    type(observation.get(k)) in (int, float) and math.isfinite(observation[k])
                    and observation[k] > 0 for k in ('aggregate_oi', 'gamma_usd_millions'))
            if not any(positive_current(r) for r in detail.get('by_expiration') or []):
                continue
        if kind.endswith('walls_top') or 'wall' in str(row.get('type', '')):
            try:
                expiry = date.fromisoformat(str(row.get('expiration', ''))[:10])
            except ValueError:
                continue
            if expiry < market_day or not any(type(row.get(key)) in (int, float)
                    and math.isfinite(row[key]) and row[key] > 0
                    for key in ('oi', 'gamma_share_pct', 'gamma_usd_millions')):
                continue
        yield row


def _origin_present(zone, context, key):
    slim = context['slim']
    tech = slim.get('technicals') or {}
    support = key in ('entry', 'ambitious_entry')
    kinds = ('supports', 'put_walls_top') if support else ('resistances', 'call_walls_top')
    if context.get('routing_revision', 1) >= 23:
        kinds += ('observed_origins',)
    if context.get('routing_revision', 1) >= 39 and support:
        kinds += ('option_origins',)
    values = [row.get('level') for kind in kinds for row in _live_levels(context, kind)]
    keys = ('sma20', 'sma50', 'sma200', 'donchian20_low', 'keltner_lower') if support else (
        'donchian20_high', 'keltner_upper', 'sma20', 'sma50', 'sma200')
    values += [tech.get(name) for name in keys]
    atr = tech.get('atr10')
    atr = atr if type(atr) in (int, float) and math.isfinite(atr) and atr > 0 else 0
    tolerance = max((zone['lower'] + zone['upper']) / 2 * .005, atr * .25)
    return any(type(value) in (int, float) and math.isfinite(value)
               and zone['lower'] - tolerance <= value <= zone['upper'] + tolerance for value in values)


def _lower_support(context, floor):
    slim = context['slim']
    scales = [(slim.get('technicals') or {}).get('atr10'), (slim.get('options') or {}).get('expected_move_1w_abs')]
    scales = [v for v in scales if type(v) in (int, float) and math.isfinite(v) and v > 0]
    return any(type(row.get('level')) in (int, float) and 0 < row['level'] < floor * .98
               and (not scales or slim['latest_price'] - row['level'] <= 2 * max(scales))
               for row in _live_levels(context, 'supports'))


def _resolve_facts(level, context):
    facts = []
    for pointer in level['facts']:
        if context.get('routing_revision', 1) >= 11:
            from src.local_runner.semantic_sources import is_report_source, resolve_source
            if is_report_source(pointer):
                value = resolve_source(context, pointer)
                if isinstance(value, (dict, list)) or value is None or type(value) is float and not math.isfinite(value):
                    raise ValueError('update_not_allowed_non_scalar_report_fact')
                reference = context['sol_reference' if pointer.startswith('/sol_reference/') else 'reference']
                facts.append({'pointer': pointer, 'value': deepcopy(value), 'historical': True,
                              'source_kind': 'historical_report', 'as_of': reference.get('generated_at'),
                              'report_markdown_sha256': hashlib.sha256(reference['analysis_markdown'].encode()).hexdigest(),
                              'options_record': None})
                continue
        historical = pointer.startswith(('/reference/slim_snapshot/', '/sol_reference/slim_snapshot/'))
        if not historical and not pointer.startswith('/slim/'):
            raise ValueError('update_not_allowed_unproven_technical_fact_source')
        try:
            value = resolve_evidence(context, pointer)
        except ValueError as exc:
            raise ValueError('update_not_allowed_unproven_technical_fact_source: ' + pointer) from exc
        if isinstance(value, (dict, list)) or value is None or type(value) is float and not math.isfinite(value):
            raise ValueError('update_not_allowed_non_scalar_technical_fact')
        # Any cited part of an options record carries its COMPLETE identity,
        # expiry and current metrics. No strike/OI parsing from prose.
        record = None
        if '/levels/' in pointer:
            root, rest = pointer.split('/levels/', 1)
            parts = rest.split('/')
            # Facts can be nested inside a level's structured evidence. Bind
            # to the containing row, not whichever nested dict is nearest.
            parent = root + '/levels/' + '/'.join(parts[:2])
            candidate = resolve_evidence(context, parent)
            if (context.get('routing_revision', 1) >= 39
                    and parts[0] == 'option_origins' and isinstance(candidate, dict)):
                # A negative/zero scoped observation is legitimate current fact,
                # not a positive support origin. _live_levels checks the latter.
                record = deepcopy(candidate)
            if isinstance(candidate, dict) and ('wall' in str(candidate.get('type', '')) or '_walls_top/' in pointer):
                record = deepcopy(candidate)
                if not historical:
                    kind = pointer.split('/levels/', 1)[1].split('/')[0]
                    if candidate not in list(_live_levels(context, kind)):
                        raise ValueError('update_not_allowed_expired_or_inactive_wall')
                    # Duplicate rows are not independent evidence. A source
                    # conflict cannot be hidden by picking one convenient copy.
                    from src.local_runner.adaptive_maintenance import _wall_records
                    all_records = _wall_records(context['slim'], '/slim')
                    selected = next((r for r in all_records if r['pointer'] == parent), None)
                    if selected is None:
                        raise ValueError('update_not_allowed_unproven_wall_identity')
                    siblings = [r['item'] for r in all_records if
                                (r['side'], r['level'], r['expiry']) ==
                                (selected['side'], selected['level'], selected['expiry'])]
                    for metric in ('oi', 'oi_share_pct', 'gamma_share_pct', 'gamma_usd_millions'):
                        values = [r[metric] for r in siblings if metric in r and r[metric] is not None]
                        if values and (any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
                                       or len(set(values)) > 1):
                            raise ValueError('update_not_allowed_conflicting_wall_sources: ' + metric)
        source = (context.get('sol_reference' if pointer.startswith('/sol_reference/') else 'reference') or {}).get('slim_snapshot', {}) if historical else context['slim']
        facts.append({'pointer': pointer, 'value': deepcopy(value), 'historical': historical,
                      'as_of': source.get('as_of'), 'options_record': record})
    return facts


def _validate_level(level, key, context, previous, *, maintenance):
    _text(level['reason'], key)
    if not level['evidence']:
        raise ValueError('update_not_allowed_missing_level_evidence: ' + key)
    for pointer in level['evidence']:
        comparison = context.get('routing_revision', 1) >= 10 and (pointer == '/comparison' or pointer.startswith('/comparison/'))
        if not comparison and not pointer.startswith(('/slim', '/reference', '/sol_reference')):
            raise ValueError('update_not_allowed_technical_evidence_root')
        try:
            if context.get('routing_revision', 1) >= 11:
                from src.local_runner.semantic_sources import resolve_source
                resolve_source(context, pointer)
            else:
                resolve_evidence(context, pointer)
        except ValueError as exc:
            raise ValueError('update_not_allowed_missing_level_source: ' + pointer) from exc
    if context.get('routing_revision', 1) >= 10 and not any(
            pointer.startswith(('/slim', '/reference', '/sol_reference')) for pointer in level['evidence']):
        raise ValueError('update_not_allowed_missing_primary_level_evidence: ' + key)
    zone, old = level['range'], previous.get('range') if previous else None
    transition = level['transition']
    if zone is None:
        optional = ('entry', 'ambitious_entry') if context.get('routing_revision', 1) >= 22 else ('ambitious_entry',)
        # Applicability belongs to the complete plan, not this isolated field.
        # Geometry below checks ownership and BOTH entries, including washout.
        if context.get('routing_revision', 1) >= 22:
            optional += ('management_stop',)
        if key not in optional or level['strength'] is not None:
            raise ValueError('update_not_allowed_missing_required_level: ' + key)
        if transition != ('remove' if old else 'keep'):
            raise ValueError('update_not_allowed_numeric_continuity: ' + key)
    else:
        if zone['lower'] > zone['upper']:
            raise ValueError('update_not_allowed_reversed_range: ' + key)
        if key in ('management_stop', 'structural_stop', 'target') and zone['lower'] != zone['upper']:
            raise ValueError('update_not_allowed_expected_single_level: ' + key)
        if zone == old:
            if transition not in ('keep', 'correct'):
                raise ValueError('update_not_allowed_numeric_continuity: ' + key)
        elif old is None:
            if transition != 'new':
                raise ValueError('update_not_allowed_numeric_continuity: ' + key)
        else:
            if transition not in ('correct', 'reprioritize'):
                raise ValueError('update_not_allowed_numeric_continuity: ' + key)
            if transition == 'reprioritize' and key in ('entry', 'ambitious_entry', 'resistance') and (
                    max(old['lower'], zone['lower']) <= min(old['upper'], zone['upper'])):
                raise ValueError('update_not_allowed_reprioritized_overlapping_level: ' + key)
        if key in ('entry', 'ambitious_entry', 'resistance'):
            strength = level['strength']
            if strength is None:
                raise ValueError('update_not_allowed_missing_strength: ' + key)
            _text(strength['factors'], key + '/factors')
            total = sum(strength['components'].values())
            if not _strength_breakdown_qualifies(total, strength['components']):
                raise ValueError('update_not_allowed_strength_pillars: ' + key)
        elif level['strength'] is not None:
            raise ValueError('update_not_allowed_unexpected_strength: ' + key)
        # Same historical zone may survive via independently assessed evidence;
        # a newly selected zone MUST have a live authoritative origin.
        # Preserve the authority boundary: this proximity gate already applied
        # to Luna, NOT to full Sol. Sol may reconstruct e.g. a broken resistance
        # as a retest support or combine HVN/structure beyond this small registry.
        # It still cites resolving source pointers and uses the identical rubric.
        # Do not introduce a new restriction while removing cosmetic checks.
        if maintenance and key in EDITABLE and zone != old and not _origin_present(zone, context, key):
            raise ValueError('update_not_allowed_unproven_current_level_origin: ' + key)
    if context.get('routing_revision', 1) >= 25 and key in ('entry', 'ambitious_entry', 'resistance'):
        from src.local_runner.volume_arithmetic import validate
        validate(level, key, context, previous)
    level['resolved_facts'] = _resolve_facts(level, context)
    level['continuity'] = {'previous': deepcopy(old), 'transition': transition}


def _validate_geometry(plan, context):
    entry = plan['entry']['range']
    if context.get('routing_revision', 1) >= 35:
        # Each buying zone is validated independently; no exit level is requested.
        return
    if context.get('routing_revision', 1) >= 29:
        # The plan now describes buying supports and ONE rebound resistance.
        # Stops/target are no longer generated, inherited or risk geometry.
        resistance = plan['resistance']['range']
        if resistance is None:
            raise ValueError('update_not_allowed_missing_required_level: resistance')
        for key in ('entry', 'ambitious_entry'):
            zone = plan[key]['range']
            if zone is not None and resistance['upper'] <= zone['upper']:
                raise ValueError('update_not_allowed_resistance_below_entry: ' + key)
        return
    if context.get('routing_revision', 1) >= 22:
        # No buyable support is a valid decision, not a fabricated entry or an
        # unparseable report. Risk references remain mandatory and protected.
        if plan['management_stop']['range'] is None and (
                context.get('owned') is not False or any(
                    plan[key]['range'] is not None for key in ('entry', 'ambitious_entry'))):
            raise ValueError('update_not_allowed_missing_applicable_management_stop')
        for key in ('target', 'structural_stop'):
            if plan[key]['range'] is None:
                raise ValueError('update_not_allowed_missing_required_level: ' + key)
        for key in ('entry', 'ambitious_entry'):
            zone = plan[key]['range']
            if zone is None:
                continue
            if plan['target']['range']['upper'] <= zone['upper']:
                raise ValueError('update_not_allowed_target_below_entry: ' + key)
            if plan['structural_stop']['range']['upper'] >= zone['lower']:
                raise ValueError('update_not_allowed_structural_stop_above_entry: ' + key)
        return
    # Revision10 collects independent issues after individual-level checks;
    # absent required levels must not mask that feedback with a TypeError.
    for key in ('entry', 'target', 'structural_stop'):
        if plan[key]['range'] is None:
            raise ValueError('update_not_allowed_missing_required_level: ' + key)
    if context.get('routing_revision', 1) < 14 and plan['ambitious_entry']['range'] is None and _lower_support(context, entry['lower']):
        raise ValueError('update_not_allowed_ambitious_entry_unavailable_despite_lower_support')
    # These are financial constraints, never inferred from explanatory prose.
    if plan['target']['range']['upper'] <= entry['upper']:
        raise ValueError('update_not_allowed_target_below_entry')
    if plan['structural_stop']['range']['upper'] >= entry['lower']:
        raise ValueError('update_not_allowed_structural_stop_above_entry')


def maintenance_document(payload, context, *, binding=None):
    from src.local_runner.adaptive_maintenance import maintenance_decision, _check_urls, _evidence
    if context.get('routing_revision', 1) >= 11:
        from src.local_runner.semantic_binding import require_response_binding
        require_response_binding(payload, context, binding)
    if maintenance_decision(payload, context.get('guards', []), context) != 'update':
        raise ValueError('update_not_allowed_uncertain_or_critical')
    baseline = context['reference']['analysis_markdown']
    if context.get('routing_revision', 1) < 11 and payload['base_markdown_sha256'] != hashlib.sha256(baseline.encode()).hexdigest():
        raise ValueError('invalid_update_base_hash')
    change = payload['update']
    revision = context.get('routing_revision', 1)
    check_schema(change, update_schema(revision))
    from src.local_runner.maintenance_text import note_text
    public_note = note_text(payload, revision)
    doc = reference_document(context['reference'], verify_projection=revision >= 11)
    if revision >= 29:
        from src.local_runner.plan_scope import project_plan
        doc = project_plan(doc, revision)
    if revision >= 16:
        # Capture the OLD scope/date before replacing commentary audit/metadata.
        from src.local_runner.review_memory import maintain_notes
        maintain_notes(doc, payload, context)
    old_plan = deepcopy(doc['plan'])
    issues = []
    if revision >= 15:
        from src.local_runner.maintenance_change import validate_commentary_changes
        commentary_issues, audit = validate_commentary_changes(payload, context)
        issues.extend(commentary_issues)
        doc['commentary_change_review'] = audit
    if revision >= 21:
        from src.local_runner.maintenance_text import unpack_explanation
        change = deepcopy(change)
        change['plan_explanation'] = unpack_explanation(change.get('plan_explanation'))
    if revision >= 10:
        from src.local_runner.semantic_sources import normalize_plan
        change = deepcopy(change)
        selected = {key: value for key, value in change['plan'].items() if value is not None}
        normalized, source_issues = normalize_plan(selected, old_plan, context)
        issues.extend(source_issues)
        change['plan'].update(normalized)
    if revision < 12 or change['setup_score'] is not None or change['setup_reason'] is not None:
        if change['setup_score'] is None and revision < 20:
            raise ValueError('update_not_allowed_missing_setup_score')
        setup_reason = change['setup_reason']
        if revision >= 18 and change.get('plan_explanation') is not None:
            setup_reason = change['plan_explanation']['setup_reason'] if revision < 20 else (
                change['plan_explanation']['setup_reason'] or setup_reason or doc['summary']['setup_reason'])
        if revision >= 20 and setup_reason is None:
            setup_reason = doc['summary']['setup_reason']
        _text(setup_reason, 'setup_reason')
        doc['summary'].update(setup_score=change['setup_score'] if change['setup_score'] is not None
                             else doc['summary']['setup_score'], setup_reason=setup_reason)
    if change['conclusion'] is not None:
        _text(change['conclusion'], 'conclusion')
    from src.local_runner.plan_scope import editable_keys
    for key in editable_keys(revision):
        level = deepcopy(change['plan'][key])
        if revision >= 12 and level is None:
            # Already-validated financial judgment, reviewed by Luna but not
            # rewritten. Its old facts stay dated; never relabel them live just
            # because a different block/news note updated today's report.
            inherited = doc['plan'][key]
            inherited['transition'] = 'keep'
            inherited['continuity'] = {'previous': deepcopy(old_plan[key]['range']), 'transition': 'keep'}
            inherited_origin = {
                'generated_at': context['reference'].get('generated_at'),
                'markdown_sha256': hashlib.sha256(baseline.encode()).hexdigest()}
            if revision >= 21:
                inherited.setdefault('retained_from_report', inherited_origin)
            else:
                inherited['retained_from_report'] = inherited_origin
            for fact in inherited.get('resolved_facts', []):
                fact['historical'] = True
                if revision >= 21:
                    fact.setdefault('retained_from_report', deepcopy(inherited['retained_from_report']))
                else:
                    fact['retained_from_report'] = deepcopy(inherited['retained_from_report'])
            continue
        if revision >= 14:
            from src.local_runner.maintenance_change import validate_change
            try:
                validate_change(level, key, context)
            except ValueError as exc:
                details = getattr(exc, 'maintenance_details', {}).get('issues')
                issues.extend(details or [{'field': '/plan/' + key + '/change_review', 'error': str(exc)}])
        try:
            _validate_level(level, key, context, old_plan[key], maintenance=True)
            sources = [p for p in level['evidence'] if not (p == '/comparison' or p.startswith('/comparison/'))]
            _check_urls(level['reason'] + '\n' + (level['strength'] or {}).get('factors', ''),
                        baseline, _evidence(context, sources, edits=True), canonical=revision >= 10)
        except ValueError as exc:
            if revision < 10: raise
            issues.append({'field': '/plan/' + key, 'error': str(exc)})
        doc['plan'][key] = level
    try:
        _validate_geometry(doc['plan'], context)
    except ValueError as exc:
        if revision < 10: raise
        issues.append({'field': '/plan', 'error': str(exc)})
    if revision >= 13:
        if change['conclusion'] is None:
            # A news-only update must not relabel a quote-dependent inherited
            # conclusion as observed in the new snapshot. Preserve its ORIGINAL
            # provenance through successive maintenance, without parsing prose.
            old_meta = doc.get('metadata') or {}
            reference = context['reference']
            doc.setdefault('conclusion_provenance', {
                'report_at': reference.get('generated_at'),
                'snapshot_at': old_meta.get('snapshot_at') or
                    (reference.get('slim_snapshot') or {}).get('as_of'),
                'reference_price': old_meta.get('reference_price', reference.get('latest_price')),
                'markdown_sha256': hashlib.sha256(baseline.encode()).hexdigest()})
        else:
            doc.pop('conclusion_provenance', None)
    # Dates/price/state/percentages/continuity are derived, never requested from Luna.
    doc['metadata'] = _metadata(context)
    if revision >= 10: doc['metadata']['source_contract_revision'] = revision
    if change['conclusion'] is not None:
        doc['conclusion'] = change['conclusion']
    if revision < 20:
        doc['routine_note'] = public_note
    if revision >= 18:
        from src.local_runner.review_contract import reconcile_plan_explanation, record_event_assessment
        issues.extend(reconcile_plan_explanation(doc, change, old_plan, context))
        record_event_assessment(doc, payload, context)
    pointers = [p for section in ('setup', 'levels', 'news', 'analysts') for p in payload[section]['evidence']]
    try:
        _check_urls((change['setup_reason'] or '') + '\n' + (change['conclusion'] or '') + '\n' + public_note,
                    baseline, _evidence(context, pointers, edits=False), canonical=revision >= 10)
    except ValueError as exc:
        if revision < 10: raise
        issues.append({'field': '/commentary', 'error': str(exc)})
    if revision >= 10:
        from src.local_runner.semantic_sources import raise_issues
        raise_issues(issues)
    if revision >= 21:
        from src.local_runner.text_provenance import stamp
        stamp(doc, context)
    return doc


def full_document(payload, context, *, binding=None):
    revision = context.get('routing_revision', 1)
    if revision >= 11:
        from src.local_runner.semantic_binding import require_response_binding
        require_response_binding(payload, context, binding, report=True)
    financial_schema = report_schema(revision)
    if revision >= 32:
        # The model receives typed display booleans. An omitted/malformed
        # editorial choice must show the fact, not fail financial publication.
        for event in (financial_schema['properties']['catalysts']['items'],
                      financial_schema['properties']['next_event']['anyOf'][0]):
            field = 'reader_assessment' if 'reader_assessment' in event['properties'] else 'show_in_report'
            event['properties'][field] = {}
            event['required'].remove(field)
    if revision >= 36:
        financial_schema['properties']['support_validity_review'] = {}
        financial_schema['required'].remove('support_validity_review')
    check_schema(payload, financial_schema)
    doc = deepcopy(payload)
    for key, value in doc['summary'].items():
        if isinstance(value, str):
            _text(value, key)
    _text(doc['conclusion'], 'conclusion')
    previous = reference_document(context['reference'], verify_projection=revision >= 11) if context.get('reference', {}).get('analysis_markdown') else None
    if revision >= 10:
        from src.local_runner.semantic_sources import normalize_plan, raise_issues
        doc['plan'], issues = normalize_plan(doc['plan'], (previous or {}).get('plan'), context)
        raise_issues(issues)
    from src.local_runner.plan_scope import plan_labels
    for key in plan_labels(revision):
        _validate_level(doc['plan'][key], key, context, (previous or {}).get('plan', {}).get(key), maintenance=False)
    _validate_geometry(doc['plan'], context)
    for event in [*doc['catalysts'], *([doc['next_event']] if doc['next_event'] else [])]:
        _text(event['title'], 'event/title')
        _text(event['description'], 'event/description')
        if event['date'] is not None:
            try:
                event['date'] = date.fromisoformat(event['date']).isoformat()
            except ValueError as exc:
                raise ValueError('update_not_allowed_invalid_event_date') from exc
    doc['catalysts'].sort(key=lambda item: item['date'] or '', reverse=True)
    doc.update(metadata=_metadata(context), routine_note='', fundamental_markdown=None)
    if revision >= 10: doc['metadata']['source_contract_revision'] = revision
    if revision >= 21:
        from src.local_runner.text_provenance import stamp
        stamp(doc, context, full=True)
    if revision >= 32:
        from src.local_runner.reader_report import full_selection
        full_selection(doc)
    if revision >= 36:
        from src.local_runner.support_validity import apply_review
        apply_review(doc, previous, doc.pop('support_validity_review', None), context)
    return doc


def _prose(value):
    """Render model commentary as content, never as headings/field authority.

    HTML is escaped; multiline commentary is quoted after its first line. This
    makes arbitrary labels/colons safe without rejecting or changing the words.
    """
    original = str(value or '')
    # Escape Markdown syntax as well as HTML, so an unbalanced fence/link/
    # emphasis from source prose cannot swallow subsequent protected fields.
    safe = html.escape(original, quote=False)
    safe = re.sub(r'([\\`*_{}\[\]()#>|~])', r'\\\1', safe)
    lines = safe.splitlines()
    if not lines:
        return ''
    rendered = lines[0] + ''.join('\n> ' + line for line in lines[1:])
    # Links come from code, not the prose's bracket/parenthesis grammar.
    urls = sorted(cited_urls(original))
    if urls:
        rendered += ' · ' + ' '.join('<' + url + '>' for url in urls)
    return rendered


def _range_text(zone):
    if zone is None:
        return 'Sin zona verificable'
    values = [format_exact_price(zone['lower'])]
    if zone['upper'] != zone['lower']:
        values.append(format_exact_price(zone['upper']))
    return '$' + '–'.join(values)


def _reader_prose(value):
    """Safe prose with named HTTP(S) citations, not escaped links plus raw URLs."""
    from urllib.parse import quote, urlsplit
    original = str(value or '')
    def plain(text):
        safe = html.escape(text, quote=False)
        return re.sub(r'([\\`*_{}\[\]()#>|~])', r'\\\1', safe)
    chunks, pos = [], 0
    for match in re.finditer(r'\[([^\]\n]+)\]\((https?://[^\s<>"\[\]]+)\)', original):
        url = match[2]
        if urlsplit(url).scheme not in ('http', 'https') or not urlsplit(url).netloc:
            continue
        chunks += [plain(original[pos:match.start()]),
                   '[' + plain(match[1]) + '](' + quote(url, safe=':/?&=%#@+-._~') + ')']
        pos = match.end()
    chunks.append(plain(original[pos:]))
    lines = ''.join(chunks).splitlines()
    return lines[0] + ''.join('\n> ' + line for line in lines[1:]) if lines else ''


def render_document(doc, *, reader=False):
    """Human report, not an audit export.

    Source selections, resolved facts and full records remain in semantic_report
    for validation/audit. Never dump those internal payloads into the reader's
    plan: the financial explanation and strength factors are its public content.
    Rendering must not mutate the validated financial document.
    """
    meta, summary = doc['metadata'], doc['summary']
    if max(meta.get('reader_format_revision', 0), meta.get('source_contract_revision', 0)) >= 32:
        from src.local_runner.reader_report import render
        return render(doc)
    reader = reader or meta.get('source_contract_revision', 0) >= 17
    prose = _reader_prose if reader else _prose
    from src.local_runner.text_provenance import label as text_date
    price = meta['reference_price']
    lines = ['# ' + prose(meta['symbol']), '', 'Fecha del análisis: ' + meta['analysis_date'],
             'Precio de referencia: $' + format_exact_price(price), 'Snapshot técnico: ' + meta['snapshot_at'], '',
             '## 0) Resumen ejecutivo', 'Tesis: ' + format_exact_price(summary['thesis_score']) + ' / 10',
             'Motivo de Tesis: ' + prose(summary['thesis_reason']),
             'Setup: ' + format_exact_price(summary['setup_score']) + ' / 10',
             'Motivo de Setup: ' + prose(summary['setup_reason']) + text_date(doc, 'setup_reason'), 'Narrativa actual: ' + prose(summary['narrative']), '']
    if reader:
        # Each executive field is a paragraph, not one unbroken wall of text.
        lines = [part for line in lines for part in (line, '')]
    if meta.get('quote') and not reader:
        lines.insert(5, '> Cotización congelada (no precio ejecutable garantizado): ' +
                     _prose(json.dumps(meta['quote'], ensure_ascii=False)))
    if doc.get('fundamental_markdown') is not None:
        lines.append(doc['fundamental_markdown'].rstrip())
    else:
        lines.append('## 1) Narrativa y catalizadores activos')
        for item in doc['catalysts']:
            lines += ['', (item['date'] or 'Fecha no confirmada') + ' · ' + prose(item['title']) + ' · (' + f"{item['impact']:+d}" + ')',
                      '> ' + prose(item['description'])]
        lines += ['', '## 2) Próximo evento clave']
        event = doc['next_event']
        if event:
            lines += [(event['date'] or 'Fecha no confirmada') + ' · ' + prose(event['title']), '> ' + prose(event['description'])]
        else:
            lines.append('Sin evento confirmado.')
    if meta.get('source_contract_revision', 0) >= 18 and doc.get('event_review'):
        event_review = doc['event_review']
        status = {'occurred': 'ya ocurrido', 'cancelled': 'cancelado', 'rescheduled': 'reprogramado',
                  'pending': 'pendiente', 'uncertain': 'estado sin confirmar'}[event_review['status']]
        lines += ['', '> Evento del informe base: ' + status + ' según la revisión del ' +
                  prose(str(event_review['reviewed_at'])[:10]) +
                  '. El texto original anterior se conserva como antecedente fechado.']
    lines += ['', '## 3) Plan']
    from src.local_runner.plan_scope import plan_labels
    for key, label in plan_labels(meta.get('source_contract_revision', 0)).items():
        level, zone = doc['plan'][key], doc['plan'][key]['range']
        percentages = ''
        if zone:
            percentages = f" ({(zone['lower']/price-1)*100:+.2f}%"
            if zone['upper'] != zone['lower']:
                percentages += f" a {(zone['upper']/price-1)*100:+.2f}%"
            percentages += ' vs precio actual)'
        display = 'No aplicable' if key == 'management_stop' and zone is None else _range_text(zone)
        lines += ['', '### ' + label, '', label + ': ' + display + percentages]
        if key == 'entry' and zone is not None:
            state = 'por encima' if price > zone['upper'] else 'por debajo' if price < zone['lower'] else 'dentro'
            if meta.get('source_contract_revision', 0) >= 30:
                lines += ['', 'Precio en la captura: ' + state + ' de la zona.']
            elif meta.get('source_contract_revision', 0) >= 13:
                lines += ['', 'Estado en el snapshot: ' + state +
                          ' de la zona; ubicación, no confirmación de ruptura ni ejecución.']
            else:
                lines += ['', 'Estado actual: ' + state + ' de la zona']
        continuity = level.get('continuity')
        explanation = ''
        if continuity and not reader:
            action = {'keep': 'Se conserva', 'correct': 'Se corrige', 'reprioritize': 'Se reprioriza',
                      'remove': 'Se retira', 'new': 'Nivel nuevo'}[continuity['transition']]
            prior = continuity['previous']
            explanation = action + (': nivel anterior ' + _range_text(prior) if prior else '') + '. '
        lines += ['', 'Motivo: ' + explanation + prose(level['reason']) + text_date(doc, key)]
        strength = level['strength']
        if key in ('entry', 'ambitious_entry', 'resistance'):
            slabel = 'Resistencia' if key == 'resistance' else label
            if strength:
                total = sum(strength['components'].values())
                if reader:
                    lines += ['', 'Fortaleza de ' + slabel + ': ' + str(total) + '/100 · ' + support_strength_category(total)]
                    continue  # Rubric arithmetic/factors stay in the typed audit.
                lines += ['', 'Fortaleza de ' + slabel + ': ' + str(total) + '/100 · ' + support_strength_category(total), '',
                          'Desglose de ' + slabel + ': ' + '; '.join(k + ' ' + str(strength['components'][k]) + '/' + str(cap) for k, cap in MAXIMA.items()),
                          '', 'Factores de ' + slabel + ': ' + _prose(strength['factors'])]
            else:
                if reader:
                    lines += ['', 'Fortaleza de ' + slabel + ': No aplicable']
                    continue
                lines += ['', 'Fortaleza de ' + slabel + ': No aplicable', '', 'Desglose de ' + slabel + ': No aplicable', '',
                          'Factores de ' + slabel + ': ' + _prose(level['reason'])]
    lines += ['', '## 4) Conclusión sencilla']
    provenance = doc.get('conclusion_provenance')
    if meta.get('source_contract_revision', 0) >= 21:
        if text_date(doc, 'conclusion'):
            lines += ['> ' + prose(text_date(doc, 'conclusion').strip()), '']
    elif meta.get('source_contract_revision', 0) >= 13 and provenance:
        observed_at = provenance.get('snapshot_at') or provenance.get('report_at') or 'fecha no disponible'
        lines += ['> Conclusión conservada · snapshot ' + prose(observed_at) + '.', '']
    lines += ['> ' + prose(doc['conclusion'])]
    news_note = doc.get('news_note') if meta.get('source_contract_revision', 0) >= 16 else None
    if news_note:
        lines += ['', '## Aclaraciones de noticias (Luna)', '',
                  '> Nota fechada · ' + prose(news_note.get('as_of')) + '.', '',
                  '> ' + prose(news_note['text'])]
    if doc.get('routine_note') and (not news_note or doc['routine_note'] != news_note['text']):
        lines += ['', '## Actualización diaria (Luna)', '']
        if meta.get('source_contract_revision', 0) >= 20 and doc.get('routine_note_at'):
            lines += ['> Nota fechada · ' + prose(doc['routine_note_at']) + '.', '']
        lines += ['> ' + prose(doc['routine_note'])]
    return '\n'.join(lines) + '\n'


def validation_result(doc):
    """Compatibility serialization of ALREADY validated data, not Markdown parsing."""
    def zone(key):
        if key not in doc['plan']:
            return None
        value = doc['plan'][key]['range']
        return PriceRange(**value) if value else None
    def strength(key):
        if key not in doc['plan']:
            return None
        value = doc['plan'][key]['strength']
        if value is None:
            return SupportStrength(None, 'no_aplica', doc['plan'][key]['reason'], {}, applicable=False)
        total = sum(value['components'].values())
        return SupportStrength(total, support_strength_category(total), value['factors'], deepcopy(value['components']))
    return ValidationResult(True, 'ok', (), doc['summary']['thesis_score'], zone('entry'), zone('ambitious_entry'),
                            zone('resistance'), strength('entry'), strength('ambitious_entry'), strength('resistance'))


def publication_fields(doc, markdown, reference, generated_at):
    """Publish numerical authority directly; downstream mirrors never parse prose."""
    summary = doc['summary']
    decision = {**deepcopy(summary), 'score': summary['thesis_score'], 'score_basis': 'thesis',
                'score_category': score_category(summary['thesis_score']), 'reference_price': doc['metadata']['reference_price']}
    plan = {}
    for key, level in doc['plan'].items():
        zone = deepcopy(level['range'])
        plan[key] = zone['lower'] if zone and key in ('management_stop', 'structural_stop', 'target') else zone
        plan[key + '_reason'] = level['reason']
        if key in ('entry', 'ambitious_entry') and 'support_validity' in level:
            plan[key + '_support_validity'] = deepcopy(level['support_validity'])
        if key in ('entry', 'ambitious_entry', 'resistance'):
            prefix = 'washout' if key == 'ambitious_entry' else key
            value = level['strength']
            total = sum(value['components'].values()) if value else None
            plan.update({prefix + '_strength_score': total,
                         prefix + '_strength_category': support_strength_category(total) if total is not None else 'no_aplica',
                         prefix + '_strength_factors': value['factors'] if value else level['reason'],
                         prefix + '_strength_breakdown': deepcopy(value['components']) if value else {}})
    def event_mirror(event):
        result = deepcopy(event)
        if result is not None and 'description' in result:
            result['explanation'] = result.pop('description')
        return result
    current = {'decision': decision, 'plan': plan, 'catalysts': [event_mirror(item) for item in doc['catalysts']],
               'next_event': event_mirror(doc['next_event'])}
    previous = {'decision': reference.get('decision', {}), 'plan': reference.get('plan', {}),
                'catalysts': reference.get('catalysts', []), 'next_event': reference.get('next_event')}
    if reference.get('analysis_markdown') and not reference.get('semantic_report'):
        previous = parse_report(reference['analysis_markdown'], latest_price=None)
    changes = compare_reports(current, previous if reference else None)
    if isinstance(current['next_event'], dict):
        _annotate_event_proximity(current['next_event'], generated_at.date())
    return {**current, 'changes': changes, 'alerts': build_analysis_alerts(current, changes),
            'semantic_report': {'version': 1, 'data': deepcopy(doc), 'data_sha256': digest(doc),
                                'markdown_sha256': hashlib.sha256(markdown.encode()).hexdigest()}}
