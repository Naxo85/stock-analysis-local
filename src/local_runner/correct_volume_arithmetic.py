"""Explicit human arithmetic correction; normal publication guards, no model calls."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.local_runner import adaptive_stage as stage
from src.local_runner.analysis_state import _read_json_gcs, reference_uri
from src.local_runner.ownership import recorded_ownership
from src.local_runner.semantic_report import reference_document, render_document, publication_fields, validation_result
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.volume_arithmetic import calculate
from src.local_runner.review_memory import rebind_memory


def build(current, anchor, context, selector, now):
    """Pure builder: only the selected volume component can change financially."""
    doc = reference_document(current, verify_projection=True)
    old = deepcopy(doc)
    selected = source_catalog(context).get(selector)
    if not selected or not selected['pointer'].startswith('/slim/levels/'):
        raise RuntimeError('correction_requires_exact_current_record')
    record = selected['value']
    level = doc['plan']['entry']
    if not level['range'] or not level['strength']:
        raise RuntimeError('correction_requires_existing_entry')
    evidence = record.get('evidence') or {}
    audit = calculate(evidence.get('volume_profile') or {},
                      evidence.get('historical_reaction') or {},
                      level['range'], context['slim']['as_of'],
                      revision=context.get('routing_revision', 1))
    if audit is None:
        raise RuntimeError('correction_requires_complete_structured_evidence')
    before = level['strength']['components']['volumen']
    after = audit['expected']
    if before == after:
        raise RuntimeError('correction_already_applied')
    level['strength']['components']['volumen'] = after
    level['superseded_change_review'] = deepcopy(level.get('change_review'))
    level['change_review'] = dict(basis='prior_error', authority='explicit_user_arithmetic_correction',
        explanation='Mechanical verification of the existing frozen financial rubric.',
        source_pointer=selected['pointer'])
    level['volume_calculation_audit'] = audit
    check = deepcopy(doc); check['plan']['entry'] = deepcopy(old['plan']['entry'])
    assert check == old, 'correction_changed_unrelated_financial_content'
    validation = validation_result(doc)
    if not validation.ok:
        raise RuntimeError('correction_validation_failed: ' + '; '.join(validation.errors))
    md = 'Correccion aritmetica autorizada · ' + now.isoformat() + '. Captura y juicios fechados conservados.\n\n' + render_document(doc)
    fields = publication_fields(doc, md, current, now)
    payload = deepcopy(current)
    payload.update(fields)
    payload.update(analysis_markdown=md, generated_at=now.isoformat(), model='manual-arithmetic-correction',
        generation_model='manual-arithmetic-correction', generation_provider='manual',
        reasoning_effort=None, analysis_kind='daily_update', validation=validation.to_dict())
    payload['maintenance'] = dict(model='manual-arithmetic-correction', updated_at=now.isoformat(),
        base_report_sha256=stage.reference_key(current), corrections=[
            dict(field='plan.entry.strength.components.volumen', before=before, after=after)])
    review = dict(symbol=current['symbol'], strategy='authorized-arithmetic-correction',
        reviewed_at=now.isoformat(), market_data_at=context['slim']['as_of'],
        status='updated', analysis_status='ok', model_calls=[],
        effective_model='manual-arithmetic-correction', routing_revision=context['routing_revision'],
        base_report_sha256=stage.reference_key(current), sol_anchor_sha256=stage.reference_key(anchor),
        last_full_report_at=anchor['generated_at'])
    payload['daily_review'] = review
    payload['manual_correction'] = dict(authority='explicit_user_request', type='volume_arithmetic',
        applied_at=now.isoformat(), previous_report_at=current['generated_at'],
        source_pointer=selected['pointer'], calculation=audit, model_calls=0)
    payload['review_memory'] = rebind_memory(current, payload, anchor)
    reference_document(payload, verify_projection=True)
    return payload, review, md


def correct(repo, batch, symbol, selector, execute=False):
    original = batch / 'adaptive' / symbol
    frozen = {str(p.relative_to(original)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in original.rglob('*') if p.is_file()}
    context = stage.read_json(original / 'input.json')
    expected = stage.read_json(original / 'publish/output' / symbol / 'latest.json')
    current = _read_json_gcs('gs://' + stage.TEST_BUCKET + '/' + symbol + '/latest.json')
    anchor = _read_json_gcs(reference_uri(symbol))
    if not current or not anchor or stage.reference_key(current) != stage.reference_key(expected):
        raise RuntimeError('correction_rejected_changed_current_report')
    if (current.get('daily_review') or {}).get('reviewed_at') != expected['daily_review']['reviewed_at']:
        raise RuntimeError('correction_rejected_changed_current_review')
    if stage.reference_key(anchor) != expected.get('sol_anchor_sha256'):
        raise RuntimeError('correction_rejected_changed_sol_anchor')
    if current.get('slim_snapshot') != context['slim']:
        raise RuntimeError('correction_rejected_changed_capture')
    now = datetime.now(timezone.utc)
    payload, review, md = build(current, anchor, context, selector, now)
    work = repo / 'logs/corrections' / now.strftime('%Y%m%dT%H%M%S%f') / symbol
    destination = work / 'publish/output' / symbol
    destination.mkdir(parents=True)
    stage.write_json(work / 'input.json', context)
    stage.write_json(work / 'review.json', review)
    stage.write_json(destination / 'latest.json', payload)
    (destination / 'latest.md').write_text(md, encoding='utf-8')
    stage.one.write_analysis_html(md, destination / 'latest.html', symbol=symbol)
    audit = dict(symbol=symbol, status='validated', executed=False, model_calls=0,
                 source_batch=str(batch), original_sha256=frozen)
    if execute:
        owned, evidence = recorded_ownership(symbol)
        if owned is not context['owned']:
            raise RuntimeError('correction_rejected_ownership_changed')
        audit['ownership_check'] = evidence
        review = stage.publish(repo, work, symbol)
        audit.update(status='published', executed=True, published_at=review['published_at'])
    audit['original_unchanged'] = frozen == {str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in original.rglob('*') if p.is_file()}
    stage.write_json(work / 'correction.json', audit)
    return work, audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker');parser.add_argument('--batch-dir',type=Path,required=True)
    parser.add_argument('--source',required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    work,audit=correct(Path.cwd(),args.batch_dir.resolve(),args.ticker.upper(),args.source,args.execute)
    print(json.dumps(dict(work=str(work),**audit),ensure_ascii=False))
if __name__ == '__main__': main()
