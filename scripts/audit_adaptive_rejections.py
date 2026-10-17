"""Read-only replay diagnostics; never calls models, stages or uploads."""
import argparse
import difflib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_budget import read_json
from src.local_runner.adaptive_maintenance import apply_update
from src.local_runner.adaptive_policy import maintenance_precheck
from src.local_runner.adaptive_news_research import attach_news_research
from src.common.analysis_validator import validate_markdown


def replay(work, name, routing_revision=None):
    original = (work / name).read_bytes()
    raw = read_json(work / 'input.json')
    original_revision = raw.get('routing_revision', 1)
    if routing_revision is not None:
        raw['routing_revision'] = routing_revision  # Evaluation copy ONLY.
    for kind in ('triage', 'triage_repair'):
        response = work / (kind + '.response')
        if response.exists():
            attach_news_research(raw, work, kind, read_json(work / (kind + '.receipt.json')),
                                 json.loads(response.read_text(encoding='utf-8')))
        if name == kind + '.response':
            break
    context = model_context(raw)
    context.update(maintenance_precheck(context['reference'], context['slim'],
        context.get('sol_reference') or context['reference'], owned=context.get('owned', False)))
    value = json.loads(original)
    result = {'ticker': work.name, 'receipt': name, 'decision': value['decision'],
              'original_revision': original_revision, 'evaluated_revision': context.get('routing_revision', 1)}
    if value['decision'] != 'update':
        result['reason'] = value['reason']
        return result
    try:
        audit = []
        if context.get('routing_revision', 1) >= 9:
            from src.local_runner.semantic_report import maintenance_document, validation_result
            validated = validation_result(maintenance_document(value, context))
        else:
            candidate = apply_update(value, context, audit=audit)
            validated = validate_markdown(candidate, authoritative_context=validation_context(context),
                require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        result.update(ok=validated.ok, errors=list(validated.errors), normalizations=audit)
    except ValueError as exc:
        result['error'] = str(exc)
        result['validation_details'] = getattr(exc, 'maintenance_details', None)
        frame = exc.__traceback__
        while frame:
            local = frame.tb_frame.f_locals
            if frame.tb_frame.f_code.co_name == '_refresh_wall_facts':
                mention = local.get('mention')
                result['wall_diagnostic'] = {
                    'available_sources': [dict(side=x['side'], level=x['level'], expiry=str(x['expiry']), pointer=x['pointer']) for x in local.get('current_records', [])],
                    'label': local.get('label'), 'line': local.get('plain'),
                    'mention': mention.group(0) if mention else None,
                    'segment': local.get('segment'), 'expiry': str(local.get('expiry')),
                    'matching_sources': [dict(side=x['side'], level=x['level'], expiry=str(x['expiry']),
                        pointer=x['pointer'], metrics={k: x['item'].get(k) for k in ('oi','oi_share_pct','gamma_share_pct','gamma_usd_millions')})
                        for x in local.get('current', [])],
                }
            if (frame.tb_frame.f_code.co_name == 'apply_update'
                    and isinstance(local.get('before'), str)):
                before, baseline = local['before'], local['baseline']
                lines = baseline.splitlines()
                nearest = difflib.get_close_matches(before, lines, n=2, cutoff=0)
                result['edit_diagnostic'] = {'before': before, 'after': local['after'],
                    'occurrences': baseline.count(before), 'nearest_lines': nearest}
            frame = frame.tb_next
    if (work / name).read_bytes() != original:
        raise RuntimeError('replay_changed_receipt')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-dir', type=Path, required=True)
    parser.add_argument('--evaluate-routing-revision', type=int, choices=(8,),
                        help='Evaluate new policy on an in-memory copy; never migrate a checkpoint/receipt')
    parser.add_argument('tickers', nargs='+')
    args = parser.parse_args()
    for ticker in args.tickers:
        work = args.batch_dir / 'adaptive' / ticker
        for name in ('triage.response', 'triage_repair.response'):
            if (work / name).exists():
                print(json.dumps(replay(work, name, args.evaluate_routing_revision), ensure_ascii=False))


if __name__ == '__main__':
    main()
