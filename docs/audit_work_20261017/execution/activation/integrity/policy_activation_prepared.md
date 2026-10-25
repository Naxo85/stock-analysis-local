# Activador preparado, configuración sin activar

activate_policy40.py está listo para revisión/ejecución exclusiva por raíz. La configuración real conserva SHA256 c2f6269b84c76e62c16732a9eeb8b3f111eb1894d062420a3bc157f54264d3ec y revisión39. La candidata exacta queda fijada por SHA256 64e54ed9d2e40a47a86538b5af82747ca9f573c00fba0784ee7ca2a28d6ec53e; sólo se admiten las cinco claves listadas en prepared_activation_manifest.json. validate_policy conserva las guardas normales. No se ha invocado el activador contra la configuración real; las9 pruebas y12 subpruebas ejecutaron copias temporales, con red/procesos externos bloqueados.

Gates: aprobación explícita root con fecha y hashes de ambas políticas; fuentes40 verificadas activas; los tres lectores Ready al100%; LEU maintenance y MRNA full finalizados, cada uno con preflight final válido, revisión financiera aprobada ligada a hash, activation_analysis_result válido, review ok y candidato40 exacto, frescura al reloj actual, bundle y respuestas/recibos locales íntegros. Modelos/esfuerzos permanecen los previstos. Preparación sola o evidencia incompleta no pasa. La comprobación es local; no firma proveedores externos ni reemplaza revisión financiera humana.

policy40_approval.template.json está deliberadamente sin aprobar y contiene null en hashes que aún faltaban. Raíz debe copiarla a policy40_approval.json y completar únicamente tras revisar los resultados finales. No marcar true ni inventar hashes para evitar un rechazo.

Comprobar sin activar:

    .venv\Scripts\python.exe -B .tmp\activation40_20261018\integrity\activate_policy40.py --approval .tmp\activation40_20261018\integrity\policy40_approval.json

Sólo después de obtener validated_not_activated, ejecutar el mismo comando con --execute. El script vuelve a validar dentro de un lock exclusivo cooperativo, conserva copia exacta39 con fsync, escribe/fsync la candidata en temporal del mismo directorio y hace os.replace. Relee el resultado y guarda recibo local. Antes de reemplazar vuelve a comprobar todos los hashes. No hace red/modelos/publicación ni cambia configuraciones de cartera.

Límites: os.replace da visibilidad atómica del archivo; no se afirma fsync del directorio ni garantía universal ante fallo eléctrico. El lock evita dos instancias de este activador, no un escritor externo que ignore el lock; la comprobación inmediata de baseline detecta cambios observados antes del replace. No debe haber otro editor de config durante esta operación. Si el recibo local falla después del replace, estado activated_receipt_write_failed y exit2 indican que la política YA cambió; no reintentar ciegamente. Un segundo intento tras activación se rechaza por hash baseline distinto. Lock abandonado exige revisión manual, no borrado automático.

package_readme_manifest.json propone sólo corregir el literal README del generador: snapshot local no acredita despliegue; ADC normal en servicios y puente gcloud-cli explícito permitido en runner. El código que produce la candidata production_enabled=false permanece exacto, comprobado por equivalencia AST fuera del literal README. No se generó ni desplegó otro paquete.
