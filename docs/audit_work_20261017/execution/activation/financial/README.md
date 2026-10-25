# Evidencia financiera de puesta en servicio40

Paquete de revisiones independientes del18-10-2026. Conserva resúmenes, comprobaciones y hashes; no contiene payloads completos, valores privados de tenencia, credenciales, tokens de autenticación ni cuerpos completos de noticias. Los originales permanecen congelados en los directorios locales referenciados por hash.

| Caso | Resultado | Modelo real | Reparación / web | Revisión financiera | Publicación |
|---|---|---|---|---|---|
| LEU mantenimiento | retained | gpt-6.1-sol medium,1 llamada |0 /0 | Sin defecto material identificado; finanzas/fechas exactas | No |
| MRNA full | regenerated | gpt-6.1-sol high,1 llamada |0 /10 | Fuentes centrales, tesis, geometría y herencia contrastadas | No |

MRNA_sources.json documenta el contraste de siete textos centrales realmente devueltos por la investigación del modelo. La mera URL no se trató como verificación. MRNA_checks.json y LEU_checks.json conservan números y límites: los scores heredados no equivalen a mediciones nuevas ni a calibración predictiva. Los casos no cubren todas las ramas update/repair/ausencia y no demuestran rentabilidad u optimalidad.

La paginación tiene revisión original con capacidad8 y delta explícito a16; permanecían30s por página y75s total. Sus pruebas locales pasaron, pero el control real fresco de NVDA agotó75s sin aceptar payload. El delta posterior elevó solo adquisición a180s, proceso a210s y backfill a600s, manteniendo respuesta30s, máximo16 y modelos intactos; ocho archivos aplicados contrastados y18 controles independientes pasan. La captura nueva de NVDA llegó después a EOF real en14 páginas,4.065 identidades únicas/19 duplicados/95 titulares en ventana,115,797s de colección y116,5s de proceso, dentro de180/210. NVDA_final_saved_evidence_review.json contrasta el resumen guardado, sin repetir la captura; el resultado satisface el gate de adquisición examinado y no garantiza capacidad universal futura. MRNA llegó a EOF real en3 páginas y no se repitió por ese cambio.

Consumo observado agregado de las dos llamadas:1.810.536 tokens de entrada (1.519.104 en caché) y11.863 de salida;1.822.399 total. No se infiere coste monetario.

INDEX.json identifica cada archivo resumido por tamaño/hash y los recibos de referencia. Las pruebas paginación final34 incluyen27 de producción y7 independientes con14 subcasos; las18 iniciales incluyen11 de reloj/llamador y7 independientes con4 subcasos. No sumar como casos únicos: los7 independientes se repiten entre ambas suites.

La reproducción UTF8 adicional demuestra un fallo de impresión en run_batch tras capturar U+FFFD. El parche aplicado invoca el helper existente al entrar en main; conserva el error original y el retorno failed_non_blocking. Dos regresiones de esa ruta —Unicode y control ASCII— pasan dentro de la unión acotada de18 pruebas y16 subcasos de UTF8, procedencia, plazos y resumen de reintentos. El subprocess se sustituye en la prueba: no ejecuta un batch real. El pipeline de fuentes conserva el mismo error sin fallo de impresión y no necesitó un parche UTF8; su ajuste de plazos ya aplicado está documentado por separado. batch_utf8_final_review.json conserva alcance, hashes y resultado aplicado.
