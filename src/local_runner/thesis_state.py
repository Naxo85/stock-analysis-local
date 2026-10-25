"""Evidence-bound thesis status for new full reports; no score or trading rule."""
from copy import deepcopy
from urllib.parse import urlsplit

STATUSES = ('vigente', 'deteriorada', 'rota', 'no_determinable')


def schema():
    from src.local_runner.semantic_report import obj, nullable
    return nullable(obj({'status': {'type': 'string', 'enum': list(STATUSES)},
                         'premise': {'type': 'string'}, 'assessment': {'type': 'string'},
                         'evidence': {'type': 'array', 'items': obj({
                             'source': {'type': 'string'}, 'observation': {'type': 'string'}})}}))


def establish(value, context):
    """Validate identity/shape, not the truth or materiality of the model's judgment.

    Public links are disclosed references, not proof their bodies were retrieved.
    Supplied pointers resolve against the bound context, including authenticated
    historical report authority. Sources stay in the audit, never a prose dump.
    """
    if value is None:
        return None  # No assessment; never infer a healthy state from absence.
    from src.local_runner.semantic_report import digest
    from src.local_runner.semantic_sources import resolve_source
    result = deepcopy(value)
    def reject(detail):
        raise ValueError('update_not_allowed_thesis_state: ' + detail)
    if value.get('status') not in STATUSES:
        reject('unknown_status')
    if any(not value.get(key, '').strip() for key in ('premise', 'assessment')):
        reject('missing_premise_or_assessment')
    if not value.get('evidence'):
        reject('missing_evidence')
    audit = []
    for row in value['evidence']:
        source = row['source']
        if not row['observation'].strip():
            reject('missing_observation')
        if source.startswith('/'):
            allowed = ('/slim', '/news', '/analyst_actions', '/reference', '/sol_reference')
            if not any(source == prefix or source.startswith(prefix + '/') for prefix in allowed):
                reject('unsupported_source_pointer')
            try:
                resolved = resolve_source(context, source)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise ValueError('update_not_allowed_thesis_state: unresolved_source_pointer') from exc
            audit.append({'source': source, 'kind': 'supplied_observation', 'value_sha256': digest(resolved)})
        else:
            try:
                url = urlsplit(source)
                valid = (url.scheme == 'https' and url.hostname and not url.username and
                         not url.password and not any(c.isspace() for c in source))
            except ValueError:
                valid = False
            if not valid:
                reject('invalid_public_source_url')
            audit.append({'source': source, 'kind': 'public_reference_not_independently_verified'})
    result['assessed_at'] = context['slim']['as_of']
    result['evidence_audit'] = audit
    return result
