"""Evaluate the existing volume gates, not financial routing or zone suitability."""
from src.local_runner.adaptive_policy import number, timestamp, session_age


def volume_ceiling(evidence, as_of, *, revision=33):
    profile = evidence.get('volume_profile') or {}
    reaction = evidence.get('historical_reaction') or {}
    distance = number(profile.get('nearest_abs_distance_pct')) if profile.get('status') == 'available' else None
    available = reaction.get('status') == 'available'
    def n(key):
        return number(reaction.get(key)) if available else None
    tests, defenses, rate = n('test_count'), n('defense_count'), n('defense_rate_pct')
    median, minimum = n('median_rebound_5d_pct'), n('defense_min_rebound_pct')
    # A session date is a New York calendar date, not midnight UTC (previous
    # NY day). Noon UTC represents that session unambiguously across DST.
    last_date = reaction.get('last_test_date')
    last = timestamp(str(last_date) + 'T12:00:00+00:00') if last_date else None
    now = timestamp(as_of)
    age = session_age(last, now) if available and last and now and last <= now else None
    paired = ((revision >= 34 or (distance is not None and distance <= 5)) and tests is not None and tests >= 3
              and defenses is not None and defenses >= 2)
    over15 = (paired and (revision >= 34 or distance <= 3) and tests >= 5 and defenses >= 3
              and rate is not None and rate >= 60 and age is not None and age <= 30
              and minimum is not None and minimum > 0 and median is not None and median >= minimum)
    over18 = (over15 and (revision >= 34 or distance <= 1.5) and tests >= 8 and rate >= 75 and age <= 10 and median >= 2*minimum)
    structured = profile.get('status') == 'available' or available
    result = {'ceiling_from_this_record': 20 if over18 else 18 if over15 else 15 if paired else 12 if structured else 4,
            'both_families_for_above_12': bool(paired), 'eligible_above_15': bool(over15),
            'eligible_above_18': bool(over18), 'nearest_node_distance_pct': distance,
            'completed_test_age_sessions': age}
    if revision >= 34:
        result.pop('both_families_for_above_12')
        result['historical_sample_for_above_12'] = bool(paired)
        result['rubric_revision'] = 34
    return result


def observations(context):
    result = {}
    from src.local_runner.semantic_sources import source_catalog
    for handle, row in source_catalog(context).items():
        value = row['value']
        if not isinstance(value, dict) or not isinstance(value.get('evidence'), dict):
            continue
        pointer = row['pointer']
        if pointer.startswith('/slim/levels/'):
            slim = context.get('slim') or {}
        elif pointer.startswith('/reference/slim_snapshot/levels/'):
            slim = (context.get('reference') or {}).get('slim_snapshot') or {}
        elif pointer.startswith('/sol_reference/slim_snapshot/levels/'):
            slim = (context.get('sol_reference') or {}).get('slim_snapshot') or {}
        else:
            continue
        gates = volume_ceiling(value['evidence'], slim.get('as_of'),
                               revision=context.get('routing_revision', 1))
        # Existing catalog already carries the evidence. Do not repeat full
        # records/paths or intermediate flags in every paid model input.
        result[handle] = {'record_level': value.get('level'),
                          'ceiling': gates['ceiling_from_this_record'],
                          'test_age_sessions': gates['completed_test_age_sessions']}
        if context.get('routing_revision', 1) >= 27:
            from src.local_runner.reaction_direction import reaction_direction
            result[handle]['reaction_direction'] = reaction_direction(value, pointer)
            result[handle]['direction_warning'] = 'Reaction points apply only to this measured direction, not both roles.'
    scope = ('Revision34 gates use historical sample, magnitude and recency; node distance '
             'affects proximity points only. A ceiling is not an assigned score. '
             'Calculate the exact zone-center sum; unavailable profile earns no invented points. '
             'No automatic rescoring or inference of new backing.'
             if context.get('routing_revision', 1) >= 34 else
             'Existing rubric gates at the exact source level, NOT assigned scores, '
            'zone-center calculations or routing decisions. Sum the five subcriteria separately. '
            'A 3-5% node allows up to 15 with both families, not merely 12. '
            'Additional independently verified evidence may satisfy a missing gate. '
            'Unavailable evidence is not proof of lost backing. No automatic rescoring.')
    return {'records': result, 'scope': scope}
