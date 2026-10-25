# Corrección local de identidad del bloqueo GCS

Causa demostrada: el lock original guardaba PID104024 a las08:06:29UTC. Windows reutilizó ese PID para conhost.exe, iniciado a las08:26:29UTC. El código anterior consideraba cualquier proceso vivo con ese número como dueño y agotó la espera180s antes de iniciar el lote. La reproducción previa con copia aislada se conserva en reproduction_before.json.

La corrección consulta el inicio real de la instancia Windows. En locks legacy {pid}, una instancia nacida después de la escritura no puede ser propietaria. Los nuevos locks añaden owner_started_ns y token, sin cambiar las llamadas GCloud, los límites60s/180s, el fail-closed de manifest ni la API de adaptive_sessions. Estado desconocido, acceso denegado o falta de hora de nacimiento conservan el lock; su edad sola no elimina un dueño vivo. Archivos ilegibles tampoco se tratan como abandonados.

Las comparaciones de contenido/identidad antes del borrado y el token al liberar evitan reemplazos deterministas; sigue existiendo el intervalo TOCTOU previo entre comparación y unlink porque no se ha rediseñado el mutex como primitiva atómica del sistema. El caller legacy de session pool mantiene su firma y liberación anterior; ese archivo permanece intacto.

Regresión staging:87 pruebas aprobadas y39subcasos;3 pruebas preexistentes excluidas tras reproducir el mismo fallo en original y staging. Los19tests nuevos incluyen PID reutilizado legacy/nuevo, propietario vivo antiguo, desconocido/permisos, contenido incompleto, reemplazos, liberación propia, timestamp Windows real y exclusión/recuperación de un proceso Python local real. Los8tests existentes de analysis_state siguen aprobados. Las pruebas de sesiones conservan seis leases distintos, no reuso ambiguo y el ejecutor configurado. Véanse staged_lock_regression.log y lock_regression_baseline_comparison.json.

No se modificó el código activo ni el lock real desde esta subtarea. No hubo llamadas GCS/modelos ni lotes. El manifiesto apply_manifest.json vincula los dos archivos listos para aplicar.
