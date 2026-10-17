# Ampliación metodológica — cobertura y alcance

Fecha: 17-10-2026. Complementa la auditoría de implementación después de leer su resultado. Autorizado: investigación pública primaria, lectura local, comprobaciones aisladas y documentación. No realizado: cambios de código/configuración/prompts/tests existentes, modelos pagados, lotes, experimentos externos, recovery, publicación o despliegue.

| Dominio | Revisado y comprobado | Parcial / pendiente | Referencia |
|---|---|---|---|
| Método real y propósito | Datos/contexto, cálculos, familias, rúbrica, continuidad, fuentes y presentación | Utilidad predictiva y horizonte único no definidos/validados | Informe §§14–16 y motor adaptativo |
| Estructura, familias y precio | Selección5%, jerarquía AVWAP, gaps, observación dirigida, historial horizontal, casos favorables/contrarios | Ventaja de inventario alternativo, multiescala y anclas de evento | methodology_structure.md |
| Volumen, opciones y confluencia | OI/signo no identificado, plazos, EM/prob_touch, perfil aproximado, recorrido, dependencia y límites matemáticos | Valor incremental y costes de datos alternativos | methodology_volume_options.md |
| Mercado, sector y empresa | Contexto realmente recibido frente a paneles separados; investigación ya presente y capacidad parcial de premisas | Ventaja de contexto compacto y datos históricos de expectativas | methodology_context_events.md |
| Noticias, eventos y actualización | Agrupación causal, memoria de riesgos, expectativa/realizado, distintos relojes | Cadencia óptima, sorpresas uniformes y estado de tesis | Informe M06/M08 y anexo de contexto |
| Horizonte, incertidumbre y lector | Descriptivos46/45/71; distinción de rango/estructura/estimación; protocolo de comprensión | Confusión real del lector y mejor anchura no medidas | methodology_evaluation.md |
| Alternativas y simplificación | Existencia/parcialidad/ausencia deliberada, utilidad, redundancia, fallo, horizonte y costes por oportunidad; retirada y no incorporación contempladas | Ninguna alternativa aprobada como ganadora | Matrices de los cuatro anexos y §17 |
| Evidencia primaria | Estudios, documentación de proveedor, mecanismos y resultados contrarios con muestra/horizonte; abstract vs texto completo explícito | Transportabilidad al producto actual; bibliografía no es revisión sistemática de toda publicación existente | Anexos con URLs verificadas durante investigación |
| Casos históricos | Originales16-10, decisiones diversas, fechas ex ante; captura39 posterior separada, sin corregir APP | Resultados futuros, varios regímenes y estrategia ejecutable no medidos | §18; rutas y selectores en anexos |
| Evaluación futura | B0/B1/B2, E1–E7; piloto vs confirmación, episodios, sesgos, costes, búsqueda múltiple y criterios de decisión | Experimentos sin ejecutar; potencia/efecto mínimo requieren definición antes del ensayo | §19 y methodology_evaluation.md |
| Documentación | Informe ampliado; motor, arquitectura, README, relevo y backlog actualizados; propuestas explícitas | Incidentes H y propuestas M siguen abiertos | §20 |

## Evidencia local nueva conservada

- [Baseline protegido](methodology_protected_baseline.json),479 archivos de código/configuración/prompts/tests/AGENTS en el alcance registrado.
- [Medición descriptiva](methodology_descriptive_cases.json):46 inputs /45 publicaciones /71 zonas del natural38 del16-10; APP sin publicación. No contiene precios futuros ni prueba de utilidad. Anchura/ATR usa la captura de revisión, no necesariamente la de formación. Conserva SHA-256 de91 originales.
- [Reproducción](methodology_descriptive_check.py) y [resultado](methodology_descriptive_check_result.json): Python estándar local, sin import del runner ni red. Conteos, rangos y hashes verificados.
- Anexo de opciones: código ejecutado de conteos completos, APP y contraejemplos matemáticos. No son experimentos de mercado.
- [Verificación de cierre](methodology_verification_results.json): huellas, enlaces, formato y alcance.

## Revisión independiente de integración

Los tres investigadores revisaron las secciones14–20 y la descripción canónica. Se incorporaron precisiones sobre las dos condiciones separadas de reacción, unidad de atm_iv, LRCX como sustitución de compras y no ausencia, anclas deterministas frente a alternativas predeclaradas, autorización futura del piloto, ampliación de muestra sin optional stopping y E5a organización frente a E5b dato adicional. No se atribuyó rentabilidad a los ejemplos.

Separar evidencia empírica externa, fundamento plausible y práctica sin validación suficiente. Un paper mensual, intradía, FX o de opciones de índice no acredita automáticamente soporte swing de una acción. El resultado es una ampliación documental y un programa de investigación propuesto, no una política nueva.
