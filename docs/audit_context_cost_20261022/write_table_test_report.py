"""Summarize completed model receipts; never launch or repeat a call."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
reading=ROOT/'logs/table_reading_test/20261022T144755704687'
maintenance=ROOT/'logs/table_maintenance_test/20261022T145022489730'
a=json.loads((reading/'results.json').read_text(encoding='utf-8'))
b=json.loads((maintenance/'results.json').read_text(encoding='utf-8'))
assert len(a)==8 and len(b)==4
assert all(r['model']=='gpt-6-luna' and r['effort']=='high' and not r['research_enabled'] for r in a+b)
for ticker in ['LEU','TSLA']:
 hashes=json.loads((maintenance/ticker/'source_hashes.json').read_text(encoding='utf-8'))
 original=ROOT/f'logs/batch/2026-10-21/06-52-46/adaptive/{ticker}'
 for name,digest in hashes.items():assert hashlib.sha256((original/name).read_bytes()).hexdigest()==digest

def totals(rows,encoding):
 selected=[r for r in rows if r['encoding']==encoding]
 return {k:sum(r['usage'].get(k,0) for r in selected) for k in ['input_tokens','cached_input_tokens','uncached_input_tokens','output_tokens','reasoning_output_tokens']}

inputs={encoding:totals(b,encoding)['input_tokens'] for encoding in ['original','tabular']}
reduction=100*(1-inputs['tabular']/inputs['original'])
lines=['# Prueba real de tablas —22Oct2026','',
 'Autorizada por el usuario.12 llamadas:8 de lectura y4 de mantenimiento histórico,',
 'todas GPT-6 Luna high con la sesión ChatGPT existente. Sin web, reparaciones,',
 'fallback, informes full ni publicación. No se activan tablas en producción.','',
 '## Lectura verificable','',
 f"{sum(r['passed'] for r in a)}/8 llamadas aprobadas; {sum(r['questions'] for r in a)} comprobaciones exactas.",
 'Cuatro escenarios: vencimientos, cero/null/ausencia, identidad con filas reordenadas,',
 'y CURRENT/ancla/observación actual.77 preguntas por formato; no154 hechos independientes.',
 'Los registros proceden de LEU21Oct. El caso cero/null/ausencia contiene modificaciones',
 'controladas declaradas, no nuevas observaciones de mercado. Respuestas esperadas',
 'congeladas antes de las llamadas, cotejadas por código contra sus valores completos.','',
 '## Mantenimiento con contexto completo','',
 '| Ticker | Original | Tablas | Entrada original | Entrada tablas | Reducción entrada |',
 '|---|---|---|---:|---:|---:|']
for ticker in ['LEU','TSLA']:
 old=next(r for r in b if r['ticker']==ticker and r['encoding']=='original')
 new=next(r for r in b if r['ticker']==ticker and r['encoding']=='tabular')
 pct=100*(1-new['usage']['input_tokens']/old['usage']['input_tokens'])
 lines.append(f"| {ticker} | {old['decision']} | {new['decision']} | {old['usage']['input_tokens']:,} | {new['usage']['input_tokens']:,} | {pct:.2f}% |")
lines.extend(['',f"{sum(r['validated'] for r in b)}/4 respuestas pasan los controles ejercitados.",
 f"Entrada acumulada: {inputs['original']:,} original frente a {inputs['tabular']:,} tablas: **{reduction:.2f}% menos tokens de entrada**.",
 'Mismo schema e instrucciones (incluido el decoder tabular) en ambos formatos, orden',
 'alternado y workspaces independientes. Baseline usa el transporte por referencias',
 'ya activado. Los inputs originales y recibos del lote se conservaron por hash.','',
 'Los controles abarcan schema, binding al input real, decisión/autoridad y cobertura',
 'de agenda cuando corresponde. Retain no se convierte en un documento actualizado;',
 'escalate no genera full. No se ha ejercitado actualización de rangos/puntuaciones',
 'ni reparación de una actualización en esta muestra. No atribuir calidad financiera',
 'general ni causalidad al formato a partir de dos casos y una ejecución por variante.','',
 '## Revisión del contenido y decisión de adopción','',
 'Las decisiones y los cuatro flags de riesgo coinciden en las dos parejas.',
 'En LEU ambos conservan las compras ausentes y tratan la discrepancia del objetivo',
 'de Needham como dato no utilizable. El original propone una selección editorial',
 'de catalizadores y la variante tabular hereda la anterior; no son salidas idénticas.',
 'En TSLA ambos escalan por la misma novedad corporativa pendiente de investigación.',
 'Sin embargo, la variante tabular agrupa n1–n9 como critical_change: n1 y n2 sólo',
 'aportan titulares de resultados de SpaceX y n3 una lista de valores; no contienen',
 'el hecho de los comités suministrado en n4–n9. Ninguno de esos tres registros',
 'incluye cuerpo de artículo. El formato original los separa de los titulares',
 'críticos. Esta asociación excesiva está en auditoría interna y no cambia la ruta,',
 'pero es un límite de calidad que el schema/coverage no detecta. No se crea por',
 'ello un gate de prosa, reparación pagada o escalado adicional en producción.',
 'Una ejecución por variante no permite atribuir causalmente la diferencia a las tablas.',
 '**No activar tablas todavía.** La prueba de lectura pasa; el contraste de juicio',
 'es limitado y contiene esta discrepancia. El ahorro observado es moderado y',
 'no justifica afirmar equivalencia general, especialmente sin casos update/repair.','',
 '## Consumo y límites','',
 '| Fase/formato | Entrada | Caché incluida | Salida | Razonamiento incluido en salida |',
 '|---|---:|---:|---:|---:|'])
for phase,rows in [('Lectura',a),('Mantenimiento',b)]:
 for encoding in ['original','tabular']:
  t=totals(rows,encoding)
  lines.append(f"| {phase}/{encoding} | {t['input_tokens']:,} | {t['cached_input_tokens']:,} | {t['output_tokens']:,} | {t['reasoning_output_tokens']:,} |")
for phase,folder in [('Lectura',reading),('Mantenimiento',maintenance)]:
 before=json.loads((folder/'quota_before.json').read_text(encoding='utf-8'))
 after=json.loads((folder/'quota_after.json').read_text(encoding='utf-8'))
 lines.extend(['',f"{phase}: contador semanal usado {before['primary']['used_percent']}%→{after['primary']['used_percent']}%."])
lines.extend(['',
 'El contador es redondeado, puede actualizarse con retraso y se comparte con otras',
 'actividades; no demuestra consumo cero ni permite atribuir un coste exacto a la prueba.',
 'Diferencias de caché, salida y razonamiento impiden trasladar el porcentaje de',
 'reducción de entrada directamente a ahorro semanal. No se ejecutan llamadas extra',
 'para igualar caché o medir cuotas.','',
 '## Evidencia','',f'- Lectura: `{reading.relative_to(ROOT)}`.',
 f'- Mantenimiento: `{maintenance.relative_to(ROOT)}`.',
 '- Scripts: run_table_reading_test.py, run_table_maintenance_test.py.',
 '- Comparación agregada: table_test_summary.json.',
 '- Cada llamada conserva input, schema, instrucciones identificadas por hash,',
 '  eventos, respuesta y recibo de uso. Las respuestas de una variante no se',
 '  incluyen en el contexto de la otra.',''])
(HERE/'table_test_report.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'reading_passed':sum(r['passed'] for r in a),'checks':sum(r['questions'] for r in a),
                  'maintenance_validated':sum(r['validated'] for r in b),
                  'maintenance_input_reduction_pct':reduction,'input_tokens':sum(r['usage']['input_tokens'] for r in a+b),
                  'output_tokens':sum(r['usage']['output_tokens'] for r in a+b)}))
