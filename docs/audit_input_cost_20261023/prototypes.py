"""Offline lossless transport/schema prototypes. NOT imported by production."""
from copy import deepcopy
from collections import Counter
import json

def compact(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def delta(old,new):
    if compact(old)==compact(new):return None
    replace={'v':deepcopy(new)}
    if isinstance(old,dict) and isinstance(new,dict):
        changes={k:({'v':deepcopy(v)} if k not in old else delta(old[k],v)) for k,v in new.items()}
        candidate={'o':{k:v for k,v in changes.items() if v is not None}}
        removed=sorted(set(old)-set(new))
        if removed:candidate['d']=removed
    elif isinstance(old,list) and isinstance(new,list):
        changes={str(i):({'v':deepcopy(v)} if i>=len(old) else delta(old[i],v)) for i,v in enumerate(new)}
        candidate={'l':{k:v for k,v in changes.items() if v is not None}}
        if len(old)!=len(new):candidate['n']=len(new)
    else:return replace
    return candidate if len(compact(candidate))<len(compact(replace)) else replace

def apply(base,patch):
    if patch is None:return deepcopy(base)
    if 'v' in patch:return deepcopy(patch['v'])
    if 'o' in patch:
        result=deepcopy(base)
        for k in patch.get('d',[]):del result[k]
        for k,p in patch['o'].items():result[k]=apply(result.get(k),p)
        return result
    result=deepcopy(base)
    length=patch.get('n',len(result))
    result=result[:length]+[None]*max(0,length-len(result))
    for k,p in patch['l'].items():result[int(k)]=apply(result[int(k)],p)
    return result

SNAPSHOTS=[('reference','slim_snapshot'),('sol_reference','slim_snapshot'),
           ('comparison','latest_published_review','slim_snapshot')]

def snapshot_pack(packed):
    result=deepcopy(packed);records=[]
    for parts in SNAPSHOTS:
        parent=result
        try:
            for key in parts[:-1]:parent=parent[key]
            value=parent[parts[-1]]
        except (KeyError,TypeError):continue
        if not isinstance(value,dict) or '$same_as' in value:continue
        patch=delta(packed['slim'],value)
        node={'$snapshot_base':'/slim','$snapshot_delta':patch}
        before,after=len(compact(value)),len(compact(node))
        if after<before:
            parent[parts[-1]]=node
            records.append({'path':'/'+('/'.join(parts)),'before':before,'after':after})
    return result,records

def snapshot_unpack(packed):
    result=deepcopy(packed)
    for parts in SNAPSHOTS:
        parent=result
        try:
            for key in parts[:-1]:parent=parent[key]
            value=parent[parts[-1]]
        except (KeyError,TypeError):continue
        if isinstance(value,dict) and set(value)=={'$snapshot_base','$snapshot_delta'}:
            assert value['$snapshot_base']=='/slim'
            parent[parts[-1]]=apply(result['slim'],value['$snapshot_delta'])
    return result

def schema_nodes(schema):
    if not isinstance(schema,dict):return
    yield schema
    for key in ('properties','$defs','definitions','patternProperties'):
        for child in schema.get(key,{}).values():yield from schema_nodes(child)
    for key in ('anyOf','allOf','oneOf','prefixItems'):
        for child in schema.get(key,[]):yield from schema_nodes(child)
    for key in ('items','additionalProperties','not','if','then','else','contains','propertyNames'):
        child=schema.get(key)
        if isinstance(child,dict):yield from schema_nodes(child)

def factor_schema(schema):
    counts=Counter(compact(v) for v in schema_nodes(schema) if isinstance(v,dict))
    definitions={};name_by_signature={}
    def visit(value,root=False):
        if not isinstance(value,dict):return value
        signature=compact(value)
        repeated=not root and counts[signature]>1 and len(signature)>100 and '$ref' not in value
        if repeated and signature in name_by_signature:
            return {'$ref':'#/$defs/'+name_by_signature[signature]}
        node=deepcopy(value)
        for key in ('properties','$defs','definitions','patternProperties'):
            if key in node:node[key]={k:visit(v) for k,v in node[key].items()}
        for key in ('anyOf','allOf','oneOf','prefixItems'):
            if key in node:node[key]=[visit(v) for v in node[key]]
        for key in ('items','additionalProperties','not','if','then','else','contains','propertyNames'):
            if isinstance(node.get(key),dict):node[key]=visit(node[key])
        if repeated:
            name='audit_'+str(len(definitions)+1)
            name_by_signature[signature]=name;definitions[name]=node
            return {'$ref':'#/$defs/'+name}
        return node
    result=visit(schema,True)
    result.setdefault('$defs',{}).update(definitions)
    return result,list(definitions)

def expand_factored(schema,names):
    definitions=schema.get('$defs',{})
    def visit(value):
        if isinstance(value,list):return [visit(v) for v in value]
        if not isinstance(value,dict):return value
        if set(value)=={'$ref'} and value['$ref'].startswith('#/$defs/audit_'):
            return visit(definitions[value['$ref'].split('/')[-1]])
        return {k:visit(v) for k,v in value.items()}
    result=deepcopy(schema)
    for name in names:del result['$defs'][name]
    if not result['$defs']:result.pop('$defs')
    return visit(result)
