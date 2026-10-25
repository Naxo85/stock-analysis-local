import json
from pathlib import Path
root=Path(__file__).resolve().parent
v=json.loads((root/'variants.json').read_text(encoding='utf-8'))
i=json.loads((root/'inventory.json').read_text(encoding='utf-8'))
r=json.loads((root/'rollup.json').read_text(encoding='utf-8'))
c=json.loads((root/'cache_layout.json').read_text(encoding='utf-8'))
n=v['cases'];wire=v['totals']['wire'];prefix=n*v['prefix_chars'];schema=n*v['schema_chars']
denom=wire+prefix+schema
groups=r['model_calls'];credit=sum(g['credit_proxy'] for g in groups.values())
out={'cases':n,'units':'chars unless explicitly recorded tokens or credit proxy',
     'visible_input_chars':denom,'average_visible_input_chars':denom/n,
     'visible_mix_pct':{'json':wire/denom*100,'instructions':prefix/denom*100,'output_schema':schema/denom*100},
     'json_sections_pct':{k:value/wire*100 for k,value in i['sections'].items()},
     'lossless_prototypes':{
         'snapshot_patch':{'json_reduction_pct':(wire-v['totals']['snapshot_patch'])/wire*100,
                           'complete_visible_reduction_pct':(wire-v['totals']['snapshot_patch'])/denom*100},
         'alias_single_target':{'json_reduction_pct':(wire-v['totals']['alias_single_target'])/wire*100,
                           'complete_visible_reduction_pct':(wire-v['totals']['alias_single_target'])/denom*100},
         'schema_defs':{'schema_reduction_pct':(v['schema_chars']-v['factored_schema_chars'])/v['schema_chars']*100,
                       'complete_visible_reduction_pct':n*(v['schema_chars']-v['factored_schema_chars'])/denom*100},
         'combined':{'json_reduction_pct':(wire-v['totals']['combined_snapshot_alias'])/wire*100,
                     'complete_visible_reduction_pct':(denom-v['totals']['combined_snapshot_alias']-prefix-n*v['factored_schema_chars'])/denom*100}},
     'cache_layout':{'matched_pairs':c['matched_pairs'],'unchanged_anchors':c['totals']['same_anchor'],
         'average_original_prefix_chars':c['totals']['original_prefix']/c['matched_pairs'],
         'average_ordered_prefix_chars':c['totals']['ordered_prefix']/c['matched_pairs'],
         'data_size_increase_pct':(c['totals']['ordered_wire']/c['totals']['original_wire']-1)*100,
         'stable_prefix_fraction_of_user_json_pct':c['totals']['ordered_prefix']/c['totals']['ordered_wire']*100},
     'credit_proxy_total':credit,'credit_proxy_shares_pct':{k:g['credit_proxy']/credit*100 for k,g in groups.items()},
     'four_contract_fulls_credit_proxy':r['four_contract_fulls']['credit_proxy'],
     'four_contract_fulls_share_credit_proxy_pct':r['four_contract_fulls']['credit_proxy']/credit*100,
     'limits':'No model calls; no tokenization-compatible offline library found. Character ratios are NOT token ratios, quality equivalence or included-weekly-allowance conversion. Credit proxy excludes unknown timeout usage.'}
(root/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True,indent=2))
