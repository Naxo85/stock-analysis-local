# 0001. Layout declarativo de Google Sheets

Estado: `accepted`

## Contexto

El formato de `Mercado` se esta definiendo mediante iteraciones visuales: anchos,
filas, bloques, separadores, colores y reglas condicionales. Si el estado solo
vive en la hoja, un cambio manual accidental puede perder decisiones ya
acordadas y no queda una forma fiable de reconstruirlo.

Ademas, el sistema nuevo debe conservar un unico escritor programatico de
Google Sheets. Introducir scripts independientes para cada ajuste volveria a
repartir la responsabilidad que se quiere centralizar.

## Decision

El estado deseado del layout vive en
`config/market_sheet_layout.json` y se versiona junto al codigo.

El flujo sera equivalente al de una herramienta de infraestructura declarativa:

```text
manifiesto -> validar -> leer estado real -> plan de diferencias -> aplicar
```

La hoja es una proyeccion del manifiesto, no la fuente de verdad del formato.
El modulo `stock_analysis.controller.sheet_layout` valida el manifiesto,
construye el estado deseado, calcula el drift sin modificar la hoja y genera las
operaciones idempotentes de dimensiones para el futuro renderer.

El acceso real a Google Sheets pertenece al unico renderer del sistema. El
comando `stock_analysis.controller.reconcile_sheet` reutiliza ese cliente y esa
identidad: no crea un segundo escritor ni introduce credenciales propias.

## Consecuencias

- Un cambio manual puede detectarse como `before -> after` antes de corregirse.
- Reaplicar el mismo estado es idempotente.
- Las medidas y reglas visuales quedan revisables en Git.
- Los cambios deliberados se hacen primero en el manifiesto y despues se
  aplican a la hoja.
- `plan` lee tablas y fusiones reales sin escribir; `apply` requiere una orden
  explicita, aplica las operaciones y comprueba que el estado converge.
- La version actual reconcilia los tres rangos con nombre, contenido estructural,
  fusiones de titulo, paletas, alineacion y dimensiones al reparar un cambio estructural. La
  deteccion aislada de drift de anchos o altos queda fuera de este primer paso.
