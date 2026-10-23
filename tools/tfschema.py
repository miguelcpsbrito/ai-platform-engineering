"""Extract a Terraform AWS provider argument schema from the cdktf jsii manifest.

Output: {"resource": {"aws_x": SCHEMA}, "data": {...}} where SCHEMA is
{"args": {snake_name: {"required": bool, "block": SCHEMA|None}}}
"""
import json, re, sys

M = json.load(open(sys.argv[1]))
T = M['types']
LINK = re.compile(r'docs/(resources|data-sources)/([a-z0-9_]+)#([a-z0-9_]+)')
SKIP = {'connection', 'count', 'dependsOn', 'forEach', 'lifecycle', 'provider', 'provisioners'}


def struct_fqn(tref):
    """Return the struct fqn behind a property type (direct, array, or union)."""
    if 'fqn' in tref:
        return tref['fqn']
    for k in ('collection',):
        if k in tref:
            return struct_fqn(tref[k]['elementtype'])
    if 'union' in tref:
        for t in tref['union']['types']:
            f = struct_fqn(t)
            if f and not f.endswith('IResolvable'):
                return f
    return None


def schema(fqn, depth=0):
    t = T.get(fqn)
    out = {}
    if not t or depth > 8:
        return out
    for p in t.get('properties', []):
        if p['name'] in SKIP:
            continue
        d = p.get('docs', {})
        m = LINK.search(d.get('summary', '') + ' ' + d.get('remarks', ''))
        name = m.group(3) if m else re.sub(r'(?<!^)([A-Z])', r'_\1', p['name']).lower()
        sf = struct_fqn(p['type'])
        blk = None
        if sf and sf in T and T[sf].get('kind') == 'interface' and T[sf].get('datatype'):
            blk = schema(sf, depth + 1)
        out[name] = {'required': not p.get('optional', False), 'block': blk}
    return out


res = {'resource': {}, 'data': {}}
for fqn, t in T.items():
    if t.get('kind') != 'class':
        continue
    s = t.get('docs', {}).get('summary', '')
    m = re.search(r'docs/(resources|data-sources)/[a-z0-9_]+ (aws_[a-z0-9_]+)', s)
    if not m:
        continue
    kind = 'resource' if m.group(1) == 'resources' else 'data'
    cfg = fqn + 'Config'
    res[kind][m.group(2)] = schema(cfg)
json.dump(res, open(sys.argv[2], 'w'))
print(len(res['resource']), 'resources', len(res['data']), 'data sources')
