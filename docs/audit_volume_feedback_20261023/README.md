# Citas y aritmética de Volumen — 23 de octubre de 2026

Incidentes del lote `logs/batch/2026-10-23/14-18-22`, revisión41:

- GEV y ASML citaron `/slim/volume_profile` como `profile_source`. El perfil
  general estaba disponible, pero el cálculo existente requiere el registro de
  nivel seleccionado con `evidence.volume_profile.nearest_level`.
- CLS comenzó con el mismo error de referencia. La única reparación seleccionó
  correctamente `s18` para perfil/reacción, pero declaró8. Los datos seleccionados
  dan proximidad0 + repetición3 + tasa4 + magnitud3 + recencia0 =10, techo15.
  La distancia ya resta proximidad; no autoriza restar otra vez a la historia.

## Corrección local

`volume_calculation_guidance=selected-sources-v1` es una opción explícita de
política para nuevas preparaciones41. Añade una aclaración a mantenimiento y a
su única reparación; full mantiene sus instrucciones. Las políticas congeladas
sin la opción mantienen prefijos/entradas anteriores.

Si hay un error de Volumen, la reparación recibe las referencias estructuradas
que el propio modelo ya seleccionó, con cálculos condicionados a esos registros
y al rango propuesto. Se incluyen aunque el primer error sea otra guarda y el
error de Volumen figure en la lista de incidencias. Un perfil general no se
convierte en perfil de nivel, no se buscan vecinos ni se escogen soportes.

No cambia la fórmula, los pesos, los umbrales, el validador, la autoridad financiera,
el modelo, ITV ni el número de llamadas. El código no aplica puntuaciones ni
modifica respuestas. Una suma correcta sólo supera la comprobación aritmética;
la selección, vigencia y justificación del cambio siguen pendientes de sus guardas.

## Verificación y alcance

`tests/test_volume_feedback.py` reproduce offline los originales CLS/GEV/ASML,
comprueba10 frente8 en CLS, rechazo continuado del perfil general, exclusión de
fuentes no seleccionadas/no disponibles y de reacciones de resistencia, ausencia
de mutación, integración de incidencias y políticas congeladas sin opción.
Las correcciones de referencia propuestas por el diagnóstico no son nuevos
informes aprobados ni validación de calidad financiera de una llamada futura.

Pruebas focalizadas:9 aprobadas y2subcasos (reproducciones reales y negativos);
3regresiones de reparación/transporte aprobadas. Se actualizaron dos expectativas
antiguas de fixtures: modelo vigente Luna6high/Sol6.1high y digest de respuesta
en el recibo simulado. No se cambian modelos ni se relaja autenticación.
Regresión de aritmética, rúbrica34, herencia de zonas y binding:58aprobadas,
3subcasos. Se excluyeron los2replays masivos de archivo histórico de herencia
(ejecución ampliada interrumpida); no se contabilizan como aprobados. Total de
comprobaciones terminadas:70tests y5subcasos. Compilación Python y diff-check pasan.

No se reanuda ni duplica el lote de origen; no se llama a modelos ni se publica
un informe. Los intentos originales conservan sus fallos. Recuperarlos exige
una nueva revisión financiera autorizada; no editar8→10 ni cambiar una cita en
la respuesta firmada y reutilizar el recibo.
