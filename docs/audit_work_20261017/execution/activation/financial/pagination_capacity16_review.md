# Delta de capacidad de paginación

El único cambio de producción respecto al collector revisado es DEFAULT_MAX_PAGES de8 a16. Se mantienen30s por respuesta,75s totales, el límite de300 por página, la exigencia de terminalFalse y todas las guardas de frontera/progreso/conflicto. Los34 tests locales (27 de producción y7 independientes;14 subcasos) pasan, incluidos14 páginas con EOF real y16 páginas todavía hasMore=True que deben fallar.

La evidencia diagnóstica anterior de NVDA en dos procesos justifica investigar la capacidad; no prueba el presupuesto de75s en un solo proceso. La captura nueva de NVDA se verifica por separado. MRNA conserva el input congelado exacto y su adquisición real de3 páginas; no se repitió su modelo por este ajuste. Hashes en pagination_capacity16_review.json.
