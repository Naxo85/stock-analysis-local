"""Expose source measurement semantics; do not infer financial decisions."""
from copy import deepcopy


def technical_observations(context):
    old = (context.get('reference') or {}).get('slim_snapshot') or {}
    current = context.get('slim') or {}
    walls = []
    for kind in ('put_walls_top', 'call_walls_top'):
        previous = (old.get('levels') or {}).get(kind) or []
        for i, row in enumerate((current.get('levels') or {}).get(kind) or []):
            matches = [item for item in previous if item.get('level') == row.get('level')]
            walls.append({'current_pointer': f'/slim/levels/{kind}/{i}',
                          'level': row.get('level'), 'dominant_expiration': row.get('expiration'),
                          'previous_dominant_expirations': [item.get('expiration') for item in matches],
                          'same_strike_previously_listed': bool(matches)})
    extrema = []
    for i, row in enumerate((current.get('levels') or {}).get('supports') or []):
        if row.get('type') in ('52w_low', '52_week_low', 'low_52w'):
            extrema.append({'current_pointer': f'/slim/levels/supports/{i}', 'observation': deepcopy(row)})
    result = {
        'option_wall_contract': (
            'For this support_resistances producer, TOP wall OI/gamma sum across sampled expirations '
            'at a strike; expiration labels the largest gamma contributor, NOT the expiry of the '
            'whole aggregate. A label switch proves neither a roll nor loss of later-dated backing. '
            'options.expirations totals are not per-strike evidence. Per-expiry strike breakdown is '
            'not supplied by these rows; do not invent it or score its absence as lost backing.'),
        'wall_observations': walls,
        'rolling_extrema_contract': (
            'A rolling Donchian/annual low or high is a changing measurement, not automatically a '
            'new defended zone or proof the old zone failed. testing_now/first test is not a '
            'completed defense. Justify changed decision/role independently before relocating '
            'or re-scoring; no automatic retain, break rule, percent band or required candle count.'),
        'support_extrema': extrema,
    }
    if context.get('routing_revision', 1) >= 31:
        result['option_wall_contract'] = (
            'TOP wall OI/gamma sum eligible contracts across sampled expirations at a strike. '
            'expiration labels the largest gamma contributor, NOT exclusive expiry. '
            'option_details, when supplied, contains the exact sampled expirations and '
            'parsed contract quotes/contributions; absence in legacy records is UNKNOWN. '
            'A dominant-label switch is neither a roll nor proof of lost backing. '
            'Use actual contributions, not whole-expiry totals, to assess persistence. '
            'Sampled coverage excludes other expirations and unparsed contracts. '
            'Missing/zero/crossed or undated quotes do not establish executable liquidity. '
            'New detail changes observability, not necessarily backing; no automatic scores.')
    if context.get('routing_revision', 1) >= 39:
        result['option_origin_contract'] = (
            'levels.option_origins observes exact option identities cited by CURRENT '
            'active buying zones, independently of the TOP ranking. Same sampled '
            'expirations/chain responses, not a complete market census. available '
            'means a contract was observed, not a viable/strong buying support. '
            'not_observed is scoped to the sample; zero OI is an observed numeric '
            'value, unavailable/missing metrics are unknown. Inspect per-expiry '
            'contracts: directed OI includes observed contracts even without usable '
            'gamma, whereas TOP sums only gamma-eligible contracts. Compare the '
            'same measurement basis; do not infer disappearance, liquidity, current backing '
            'or new market change from coverage/metadata alone.')
    return result
