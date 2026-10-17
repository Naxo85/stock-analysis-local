# support-resistances-raw

Código recuperado el 2026-09-04 a partir del fichero facilitado por el usuario.
Se conserva bajo `incoming_from_gcp/` porque todavía no se ha comprobado que
coincida exactamente con la revisión desplegada en Cloud Run.

Antes de guardarlo se retiraron del código dos credenciales escritas en claro.
El servicio espera ahora `TRADIER_TOKEN` y `GH_TOKEN` mediante variables de
entorno. Ambas credenciales originales deben revocarse o rotarse, ya que haber
eliminado los literales de esta copia no invalida los valores expuestos. Las
versiones de `requirements.txt` se han reconstruido a partir de los imports y
de los servicios históricos vecinos; no proceden del despliegue.

No debe redesplegarse esta copia hasta comparar configuración, revisión e imagen
de Cloud Run, fijar las dependencias efectivas y documentar el despliegue.
