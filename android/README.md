# Growth Android

Aplicacion personal de lectura para el sistema de analisis. Kotlin, Jetpack
Compose, Android 8.0 o posterior. Diseno Panel con cuatro pantallas y temas
claro/oscuro.

Desde la raiz del repositorio:

```
.venv\Scripts\python.exe scripts\verify_mobile_service.py
.venv\Scripts\python.exe scripts\build_android.py
```

La API privada ya esta desplegada; su URL se guarda en
`.local/mobile/deployment.json`. El resultado conectado es
`releases/android/Growth-0.1.0.apk`. En la primera apertura se introduce el
codigo de `.local/mobile/access-code.txt`.

Para regenerar la edicion local, ejecutar `scripts\verify_mobile_data.py` y
despues `scripts\build_android.py --offline`. Esa variante incluye una copia
fija de los datos e informes y no se conecta a la API.

Operacion, permisos, firma e instalacion: [documentacion de Android](../docs/android_app.md).
Las claves, los datos y las herramientas descargadas permanecen en `.local/`.
