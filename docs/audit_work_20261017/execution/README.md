# Evidencia de ejecución — 17 octubre 2026

Este directorio conserva los resultados y reproducciones del [informe de ejecución](../../execution_audit_20261017.md). Es evidencia de implementación y exploración local; no constituye una validación predictiva ni un despliegue.

- [Datos](data_execution.md), [contratos financieros](financial_execution.md), [integridad/publicación](integrity_execution.md).
- [Archivo técnico opcional](technical_archive_execution.md) y [guarda de identidad de opciones](option_identity_execution.md), con resultados adversariales y exportación de184 originales.
- [Revisión metodológica](methodology_execution_review.md), [revisión final de datos](final_data_review.md) y [revisión final financiera](final_financial_review.md).
- Resultados completos en results/. Sus denominadores, controles negativos y carencias se explican en el informe. No sumar suites solapadas.
- Scripts originales de los estudios en scripts/. El manifiesto registra sus bytes y SHA-256. baseline_contracts/ contiene tres módulos previos usados solo para comparar contratos; no son una segunda implementación activa.
- model_attempt/ conserva criterios, inventario de clases de datos, hashes, negativa de acceso y estado final. No duplica los payloads financieros ni autoriza enviarlos. AMD no produjo respuesta; LEU/TLN/MRNA no iniciados. No hubo cambio de motor.

## Reproducción offline

Desde la raíz del repositorio, con el entorno virtual existente:

    .venv\Scripts\python.exe -B docs\audit_work_20261017\execution\reproduce.py

El runner verifica el manifiesto y los2.152 originales, bloquea sockets y procesos, y ejecuta los estudios en .tmp/audit40_reproduction. Solo sustituye raíz y carpeta de salida en los scripts registrados; no cambia muestras, fórmulas o selección. Los resultados registrados de este directorio no se sobrescriben. Requiere el corpus local de logs indicado en los hashes: esos originales no se descargan si faltan. Un checkout de código sin ese corpus no permite replicar resultados históricos.

El script compara JSON reproducido con resultados registrados y deja reproduction_result.json. Coincidencia prueba reproducibilidad de esos cálculos, no alpha. Una diferencia exige inspección; no se acepta silenciosamente ni se adapta el original al nuevo resultado.

Las pruebas de implementación están en los archivos test_* y tests/ del repositorio. Sus comandos exactos y resultados figuran en results/data_test_results.json, results/option_identity_combined_results.json y las notas de cada rama; safe_test_runner.py original permanece en .tmp/audit_execution_20261017. El comando de reproducción anterior no llama pytest ni Codex y no despliega ni publica.

## Retorno y activación

Checkpoint anterior a implementar:8034b7a. Los681 archivos previos se conservaron sin modificar el árbol de trabajo; cinco documentos se reconstruyeron por ediciones conocidas, con la limitación documentada. No ejecutar git reset --hard para volver a él sin preservar primero el trabajo actual.

El paquete revisable de código se genera con scripts/prepare_audit40_package.py en una carpeta vacía dentro de .tmp. Contiene overlays sobre imágenes registradas, fuentes exactas y una política inactiva. Las actuaciones externas A1–A3 están en la matriz y no fueron ejecutadas.

review_package/ conserva manifiesto, política candidata inactiva y orden de activación del paquete final de48 archivos. identity_control/ conserva el script antes/después y las dos fuentes exactas: son evidencia, no módulos activos. Para repetir ese control, copiar la carpeta completa a una carpeta temporal y ejecutar allí; escribe su resultado junto al script y no debe sobrescribir evidencia registrada. Los tests específicos del repositorio verifican la fuente actual.
