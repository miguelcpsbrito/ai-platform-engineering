"""Offline Terraform checker: HCL syntax + argument names/required args against the
AWS provider 6.25 schema + undefined var./local. references. Not a replacement for
`terraform validate` (CI runs that); it is the local gate while no binary is available.
usage: tfcheck.py SCHEMA.json DIR [DIR...]
"""
import json, re, sys, pathlib
import hcl2

S = json.load(open(sys.argv[1]))
META = {'count', 'for_each', 'depends_on', 'provider', 'lifecycle', 'provisioner', 'connection'}
errors = []


def check(body, sch, where):
    if isinstance(body, list):
        for b in body:
            check(b, sch, where)
        return
    if not isinstance(body, dict):
        return
    for k, v in body.items():
        if k in META or k.startswith('__'):
            continue
        if k == 'dynamic':
            for d in v:
                for name, spec in d.items():
                    if name not in sch:
                        errors.append(f'{where}: unknown dynamic block "{name}"')
                    elif sch[name]['block'] is not None:
                        check(spec.get('content', {}), sch[name]['block'], f'{where}.{name}')
            continue
        if k not in sch:
            errors.append(f'{where}: unknown argument "{k}"')
            continue
        blk = sch[k]['block']
        if blk is not None and isinstance(v, list) and v and isinstance(v[0], dict):
            check(v, blk, f'{where}.{k}')
    for k, spec in sch.items():
        if spec['required'] and k not in body and k not in ('region',):
            errors.append(f'{where}: missing required argument "{k}"')


for d in sys.argv[2:]:
    for f in sorted(pathlib.Path(d).rglob('*.tf')):
        if '.terraform' in f.parts:
            continue
        text = f.read_text()
        try:
            doc = hcl2.loads(text)
        except Exception as e:  # syntax error
            errors.append(f'{f}: HCL parse error: {str(e)[:200]}')
            continue
        for kind, key in (('resource', 'resource'), ('data', 'data')):
            for blk in doc.get(key, []):
                for rtype, inst in blk.items():
                    for name, body in inst.items():
                        if not rtype.startswith('aws_'):
                            continue
                        sch = S[kind].get(rtype)
                        if sch is None:
                            errors.append(f'{f}: unknown {kind} type {rtype}')
                            continue
                        check(body, sch, f'{f.name}:{rtype}.{name}')
    # module-level reference check
    for mod in {p.parent for p in pathlib.Path(d).rglob('*.tf') if '.terraform' not in p.parts}:
        text = '\n'.join(p.read_text() for p in mod.glob('*.tf'))
        vars_ = set(re.findall(r'^variable\s+"([^"]+)"', text, re.M))
        locs = set()
        for m in re.finditer(r'^locals\s*{(.*?)^}', text, re.M | re.S):
            locs |= set(re.findall(r'^\s{2}([a-z_][a-z0-9_]*)\s*=', m.group(1), re.M))
        for v in set(re.findall(r'\bvar\.([a-z_][a-z0-9_]*)', text)) - vars_:
            errors.append(f'{mod}: var.{v} used but not declared')
        for v in set(re.findall(r'\blocal\.([a-z_][a-z0-9_]*)', text)) - locs:
            errors.append(f'{mod}: local.{v} used but not declared')
        outs_refs = re.findall(r'\bmodule\.([a-z_][a-z0-9_]*)\.', text)
        mods = set(re.findall(r'^module\s+"([^"]+)"', text, re.M))
        for m_ in set(outs_refs) - mods:
            errors.append(f'{mod}: module.{m_} referenced but not declared')
print('\n'.join(errors) if errors else 'tfcheck: OK')
sys.exit(1 if errors else 0)
