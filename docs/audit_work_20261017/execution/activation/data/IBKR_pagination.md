# Adquisición histórica IBKR: cursor compatible y cobertura acotada

18-Oct-2026. El flujo MRNA falló con terminal hasMore=True: el límite de una página no demostraba cobertura. No se completó ni se publicó ese intento. Las observaciones y pruebas siguientes motivan el cambio local, sin tocar modelos, cartera ni informes congelados.

## Contrato oficial y discrepancia observada

La [referencia oficial EClient](https://interactivebrokers.github.io/tws-api/classIBApi_1_1EClient.html) describe start exclusivo, end inclusivo, formato yyyy-MM-dd HH:mm:ss.0 y límite de 1 a 300 por petición. Es documentación primaria antigua; la [referencia protobuf vigente](https://www.interactivebrokers.com/docs/tws-api/protobuf/historical-news-request) describe otros formatos generales. [EWrapper](https://interactivebrokers.github.io/tws-api/interfaceIBApi_1_1EWrapper.html) y [HistoricalNewsEnd](https://www.interactivebrokers.com/docs/tws-api/protobuf/historical-news-end) transmiten hasMore. Esos contratos no validan por sí solos la interpretación temporal efectiva de este Gateway.

Con MRNA/DJ-N, el formato compacto local devolvió las mismas 300 noticias en distintas ventanas, muchas anteriores a start. Con ISO, el primer argumento actuó como cursor hacia atrás, y end no restringió la ventana observada. Reversar fechas o dejar end vacío produjo historia anterior al cursor. No se afirma que esta conducta sea el contrato oficial ni que todos los entornos/proveedores se comporten igual. Un [reporte de primera mano](https://github.com/ib-api-reloaded/ib_async/issues/108) coincide, pero la decisión se basa en las capturas locales.

## Evidencia real y límites

DJ-N: páginas 300 + 300 + 54, con dos duplicados de frontera, dieron 652 identidades únicas y terminal False real. La segunda y tercera respuesta tardaron 11.000 y 12.188 s. Otras dos respuestas válidas tardaron 10.953 y 10.781 s: el reloj de 10 s podía rechazar respuestas válidas. El filtro local produjo 14 noticias en la ventana 13-Oct 16:17:46 a 18-Oct 07:35:13 UTC; llegar a una noticia anterior a start nunca completó la adquisición.

BRFUPDN: una petición ISO de control devolvió 17 noticias, terminal False, 4.594 s, entre 15-Nov-2024 y 30-Sep-2026; cero en la ventana solicitada. Esto confirma el comportamiento hacia atrás también para ese proveedor en el Gateway consultado. El vacío resultante tiene cobertura del caché disponible, no garantiza cobertura mundial de noticias.

Los timestamps naïve del proveedor siguen interpretándose como UTC conforme al contrato local previo; estas pruebas no verifican independientemente su zona horaria. La primera petición usa end truncado al segundo más un segundo; el payload aplica después el final exacto. Un cambio de semántica temporal remoto podría necesitar otro adaptador.

## Implementación y negativas

Collector final máximo 16 páginas, 300 como máximo por página (respeta límites menores del llamador), 30 s por respuesta y 180 s acumulados; conexión conserva su reloj anterior, normalmente 10 s. Los procesos de noticias tienen un default compartido de 210 s; los overrides explícitos siguen vigentes. El backfill concreto permite 600 s para su único reintento existente y un posible reinicio Gateway de 120 s. La fase prepare sigue en 900 s y ningún reloj de modelo cambia. Solo un terminal False real completa. Las páginas posteriores repiten todo el segundo de frontera y deben incluir las identidades observadas previamente allí; nuevas identidades empatadas se conservan. Conflictos de contenido, orden ascendente, timestamps/identidades ausentes, saturación del segundo, pérdida de frontera, falta de progreso, terminal ambiguo y agotamiento de límites fallan visiblemente. No se decrementa un segundo para saltar empates.

El helper de página conserva el rechazo de hasMore por defecto; su modo interno allow_more solo devuelve status incomplete al collector. Dos terminales del mismo reqId, incluso false→false, son ambiguos y se rechazan. Timeout/error limpian futuros/resultados y el llamador desconecta su instancia privada. No se acepta parcial.

El raw nuevo conserva todas las noticias únicas recibidas en raw_headlines, además de headlines filtradas y contadores separados de antes/después de la ventana. Coverage registra páginas, cursores, límites, tiempos, terminales y duplicados. No se reescribieron los raws históricos de LEU ni se repitió su modelo: sus 146 noticias y filtro vacío no demostraban daño, aunque el raw antiguo no conservaba timestamps descartados.

88 pruebas +16 subcasos pasan contra los archivos finales aplicados, mediante safe_test_runner sin red/procesos externos. Incluyen 28 pruebas de paginación, 8 de relojes/argv efectivos, 2 de recuperación Gateway y 50 de adquisición/datos. La revisión financiera independiente añade siete controles, incluido replay de las tres páginas originales. No se suman denominadores solapados como si fueran observaciones de mercado.

La preparación MRNA nueva superó analistas y noticias con EOF real; sus entradas/modelos congelados permanecen exactos. El control NVDA y sus negativos se detallan debajo. Ninguna ampliación reemplaza terminal False por cruce de fecha.

## Capacidad y reloj: controles negativos conservados

NVDA con 8 páginas/75 s falló por page_limit tras 8×300 observaciones en 38.032 s. Había 2.390 identidades únicas, 10 duplicados y 95 noticias observadas en la ventana; esas 95 NO se admitieron como una ventana completa. Una continuación diagnóstica autorizada añadió seis páginas y llegó al terminal False en la página 14: 4.084 observaciones, 4.065 identidades únicas, 19 duplicados y 95 en ventana. Los tiempos de respuesta sumaron 63.126 s en DOS procesos (64.032 s sumando sus duraciones). Esto justificó medir capacidad16, sin garantizar una petición fresca completa en75 s.

La adquisición fresca16/75 falló: siete páginas completas y timeout en la octava, que recibió solo9.375 s restantes; duración75.391 s. Varias páginas tardaron10–13 s. Este negativo permanece íntegro y motivó180 s total, manteniendo30 s por página y16 páginas. El coste de una única captura no garantiza latencia futura ni cobertura universal de tickers.

Un intento de continuar el prefijo de NVDA terminó antes de cualquier petición de noticias porque el script diagnóstico comparó hash de texto LF con bytes escritos como CRLF en Windows. La continuación v2 verificó la normalización exacta utilizada por el escritor; no alteró originales. No fue corrupción del proveedor ni cobertura aceptada por excepción.

## Coste y alternativa examinada

Acciones y noticias emplean DJ-N en procesos/capturas separados; un backfill puede añadir otra adquisición. Cada captura tiene su propio final temporal y límites: no se afirma deduplicación entre snapshots. La alternativa de reutilizar un raw completo ya recibido para otra ventana podría ahorrar descargas, pero exige vincular identidad, proveedor, tiempo de captura, hash y cobertura sin presentar datos anteriores como recién descargados. No se introdujo una caché compartida sin demostrar esa equivalencia. El parche actual es el ajuste acotado de relojes sustentado por las latencias observadas.

## Adquisición final fresca

La única adquisición nueva final de NVDA con código aplicado e8b16b0/fd7ccf8 y límites180/30/16 completó el caché con terminal False real en14 páginas. Resultado:4.084 observaciones,4.065 identidades únicas,19 duplicados y95 noticias en la ventana13-Oct08:07:07.939048→18-Oct08:07:07.939048UTC;3.970 anteriores y0 posteriores filtradas. La adquisición tardó115.797 s y el proceso116.500 s, dentro de180/210. No reutilizó un prefijo local: pidió las14 páginas. No demuestra caché remoto frío ni latencia garantizada para todos los tickers. Cero escrituras latest, modelos, órdenes y publicaciones financieras.

Los controles negativos8páginas y75 s, la continuación partida y este positivo fresco permanecen separados. No se sustituyeron originales ni se repitieron los canarios financieros.
