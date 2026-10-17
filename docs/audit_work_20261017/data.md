# Auditoría independiente de adquisición, datos y fuentes — 17-10-2026

Ámbito: adquisición Tradier raw/slim, preparación del input, opciones dirigidas39, observaciones OHLCV/volumen, catálogo de fuentes y frontera IBKR noticias/analistas. Trabajo de solo lectura y ejecución offline; no hubo modelo, batch, descarga técnica viva, recuperación, publicación, despliegue ni cambio de código/configuración/prompts/tests/originales. Las pruebas sintéticas se ejecutaron en memoria mediante Python -B; el único archivo escrito por esta rama es este informe.

## Evidencia y límites

Se leyeron AGENTS.md y las secciones vigentes de handoff_current, pending_work_current, codex_adaptive_analysis y operations, sin adoptar sus conclusiones. Se inspeccionaron directamente código y originales:

- Los 46 inputs originales de logs/batch/2026-10-16/15-58-24/adaptive/*/input.json; APP fallido permanece revision38. También inputs/recibos/review de MU, CRWV e IBKR del 15-10/12-01-08 y OKLO del 14-10/11-43-17.
- Captura técnica logs/deploy_origins39/live-source.json (APP, 16-10 21:07:48 UTC) y fuentes de build archivadas raw-source/main.py y slim-source/main.py.
- 3.128 archivos .log directamente bajo news/analysts de logs/source_updates en octubre hasta el 16; no equivale a 3.128 análisis financieros únicos. No se escanearon otros subdirectorios ni septiembre para ese denominador.
- 71 tests y 5 subtests pasaron: python -B -m pytest -q -p no:cacheprovider test_option_origins_v39.py test_capture_routing_v23.py tests/test_support_resistances_slim_evidence.py. Hubo 124 warnings de datetime.utcnow; no fallos. Son pruebas offline, no validación de calidad financiera ni nuevo smoke vivo.
- Comparación AST independiente: _volume_20d_package, _tradier_options_chain, _extract_latest_price, _observe_option_origins y _complete_daily_bars de raw; _normalize_pct y _build_slim de slim coinciden con las fuentes archivadas del despliegue origins39. Eso vincula el diagnóstico a dichas fuentes; no es una consulta de tráfico cloud actual.

Prioridades: P1 afecta un control esencial o datos de decisión y debe corregirse pronto; P2 defecto relevante acotado; limitación describe alcance no validado. Confianza alta significa prueba reproducible y/o original directo, no certeza de perjuicio económico. No se infiere ninguna noticia omitida ni cambio de nota o rentabilidad sin evidencia.

## D1 — P1: un timeout real de noticias se convierte en cobertura reciente vacía y permite publicar

**Demostrado en producción archivada; confianza alta.** La librería instalada devuelve None tras timeout de 4 s en .venv/Lib/site-packages/ib_insync/ib.py:2142-2161. El adaptador src/local_runner/ibkr_analyst_probe.py:138-144 hace reqHistoricalNews(...) or [], borrando la distinción entre fallo y cero noticias. src/local_runner/ibkr_news_update.py:279-289 declara siempre status=ok, truncated=false y generated_at nuevo. data_ready comprueba ese estado y hora, no la terminación real del proveedor (src/local_runner/adaptive_stage.py:247-253).

Cadena original completa: logs/source_updates/2026-10-15/12-01-14/news/MU.log:4 dice headlines=0 persistido; línea6 registra reqHistoricalNewsAsync: Timeout. El summary de esa actualización marca news.status=ok. En logs/batch/2026-10-15/12-01-08/adaptive/MU/input.json:20164 la fuente ya congelada declara status=ok, count=0 y generated_at=2026-10-15T12:01:49.339093+00:00. Tiene recibo medium exitoso y review.json retained, analysis_status=ok, publicado12:04:37UTC. CRWV e IBKR de ese mismo lote tienen la misma cadena: CRWV retained12:05:04; IBKR updated12:04:47. Los tres recibos indican web_search_count=0. Esto prueba admisión y publicación con cobertura defectuosa; no prueba que hubiera una noticia material ni que la decisión fuese equivocada.

El barrido de3.128 logs encontró94 archivos con el timeout exacto:53news y41analysts. Muchos corresponden al04oct; otros alcanzan15oct. No son94 publicaciones ni94incidentes independientes. Los92 logs news/analysts del16oct no contienen Timeout/Error/Traceback: los feeds vacíos de ese día no deben imputarse al defecto.

La variante analistas también redatada está observada: logs/source_updates/2026-10-14/11-43-22/analysts/OKLO.log:1 timeout, línea2 Analyst ratings updated. src/local_runner/ibkr_analyst_update.py:103-117 aplica el payload y asigna as_of nuevo incondicionalmente. El input original OKLO14oct conserva analyst_actions.status=ok, count=0 y as_of11:57:12UTC (input.json:30914). El resumen heredado puede por tanto parecer revisado hoy aunque la consulta no terminó.

**Prueba independiente:** FakeIB.reqHistoricalNews devuelve None; invocar fetch_ibkr_analyst_headlines y _compact_payload produce status=ok,count=0,truncated=false,generated_at del día. No se abrió conexión. Control positivo: una respuesta terminada con lista vacía debe seguir siendo una observación vacía válida; una excepción de conexión ya se propaga y no es el defecto.

**Alternativa descartada:** que simplemente se reutilice last_good sin redatar. Los loaders normales preservan as_of (analyst_recent_actions.py:63-74; analyst_summary.py:46-61; ibkr_recent_news.py:13-39) y data_ready sí rechaza antigüedad del contenedor. El defecto es convertir un fallo específico en un éxito nuevo. La fecha fin de ventana solicitada tampoco acredita cobertura completada.

**Recomendación:** propagar terminación, error y timeout tipados del proveedor; no escribir latest ni avanzar as_of/last_update cuando no hay terminación exitosa. Conservar last_good con su fecha y mostrar fuente incompleta mediante la ruta premodelo existente. No añadir llamada financiera para remediar transporte.

**Aceptación:** timeout, error de suscripción y pérdida de conexión no se confunden con lista vacía; prueba con proveedor falso y replay de los logs citados impide admisión antes de modelo; una respuesta explícitamente terminada sin noticias pasa; no cambia ningún recibo histórico ni redatada financiera. Revisar si los intervalos posteriores fueron realmente recuperados, sin suponerlo ni reescribir originales.

## D2 — P1: volumen de sesión abierta etiquetado como último día completo

**Demostrado en46/46 inputs del16oct; confianza alta.** raw/main.py:2616-2679 promete usar20días completos, pero usa days[-20:] y days[-1] (2635-2655), sin _complete_daily_bars. Slim lo publica como technicals.volume_last_complete_day y volume_rel_20d (slim/main.py:150-151). En cambio price_history y reacciones sí excluyen el día UTC en curso (raw:1165-1194,1335,1435).

Ejemplo original APP16oct: input.json:37082 contiene date=2026-10-16, shares=932192, rel_to_20d=0.194, captura16:14:23UTC; price_history.last_session=2026-10-15 (36865). Los46inputs del lote capturados15:59–16:15UTC tienen el mismo desacoplamiento. No se está diciendo que price_history contenga una falsa barra cerrada: ese bloque conserva correctamente el15.

Además hay propagación determinista: _trend_bias_confidence_1_2w lee ese valor (raw:4111-4115), aplica <=0.9 => -5 o >=1.2 => +10 (4170-4172) y lo llama volume_rel_20d_last_close (4202). Recalculando exclusivamente con las20barras completas ya congeladas, cambia el componente D_volume_tape en42/46casos. AMAT: ratio parcial0.471 y score-5, ratio cerrado1.811 y score+10. MU:0.505/-5 frente1.435/+10. TSLA:1.064/0 frente0.787/-5. Es sensibilidad del indicador auxiliar, no recálculo autorizado de fortalezas financieras ni prueba de que el modelo siga ese indicador.

**Prueba independiente:**20barras previas de volumen1000 más barra de hoy100: _recent_price_history excluye hoy, pero _volume_20d_package devuelve hoy como last_complete_day y ratio0.105. Control: historia sin barra de hoy produce el último día cerrado habitual. La fuente archivada de origins39 conserva exactamente esta función.

**Recomendación:** una política temporal explícita por sesión para todos los campos llamados completed/last_close; mantener intradía separado y con su condición. La solución más pequeña es usar el mismo conjunto cerrado para esa métrica; evaluar aparte la política de cierre real frente al día UTC.

**Aceptación:** a igualdad de20barras cerradas, variar OHLCV de la sesión abierta no cambia last_complete_day, ratio ni D_volume_tape; replay de46capturas muestra fecha/ratio coherentes; después del cierre se incorpora la sesión según contrato explícito. No ajustar notas/rangos publicados automáticamente.

## D3 — P2: put walls por encima del precio generan falsa distancia inferior cero

**Demostrado en originales; confianza alta.** raw/main.py:4094 calcula downs, pero lo descarta. El bucle4098-4104 procesa todas las paredes y usa abs(min(0,d)), de modo que cualquier pared superior tiene distancia inferior0. PUTWALL_NEAR activa +5 cuando <=3 (4149-4151). La distancia originaria está bien firmada en _compute_top_putwalls_gamma:3898 y slim conserva el signo.

En6/46inputs16oct, la regla se activa aunque no hay ningún put TOP a<=3% por debajo: AUR, IONQ, LRCX, PLTR, QBTS, RKLB. PLTR es inequívoco: quote187.255; TOPputs190,192.5,195,197.5,200, todos por encima; trend_1_2w.features.nearest_put_wall_dist_pct=0 y regla PUTWALL_NEAR,+5. IONQ tiene put inferior29 a9.26% y superiores32–35; también devuelve0. No se declara que un strike superior sea una compra viable ni que el modelo haya usado ese +5.

**Prueba independiente adicional:** extrayendo la función real por AST: pared superior+10% => distancia0 y PUTWALL_NEAR+5; inferior-8% => distancia8 sin regla; inferior-2% => distancia2 con regla; mezcla+10/-8 => distancia0 y regla. Los controles del lado inferior funcionan, el fallo está en introducir el lado superior.

**Alternativa:** intención de medir cualquier pared cercana. El código, nombre y comentario especifican pared inferior, y una pared arbitrariamente lejana por arriba devuelve0; tampoco sería una distancia absoluta válida.

**Recomendación/aceptación:** filtrar lados antes de calcular distancia; todas las paredes superiores => inferior desconocida/ausente; inferior distante no activa cercanía; control inferior real2% sí activa. Conservar valores fuente y ranking. Reproducir seis originales para el indicador auxiliar sin repuntuar informes.

## D4 — P2: expected move de hasta1% se multiplica por100 otra vez

**Defecto reproducible; incidencia económica real no demostrada; confianza alta.** raw/main.py:794-822 ya convierte la fracción del straddle a porcentaje. Slim/main.py:162 aplica _normalize_pct, cuya heurística abs(v)<=1 => v*100 está en578-591. Resultado:0.75% =>75%,1%=>100%,1.01%=>1.01%. La discontinuidad es inequívoca. El mismo helper pretende cubrir otra representación: summary_by_expiration raw:3977-3979 guarda una fracción; no debe tratarse como unidad indistinguible.

Prueba AST independiente confirmó los cuatro casos y el control5.82=>5.82. Los valores EM presentes de los46inputs16oct son>1; no se encontró una incidencia de este defecto en ese lote. LEU no tiene EM publicado. No se afirma que toda la serie histórica esté libre: un inventario global de archivos ignorados agotó el tiempo del runtime y no se usó como prueba.

**Recomendación/aceptación:** unidad explícita por campo/versión y conversión determinista. Probar0.01,0.75,1,1.01,10.29 y coherencia porcentaje=100*dólares/spot con tolerancia de redondeo, también por expiración. No resolver con otra heurística de magnitud.

## D5 — P2: el parser de gamma elimina contratos necesarios para otras métricas

**Defecto reproducible; alcance real desconocido por falta de wire original; confianza alta.** _tradier_options_chain (raw:1993-2021) exige float(greeks/gamma); si falta, descarta todo el contrato aunque OI y bid/ask estén presentes. También transforma OI ausente en0 (2009). Ese parser alimenta no solo TOPgamma sino OI puts/calls (2845-2854), straddle/EM (2297), maxpain (2329,4000) y resumen por expiración (3948,3970-3971). Por tanto la ausencia de una griega altera métricas que no requieren gamma.

Prueba wire sintética: call strike100/OI100/gamma0.02 y put strike100/OI900/gammaausente. Parser conserva solo call; overview informa puts0,calls100,ratio0.0 en vez del ratio9 de los OI observados. La observación dirigida39 sobre el mismo XML conserva put/OI900,gamma desconocida, statusavailable. Esto NO es la diferencia legítima entre agregado TOP gamma-elegible y agregado dirigido de todos los contratos: el problema aquí es presentar totales OI/straddle/maxpain tras un filtro de gamma sin declarar esa cobertura.

**Control positivo:** contratos con gamma finita y OI explícito llegan; zeroOI se conserva por el camino dirigido; fallosHTTP/XML se elevan. No se dispone deXML original para afirmar cuántos OI concretos del lote se perdieron.

**Recomendación/aceptación:** parser contractual conserva identidad y métricas por separado; cada consumidor decide elegibilidad; unknownOI distinto de0; contadores/razones de exclusión por métrica. Fixture anterior debe producir OIputs900 y gamma desconocida; EM usa bid/ask válidos sin depender de gamma; TOP existente permanece exacto para contratos completos.

## D6 — P2: la frescura se valida sobre el envoltorio, no sobre cotización ni última sesión

**Guarda incompleta reproducida; no se ha probado proveedor stale en el lote16oct.** raw/main.py:967 fija as_of a la hora de serialización, pero no exporta timestamp/basis de la cotización seleccionada. _extract_latest_price:1143-1153 prioriza cualquier bid/ask numéricos y luego last/close/prevclose, sin edad. Require_price_history (technical_preparation.py:6-33) valida orden, OHLCV y fechas anteriores al snapshot, pero acepta una sola barra arbitrariamente antigua pese a window_sessions=20; no compara con la última sesión esperada. data_ready solo compara prepared/slim.as_of con reloj (adaptive_stage.py:238-242).

Prueba completa: copiar inputAPP16oct en memoria, sustituir price_history por una sola barra válida fechada02ene y mantener fechas de envoltorio => data_ready acepta. No se llamó al modelo ni se escribió original. Una barra inválida/duplicada sí se rechaza por los controles existentes.

**Recomendación/aceptación:** separar captured_at, quote_at, history_last_session y sesión cerrada esperada; validar frescura/longitud acorde a mercado y antigüedad real del activo, incluidos IPO, festivos y sesión no terminada. Un timestamp de captura nuevo nunca rejuvenece datos viejos. No sustituir este control por porcentajes de movimiento financiero.

## D7 — P2: el midpoint de cotización acepta un libro inválido

**Defecto reproducible; incidencia real no probada.** raw/main.py:1144-1153 usa midpoint si bid/ask son finitos, sin exigir bid>0, ask>=bid ni spread razonable. bid0/ask100/last99 produce latest_price50; bid120/ask80/last101 produce100; bid0/ask0/last100 produce0 y después puede causar división por cero/502 en el handler antes de llegar a la guarda positiva local. Control bid99/ask101 devuelve100 como se espera. El helper de precio de opciones sí comprueba orden/no negatividad (raw:2284-2288), evidenciando criterios distintos.

**Recomendación/aceptación:** definir calidad mínima y procedencia de cada alternativa, degradar a last válido y fechado cuando el libro no es utilizable. Probar cero, cruzado, unilateral, no finito y último precio stale. No usar un umbral financiero de ruptura para resolver calidad de quote.

## D8 — P2: la cobertura de titulares no representa saturación ni hasMore

**Defecto de cobertura reproducible por código; no saturación observada en los últimos lotes14–16oct.** reqHistoricalNews hace una única consulta con total_results (probe:138-144). La librería declara máximo300 (ib.py:1615) y descarta hasMore (wrapper.py:1043-1044); _compact_payload fija truncated=false sin mirar ni límite ni señal del servidor (news_update:289). La ventana almacenada es la solicitada, no la probada completa. Prueba independiente: _compact_payload sobre300titulares devuelve truncated=false. Aun300titulares se presentan como cobertura no truncada. El control data_ready de truncated por tanto no protege esta vía.

**Recomendación/aceptación:** preservar respuesta terminal y hasMore, paginar con límite operativo y deduplicación estable o marcar cobertura incompleta. Pruebas vacía completa,299completa,300con hasMore y error intermedio; no permitir statusok completo solo por haber recibido datos. Separar completitud del feed de relevancia editorial y de cobertura web.

## Controles que sí quedaron corroborados

- Rev39 deriva identidades put/call+strike de CURRENT autenticado y activo (technical_preparation.py:87-118), no de prosa/precio/ancla retirada. Es una petición de observación, no prueba de vigencia. Congelados<=38 retornan antes de adquirir bajo39; test originalAPP38 conserva bytes.
- La captura original APP21:07:48 tiene puts250 y255 disponibles en16/23/30oct; elTOP es265,262.5,270,260,250, por lo que255 está realmente fuera delTOP y llega. El código lee las mismas respuestas cacheadas en request (raw:1837-1858,1878-1943); pruebas cuentan4descargas paraTOP y ninguna extra al observar las identidades.
- Directed distingue ceroOI, OI/gamma desconocidos, identidad noobservada y descarga fallida. aggregate_oi_basis explicita todos los contratos observados. No comparar ese agregado con TOP gamma-elegible para declarar pérdida de respaldo. La prueba de fallo de captura comprueba502 y ninguna publicación del mirror.
- La cobertura se verifica antes de congelar/admitir (adaptive_stage.py:53-63,96-103; technical_preparation.py:121-159). Se rechazan identidades pedidas ausentes/contradictorias y el origen positivo descarta call, noobservado, expiración anterior y cero métricas. No se confunde available con selección financiera.
- Las reacciones usan solo ventanas completas de5sesiones y exponen pendientes/exclusiones (raw:1355-1402). El ATR histórico y hash de historial/parametrización están separados delATR vivo (1431-1453). Los tests positivos y negativos de madurez pasaron. Esto valida la implementación de la medida, no su capacidad predictiva ni independencia estadística de eventos.
- Volume_profile se declara aproximado y usa distribución deOHLCV diario por48bins (1197-1289); no es un perfil intradía medido. Datos insuficientes devuelven unavailable.
- Catálogo: identidades hash incluyen scope,grupo,valor completo, rechazan colisión y duplicado idéntico no se vende como evidencia adicional (semantic_sources.py:14-68). Prueba independiente reordenó soportes y conservó asociación handle/valor; /source_catalog/sN/value resolvió igual y /pointer fue rechazado. Historicalreport se reconstruye de autoridad verificada (100-130), no se convierte por ese mecanismo en origen vivo.

## Límites restantes que no se presentan como defectos financieros demostrados

1. **Auditoría de proveedor.** El servicio guarda métricas y20barras recientes, pero no todos los252OHLCV ni XML completos de cadenas usados. El hash de historia1443 no permite reconstruir sus datos. El cache de opciones es solo de request. Sin wire conservado no se puede validar retrospectivamente pérdida de contratos, ajustes corporativos, revisiones de proveedor o integridad exacta del perfil. Recomendación: recibo de adquisición versionado con respuestas/alcance/tiempos y hash, almacenamiento adecuado sin nuevas consultas.
2. **Ajustes/unidades contractuales.** No hay metadato explícito de adjusted/unadjusted, moneda, split/deliverable o multiplicador real en slim. Raw supone100por contrato (3858,3921), usa OHLCV tal cual devuelve Tradier y descarta identidad de símbolo contractual en los detalles exportados. Es una suposición no verificada, no evidencia de que los tickers actuales estén mal ajustados. Requiere casos split/contrato ajustado y contratos de proveedor antes de declarar garantía.
3. **Muestreo.** TOPprimeras3expiraciones/5strikes y filtros de selección son límites del conjunto suministrado, no pruebas de inexistencia del resto del mercado. _put_call_oi_views descarga además una vista hasta60DTE (2928-2949); slim solo conserva nearterm y3expiraciones. Eso pierde información ya adquirida, pero está dentro del alcance actualmente declarado y no justifica automáticamente más análisis ni mayor nota. Evaluar utilidad/costo antes de ampliar el contexto.
4. **Cierre temporal.** _complete_daily_bars define completitud por fechaUTC, por lo que omite una sesión ya cerrada hasta el siguiente díaUTC. APP21:07 lo ejemplifica. _live_levels usa expiración>=fecha snapshot (semantic_report.py:281,291), no hora del contrato: la captura vespertina puede considerar un vencimiento del mismo día aún elegible. Se necesita contrato de sesión/expiración explícito; no se inventa un cutoff universal ni se afirma daño.
5. **Noticias son titulares.** Los46inputs16oct suministran solo published_at,providerCode,articleId,headline. Los cuerpos están fetched=false en el probe (224-242); la ruta opcional de bodies requiere aggregate_news y está desactivada por defecto (news_update:75-105,153-159). Es correcto llamarlos pistas del feed, no artículos leídos completos ni investigación primaria. La investigación web de la llamada es otra evidencia y debe acreditarse en su recibo.
6. **Analistas son estado condensado.** _collect_recent_actions solo exporta last_event/target_last_event por firma (analyst_recent_actions.py:110-145), no una cronología íntegra de todas las acciones. Si hubo varias entre revisiones, acciones intermedias pueden quedar fuera de este resumen; el feed general puede contenerlas pero no es garantía. El resumen conserva basis/quality/as_of y exclusiones; las medias/targets no son un dataset fundamental ni consenso completo universal.
7. **Fundamentales y earnings.** El input no contiene estados financieros normalizados completos; depende de autoridad previa, calendarioFinnhub, titulares y búsqueda de la misma llamada cuando proceda. Calidad de esas afirmaciones exige fuentes específicas; un statusok técnico no acredita balance, cifras o guidance.
8. **Filtros de candidatos.** Distancia mínima5% para algunas familias (raw:50-57,87) y selección de un cluster/gap/AVWAP reducen lo visible. La observación dirigida evita ausencia artificial de algunas fuentes históricas, pero no proporciona inventario exhaustivo de toda estructura. No atribuir un null financiero a inexistencia de niveles sin revisar el conjunto suministrado.

## Orden de trabajo recomendado y comprobación

Primero arreglar el contrato de terminación/frescura del feed IBKR y la separación volumen cerrado/intradía; después los cálculos deterministas D3/D4 y separación parser contractual/gamma D5; endurecer cotización/frescuraD6/D7 y coberturaD8. Hacer cambios acotados y versionados, con fixtures offline y reproducción de originales; conservar recibos/versiones y no reescribir informes para ocultar defectos. Los controles de origen, autoridad, fuentes y continuidad deben permanecer. El impacto sobre selección, puntuación, precisión o rentabilidad debe medirse separadamente: esta auditoría detecta errores de datos y límites de verificación, no demuestra una mejora financiera por cambiar un indicador.

## Apéndice reproducible — pruebas sintéticas exactas

Este bloque conserva las reproducciones mínimas ejecutadas durante la auditoría, reunidas para poder repetirlas. Ejecutar desde la raíz del repositorio con Python3.12 de la venv. No llama a proveedores: carga funciones puras del código real mediante AST y sustituye IBKR/XML por dobles locales. No invoca handlerHTTP, mirror, modelo, lote ni publicación; no escribe archivos. Las aserciones documentan los defectos actuales: tras corregirlos deben fallar y convertirse en controles de comportamiento correcto, no mantenerse como resultados deseados.

Comando PowerShell: pegar el programa entre un here-string literal y pasarlo por stdin a la venv:

~~~powershell
@'
# Pegue aquí el programa Python completo que sigue.
'@ | & '.\.venv\Scripts\python.exe' -B -
~~~

~~~python
import ast
import json
import logging
import math
import statistics
import sys
import types
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path.cwd()
RAW = ROOT / 'gcp_functions/support_resistances_raw/main.py'
SLIM = ROOT / 'gcp_functions/support_resistances_slim/main.py'


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]),
                 str(path), 'exec'), namespace)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 16, 16, 0, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    @classmethod
    def utcnow(cls):
        return cls(2026, 10, 16, 16, 0)


ns = {
    'math': math, 'statistics': statistics, 'ET': ET,
    'datetime': FrozenDateTime, 'timezone': timezone,
    'tlogger': logging.getLogger('audit_offline'),
    'TRADIER_BASE': 'offline', 'HEADERS_XML': {},
    'CALLWALL_TOP_EXPIRATIONS': 1,
}
load_functions(RAW, [
    '_to_float', '_median', '_complete_daily_bars', '_recent_price_history',
    '_volume_20d_package', '_extract_latest_price',
    '_tradier_options_chain', '_put_call_oi_overview_for_exp_list',
    '_days_to', '_observe_option_origins', '_trend_bias_confidence_1_2w',
], ns)
load_functions(SLIM, ['_num', '_normalize_pct'], ns)
results = {}

# D1: la librería real devuelve None al agotar su timeout. No se conecta IBKR.
from src.local_runner.ibkr_analyst_probe import fetch_ibkr_analyst_headlines
from src.local_runner.ibkr_news_update import _compact_payload


class FakeIB:
    def connect(self, *args, **kwargs):
        pass

    def reqNewsProviders(self):
        return []

    def qualifyContracts(self, contract):
        return [types.SimpleNamespace(conId=1, symbol='TEST', exchange='SMART',
                                      currency='USD', secType='STK')]

    def reqHistoricalNews(self, *args, **kwargs):
        return None

    def isConnected(self):
        return False


fake_module = types.SimpleNamespace(IB=FakeIB, Stock=lambda *args: None)
now = datetime(2026, 10, 17, tzinfo=timezone.utc)
with patch.dict(sys.modules, {'ib_insync': fake_module}):
    payload = fetch_ibkr_analyst_headlines(
        symbol='TEST', host='offline', port=0, client_id=1, provider='DJ-N',
        start=now - timedelta(days=1), total_results=300, readonly=True,
        timeout=1, generated_at=now)
    compact = _compact_payload(payload)
assert compact['status'] == 'ok' and compact['count'] == 0
assert compact['truncated'] is False
assert compact['generated_at'] == now.isoformat()
results['D1_timeout_reported_as_success'] = compact

# D2: veinte barras anteriores más barra abierta. Fechas sintéticas; no calendario.
rows = [dict(date=(date(2026, 9, 26) + timedelta(days=i)).isoformat(),
             open=100, high=101, low=99, close=100, volume=1000)
        for i in range(20)]
rows.append(dict(rows[-1], date='2026-10-16', volume=100))
volume = ns['_volume_20d_package'](rows)['last_complete_day']
history = ns['_recent_price_history'](rows)
assert volume['date'] == '2026-10-16' and volume['rel_to_20d'] == 0.105
assert history['last_session'] == '2026-10-15'
closed_control = ns['_volume_20d_package'](rows[:-1])['last_complete_day']
assert closed_control['date'] == '2026-10-15'
assert closed_control['rel_to_20d'] == 1.0
results['D2_partial_volume'] = dict(volume=volume,
    history_last=history['last_session'], closed_control=closed_control)

# D4: el campo weekly raw ya expresa porcentaje; no fracción.
normalized = {str(v): ns['_normalize_pct'](v) for v in [0.75, 1, 1.01, 5.82]}
assert normalized == {'0.75': 75.0, '1': 100.0, '1.01': 1.01, '5.82': 5.82}
results['D4_weekly_percent'] = normalized

# D5: falta gamma del put, pero OI/bid/ask están en la respuesta ya descargada.
wire = (
    '<options><option><option_type>call</option_type><strike>100</strike>'
    '<open_interest>100</open_interest><greeks><gamma>0.02</gamma></greeks>'
    '<bid>1</bid><ask>2</ask></option>'
    '<option><option_type>put</option_type><strike>100</strike>'
    '<open_interest>900</open_interest><bid>1</bid><ask>2</ask>'
    '</option></options>'
)
ns['_option_response'] = lambda *args, **kwargs: Mock(text=wire)
ns['_tradier_option_expirations'] = lambda *args: ['2026-10-23']
chain = ns['_tradier_options_chain']('TEST', '2026-10-23')
overview = ns['_put_call_oi_overview_for_exp_list'](
    'TEST', ['2026-10-23'], 'near_term')
directed = ns['_observe_option_origins']([('put', 100)], 'TEST', 100)
assert len(chain) == 1 and chain[0]['option_type'] == 'call'
assert overview['total_put_oi'] == 0 and overview['total_call_oi'] == 100
assert overview['ratio'] == 0.0
observation = directed[0]['option_details']['by_expiration'][0]
assert observation['aggregate_oi'] == 900
assert observation['gamma_usd_millions'] is None
results['D5_gamma_filter_loses_oi'] = dict(chain=chain, overview=overview,
                                        directed=directed)

# D3: una pared superior se convierte en distancia inferior cero.
trend = ns['_trend_bias_confidence_1_2w']
wall_cases = {}
for label, walls in [
    ('above', [{'distance': 10}]),
    ('below_far', [{'distance': -8}]),
    ('below_near', [{'distance': -2}]),
    ('mixed', [{'distance': 10}, {'distance': -8}]),
]:
    value = trend(100, {}, None, {}, [], walls)
    wall_cases[label] = dict(
        distance=value['features_flat']['nearest_put_wall_dist_pct'],
        rules=value['rules_triggered'])
assert wall_cases['above']['distance'] == 0
assert wall_cases['mixed']['distance'] == 0
assert wall_cases['above']['rules'][0]['code'] == 'PUTWALL_NEAR'
assert wall_cases['below_far']['distance'] == 8
assert wall_cases['below_far']['rules'] == []
assert wall_cases['below_near']['distance'] == 2
results['D3_put_side'] = wall_cases

# D8: el límite del feed no genera marca de truncación.
cap = _compact_payload({'headlines': [
    {'headline_clean': str(i)} for i in range(300)]})
assert cap['count'] == 300 and cap['truncated'] is False
results['D8_cap_truncated'] = cap['truncated']

# D7: libro unilateral/cruzado no invalida el midpoint.
quotes = [dict(bid=0, ask=100, last=99), dict(bid=120, ask=80, last=101),
          dict(bid=99, ask=101, last=98)]
selected = [ns['_extract_latest_price'](q) for q in quotes]
assert selected == [50.0, 100.0, 100.0]
results['D7_quotes'] = list(zip(quotes, selected))

print(json.dumps(results, ensure_ascii=False, indent=2))
~~~

La combinación del bloque no se volvió a ejecutar: se preservan las llamadas ya realizadas y se fija explícitamente el reloj para que la prueba temporal siga reproduciéndose después del17oct. La extracción AST evita la inicialización de clientes cloud de main.py. Las regresiones existentes se reproducen separadamente con:

~~~powershell
& '.\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider test_option_origins_v39.py test_capture_routing_v23.py tests/test_support_resistances_slim_evidence.py
~~~
