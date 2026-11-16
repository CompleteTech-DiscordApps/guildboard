#!/usr/bin/env python3
"""Validate the retained license inventory; assessment is not legal clearance."""
import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys

MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
HEX = re.compile(r'^[0-9a-f]{64}$')
STATUS = {'interpreted', 'unresolved'}
# Section decision identity, subject to fresh independent review; not legal approval.
# Changes to the catalog require an explicit code update and fresh review.
DECISION_CATALOG_SHA256 = '462025adc40459385adf50df0be7b647ec0669af09d0b4ec2ac6ed20302bc1bc'

def decision_catalog_digest(inventory):
    # Scope and coverage are assessed separately; every other field, including
    # unknown fields, belongs to the bounded decision and evidence catalog.
    catalog = {k: v for k, v in inventory.items()
               if k not in ('distribution_scope', 'distribution_coverage')}
    return digest(json.dumps(catalog, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8'))

class Invalid(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise Invalid(message)

def path_parts(path):
    require(isinstance(path, str) and path and not path.startswith('/') and '\\' not in path and '\x00' not in path, 'invalid relative path')
    parts = path.split('/')
    require(all(p not in ('', '.', '..') for p in parts), 'invalid relative path: ' + path[:200])
    return parts

def digest(data):
    return hashlib.sha256(data).hexdigest()

def pairs(items):
    result = {}
    for k, v in items:
        require(k not in result, 'duplicate JSON key: ' + k[:200])
        result[k] = v
    return result

def identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

class Reader:
    """Descriptor traversal detects observable replacement, not hostile transient swaps.

    A stable checkout is still required: an attacker can swap and restore entries
    between observations, and filesystem snapshots are outside this API's scope.
    """
    def __init__(self, root):
        root = os.fspath(root)
        require(isinstance(root, str) and root and '\x00' not in root, 'invalid root')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
        self.chain = []
        fd = os.open('/' if os.path.isabs(root) else '.', flags)
        self.chain.append((None, None, fd, None))
        try:
            for part in root.split('/'):
                if part in ('', '.'): continue
                require(part != '..', 'invalid root ancestor')
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISDIR(before.st_mode), 'unsafe root ancestor')
                child = os.open(part, flags, dir_fd=fd)
                self.chain.append((fd, part, child, identity(before)))
                require(identity(os.fstat(child)) == identity(before), 'root changed')
                fd = child
            self.fd = fd
            self.total = 0
            self.hashes = {}
            self._check_chain(self.chain)
        except BaseException:
            self.close()
            raise
    @staticmethod
    def _check_chain(chain):
        for parent, name, fd, expected in chain:
            if parent is not None:
                require(identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == expected
                        and identity(os.fstat(fd)) == expected, 'directory changed')
    def close(self):
        for _, _, fd, _ in reversed(self.chain): os.close(fd)
        self.chain = []
    def read(self, path, limit=MAX_FILE):
        parts = path_parts(path)
        chain = []
        fd = self.fd
        try:
            self._check_chain(self.chain)
            for part in parts[:-1]:
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISDIR(before.st_mode), 'unsafe directory: ' + path)
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                chain.append((fd, part, nxt, identity(before)))
                require(identity(os.fstat(nxt)) == identity(before), 'directory changed: ' + path)
                fd = nxt
            before = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'unsafe or oversized file: ' + path)
            f = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                require(identity(os.fstat(f)) == identity(before), 'file changed: ' + path)
                chunks = []; size = 0
                while True:
                    chunk = os.read(f, min(65536, limit + 1 - size))
                    if not chunk: break
                    chunks.append(chunk); size += len(chunk)
                    require(size <= limit and self.total + size <= MAX_TOTAL, 'read budget exceeded: ' + path)
                require(identity(os.fstat(f)) == identity(before) and size == before.st_size
                        and identity(os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)) == identity(before), 'file changed: ' + path)
                self._check_chain(chain)
                self._check_chain(self.chain)
                data = b''.join(chunks); self.total += size
                self.hashes[path] = digest(data)
                return data
            finally: os.close(f)
        finally:
            for _, _, opened, _ in reversed(chain): os.close(opened)
    def json(self, path, limit=MAX_FILE):
        return json.loads(self.read(path, limit).decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(Invalid('invalid JSON constant')))

def valid_status(obj):
    require(isinstance(obj, dict) and obj.get('status') in STATUS and isinstance(obj.get('rationale'), str) and bool(obj['rationale'].strip()) and isinstance(obj.get('obligations'), list) and all(isinstance(x, str) and x.strip() for x in obj['obligations']), 'malformed classification')

def _validate(root):
    r = Reader(root)
    try:
        inv = r.json('docs/licenses/inventory.json', 2 * 1024 * 1024)
        require(isinstance(inv, dict) and inv.get('schema_version') == 3 and inv.get('status') in ('incomplete-not-clearance', 'complete-not-clearance'), 'invalid inventory schema or status')
        require(decision_catalog_digest(inv) == DECISION_CATALOG_SHA256, 'section decision catalog identity mismatch')
        pkg = r.json('package.json'); lock = r.json('package-lock.json')
        packages = lock['packages']; require(isinstance(packages, dict) and all(isinstance(k, str) and isinstance(v, dict) and type(v.get('link', False)) is bool for k, v in packages.items()), 'invalid lock packages')
        workspaces = pkg.get('workspaces', [])
        if isinstance(workspaces, dict): workspaces = workspaces.get('packages')
        require(isinstance(workspaces, list) and all(isinstance(x,str) and re.fullmatch(r'[A-Za-z0-9_.-]+/\*', x) for x in workspaces), 'unsupported workspace configuration')
        workspace_paths = {p for p in packages if p and any(p.startswith(w[:-1]) and '/' not in p[len(w)-1:] for w in workspaces)}
        inputs = {'package.json', 'package-lock.json'} | {p + '/package.json' for p in workspace_paths}
        anchors = inv['input_sha256']; require(isinstance(anchors,dict) and set(anchors) == inputs, 'input anchor set mismatch')
        for p in sorted(inputs):
            path_parts(p)
            if p not in r.hashes: r.read(p)
            require(anchors[p] == r.hashes[p], 'input hash mismatch: ' + p)
        components = inv['components']; require(isinstance(components,dict), 'invalid components')
        external = {p for p,v in packages.items() if 'node_modules/' in p and isinstance(v,dict) and not v.get('link',False)}
        require(set(components) == external, 'lock component set mismatch')
        selected = set()
        for p,c in components.items():
            path_parts(p); entry = packages[p]
            require(isinstance(c,dict), 'invalid component: '+p)
            name = p.rsplit('node_modules/',1)[-1]
            require(c['actual_package_name'] == entry.get('name', name) and c['version'] == entry.get('version'), 'component identity mismatch: '+p)
            a = c['artifact']; require(a['url'] == entry.get('resolved') and a['integrity'] == entry.get('integrity'), 'artifact mismatch: '+p)
            sri = a['integrity'].split('-',1); require(len(sri)==2 and sri[0] in ('sha256','sha384','sha512'), 'invalid integrity: '+p)
            raw = base64.b64decode(sri[1], validate=True); require(len(raw) == {'sha256':32,'sha384':48,'sha512':64}[sri[0]], 'invalid integrity length: '+p)
            valid_status(c['classification']); effective = c.get('classification_overlay',c['classification']); valid_status(effective)
            require(c.get('effective_classification') == effective, 'effective classification mismatch: '+p)
            require(isinstance(c['notices'],list), 'invalid notices: '+p)
            for n in c['notices']:
                path_parts(n['installed_path']); path_parts(n['archive_path'])
                require(HEX.fullmatch(n['sha256']) and type(n['bytes']) is int and n['bytes'] >= 0, 'invalid notice metadata')
                key = (p,n['archive_path'],n['sha256'],n['bytes']); require(key not in selected, 'duplicate selected notice'); selected.add(key)
        retained = inv['retained_notices']; require(isinstance(retained,list), 'invalid retained notices')
        seen = set(); bound = set(); retained_hashes = set()
        for n in retained:
            h=n['sha256']; p=n['path']; require(isinstance(h,str) and HEX.fullmatch(h) and p == 'docs/licenses/notices/'+h+'.txt' and h not in seen, 'invalid or duplicate retained notice')
            seen.add(h); data=r.read(p); require(type(n['bytes']) is int and len(data)==n['bytes'] and digest(data)==h, 'retained notice mismatch: '+p)
            retained_hashes.add(h); sources=n['sources']; require(isinstance(sources,list) and sources, 'missing notice sources')
            matched=False
            for s in sources:
                kind=s['kind']
                if kind == 'archive_member':
                    lp=s['lock_path']; member=s['member']; path_parts(member); path_parts(s['archive_path'])
                    require(lp in components, 'unknown notice source component')
                    a=components[lp]['artifact']; require(s['url']==a['url'] and s['integrity']==a['integrity'] and s['archive_sha256']==a['archive_sha256'], 'notice source artifact mismatch')
                    key=(lp,member,h,len(data)); require(key in selected, 'unknown archive notice binding'); bound.add(key); matched=True
                elif kind == 'supplemental_notice':
                    path_parts(s['path']); path_parts(s.get('member',s.get('source_path'))); require(s['sha256']==h and any(q.get('ordinal')==s['ordinal'] and q.get('notice_sha256')==h for q in inv['prettier_supplemental']['sections']), 'invalid supplemental binding'); matched=True
                elif kind in ('supplemental_source','supplemental_path'):
                    path_parts(s['path']); require(s['lock_path'] in components, 'unknown supplemental component')
                    c=components[s['lock_path']]; refs=c['effective_classification'].get('supplemental_notice_sources',[])
                    require(any(isinstance(ref,dict) and ref.get('sha256')==h for ref in refs), 'invalid supplemental source binding'); matched=True
                else: raise Invalid('unknown notice source kind')
            require(matched, 'unbound retained notice')
        require(selected == bound, 'selected notice missing retained binding')
        original=inv['prettier_original_sections']; effective=inv['effective_prettier_sections']; supp=inv['prettier_supplemental']['sections']
        canonical_hash = '1adf328f64b26383979c603da48518620b766bd0c2044b7628640eb7d6b96bdc'
        require(canonical_hash in retained_hashes, 'missing canonical Prettier notice')
        canonical = r.read('docs/licenses/notices/' + canonical_hash + '.txt').replace(b'\r\n', b'\n')
        headers = list(re.finditer(rb'(?m)^## ([^\n]+)\n', canonical))
        require(len(headers) == 246 and len(original) == 246, 'canonical section count mismatch')
        require(isinstance(original,list) and isinstance(effective,list) and isinstance(supp,list) and len(original)==len(effective), 'invalid section lists')
        supplements={}
        for s in supp:
            i=s['ordinal']; require(type(i) is int and 1 <= i <= len(original) and i not in supplements and s['original_decision']==original[i-1] and s['name']==original[i-1]['name'] and s['current_status'] in STATUS, 'invalid supplemental decision')
            require(s['notice_sha256'] in retained_hashes and digest(s['actual_full_notice'].encode())==s['notice_sha256'], 'supplemental notice missing')
            supplements[i]=s
        unresolved=[]
        for i,(o,e) in enumerate(zip(original,effective),1):
            require(o['ordinal']==i and e['ordinal']==i and o['status'] in STATUS and e['original_decision']==o, 'section identity mismatch')
            text=o.get('full_notice_text',o.get('full_section_text',o.get('section_text'))).encode(); require(digest(text)==o.get('section_sha256',o.get('source_section_sha256')) and ('notice_byte_length' not in o or len(text)==o['notice_byte_length']), 'section text mismatch')
            header = headers[i-1]; end = headers[i].start() if i < len(headers) else len(canonical)
            require(o['name'].encode() == header.group(1) and text.replace(b'\r\n', b'\n') == canonical[header.end():end], 'canonical section mismatch')
            require(isinstance(o.get('rationale'), str) and o['rationale'].strip() and isinstance(o.get('obligations'), str) and o['obligations'].strip(), 'malformed section decision')
            s=supplements.get(i); status=s['current_status'] if s else o['status']
            require(e['effective_status']==status and (e.get('supplemental_decision')==s if s else 'supplemental_decision' not in e), 'effective section mismatch')
            if status=='unresolved': unresolved.append(i)
        require(inv['unresolved_section_ordinals']==unresolved and inv['remaining_unresolved_section_ordinals']==unresolved, 'unresolved section mismatch')
        gaps=inv['notice_coverage_gaps']; require(isinstance(gaps,list) and all(isinstance(g,dict) and g.get('component') in components and g.get('status') in STATUS for g in gaps), 'invalid coverage gaps')
        return {'counts':{'components':len(components),'sections':len(original),'notices':len(retained)}, 'hashes':dict(sorted(r.hashes.items()))}, inv
    finally: r.close()

def validate_structure(root):
    """Return structural evidence; raise ValueError for malformed or unsafe input."""
    try: return _validate(root)[0]
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError, ValueError) as e:
        if isinstance(e,Invalid): raise
        raise Invalid('invalid input: '+str(e)[:300]) from e

def assess(root):
    try: evidence, inv = _validate(root)
    except (OSError, KeyError, TypeError, UnicodeError, ValueError) as e:
        return {'structure_valid':False, 'diagnostics':[{'kind':'structure','detail':str(e)[:300]}], 'clearance_status':'unknown'}
    diagnostics=[]
    for p,c in inv['components'].items():
        if c['effective_classification']['status']=='unresolved': diagnostics.append({'kind':'classification','component':p})
    for i in inv['unresolved_section_ordinals']: diagnostics.append({'kind':'section','ordinal':i})
    for gap in inv['notice_coverage_gaps']:
        if gap['status']=='unresolved': diagnostics.append({'kind':'notice_coverage','component':gap['component'],'reference':str(gap.get('reference',''))[:200]})
    # Distribution scope requires independently reviewed, versioned evidence.
    diagnostics.append({'kind':'distribution_scope','detail':'unknown; explicit supported scope and coverage required'})
    return {'structure_valid':True, **evidence, 'clearance_status':'unknown', 'diagnostics':diagnostics}

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    args=parser.parse_args(); result=assess(args.root)
    # Keep output bounded even for hostile input.
    if len(result['diagnostics']) > 256:
        result['diagnostics']=result['diagnostics'][:256]+[{'kind':'truncated'}]
    if 'hashes' in result and len(result['hashes']) > 1024:
        result['hashes']={}; result['diagnostics'].append({'kind':'output_limit'})
    print(json.dumps(result,sort_keys=True)); return 1 if result['diagnostics'] else 0

if __name__ == '__main__': sys.exit(main())
