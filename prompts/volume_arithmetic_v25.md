Revision25: comprobacion aritmetica de la rubrica existente, sin nueva metodologia.
Cada bloque de nivel incluye volume_calculation: null o {profile_source, reaction_source}.
Selecciona fuentes s exactas de registros de niveles del catalogo, ambas presentes en evidence.
Pueden ser distintas si sustentan el perfil y la reaccion de la zona; el codigo no elige soportes.
Al crear o cambiar Volumen con ambas familias estructuradas disponibles, declara esas fuentes.
El codigo verifica los cinco subcriterios y limites existentes al centro del rango y a la fecha
de la captura de reaccion seleccionada. Perfil OHLCV diario limitado a 3 puntos.
Magnitud: >=1x=1, >=1,5x=2, >=2x=3, >=3x=4; ultimo rebote bajo minimo limita a 2.
No confundas 1,5x con 2x. No redondees antes de comparar.
Null puede heredar rango y Volumen exactamente iguales, sin nueva afirmacion aritmetica.
Sin cuenta estructurada completa, null deja el juicio financiero y los limites existentes.
Datos no disponibles no prueban perdida de respaldo. No inventes campos ni omitas fuentes.
Discrepancias entran en la unica reparacion existente, sin Sol ni retencion automaticos.
Nunca publiques volume_calculation, su auditoria o catalogos internos en Markdown.
