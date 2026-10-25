"""Versioned, lossless sharing of repeated maintenance output subschemas.

Only the wire schema changes. Financial validators keep the original contract;
frozen policies without the option and full reports retain their exact schemas.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json

VERSION = 'shared-defs-v1'
MAPPING_CHILDREN = ('properties', '$defs', 'definitions', 'patternProperties')
LIST_CHILDREN = ('anyOf', 'allOf', 'oneOf', 'prefixItems')
SINGLE_CHILDREN = ('items', 'additionalProperties', 'not', 'if', 'then', 'else',
                   'contains', 'propertyNames')


def _wire(value) -> str:
    # Property order is part of the output presentation contract. Do not merge
    # otherwise equal objects with different property/required ordering.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _children(node, visit):
    """Visit schema positions only, never enum/const/default example data."""
    result = deepcopy(node)
    for key in MAPPING_CHILDREN:
        if key in result:
            result[key] = {name: visit(child) for name, child in result[key].items()}
    for key in LIST_CHILDREN:
        if key in result:
            result[key] = [visit(child) for child in result[key]]
    for key in SINGLE_CHILDREN:
        if isinstance(result.get(key), dict):
            result[key] = visit(result[key])
    return result


def share_definitions(schema: dict) -> dict:
    """Share identical ordered nodes and verify exact ordered expansion.

    Names avoid existing definitions. Existing refs and all constraints remain
    literal; only newly created refs are expanded for the equivalence check.
    """
    counts = Counter()
    def count(node):
        if isinstance(node, dict):
            counts[_wire(node)] += 1
            _children(node, count)
        return node
    count(schema)
    existing_names = set(schema.get('$defs', {}))
    definitions, by_signature = {}, {}
    next_index = 1

    def visit(node, *, root=False):
        nonlocal next_index
        if not isinstance(node, dict):
            return deepcopy(node)
        signature = _wire(node)
        repeated = not root and '$ref' not in node and counts[signature] > 1 and len(signature) > 100
        if repeated and signature in by_signature:
            return {'$ref': '#/$defs/' + by_signature[signature]}
        result = _children(node, visit)
        if repeated:
            while 'm' + str(next_index) in existing_names or 'm' + str(next_index) in definitions:
                next_index += 1
            name = 'm' + str(next_index)
            next_index += 1
            definitions[name] = result
            by_signature[signature] = name
            return {'$ref': '#/$defs/' + name}
        return result

    result = visit(schema, root=True)
    if not definitions:
        return result
    result.setdefault('$defs', {}).update(definitions)

    def expand(node):
        if not isinstance(node, dict):
            return deepcopy(node)
        if set(node) == {'$ref'}:
            name = node['$ref'].removeprefix('#/$defs/')
            if node['$ref'] == '#/$defs/' + name and name in definitions:
                return expand(definitions[name])
        return _children(node, expand)

    expanded = deepcopy(result)
    for name in definitions:
        del expanded['$defs'][name]
    if '$defs' not in schema:
        del expanded['$defs']
    if _wire(expand(expanded)) != _wire(schema):
        raise ValueError('maintenance_schema_roundtrip_failed')
    # Definition/ref overhead must never enlarge the wire representation.
    return result if len(_wire(result)) < len(_wire(schema)) else deepcopy(schema)


def output_schema(schema: dict | None, policy: dict, *, kind: str) -> dict | None:
    """Apply only to opted-in new maintenance/repair model contracts."""
    if kind not in ('triage', 'triage_repair') or schema is None:
        return schema
    version = policy.get('maintenance_output_schema')
    if version is None:
        return schema
    if version != VERSION:
        raise ValueError('unsupported_maintenance_output_schema')
    if policy.get('routing_revision', 1) < 41:
        raise ValueError('maintenance_output_schema_requires41')
    return share_definitions(schema)
