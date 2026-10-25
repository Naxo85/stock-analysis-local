# Aplicación autorizada: esquema compartido de mantenimiento

23/10/2026. El usuario autorizó aplicar los cambios recomendados. Se activa
únicamente la factorización del esquema de salida, el cambio más acotado del
estudio. Compresión histórica, orden para caché, alias con null, recorte de
instrucciones y lectura bajo demanda siguen desactivados.

## Comportamiento

La configuración local añade `maintenance_output_schema=shared-defs-v1` para
nuevas preparaciones41. Revisiones y su única reparación comparten mediante
`$defs` las partes idénticas del schema. El contrato financiero, campos,
required, tipos, nulls, enums de fuentes, límites, patrones y orden expandido
son exactamente los mismos. No se modifica ningún prompt ni dato financiero.

Sol6.1 medium sigue en mantenimiento y Sol6.1 high en completos. Full conserva
su schema, aunque la nueva política tenga la opción. Una preparación congelada
sin ella devuelve el schema original sin transformación. La recuperación
autentica el esquema realmente enviado; no admite un recibo del contrato
alternativo ni vuelve a llamar al modelo para corregir esa discrepancia.

La transformación ocurre en `adaptive_stage.model_call`, después de construir
las restricciones de reparación y antes de calcular claves de caché, comprobar
recibos o reservar la llamada. El validador financiero sigue usando el contrato
original. `adaptive_codex` escribe y autentica el schema transformado real con
su mecanismo existente. No se retiran las elecciones exactas de fuentes para
estabilizar el schema de reparación.

`maintenance_schema_transport.py` recorre sólo posiciones de schema, no datos
de enum/const/default; distingue el orden de propiedades, evita colisiones con
definiciones previas y verifica por expansión el contrato ordenado completo.
Si una transformación no ahorra caracteres, conserva la copia original. Una
discrepancia de expansión falla antes de reservar un modelo. No se incorpora
fallback automático de formato ni llamadas extra si el proveedor lo rechaza.

## Tamaño y pruebas

El schema ordinario de los 92 originales Sol pasa de **14.935 a 7.611 caracteres
compactos, 49,04% menos**. La implementación usa nombres breves de definición,
por eso mejora ligeramente los 7.881 del prototipo. Sobre JSON + instrucciones
+ schema representa 1,52% del lote21 y 1,49% del lote22, normalizados al
transporte pointer-diff ya activo. **Son caracteres, no ahorro medido de tokens
ni cuota semanal.** El servidor puede transformar la representación del schema;
la admisión real y el efecto sobre uso/caché se observarán en el siguiente uso
natural, sin lote duplicado.

Verificación realizada sin llamadas de modelo:

- 92 schemas históricos generados iguales a sus originales, preservando los
  contratos congelados; 92 respuestas originales admitidas por ambos schemas.
- 13.606 mutantes de campos ausentes/extra y tipos incorrectos rechazados igual.
- 92 schemas de reparación con restricciones de fuentes y expansión exacta;
  92 comprobaciones de schema full sin transformación.
- 552 archivos originales intactos por hash y los 13 prompts inventariados
  intactos. Ningún informe regenerado, recuperado o publicado.
- Pytest: **55 pruebas y 7 subtests aprobados**, incluyendo contrato financiero40
  y las pruebas nuevas de fuentes, orden, colisiones, integración y recibos.
  Sólo aviso de escritura denegada de `.pytest_cache`; no afecta al resultado.
- **39 pruebas antiguas aprobadas** con el ejecutor de fixtures offline descrito
  debajo. Total de pruebas distintas:94, además del replay y sus mutaciones.

Los primeros intentos directos de las dos suites antiguas fallaron porque sus
fixtures revisión3 heredaban las opciones actuales de manifest/último intento,
y una aserción de recuperación escapaba al reloj03Oct. El script
`legacy_regressions.py` fija sólo esos globals de prueba a publicación legacy,
sin intento remoto, sin opción nueva y con su reloj histórico. Bloquea cualquier
GcsStore real. Las pruebas originales y las reglas de producción no se cambian.
Los intentos iniciales de lectura remota fallaron en refresco de credencial;
no hubo publicación ni se solicitaron credenciales para hacer pasar las pruebas.

## Activación y reproducción

`activation.json` comprueba que el único cambio de configuración respecto a la
restauración previa de Sol medium es añadir la opción. SHA anterior:
`2836bde9712e17d3a5ddcbf3cdccc34a034b5719dd42cce616344aebf1a0edd2`.
SHA activo:
`a641cddc3c97883079aea83536ee031b7dbe3ea20124d5021b6b8f551cb7412c`.

Con `.venv\Scripts\python.exe`:

- `-m pytest -q tests/test_maintenance_schema_transport.py tests/test_financial_contract_v40.py`
- `docs/audit_sol_input_cost_20261023/implementation/legacy_regressions.py`
- `docs/audit_sol_input_cost_20261023/implementation/replay.py`
- `docs/audit_sol_input_cost_20261023/implementation/verify_activation.py`

No se toca un congelado para retirar la opción. Cualquier reversión futura se
aplica sólo a preparaciones nuevas; los intentos ya admitidos conservan su
policy/schema/recibo exactos. No se hizo un despliegue cloud: el ejecutor local
carga el código y la política en su próxima ejecución normal.
