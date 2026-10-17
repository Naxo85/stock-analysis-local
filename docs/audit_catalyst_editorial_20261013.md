# Revision33: origen del exceso de catalizadores

## Evidencia original

ASTS full32, logs/adaptive_individual/20261013T144923435879/ASTS:
11 catalyst records,11 show_in_report=true, hidden_catalysts=[].
El contrato32 estaba en instructions.md y el renderer obedecio. No habia
seleccion efectiva ni agrupacion. El prompt financiero v8 ademas exigia integrar
la narrativa desde earnings en bullets. Mantener resultados/riesgos como memoria
se confundia con mostrar cada antecedente como motor actual.

## Correccion compartida

V9 es identico a v8 salvo el apartado Catalizadores: historial interno separado
de sintesis publica; conservar la escala de impactos no concede visibilidad.
reader_report_v33 sustituye instrucciones binarias32, catalyst_editorial_v33
define driver/background/covered. Ambos roles reciben el mismo contrato.
Full selecciona por titulo exacto unico del driver en su propia respuesta;
mantenimiento por cIDs del CURRENT autenticado. No se adivinan source handles.

Cada driver necesita rationale interno con mecanismo vigente y brief publico
compacto. Noticias sobre una misma fuerza, incluidos articulos y reacciones de
brokers, se integran en ese driver. Antecedentes no se borran ni rejuvenecen.
La fecha/impacto visibles pertenecen al hecho representante, no a un score o
fecha sinteticos calculados para el grupo; el brief conserva atribuciones.

El juicio sigue siendo financiero/editorial del modelo: no regex de verdad,
corte por edad, score, numero de bullets o clasificacion automatica de demandas.
Una noticia vieja puede seguir decisiva; una reciente puede ser ruido. Riesgos
materiales/actuales siguen visibles y siguen las guardas normales. Esta via no
permite introducir novedades investigadas al margen del contrato financiero.

Implementacion catalyst_editorial.py y reader_report.py: hechos originales
intactos; proyeccion separada en reader_presentation. Referencias invalidas,
duplicadas, ciclos o instrucciones editoriales malformadas mantienen la vista
anterior, sin fallo del ticker ni otra llamada. Si cambia/desaparece un miembro,
no se reutiliza el brief del grupo viejo para ocultar hechos distintos.
Retain puede ajustar la vista sin cambiar generated_at, ITV, ancla o finanzas.
Full<=32 y prompts congelados se mantienen exactos. Modelos/esfuerzos/cap6 igual.

## Pruebas y limites

29 tests en test_catalyst_editorial_v33.py y test_reader_report_v32.py.
Fixture editorial ASTS:11 hechos en memoria y3 temas visibles; seleccion
construida para prueba, no modelo ejecutado. Finanzas, parser de hoja, fechas,
contexto siguiente, memoria autenticada e idempotencia iguales. Full33 vinculado
al recibo, manipulacion rechazada, retain con una sola llamada simulada, riesgo
protegido, noticias antiguas vigentes, ruido reciente, ninguna cuota minima,
malformados/ciclos/IDs desconocidos, reordenacion y cambio de hechos probados.

Regresion:119 tests y44 subtests correctos. Bateria adicional:
reader_budgets_v30, plan_scope_v29, semantic_presentation,
semantic_contract_v3, adaptive_luna_repair, volume_arithmetic,
plan_evidence_roles, buy_zone_volume_inheritance. Comprueba que las mejoras de
CRWV/MU y los contratos financieros anteriores permanecen intactos.

No se ha regenerado/republicado ASTS ni lanzado modelos, lotes o despliegues.
Config33 activa tras pruebas; siguiente ejecucion natural valida el criterio
editorial real. Tests deterministas no garantizan el juicio del modelo.
