"""Measurement provenance, never a financial materiality verdict."""


def observations(context):
    from src.local_runner.semantic_sources import source_catalog
    catalog = source_catalog(context)
    prior = {}
    for handle, row in catalog.items():
        path = row['pointer'].split('/')
        if row['pointer'].startswith('/reference/slim_snapshot/levels/'):
            value = row['value']
            key = (path[4], value.get('level'), value.get('type'))
            prior.setdefault(key, []).append((handle, value))
    result = []
    for handle, row in catalog.items():
        if not row['pointer'].startswith('/slim/levels/'):
            continue
        value = row['value']
        matches = prior.get((row['pointer'].split('/')[3], value.get('level'), value.get('type')), [])
        if len(matches) != 1:
            continue  # No nearest-price, family mixing or ambiguous identity.
        previous_handle, previous = matches[0]
        a = (previous.get('evidence') or {}).get('historical_reaction') or {}
        b = (value.get('evidence') or {}).get('historical_reaction') or {}
        if a.get('status') != 'available' or b.get('status') != 'available':
            continue
        x, y = a.get('measurement_basis') or {}, b.get('measurement_basis') or {}
        required = ('calibration', 'history_sha256', 'parameters_sha256')
        if not all(x.get(k) and y.get(k) for k in required):
            kind = 'legacy_basis_not_comparable'
        elif x['calibration'] != y['calibration']:
            kind = 'measurement_method_changed'
        elif x['history_sha256'] != y['history_sha256']:
            kind = 'completed_history_changed'
        elif x['parameters_sha256'] != y['parameters_sha256']:
            kind = 'same_history_recalibrated'
        else:
            kind = 'same_history_same_measurement'
        changed = sorted(k for k in set(a) | set(b)
                         if k != 'measurement_basis' and a.get(k) != b.get(k))
        result.append({'current_source': handle, 'previous_source': previous_handle,
                       'classification': kind, 'changed_fields': changed})
    return {'comparisons': result,
            'scope': 'Measurement provenance only. Changed statistics are not proof of a new '
                     'failed defense. Completed history can change through matured windows, '
                     'rolling history or corrected bars. Legacy bases are not directly '
                     'comparable. Genuine prior errors and material risk still require review.'}
