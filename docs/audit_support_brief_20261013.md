# Vigencia de soportes y resumen ejecutivo — 13-10-2026

## Evidencia y causa

Natural27: logs/batch/2026-10-13/08-03-29, orden
20261013-080034-735-market-92e7cd52.46/46,37retain,3update(KTOS,AMD,HIMS),
6full(HOOD,AMAT,PLTR,QCOM,WDC,CRDO),sin fallos ni reintentos.

Se revisaron input/triage/review y payloads originales, no solo contadores.
Los modelos tenian indicadores y estadisticas de rebotes, pero no la secuencia
OHLCV reciente necesaria para distinguir un soporte perforado marginalmente de
una compra ya perdida. La politica de continuidad dominaba el juicio: ausencia
de fallo registrado o un test pendiente de cinco sesiones se usaban para conservar.
La politica ya decia evaluar vigencia, pero el dato y la prioridad eran insuficientes.

| Caso | Observacion original | Problema a corregir |
|---|---|---|
| LRCX |303.29; entrada329–331,washout307–309 | Mantener por falta de perdida demostrada no prueba compra vigente; AVWAP es coordenada, no defensa. |
| RKLB |64.675; entrada70–70.6,washout64.7–65.3 | No equiparar ambas: washout solapa spread; entrada requiere evaluar cronologia, no solo paredes/retención anterior. |
| AMD |583.785; entrada599–601 | Test12-10 pendiente no concede cinco sesiones de vigencia automatica. |
| CLS |344.44; entrada355–360 | Respaldo SMA/POC/opciones historico necesita juicio de papel actual; spread amplio importa. |
| SOFI |15.215; entrada15.5–15.56 | Decir que no hay defensa confirmada y tampoco fallo no resuelve vigencia. |
| GEV |986.05; entrada998–1002 | No borrar automaticamente por distancia: penetracion relativa a volatilidad puede seguir siendo marginal. |
| CRDO |195.495; ambas compras ausentes | Ya retiro recuperaciones no defendibles; no imponerle compras nuevas. |

No son siete veredictos de compra/venta ni entradas que codigo deba retirar.
La secuencia completa ahora permite al modelo fundamentar el juicio, sin un
umbral nuevo de porcentaje/ATR/cierres. Riesgo/ownership/stops/ITV no se relajan.

CRDO: narrativa de cinco parrafos mezclaba negocio, productos, mercado, plan,
insiders y limitaciones. Causa editorial: investigar se convertia en mostrar todo.
Nueva instruccion separa razones breves de Tesis/Setup y un parrafo ejecutivo;
detalle material en catalizadores/plan, trabajo interno en auditoria. Sin contador
de palabras, recorte automatico, gate ni pago extra para corregir estilo.

## Implementacion y verificacion

price_history usa las mismas barras ya descargadas, ultimas20 sesiones completas,
sin nuevas peticiones a Tradier ni cambiar indicadores/reacciones. Observaciones,
no verdictos. Ventana declarada y limitada; no se inventa historia anterior.
Raw/slim AST, quitando exclusivamente el campo/helper nuevo, igual al codigo de
las imagenes activas26. Despliegue por capa sin trafico primero; Ready/runtime
verificados antes de activar100%. Evidencia logs/deploy_history28; script
scripts/deploy_price_history_v28.py. Smoke tecnico LRCX:20 sesiones, ultima12-10,
historia exacta entre capas. No batch/modelo/publicacion financiera.

Revision28 agrega fuente autentica al catalogo solo para nuevos contratos.
data_ready rechaza historia malformada/ausente antes de freeze/modelo: no llama
a Sol para suplir datos fallidos. Casos antiguos<=27 siguen intactos.
Instrucciones normales de ambos roles y reparacion comparten orden de decision.
No schema financiero nuevo ni autorizacion para editar stops o tesis en medium.

Regresion207 tests+197subtests offline: datos invalidos, dia vivo excluido,
raw/slim exactos, fuente citada, contratos27 identicos,28 ambos roles y reparacion,
preparacion congelada,46proyecciones originales con cifras/fechas/texto intactos,
aritmetica/riesgo/fuentes/procesos/publicacion y reparacion anteriores.
No prueba de juicio vivo: observar proximo natural, no generar duplicado.

## Limites y pendiente separado

No se han reescrito informes existentes. Narrativa protegida de mantenimiento
se conserva hasta el siguiente full natural. Cambio de instrucciones no certifica
que una futura respuesta vaya a seguirlas perfectamente.
Captura Sheet mostraba CRDO209.5 mientras ultimo JSON local/remoto ya tenia compras
null; LRCX aparecia vacio pese a entrada publicada329–331. No se ha demostrado si
era antiguedad, filtrado o fallo de consumidor. No atribuir esas celdas al modelo
ni declarar reparado ese desfase por desplegar28; pendiente de auditoria separada.
