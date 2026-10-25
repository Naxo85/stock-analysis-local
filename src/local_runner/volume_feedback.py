"""Explain volume arithmetic on model-selected frozen sources; never edit a plan."""
from copy import deepcopy

MODE = 'selected-sources-v1'
INSTRUCTION = (
    'Volumen: profile_source y reaction_source son handles s exactos de registros '
    'de niveles seleccionados en evidence. profile_source debe contener '
    'evidence.volume_profile (nearest_level); /slim/volume_profile es el perfil '
    'general, no ese registro. reaction_source debe contener historical_reaction '
    'con direccion aplicable. Calcula cada subcriterio y su suma con la rubrica '
    'vigente; distancia del nodo solo resta proximidad, no vuelve a restar historia. '
    'Los diagnosticos de reparacion explican calculos condicionados a tus fuentes '
    'y rango; no eligen soporte, no prueban vigencia ni autorizan cambiarlo. '
    'No cambies fuentes para obtener una nota deseada ni suprimas evidencia para '
    'eludir la comprobacion. Conserva herencia exacta cuando corresponda.'
)


def instructions(text, policy, kind):
    if kind in ('triage', 'triage_repair') and policy.get('volume_calculation_guidance') == MODE:
        return text + '\n\n' + INSTRUCTION
    return text


def selected_source_feedback(context, response):
    """Enumerate only explicit selections, with conditional arithmetic, not rankings."""
    from src.local_runner.semantic_sources import source_catalog, source_pointer
    from src.local_runner.reaction_direction import applicable_reaction
    from src.local_runner.volume_arithmetic import calculate

    catalog = source_catalog(context)
    result = {}
    for key, level in ((response.get('update') or {}).get('plan') or {}).items():
        if not level or not level.get('range') or not level.get('strength'):
            continue
        selected = set()
        for token in level.get('evidence') or []:
            try:
                selected.add(source_pointer(token, catalog, revision=context.get('routing_revision', 1)))
            except ValueError:
                continue  # The source validator reports unknown selections independently.
        profiles, reactions = {}, {}
        for handle, row in catalog.items():
            pointer, value = row['pointer'], row['value']
            if pointer not in selected or not isinstance(value, dict):
                continue
            if not pointer.startswith(('/slim/levels/', '/reference/slim_snapshot/levels/',
                                       '/sol_reference/slim_snapshot/levels/')):
                continue
            evidence = value.get('evidence') or {}
            profile = evidence.get('volume_profile') or {}
            reaction = evidence.get('historical_reaction') or {}
            if profile.get('status') == 'available':
                profiles[handle] = row
            if reaction.get('status') == 'available' and applicable_reaction(value, pointer, key):
                reactions[handle] = row
        audits = []
        for ph, profile in profiles.items():
            for rh, reaction in reactions.items():
                pointer = reaction['pointer']
                slim = (context['slim'] if pointer.startswith('/slim/') else
                        context[pointer.split('/')[1]]['slim_snapshot'])
                item = {'profile_source': ph, 'reaction_source': rh}
                try:
                    audit = calculate(profile['value']['evidence']['volume_profile'],
                                      reaction['value']['evidence']['historical_reaction'],
                                      level['range'], slim.get('as_of'),
                                      revision=context.get('routing_revision', 1))
                    item['calculation'] = audit
                except ValueError as exc:
                    item['error'] = str(exc)
                audits.append(item)
        result[key] = {
            'range': deepcopy(level['range']),
            'declared_volume': level['strength']['components']['volumen'],
            'declared_sources': deepcopy(level.get('volume_calculation')),
            'selected_profile_sources': {h: row['pointer'] for h, row in profiles.items()},
            'selected_reaction_sources': {h: row['pointer'] for h, row in reactions.items()},
            'conditional_calculations': audits,
        }
    return result
