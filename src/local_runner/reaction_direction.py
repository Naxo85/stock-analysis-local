"""Direction of measured reactions, not the current market role of a zone."""


def reaction_direction(value, pointer=''):
    reaction = (value.get('evidence') or {}).get('historical_reaction') or {}
    method = reaction.get('method')
    # This producer measures upward rebounds. A broken support, a put/call
    # overlap or a quote above/below it cannot turn those into supply rejections.
    if method == 'daily_level_tests_collapsed_then_max_high_5_sessions':
        return 'support'
    if reaction.get('direction') in ('support', 'resistance'):
        return reaction['direction']
    # Legacy slim omitted method, but these two producer collections contained
    # only the same support-rebound measurement. Unknown methods stay unknown.
    if method is None and any('/levels/' + k + '/' in pointer for k in ('supports', 'put_walls_top')):
        return 'support'
    return None


def applicable_reaction(value, pointer, key):
    return reaction_direction(value, pointer) == ('resistance' if key == 'resistance' else 'support')
