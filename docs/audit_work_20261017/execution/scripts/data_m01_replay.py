import json, pathlib, collections, hashlib, copy
root=pathlib.Path.cwd()
paths=sorted((root/'logs/batch/2026-10-16/15-58-24/adaptive').glob('*/input.json'))
rows=[]
removed=collections.Counter()
for path in paths:
    context=json.loads(path.read_text(encoding='utf8'))
    slim=context['slim']; trend=slim.get('trend_1_2w') or {}; options=slim.get('options') or {}
    rule_codes=[r['code'] for r in trend.get('rules_triggered') or []]
    obsolete={'GAMMA_REGIME_POS','GAMMA_REGIME_NEG','CALLWALL_NEAR_POS_GAMMA','IV_RICH_GT_1_8','IV_CHEAP_LT_1_0','EM2W_ATR_GT_1_6','EM2W_ATR_LT_1_0','PUTWALL_NEAR'}
    contributions=[r for r in trend.get('rules_triggered') or [] if r['code'] in obsolete]
    removed.update(r['code'] for r in contributions)
    levels=slim.get('levels') or {}
    puts=levels.get('put_walls_top') or []
    touches=sum('prob_touch_1w_pct' in row for group in levels.values() if isinstance(group,list) for row in group if isinstance(row,dict))
    strengths=sum('strength_score' in row for group in levels.values() if isinstance(group,list) for row in group if isinstance(row,dict))
    distances=[row.get('distance_pct',row.get('distance')) for row in puts]
    rows.append({'symbol':slim.get('symbol',path.parent.name),'source':str(path.relative_to(root)),
      'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'as_of':slim.get('as_of'),
      'legacy_bias':trend.get('bias'),'legacy_confidence':trend.get('confidence'),
      'legacy_scores':trend.get('scores'), 'legacy_rule_contribution_sum':sum(r.get('side',0)*r.get('weight',0) for r in contributions),
      'removed_rules':contributions,'touch_fields_removed':touches,'strength_fields_removed':strengths,
      'put_distances_pct':distances,'below_or_at_quote_puts':sum(x is not None and x<=0 for x in distances),
      'gamma_regime':options.get('gamma_regime'), 'iv_to_rv_ratio':options.get('iv_to_rv_ratio'),
      'new_auxiliary_bias':None,'new_auxiliary_confidence':None})
summary={'case_count':len(rows),'with_legacy_trend':sum(r['legacy_bias'] is not None for r in rows),
  'touch_fields_removed':sum(r['touch_fields_removed'] for r in rows),
  'strength_fields_removed':sum(r['strength_fields_removed'] for r in rows),
  'removed_rule_counts':dict(removed),
  'false_lower_put_cases':[r['symbol'] for r in rows if not any(d is not None and -3<=d<=0 for d in r['put_distances_pct']) and any(t['code']=='PUTWALL_NEAR' for t in r['removed_rules'])],
  'method':'Descriptive replay of original frozen observations, without labeling them source40. Source40 emits no auxiliary direction or confidence; no return or financial-rubric effect inferred.'}
out={'summary':summary,'cases':rows}
(root/'.tmp/audit_execution_20261017/data_m01_descriptive_replay.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(summary,indent=2))
