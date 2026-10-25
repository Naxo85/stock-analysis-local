"""Create new revision41 prompt files; never modify frozen prompt sources."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / 'prompts'

def replace_once(text, before, after):
    assert text.count(before) == 1, (before, text.count(before))
    return text.replace(before, after, 1)

knowledge = '''

REVISION41 — MATERIAL KNOWLEDGE UPDATES, SAME FINANCIAL RUBRIC
This clarification applies to full, maintenance and the existing directed repair.
Distinguish an observed market change, a demonstrated past error, and materially
improved present knowledge. New applicable evidence can change the CURRENT
judgment even when the old capture cannot establish when that backing appeared.
An earlier score based on unobserved evidence may have been reasonable then;
correctly updating today's judgment does not require accusing it of prior_error
or inventing new contracts, flows, defenses or a comparable historical OI delta.

Use the existing material_improvement basis for a justified knowledge update to
the SAME support/component. Internally identify: the exact dated CURRENT judgment
and its relevant evidence limitation; the verified current observation that is
newly informative; why it applies to this zone and affected rubric subcriteria;
and why incorporating it materially changes the judgment rather than merely
completing data or describing a new quote. Cite CURRENT and current live sources.
The justification can support an increase or decrease, but measurement changes,
unknown coverage and TOP-list absence alone prove neither new backing nor loss.
Do not relabel an unsupported proposal to pass the contract.

Read CURRENT, latest_published_review and the supplied dated observations before
claiming novelty. Distinguish information supplied, reviewed and incorporated in
the score: a previous mention is not another independent confirmation, and a
previous retain is not a permanent veto on revisiting an unresolved limitation.
If evidence has already been incorporated, do not award or deduct its contribution
again; repeated snapshots, the same contract seen in another lane, changed rank,
or a changed dominant-expiry label are not additional evidence. If the latest
review considered it but retained, explain concretely why that judgment now needs
change. If this cannot be established, preserve the dated valid judgment.

Assess present buying viability before scoring. Observed OI, a coordinate, a new
source lane or new coverage is not buying defense, causal dealer flow or a score.
Assess applicability, concentration versus neighbors, actual expiry contributions,
quote quality and independent backing under the existing rubric. Missing old
coverage does not invalidate new evidence; missing essential current evidence
still cannot be invented. A knowledge update is not automatically reader-relevant
and does not require a public note, score uplift, lower score, replacement zone,
extra research, extra model call, new repair or escalation.

Keep the exact range of the same valid support and the unaffected components,
financial fields and dated text. Explain each actually affected component without
compensating across them. Updating knowledge about one support does not itself
authorize moving/promoting it or replacing another still-valid support; those
decisions retain their own materiality, live origin and viability requirements.
Use the existing structured block, source and change_review fields; no new output
field or prose validator. The published state records the incorporated evidence
through the ordinary runner-owned audit, dates and review memory. Preserve full
anchor, ITV, thesis authority, ownership, real risk and all integrity checks.

Apply STRENGTH EVIDENCE41 to distinguish component-specific consequences. The
25+20+25+15+15 weights, Options maximum25, existing financial category guards,
visibility65 and solid70 remain unchanged. None is a scoring target. This policy
does not establish prior_error, force a rescore or guarantee more visible zones.
'''

def build_adaptive(old):
    text=replace_once(old,'REVISION40 — explicit publication edits, partial text maintenance and dated evidence.','REVISION41 — explicit publication edits, partial text maintenance and dated evidence.')
    text=replace_once(text,'This consolidated policy replaces revision35 for BOTH models on new preparations.','This consolidated policy replaces revision40 for BOTH models on new preparations.')
    text=replace_once(text,'Inherited valid scores need not be recomputed just because a new snapshot exists.','Inherited valid scores need not be recomputed just because a new snapshot exists.\nA material knowledge update follows REVISION41 below; unchanged evidence and mere\nrecalibration are not such an update.')
    return text.rstrip()+knowledge+'\n'

def build_daily(old):
    text=replace_once(old,'Daily maintenance, revision40.','Daily maintenance, revision41.')
    text=replace_once(text,'The shared revision40 contract below defines partial text edits and note objects.','The shared revision41 contract below defines partial text edits and note objects.')
    text=replace_once(text,'backing_changed, demonstrated prior_error, material_improvement MAY justify edits.','backing_changed, demonstrated prior_error, material_improvement MAY justify edits.\nmaterial_improvement also permits a material knowledge update for the SAME\nsupport/component: applicable current evidence may resolve a dated observation\nlimitation without proving new market backing or a past error. Explain the prior\nlimitation, the newly informative current fact, its rubric relevance and material\nconsequence; follow the shared REVISION41 memory and non-duplication rules.')
    text=replace_once(text,'No subjective rescoring of identical evidence. Keep exact ranges for the SAME','No subjective rescoring of identical or already incorporated evidence. Newly\napplicable evidence is not identical merely because the market-change date is\nunknown; do not mistake missing past coverage for proof of unchanged knowledge.\nKeep exact ranges for the SAME')
    text=replace_once(text,'Recalculate only affected components/Setup if the backing/decision truly changed,\nusing the full rubric; never strength/100 -> Setup/10.','Recalculate only affected components/Setup if the backing/decision truly changed\nor a justified material knowledge update changes the CURRENT judgment, using the\nfull rubric; never strength/100 -> Setup/10.')
    return text

def build_financial(old):
    text=replace_once(old,'Solo cambia por error/invalidez demostrada o mejora MATERIAL de operatividad/riesgo/defendibilidad de un origen distinto; justifica internamente por qué conservar lo anterior no basta.','Sustituir un soporte exige error/invalidez demostrada o mejora MATERIAL de operatividad/riesgo/defendibilidad de un origen distinto; justifica internamente por qué conservar lo anterior no basta. Actualizar componentes del MISMO soporte también puede responder a evidencia nueva aplicable que cambie materialmente el conocimiento actual, según CONOCIMIENTO41; eso no autoriza mover su rango ni exige inventar un cambio del mercado o error pasado.')
    text=replace_once(text,'Medición desplazada del mismo origen, ranking o preferencia marginal no justifican sustituir ni repuntuar.','Medición desplazada del mismo origen, ranking o preferencia marginal no justifican sustituir ni repuntuar. Distingue esos casos de nueva evidencia aplicable que resuelva una carencia relevante del juicio actual bajo CONOCIMIENTO41.')
    text=replace_once(text,'FUENTES DEL CONTRATO13:','FUENTES DEL CONTRATO14:')
    text=replace_once(text,'Los contratos<=39 conservan su schema exacto.','Los contratos<=40 conservan su schema exacto.')
    text += '''

CONOCIMIENTO41 — evidencia nueva aplicable, continuidad y componentes
Separa cambio observado del mercado, error anterior demostrado y actualización
material del conocimiento. Un cero o una nota baja por evidencia antes no
observada pueden revisarse cuando una observación vigente y aplicable cambia el
juicio actual. No hace falta demostrar que los contratos o el soporte nacieron
después, ni acusar de error un juicio que era razonable con su información fechada.
Esto no concede puntos por aparecer en TOP, ampliar cobertura o tener OI positivo.

En el mismo soporte explica internamente qué carencia del juicio CURRENT resuelve
el dato, qué información aporta frente a CURRENT/última revisión, por qué aplica al
rango y a cada subcriterio afectado, y qué consecuencia material tiene. En
mantenimiento usa material_improvement con CURRENT y evidencia actual exacta;
no fabriques backing_changed o prior_error para habilitar la edición. Evalúa la
información favorable y adversa con la misma regla, sin inferir pérdida de respaldo
de cobertura desconocida, ranking o ausencia de lista.

Lo suministrado, revisado e incorporado no es lo mismo. Una mención previa que no
cambió la nota no hace que el dato sea una confirmación adicional, pero tampoco
impide revisar justificadamente una limitación pendiente. Si la última revisión
lo valoró y retuvo, explica por qué ese juicio requiere cambio; no vuelvas a sumar
ni restar lo ya incorporado. Otra captura o vencimiento dominante distinto no son
nuevas aperturas, demanda compradora ni una segunda familia independiente.

La revisión de conocimiento mantiene el rango exacto y los componentes no
afectados; no autoriza por sí sola promover, sustituir o mover una zona válida.
Aplica vigencia antes de puntuar, toda la rúbrica y STRENGTH EVIDENCE41. Opciones
conserva25 puntos y los pesos completos son25+20+25+15+15; visibilidad65/sólido70
no son objetivos de puntuación. No fuerces subidas, bajadas, casillas, notas públicas,
investigación, llamadas, reparaciones ni escaladas por esta política. Mantén los
riesgos, autoridad, fuentes, integridad, ancla y fechas; sólo full reinicia ITV.
'''
    return text

sources={
    'adaptive_revision40.md':('adaptive_revision41.md',build_adaptive),
    'daily_maintenance_semantic_v40.md':('daily_maintenance_semantic_v41.md',build_daily),
    'stock_analysis_semantic_v13.md':('stock_analysis_semantic_v14.md',build_financial),
}
hashes={}
for name,(target,transform) in sources.items():
    src=PROMPTS/name
    original=src.read_bytes();hashes[name]=hashlib.sha256(original).hexdigest()
    result=transform(original.decode('utf-8-sig'))
    if len(sys.argv)>1 and sys.argv[1]=='--verify':
        actual=(PROMPTS/target).read_text(encoding='utf-8-sig')
        assert actual.rstrip()==result.rstrip(),target
        print(target,hashlib.sha256((PROMPTS/target).read_bytes()).hexdigest(),'MATCH')
        continue
    if len(sys.argv)>1 and sys.argv[1]=='--emit':
        if len(sys.argv)>2 and sys.argv[2]==target:
            sys.stdout.reconfigure(encoding='utf-8')
            print(json.dumps({'target':target,'content':result},ensure_ascii=False))
        continue
    with (PROMPTS/target).open('x',encoding='utf-8',newline='\n') as stream:stream.write(result)
for name,sha in hashes.items():
    assert hashlib.sha256((PROMPTS/name).read_bytes()).hexdigest()==sha
    if len(sys.argv)<2 or sys.argv[1]=='--verify':print(name,sha,'UNCHANGED')
