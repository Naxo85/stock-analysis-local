"""Lossless, policy-selected references for deterministic difference values.

Only the model transport copy is compacted. Original authority stays complete.
"""
from copy import deepcopy

VERSION = 'pointer-diff-v1'
FIELD = '_context_transport'
INSTRUCTIONS = '''
POINTER DIFF TRANSPORT v1: In comparison.deterministic.since_current and
since_full_sol, rows of changes and capture_only_changes omit previous/current
copies. For each side, *_present=false means the field was absent (not zero or
unknown); otherwise read its COMPLETE value at *_pointer in the logical input,
resolving _context_aliases first. A present null remains null. Read old values
only from the dated reference/sol_reference and current values from slim.
These paths replace duplicate copies, not evidence. Keep chronology, source
identity, risks and materiality judgment; the comparison is not independent
backing. Do not infer an unchanged or harmless value from an omitted copy.
'''


def select_transport(view, policy):
    """Select from frozen policy, never from the model's response."""
    selected = policy.get('maintenance_context_transport')
    if selected is None:
        return False
    if selected != VERSION:
        raise ValueError('unsupported_maintenance_context_transport')
    # Legacy revision fixtures/policies cannot acquire a new transport by
    # inheriting a modern config option. Their frozen receipt semantics win.
    if policy.get('routing_revision', 41) < 41:
        return False
    view[FIELD] = VERSION
    return True


def _rows(context):
    delta = context.get('comparison', {}).get('deterministic', {})
    for group, old_root in (('since_current', '/reference/slim_snapshot/'),
                            ('since_full_sol', '/sol_reference/slim_snapshot/')):
        for field in ('changes', 'capture_only_changes'):
            for row in delta.get(group, {}).get(field, []):
                yield row, old_root


def _value(context, row, side, old_root):
    from src.local_runner.adaptive_context import resolve_evidence
    present = row.get(side + '_present')
    pointer = row.get(side + '_pointer')
    root = old_root if side == 'previous' else '/slim/'
    if type(present) is not bool or not isinstance(pointer, str) or not pointer.startswith(root):
        raise ValueError('invalid_diff_transport_reference')
    try:
        value = resolve_evidence(context, pointer)
    except ValueError as exc:
        if not present and str(exc).startswith('triage_evidence_path_missing:'):
            return None
        raise
    if not present:
        raise ValueError('diff_transport_presence_mismatch')
    return value


def compact_diffs(context):
    from src.local_runner.adaptive_context import compact_json
    result = deepcopy(context)
    for row, old_root in _rows(result):
        for side in ('previous', 'current'):
            value = _value(context, row, side, old_root)
            if side not in row or compact_json(row[side]) != compact_json(value):
                raise ValueError('diff_transport_value_mismatch')
            del row[side]
    return result


def restore_diffs(context):
    for row, old_root in _rows(context):
        for side in ('previous', 'current'):
            if side in row:
                raise ValueError('diff_transport_unexpected_value_copy')
            row[side] = deepcopy(_value(context, row, side, old_root))
    return context
