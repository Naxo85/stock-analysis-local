# Auditoría independiente del 17-10-2026 — cobertura y registro

Alcance autorizado: lectura, pruebas locales aisladas, reproducciones y documentación. Sin llamadas de modelo, lotes, acceso cloud, recuperación/publicación, despliegue ni cambios de código/configuración/prompts/tests/originales. [Informe completo](../audit_analysis_system_20261017.md).

## Matriz final

Comprobado significa que se contrastó una pregunta concreta, no que toda el área esté validada. Los límites no son instrucciones para ejecutar operaciones nuevas.

| Fase | Trabajo y evidencia conservada | Estado de la auditoría y límite |
|---|---|---|
| 1. Sistema real | AGENTS, configuración, canónicos, rutas, servicios, consumidores y ensamblado final; arquitectura actualizada | Revisado y comprobado localmente. Despliegue actual remoto no consultado; evidencias guardadas fechadas |
| 2. Criterio financiero | [Finanzas](financial.md): composición, pesos, geometría, TLN, GEV, casos retain/update/full/ausentes | Comprobadas contradicción y reproducciones. Utilidad predictiva, calibración y todas las narrativas pendientes |
| 3. Datos y fuentes | [Datos](data.md): wire sintético, logs IBKR, 46 inputs, unidades, lado, gamma, fecha y calidad de quote | Defectos originales y sintéticos separados. Wire completo, ajustes y exhaustividad real no disponibles |
| 4. Evolución y parches | Cronologías, contratos por revisión, llamadas congeladas y clasificación en informe | Historia reconstruida hasta evidencia disponible. HEAD de septiembre no explica cambios de octubre sin commit |
| 5. Integridad y presentación | [Integridad](integrity.md): 101 recibos, 91 publicaciones, autoridad/fechas, cuatro reproducciones aisladas | Comprobado corpus seleccionado. Sin corrupción original observada ni medición de frecuencia de fallos remotos |
| 6. Pruebas y casos | 350 tests aprobados, 1 expectativa obsoleta fallida, 184 subtests reportados; [pruebas raíz](root_tests.txt) e [inventario de lotes](batch_inventory.json) | Suites focalizadas concluidas; no suite completa ni prueba de rentabilidad. Intentos repetidos/inconclusos no sumados |
| 7. Alternativas | Hallazgos, costes, dependencias, aceptación y evaluación prospectiva en informe/backlog | Propuestas comparadas y separadas de cambios aplicados. Ninguna mejora técnica implementada |
| 8. Documentación | Canónicos reescritos, antecedentes archivados, avisos históricos, revisión cruzada y comprobación de enlaces | Actualización aplicada. Guías especializadas conservan su alcance; no verifican estado remoto actual |

## Evidencia y procedimientos

- Baseline de 479 archivos protegidos: [huellas iniciales](protected_baseline.json), [estado git inicial](baseline_git_status.txt). El árbol ya contenía modificaciones y archivos sin seguimiento.
- Pruebas raíz: [argumentos y exit code](root_tests_result.json); resultados y reproducciones de los tres dominios en sus anexos. Las reproducciones mutan copias/memoria, usan transportes simulados y prohíben llamadas de modelo.
- Documentación histórica: [manifiesto de origen](documentation_archive_manifest.json), [índice contextual](../history/README.md).
- Verificación de cierre: [resultado local](verification_results.json). Contiene comparación de hashes protegidos, enlaces de los documentos intervenidos y revisión de cambios documentales. No equivale a verificar todos los archivos del repositorio ni el contenido remoto.

## Registro de decisiones

1. Se leyó íntegra la solicitud y se inició por AGENTS y los cuatro canónicos. La investigación se dividió en datos, finanzas e integridad con lectura independiente y síntesis central.
2. No se usó el diseño original como referencia normativa. Se distinguieron preferencias del usuario, convenciones, cálculos y validación empírica.
3. Se buscaron controles contrarios: originales coherentes, feeds vacíos válidos, geometría publicada correcta, recuperaciones inmediatas y decisiones razonables de mantenimiento.
4. Se conservaron incidentes originales y estados pendientes. Natural 38 ya ocurrió; natural financiero 39 permanece pendiente en la evidencia examinada.
5. Revisión final independiente corrigió denominador de falsas señales de pared, alcance de herencia de Volumen, comprobación de propiedad en recovery y procedencia local del estado APP. Se separaron causas distintas en subhallazgos.
6. Solo se aplicaron documentación, notas y reproducciones aisladas. No se hicieron commits ni se alteró el árbol de implementación previo.

## Preguntas abiertas

Las comprobaciones externas pendientes, la evaluación financiera y sus criterios de aceptación figuran en el [informe](../audit_analysis_system_20261017.md) y el [backlog canónico](../pending_work_current.md). Este cuaderno no crea otro backlog.
