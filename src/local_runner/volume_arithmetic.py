"""Revision25: arithmetic on explicit sources; no financial decisions."""
from decimal import Decimal
from src.local_runner.adaptive_policy import timestamp, session_age

PREFIX = 'update_not_allowed_volume_arithmetic: '

def n(value):
    if type(value) not in (int, float):
        raise ValueError(PREFIX + 'incomplete_numeric_evidence')
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(PREFIX + 'nonfinite_numeric_evidence')
    return result

def calculate(profile, reaction, zone, as_of, *, revision=33):
    if profile.get('status') != 'available' or reaction.get('status') != 'available':
        return None
    center = (n(zone['lower']) + n(zone['upper'])) / 2
    node = n(profile.get('nearest_level'))
    if center <= 0 or node <= 0:
        raise ValueError(PREFIX + 'invalid_node_or_center')
    distance = abs(node-center) / center * 100
    proximity = min(3, 0 if distance > 5 else 1 if distance > 3 else
                    2 if distance > Decimal('1.5') else 3 if distance > Decimal('0.75') else 4)
    defenses, tests, rate = [n(reaction.get(k)) for k in ('defense_count', 'test_count', 'defense_rate_pct')]
    median, minimum, last_rebound = [n(reaction.get(k)) for k in
        ('median_rebound_5d_pct', 'defense_min_rebound_pct', 'last_test_rebound_5d_pct')]
    if minimum <= 0 or defenses < 0 or tests < defenses or not 0 <= rate <= 100:
        raise ValueError(PREFIX + 'invalid_reaction_evidence')
    repetition = 0 if defenses < 1 else 1 if defenses < 2 else 2 if defenses < 3 else 3 if defenses < 5 else 4 if defenses < 8 else 5
    defense_rate = 0 if rate < 40 else 1 if rate < 50 else 2 if rate < 65 else 3 if rate < 80 else 4
    if tests < 3:
        defense_rate = min(defense_rate, 2)
    magnitude = (4 if median >= 3*minimum else 3 if median >= 2*minimum else
                 2 if median >= Decimal('1.5')*minimum else 1 if median >= minimum else 0)
    if last_rebound < minimum:
        magnitude = min(magnitude, 2)
    date = reaction.get('last_test_date')
    last = timestamp(str(date) + 'T12:00:00+00:00') if date else None
    now = timestamp(as_of)
    if not last or not now or last > now:
        raise ValueError(PREFIX + 'invalid_reaction_observation_date')
    age = session_age(last, now)
    recency = 3 if age <= 10 else 2 if age <= 30 else 1 if age <= 60 else 0
    parts = dict(proximity=proximity, repetition=repetition, defense_rate=defense_rate,
                 magnitude=magnitude, recency=recency)
    # >=34: node distance earns only its proximity points. Historical quality
    # still gates the sum, but a distant node cannot gate the same history again.
    paired = (revision >= 34 or distance <= 5) and tests >= 3 and defenses >= 2
    over15 = paired and (revision >= 34 or distance <= 3) and tests >= 5 and defenses >= 3 and rate >= 60 and age <= 30 and median >= minimum
    over18 = over15 and (revision >= 34 or distance <= Decimal('1.5')) and tests >= 8 and rate >= 75 and age <= 10 and median >= 2*minimum
    ceiling = 20 if over18 else 18 if over15 else 15 if paired else 12
    result = dict(parts=parts, ceiling=ceiling, expected=min(sum(parts.values()), ceiling),
                  node_distance_pct=str(distance), test_age_sessions=age)
    if revision >= 34:
        result['rubric_revision'] = 34
    return result

def _inherited_buy_volume(level, key, context):
    """A buying zone's dated score belongs to the zone, not its UI slot.

    Only an explicitly cited, authenticated CURRENT opposite buying slot can
    supply this inheritance. The Sol anchor is not the maintained plan, and a
    resistance cannot lend support-rebound arithmetic. This does not authorize
    the move, establish live backing or approve other strength components.
    """
    if context.get('routing_revision', 1) < 28 or key not in ('entry', 'ambitious_entry'):
        return False
    other = 'ambitious_entry' if key == 'entry' else 'entry'
    pointer = '/reference/semantic_data/plan/' + other
    cited = pointer in level['evidence']
    if not cited and context.get('routing_revision', 1) >= 40:
        from src.local_runner.semantic_sources import source_catalog
        catalog = source_catalog(context)  # Rebuilt from authenticated inputs.
        selected = (level.get('change_review') or {}).get('previous_evidence', [])
        cited = any((catalog.get(handle) or {}).get('pointer') == pointer for handle in selected)
    if not cited:
        return False
    from src.local_runner.semantic_sources import resolve_source
    prior = resolve_source(context, pointer)  # Verified envelope, not model mirrors.
    old_components = (prior.get('strength') or {}).get('components', {})
    return (level['range'] is not None and level['range'] == prior.get('range') and
            level['strength']['components']['volumen'] == old_components.get('volumen'))


def validate_rubric_change(level, key, context):
    """Narrow maintenance authority for an explicitly selected method migration.

    No automatic edits: the model must select current complete observations and
    the exact prior decision. A method change cannot move a zone, alter another
    component, claim a market event or migrate the same calculation repeatedly.
    """
    from src.local_runner.semantic_report import reference_document
    from src.local_runner.semantic_sources import source_catalog

    def reject(reason):
        raise ValueError('volume_rubric_change_' + reason)

    if context.get('routing_revision', 1) < 34 or key not in ('entry', 'ambitious_entry', 'resistance'):
        reject('wrong_revision_or_level')
    prior = reference_document(context['reference'], verify_projection=True)['plan'][key]
    if level['range'] is None or level['range'] != prior['range'] or not prior['strength']:
        reject('requires_same_active_zone')
    before, after = prior['strength']['components'], level['strength']['components']
    if any(before[name] != after[name] for name in before if name != 'volumen'):
        reject('other_component_changed')
    if (prior.get('volume_calculation_audit') or {}).get('rubric_revision', 0) >= 34:
        reject('already_migrated')
    basis = level.get('volume_calculation')
    if not basis:
        reject('requires_explicit_calculation')
    catalog = source_catalog(context)
    review = level['change_review']
    own = '/reference/semantic_data/plan/' + key
    if not any((catalog.get(h) or {}).get('pointer') == own for h in review['previous_evidence']):
        reject('requires_prior_decision')
    records = []
    for field in ('profile_source', 'reaction_source'):
        row = catalog.get(basis[field])
        if (not row or not row['pointer'].startswith('/slim/levels/') or
                row['pointer'] not in level['evidence'] or basis[field] not in review['current_evidence']):
            reject('requires_selected_current_sources')
        records.append(row['value'])
    profile = (records[0].get('evidence') or {}).get('volume_profile') or {}
    reaction = (records[1].get('evidence') or {}).get('historical_reaction') or {}
    old = calculate(profile, reaction, level['range'], context['slim']['as_of'], revision=33)
    new = calculate(profile, reaction, level['range'], context['slim']['as_of'], revision=34)
    if old is None or new is None:
        reject('incomplete_evidence')
    if before['volumen'] != old['expected'] or after['volumen'] != new['expected'] or old['expected'] == new['expected']:
        reject('not_exact_method_delta')


def validate(level, key, context, previous):
    if context.get('routing_revision', 1) < 25:
        return
    from src.local_runner.semantic_sources import source_catalog, resolve_source
    from src.local_runner.reaction_direction import applicable_reaction
    basis, strength = level.get('volume_calculation'), level['strength']
    if not strength:
        if basis is not None:
            raise ValueError(PREFIX + key + ': calculation_without_strength')
        return
    old_strength = (previous or {}).get('strength') or {}
    unchanged = (level['range'] == (previous or {}).get('range') and
                 strength['components']['volumen'] == old_strength.get('components', {}).get('volumen'))
    if basis is None and (unchanged or _inherited_buy_volume(level, key, context)):
        return  # Inherited number is not a new arithmetic claim.
    catalog = source_catalog(context)
    if basis is None:
        selected = [(p, resolve_source(context, p)) for p in level['evidence']]
        selected = [(p, v) for p, v in selected if isinstance(v, dict)]
        complete = (any(((v.get('evidence') or {}).get('volume_profile') or {}).get('status') == 'available'
                        for _, v in selected) and
                    any(((v.get('evidence') or {}).get('historical_reaction') or {}).get('status') == 'available'
                        and applicable_reaction(v, p, key) for p, v in selected))
        if complete:
            raise ValueError(PREFIX + key + ': select_profile_and_reaction_sources')
        return  # No fully structured pair: never guess inputs or parse prose.
    records = []
    for field in ('profile_source', 'reaction_source'):
        row = catalog.get(basis[field])
        if row is None or row['pointer'] not in level['evidence']:
            raise ValueError(PREFIX + key + ': unselected_' + field)
        roots = ('/slim/levels/', '/reference/slim_snapshot/levels/', '/sol_reference/slim_snapshot/levels/')
        if not row['pointer'].startswith(roots):
            raise ValueError(PREFIX + key + ': nonstructured_' + field)
        records.append(row)
    profile_row, reaction_row = records
    if not applicable_reaction(reaction_row['value'], reaction_row['pointer'], key):
        raise ValueError(PREFIX + key + ': reaction_direction_not_applicable')
    profile = (profile_row['value'].get('evidence') or {}).get('volume_profile') or {}
    reaction = (reaction_row['value'].get('evidence') or {}).get('historical_reaction') or {}
    pointer = reaction_row['pointer']
    slim = context['slim'] if pointer.startswith('/slim/') else context[pointer.split('/')[1]]['slim_snapshot']
    audit = calculate(profile, reaction, level['range'], slim.get('as_of'),
                      revision=context.get('routing_revision', 1))
    if audit is None:
        raise ValueError(PREFIX + key + ': unavailable_declared_calculation')
    actual = strength['components']['volumen']
    if actual != audit['expected']:
        raise ValueError(PREFIX + key + ': expected=' + str(audit['expected']) +
                         ', received=' + str(actual) + ', subcriteria=' + str(audit['parts']) +
                         ', ceiling=' + str(audit['ceiling']))
    level['volume_calculation_audit'] = audit  # Internal only.


def arithmetic_only(error):
    issues = getattr(error, "maintenance_details", {}).get("issues") or []
    return (bool(issues) and all(row.get("error", "").startswith(PREFIX) for row in issues)) or (not issues and str(error).startswith(PREFIX))
