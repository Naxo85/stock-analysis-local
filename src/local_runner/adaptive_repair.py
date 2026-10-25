"""One explicit Luna correction, separate from transport retries and Sol work."""
from copy import deepcopy
import difflib
import hashlib


def repairable_update_error(reason: str) -> bool:
    # Hash/base integrity and source/preflight failures are NOT model repair.
    return (reason.startswith("update_not_allowed_")
            and reason != "update_not_allowed_uncertain_or_critical") or reason in {
        "invalid_update_noop_edit", "invalid_update_empty_patch",
        "invalid_update_ambiguous_or_missing_match", "invalid_update_overlapping_edits",
    }


def repair_context(context: dict, previous: dict, reason: str, *, validation_details=None, candidate_markdown=None, policy=None) -> dict:
    data = deepcopy(context)
    data.pop("triage", None)
    data["maintenance_repair"] = {
        "attempt": 1, "rejection": reason, "previous_response": deepcopy(previous),
        "instruction": (
            "Tu actualización anterior NO se publicó: falló la validación indicada. "
            "Corrige una vez el JSON completo usando el MISMO informe base y fuentes congeladas. "
            "Copia before literalmente (incluidas negritas), omite before==after, no solapes edits. "
            "Revisa todas las métricas de opciones contra su strike/vencimiento y fuente actual; "
            "OI en porcentaje no son contratos. No conserves datos antiguos como si fueran actuales. "
            "Mantén tesis/narrativa/catalizadores/evento/stops protegidos. "
            "Si necesitas aclarar una comparación histórica, usa routine_note fechada, no la reescribas. "
            "No inventes datos ni suprimas evidencia para pasar. Si el cambio excede tu autoridad "
            "o sigue siendo incierto, responde escalate; si faltan datos esenciales, blocked. "
            "Return ONLY the same maintenance JSON schema, no tools."
        ),
    }
    if validation_details:
        data["maintenance_repair"]["validation_details"] = deepcopy(validation_details)
    from src.local_runner.volume_feedback import MODE, selected_source_feedback
    issues = (validation_details or {}).get('issues') or []
    if ((policy or {}).get('volume_calculation_guidance') == MODE and
            (reason.startswith('update_not_allowed_volume_arithmetic:') or
             any(row.get('error', '').startswith('update_not_allowed_volume_arithmetic:') for row in issues))):
        from src.local_runner.adaptive_context import model_context
        data['maintenance_repair']['volume_source_feedback'] = selected_source_feedback(model_context(context), previous)
    if context.get('routing_revision', 1) >= 29:
        data['maintenance_repair']['instruction'] = (
            'Corrige UNA VEZ TODOS los errores con el mismo contrato29 y fuentes congeladas. '
            'Solo entry, ambitious_entry y resistance; sin stops ni objetivo duplicado. '
            'No calcules stops ni ratios con stops antiguos; su ausencia no invalida un soporte. '
            'Tesis, riesgo material, incertidumbre esencial y datos ausentes conservan su autoridad. '
            'Usa las claves s exactas. Separa motivo para cambiar CURRENT del origen de la alternativa. '
            'Contexto de otros campos del mismo plan no equivale a evidencia tecnica actual. '
            'Puedes retirar una propuesta injustificada, no ocultar un riesgo ni forzar retain. '
            'Cada texto no-null de plan_explanation es {text,review}; null hereda texto y fecha. '
            'Completa cobertura pendiente real. Notas breves, auditoria interna; no copies JSON. '
            'Aplica rubrica/volume_calculation y direccion de reaccion correctas sin repuntuar por '
            'recalibracion o por una reparacion de referencias. Evalua vigencia con price_history '
            'sin regla automatica de porcentaje/ATR/cierres ni gracia de cinco sesiones. '
            'Conserva penetraciones marginales viables, retira soportes perdidos; sin obligar '
            'a inventar alternativas. Una sola resistencia relevante para el rebote, no un '
            'techo remoto por fuerza absoluta. No escalada por un mero error contractual. '
            'Noticias publicas solo con permiso explicito. Devuelve solo el mismo schema29.')
        if context.get('routing_revision', 1) >= 30:
            data['maintenance_repair']['instruction'] += (
                ' La revision30 conserva ese schema financiero. Aplica los presupuestos '
                'editoriales congelados a textos publicos nuevos/autorizados: motivos de '
                'plan 2 frases/45 palabras; Setup 1/20; conclusion y nota 2/35. '
                'Justificacion de cambios, alternativas y busquedas van en auditoria interna, '
                'no en el informe. Conserva riesgos y limites relevantes sin repetir reglas '
                'del sistema. No reescribas texto protegido por estilo ni repares longitud '
                'con otra llamada, truncado o escalada.')
        if context.get('routing_revision', 1) >= 31:
            data['maintenance_repair']['instruction'] += (
                ' Evidencia31: usa option_details solo dentro de vencimientos muestreados; '
                'expiration es dominante, no exclusivo. No confundas cobertura nueva con '
                'respaldo nuevo o desconocido con deteriorado. No dupliques penalizaciones '
                'por liquidez ausente en estructura/confluencia/durabilidad sin causa propia. '
                'Conserva la rubrica y corrige errores demostrados sin inflar puntuaciones. '
                'Totales y categorias los deriva el renderer: no los repitas en factors.')
        if context.get('routing_revision', 1) >= 32:
            data['maintenance_repair']['instruction'] += (
                ' Reader32: no bloques publicos de tesis/setup ni conclusion repetida. '
                'reader_review solo selecciona visibilidad mediante IDs c del CURRENT; '
                'null hereda. No elimina hechos ni memoria, no cambia fechas/ITV, no '
                'reescribe narrativa protegida ni sustituye cobertura o riesgo. '
                'Conserva riesgos vigentes aunque antiguos; sin corte de edad/nota.')
        if context.get('routing_revision', 1) >= 33:
            data['maintenance_repair']['instruction'] += (
                ' Reader33 sustituye la seleccion binaria por driver/background/covered '
                'para cada cID: mecanismo actual explicito, brief publico compacto y '
                'covered_by apuntando al driver que integra el mismo tema. No inventario '
                'de noticias ni contexto historico mostrado solo porque siga siendo cierto. '
                'No cambies hechos/fechas/riesgo/ITV ni introduzcas novedades por esta via. '
                'La seleccion editorial no causa otra llamada ni escalada.')
        if context.get('routing_revision', 1) >= 34:
            data['maintenance_repair']['instruction'] += (
                ' Rubrica34: distancia del nodo solo afecta proximidad, no los techos '
                'de historia; conserva controles de muestra/recencia/magnitud y perfil diario. '
                'rubric_change permite solo el delta exacto de Volumen sobre el mismo rango, '
                'con fuentes actuales completas y decision anterior citada. No es noticia '
                'nueva ni prior_error, no autoriza otros componentes, niveles o texto protegido. '
                'No hay cuota de visibilidad ni repuntuacion automatica; puedes heredar '
                'el juicio fechado con calculo null. Una reparacion, sin llamada full adicional.')
        if context.get('routing_revision', 1) >= 35:
            instruction = data['maintenance_repair']['instruction']
            instruction = instruction.replace('contrato29', 'contrato35').replace('schema29', 'schema35')
            instruction = instruction.replace('Solo entry, ambitious_entry y resistance; sin stops ni objetivo duplicado.',
                'Solo entry y ambitious_entry; no calcules ni mantengas resistencia, stops u objetivos.')
            instruction = instruction.replace('Una sola resistencia relevante para el rebote, no un techo remoto por fuerza absoluta. ', '')
            instruction = instruction.replace('La revision30 conserva ese schema financiero.', 'El schema35 contiene solo las dos compras.')
            data['maintenance_repair']['instruction'] = instruction
        if context.get('routing_revision', 1) == 36:
            data['maintenance_repair']['instruction'] += (
                ' Vigencia36: support_validity_review aporta una extension inferior '
                'estimada con fuentes actuales para colorear; no stop ni nueva guarda. '
                'Puede ser null; no rescates soportes perdidos ni inventes margenes.')
        if context.get('routing_revision', 1) >= 37:
            data['maintenance_repair']['instruction'] += (
                ' Vigencia37: support_validity_review estima prospectivamente desde '
                'estructura y reacciones con fuentes actuales exactas y rango vinculado, '
                'sin exigir rebote actual ni test exactamente en el limite. Resuelve '
                'extensiones ausentes si el respaldo se puede localizar, incluso en retain. '
                'Limite null solo por carencia estructural esencial concreta; item null '
                'hereda la extension conocida de un rango exacto sin cambios. Una penetracion '
                'juzgada viable debe ser coherente con su extension estimada. '
                'No limites automaticos, numero inventado, nuevo precio de entrada ni '
                'escalada por este dato visual.')
        if context.get('routing_revision', 1) >= 38:
            data['maintenance_repair']['instruction'] += (
                ' Seleccion38: separa origen, vigencia, fortaleza y seleccion. '
                'Una sola defensa, poca confluencia o falta de rebote reciente no '
                'vetan por si solos un soporte inferior objetivamente identificado. '
                'Una alternativa inferior apta puede ser Entrada; Washout es otro '
                'bloque distinto, no obligatorio. No inventes soporte en un minimo '
                'movil ni rescates papeles perdidos o conserves zonas sobre precio '
                'solo por ausencia de ruptura. Motivo null-range explica ausencia '
                'de origen o descarte concreto, no inexistencia por nota baja. '
                'Misma rubrica, fuentes, autoridad y change_review; sin relleno '
                'automatico, nuevas guardas, llamadas o reparacion por estilo.')
        if context.get('routing_revision', 1) >= 39:
            data['maintenance_repair']['instruction'] += (
                ' Origenes39: levels.option_origins observa los strikes citados '
                'por CURRENT fuera del TOP con los mismos vencimientos muestreados. '
                'Consulta el detalle actual; no confundas fuera del TOP con ausencia, '
                'not_observed acotado con desaparicion global, OI cero con dato '
                'ausente ni unavailable con deterioro. No es aprobacion del soporte, '
                'novedad de mercado ni motivo automatico para cambiar o escalar.')
        if context.get('routing_revision', 1) >= 40:
            data['maintenance_repair']['instruction'] = data['maintenance_repair']['instruction'].replace('contrato35', 'contrato40').replace('schema35', 'schema40')
            data['maintenance_repair']['instruction'] += (
                ' Contrato40: Washout activo es un bloque distinto estrictamente inferior '
                'a Entry activo, sin solapamiento ni separacion minima porcentual/ATR. '
                'previous_evidence puede citar el bloque CURRENT opuesto para heredar '
                'su rango y Volumen exactos con calculo null, sin duplicar esa cita. '
                'No repuntues por reparar referencias. plan_explanation null no exige '
                'certificado vacio: revisa las dependencias y justifica cada texto '
                'realmente editado. El bloque editado es la unica autoridad de su motivo. '
                'Conserva origen actual, cambio material, fuentes, riesgo y autoridad.')
        if context.get('routing_revision', 1) >= 41:
            data['maintenance_repair']['instruction'] += (
                ' Contrato41: material_improvement admite conocimiento nuevo material '
                'del mismo soporte; vincula la premisa anterior limitada, la observacion '
                'actual aplicable y el componente afectado sin inventar cambio de mercado '
                'o error pasado. No vuelvas a premiar evidencia ya incorporada. '
                'levels.support_origins observa identidades CURRENT de suelo/gap fuera '
                'de ranking/distancia; disponible no significa viable ni obliga a conservar. '
                'Ausencia acotada/ambiguedad no prueba perdida. Distingue las consecuencias '
                'propias de cada componente y el aporte independiente de confluencia; '
                'unknown no equivale a deterioro. No hay puntos automaticos, cambio de '
                'pesos, cuota visible ni autoridad nueva por esta aclaracion.')
        return data
    if context.get('routing_revision', 1) >= 21:
        data['maintenance_repair']['instruction'] = (
            'Corrige una sola vez todos los errores con las mismas fuentes. Usa el schema21: '
            'cada texto no-null de plan_explanation es {text, review} con justificacion propia; '
            'change_review.plan_explanation es null. Null conserva literalmente cada motivo '
            'y su fecha: no sustituyas motivos validos por comentarios de que se conservan. '
            'Consulta comparison.text_origins: compara un supuesto error con la observacion '
            'original del parrafo, no con la fecha/precio posterior del informe contenedor. '
            'Fecha desconocida no es prueba de error. Compara tambien ultima revision real. '
            'reason/assessments son internos; public_note={text,review} solo si hace falta '
            'publicar algo, null conserva la nota. No conviertas A->B historico en A actual. '
            'Corrige solo campos afectados, sin mover precios, puntuaciones o protecciones '
            'por errores de formato/fuente. Fuentes s exactas; no hashes ni JSON en prosa. '
            'Completa cobertura real, usa memoria y distingue snippet de pagina leida. '
            'Puedes retirar el cambio; riesgo/tesis/stop protegido o incertidumbre esencial '
            'siguen Sol, dato esencial ausente blocked. No hay segunda correccion ni '
            'escalada por fallo meramente contractual. Noticias web solo si habilitadas.')
        if context.get('routing_revision', 1) >= 22:
            data['maintenance_repair']['instruction'] = data['maintenance_repair']['instruction'].replace('schema21', 'schema22')
            data['maintenance_repair']['instruction'] += (
                ' Entrada/Washout son compras en soporte vigente, no recuperaciones de '
                'zonas perdidas. Una perforacion marginal no prueba ruptura. Evalua '
                'vigencia antes de continuidad y alternativas inferiores. Sin soporte '
                'comprable puedes retirar entry y/o ambitious_entry con bloque range=null, '
                'strength=null, motivo y evidencia; bloque null completo hereda. Retirar '
                'una zona perdida no exige encontrar otra mejor ni comprar un informe '
                'completo por si solo. Riesgos/stops/autoridad siguen protegidos.')
        if context.get('routing_revision', 1) >= 23:
            data['maintenance_repair']['instruction'] += (
                ' Una aplicacion erronea de la rubrica tecnica vigente puede corregirse '
                'en mantenimiento aunque la firmara Sol. No es cambiar metodologia. '
                'Revisa comparison.volume_rubric: techos, no puntuaciones impuestas. '
                'observed_origins son mediciones actuales de anclas exactas, no prueba '
                'automatica de soporte defendido. Sigue la politica23 congelada.')
        if context.get('routing_revision', 1) >= 24:
            data['maintenance_repair']['instruction'] += (
                ' Aclaracion24: stop de gestion ausente solo es aplicable con owned=false '
                'y ambas entradas ausentes. Mantenimiento lo hereda, no edita stops. '
                'Reactivar una compra sin stop aplicable exige revision de riesgo Sol; '
                'no inventes nivel ni sustituyas automaticamente por el estructural.')
        if context.get('routing_revision', 1) >= 25:
            data['maintenance_repair']['instruction'] += (
                ' Rubrica25: volume_calculation selecciona profile_source/reaction_source '
                'exactos del catalogo y presentes en evidence. Calcula al centro de la zona; '
                'magnitud >=1x=1, >=1.5x=2, >=2x=3, >=3x=4. Corrige la cuenta '
                'o retira una repuntuacion injustificada sin alterar niveles/riesgos. '
                'Null hereda Volumen sin cambios o declara calculo no estructurado.')
        if context.get('routing_revision', 1) >= 26:
            data['maintenance_repair']['instruction'] += (
                ' Revision26: comparison.historical_measurements distingue recalibracion '
                'de evidencia historica nueva; un cambio de estadistica no demuestra '
                'otra defensa fallida. Justifica materialidad o retira la repuntuacion, '
                'sin ocultar errores aritmeticos reales ni riesgo. Un stop historico '
                'en plan sin posicion ni compras es una pregunta de riesgo, no '
                'escalada automatica ni permiso para reactivar compras.')
        if context.get('routing_revision', 1) >= 27:
            data['maintenance_repair']['instruction'] += (
                ' Revision27: rebotes de soporte no son rechazos de resistencia '
                'aunque coincidan en precio. Solo selecciona reacciones aplicables '
                'al papel puntuado; sin pareja aplicable, volume_calculation=null '
                'con limites y explicacion financiera, sin inventar ni omitir fuentes.')
        if context.get('routing_revision', 1) >= 28:
            data['maintenance_repair']['instruction'] += (
                ' Revision28: evalua primero vigencia de cada compra con price_history '
                'y cotizacion separada; un test pendiente de cinco sesiones no obliga '
                'a conservar ni prueba ruptura. Fortaleza historica o ausencia de '
                'fallo registrado no bastan para vigencia actual. Conserva soportes '
                'viables con perforacion marginal; retira roles perdidos con evidencia, '
                'sin rescatar entradas con una futura recuperacion. No borres por '
                'porcentaje/distancia ni fuerces alternativas. Corrige juicio previo '
                'erroneo con prior_error; datos esenciales ausentes siguen blocked. '
                'Nota publica breve: cambio y consecuencia, detalle en auditoria; '
                'no reescribas narrativa protegida ni pagues Sol por estilo.')
        return data
    if context.get('routing_revision', 1) >= 20:
        data['maintenance_repair']['instruction'] = (
            'Corrige UNA VEZ todos los errores indicados con el mismo informe y fuentes. '
            'El comentario de tu trabajo va SOLO en reason/assessments; no se publica. '
            'public_note=null significa no editar la nota. Si hace falta editarla, devuelve '
            'juntos text y review dentro de update.public_note; no existe routine_note en la respuesta. '
            'Plan_explanation es parcial: null en cada texto sin cambios, el runner hereda '
            'contenido y fecha; no copies todo ni borres fundamentos con cadenas vacias. '
            'Corrige TODOS los motivos realmente afectados, no solo conclusion. '
            'prior_error puede probarse con la referencia autenticada para cualquier texto; '
            'una transicion historica de A a B no afirma que A sea el precio actual. '
            'No borres comparaciones fechadas validas ni atribuyas a hoy frases antiguas. '
            'Niveles/facts usan claves s1,s2 del catalogo; revisiones de texto usan pointers '
            'exactos. Un error de referencia no autoriza repuntuar ni investigar todo el negocio. '
            'Mantén rubrica, tesis, stops y riesgos protegidos. Ante cambio estructural/riesgo '
            'o investigacion esencial pendiente, escalate; dato tecnico esencial ausente, blocked. '
            'Retira ediciones injustificadas; no fuerces retain si existe riesgo. '
            'Completa solo agenda pendiente real; lista vacia no requiere inventar IDs. '
            'Usa memoria de noticias y ultima revision. Investigacion no obliga a publicar. '
            'No hay gates de frases/puntuacion. Devuelve el schema20 completo. '
            'Solo se permite consulta publica de noticias si esta explicitamente habilitada.')
        return data
    if context.get('routing_revision', 1) >= 9:
        data['maintenance_repair']['instruction'] = (
            'Corrige UNA VEZ los datos JSON indicados usando el MISMO informe y fuentes. '
            'No copies Markdown ni before/after. No hay comprobación de frases o puntuación. '
            'El runner calcula precio/fecha/estado/porcentajes/total/categoría y nivel anterior. '
            'Revisa rangos, transición numérica, componentes de fuerza y los pointers de fuentes. '
            'Mantén la rúbrica y la autoridad: no inventes niveles/fuentes ni ocultes riesgos. '
            'Tesis/eventos/catalizadores/stops no se pueden cambiar con Luna. '
            'Si no puedes corregir datos financieros con respaldo, escalate; fuente esencial fallida, blocked. '
            'Return ONLY the same semantic maintenance JSON schema. '
            'No tools except explicitly permitted public-news lookup.'
        )
        if context.get('routing_revision', 1) >= 10:
            data['maintenance_repair']['instruction'] = (
                'Corrige UNA VEZ TODOS los problemas de validation_details, sin rehacer las decisiones válidas. '
                'Selecciona las fuentes exactas por su source_catalog ID; no cuentes posiciones de arrays '
                'ni inventes el vecino de un índice. Puedes citar objetos completos: código copia sus valores. '
                'No devuelvas transition: se deriva de rangos anteriores/actuales. '
                'comparison es contexto auxiliar, nunca fuente técnica independiente. '
                'Un error de referencia no es investigación fundamental pendiente ni autoriza cambiar stops/tesis. '
                'Mantén niveles y puntuaciones respaldados; corrige sólo las decisiones financieras que '
                'realmente carezcan de origen vigente. Si no existe una continuación segura, escalate; '
                'fuente esencial fallida, blocked. No ocultes riesgos ni inventes fuentes. '
                'Return ONLY the same semantic maintenance JSON schema. '
                'No tools except explicitly permitted public-news lookup.'
            )
        if context.get('routing_revision', 1) >= 12:
            data['maintenance_repair']['instruction'] += (
                ' Selecciona SOLO claves cortas s1,s2,... enumeradas por el schema de corrección, '
                'nunca hashes/pointers/subcampos. Null hereda cada bloque no afectado: '
                'no reoptimices ni repuntúes el resto del plan por reparar una referencia. '
                'Mantén ambos campos Setup null si no requieren un cambio demostrado.'
            )
        if context.get('routing_revision', 1) >= 14:
            data['maintenance_repair']['instruction'] += CHANGE_REVIEW_REPAIR
        if context.get('routing_revision', 1) >= 16:
            data['maintenance_repair']['instruction'] += (
                ' Un rechazo de scope/pointer no cambia el dato financiero: no repuntúes '
                'componentes ni muevas rangos por ese rechazo. Sólo una equivocación '
                'financiera demostrada independientemente justifica esos cambios. '
                'Consulta news.prior_reviews y las notas conservadas; no redescubras '
                'noticias ya aclaradas ni confundas vencimiento dominante con exclusivo.'
            )
        if context.get('routing_revision', 1) >= 18:
            data['maintenance_repair']['instruction'] += (
                ' Revisa news.review_agenda: agrupa los items pendientes con una '
                'valoracion concreta y el estado del evento vencido, sin inventar '
                'riesgo ni forzar un cambio de informe. Si retiras una propuesta '
                'y conservas el informe, completa igualmente esa cobertura. '
                'Si cambias rangos, plan_explanation reconcilia los motivos y la '
                'conclusion con el plan resultante; no mueve stops ni otros niveles. '
                'Compara tambien con comparison.latest_published_review. Un error '
                'de cobertura/coherencia no es por si mismo motivo para Sol.')
        if context.get('routing_revision', 1) >= 19:
            data['maintenance_repair']['instruction'] += (
                ' Si la agenda no tiene items pendientes no debes inventarlos: '
                'news_review=[] es valido; grupos vacios no cubren noticias. '
                'No inventes e1 para un evento futuro fuera de la agenda. '
                'Puedes corregir una contradiccion ya publicada SIN mover rangos: '
                'plan_explanation con change_review.plan_explanation de prior_error '
                'y fuentes concretas; reconcilia todos los motivos afectados. '
                'Investigar una noticia no obliga a publicar una nota. Si no '
                'cambia una decision, un riesgo relevante o corrige un error '
                'real del informe, conserva y registra solo la evaluacion. '
                'Conservar numeros no permite ignorar una perdida de soporte '
                'ni transformar una entrada en otra estrategia sin evaluarla. '
                'Juicio historico y viabilidad actual no son equivalentes; '
                'no fuerces retain por reparar cobertura/coherencia.')
        return data
    if context.get('routing_revision', 1) >= 8:
        baseline = (context.get('reference') or {}).get('analysis_markdown') or ''
        # Check ALL proposed edits, not just the first exception. Suggestions
        # are feedback only, never fuzzy-applied or saved over original receipts.
        data['maintenance_repair']['patch_source_check'] = [
            {'edit_index': index, 'occurrences': baseline.count(edit.get('before', '')),
             'before_sha256': hashlib.sha256(str(edit.get('before', '')).encode()).hexdigest(),
             'source_lines': ([] if baseline.count(edit.get('before', '')) == 1
                              else difflib.get_close_matches(str(edit.get('before', '')), baseline.splitlines(), n=3, cutoff=.5))}
            for index, edit in enumerate(previous.get('edits') or [])]
        data['maintenance_repair']['instruction'] = (
            'Repara la propuesta, no vuelvas a investigar el negocio por un error mecánico. '
            'MISMO informe y datos permiten corregir Estado actual, porcentaje, fecha o copia literal; '
            'que las fuentes no hayan cambiado NO impide corregir tu respuesta. '
            'Revisa TODOS los edits y motivos de continuidad, no solo la primera excepción. '
            'Copia before del informe base sin parafrasearlo, incluso al reusar la propuesta anterior. '
            'El runner deriva precio heredado, estado posicional y porcentajes de los niveles elegidos; '
            'no cambia niveles, stops, fuerza ni conclusiones. '
            'Para cada nivel NUEVO explica su origen y el nivel anterior exacto en Motivo. '
            'Para soporte opcional ausente evalúa los soportes inferiores reales y su rúbrica. '
            'Una URL no observada exige verificarla con las herramientas públicas permitidas o retirar '
            'la afirmación sin respaldo, no inventar fuentes ni declarar inocuo el evento. '
            'Una consulta web resuelta no es investigación esencial pendiente. '
            'Mantén las protecciones: riesgo real, stop que requiere cambio o incertidumbre ESENCIAL '
            'exigen Sol; fuente esencial fallida, blocked. '
            'Return ONLY the same maintenance JSON schema. No tools except explicitly permitted public-news lookup.'
        )
        if candidate_markdown is not None:
            from src.common.analysis_validator import (
                _extract_line_value, _parse_strength_breakdown, extract_support_strength,
                support_strength_category,
            )
            import re
            checks = []
            for label in ('Entrada', 'Entrada ambiciosa', 'Resistencia'):
                strength = _extract_line_value(candidate_markdown, 'Fortaleza de ' + label)
                breakdown = _parse_strength_breakdown(_extract_line_value(candidate_markdown, 'Desglose de ' + label))
                declared = re.match(r'\s*(\d+)\s*/\s*100', strength)
                if strength and extract_support_strength(candidate_markdown, label) is None:
                    total = sum(breakdown.values()) if breakdown else None
                    checks.append({'label': label, 'declared': strength, 'components': breakdown,
                        'declared_total': int(declared[1]) if declared else None,
                        'component_sum': total,
                        'category_from_sum': support_strength_category(total) if total is not None else None,
                        'factors': _extract_line_value(candidate_markdown, 'Factores de ' + label),
                        'instruction': 'Choose supported component scores under the SAME rubric, then make total/category consistent. Do not change a component just to fit the old total.'})
            data['maintenance_repair']['strength_checks'] = checks
    if context.get('routing_revision', 1) >= 15:
        data['maintenance_repair']['instruction'] += (
            ' Revisa tambien update.change_review para Setup/conclusion/routine_note; '
            'mismo criterio de materialidad que niveles. Retira cambios sin fundamento, '
            'no cambies su etiqueta para pasar. Una contradiccion fundamental/estructural '
            'requiere Sol aunque la pongas en conclusion/nota; scope y risk deben coincidir. '
            'El historial maintenance_handoff contiene propuestas RECHAZADAS, no evidencia verificada.')
    return data


CHANGE_REVIEW_REPAIR = (
    ' Antes de buscar otra zona, revisa por separado POR QUE cambiar la anterior. '
    'Que no aparezca en un listado no demuestra invalidacion; comprueba todos los '
    'registros suministrados. Una alternativa valida no justifica abandonar otra. '
    'change_review compara fuentes del informe CURRENT con fuentes actuales y '
    'explica el cambio real, error demostrado o mejora material. No reclasifiques '
    'missing_from_snapshot como backing_changed para pasar. Puedes retirar la '
    'edicion injustificada (bloque null) y retain si no hay otro cambio ni riesgo; '
    'no se fuerza esa decision. Si falta evidencia tecnica esencial, blocked, '
    'no Sol por omision de lista. No es obligatorio inventar entrada ambiciosa '
    'por existir algun soporte inferior; juzga si realmente es apto. '
    'Los riesgos estructurales y stops protegidos siguen siendo trabajo Sol.')
