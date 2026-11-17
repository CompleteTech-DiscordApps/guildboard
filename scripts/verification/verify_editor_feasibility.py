#!/usr/bin/env python3
"""Bounded identity checks; research semantics remain inspection-only."""
import argparse, hashlib, json, os, pathlib, re, stat, sys, tempfile

LIMIT = 4_000_000

def digest(data): return hashlib.sha256(data).hexdigest()
def require(value, message):
    if not value: raise ValueError(message)

def read(path):
    # Traverse every directory by descriptor without following symlinks.
    path = pathlib.Path(path).absolute()
    parts = path.parts
    fd = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        f = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(f)
            require(stat.S_ISREG(before.st_mode), 'not regular: '+str(path))
            require(before.st_size <= LIMIT, 'oversize')
            chunks=[]; remaining=LIMIT+1
            while remaining:
                b=os.read(f,min(65536,remaining))
                if not b: break
                chunks.append(b); remaining-=len(b)
            data=b''.join(chunks); after=os.fstat(f)
            require(len(data)<=LIMIT and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and len(data)==after.st_size, 'unstable file')
            return data
        finally: os.close(f)
    finally: os.close(fd)

def obj(path): return json.loads(read(path))

# SQL inputs must come from an immutable revision: a full commit SHA, or the exact MySQL release tag.
PINNED_SQL_URL = re.compile(r'https://raw\.githubusercontent\.com/(?:mariadb-corporation/mariadb-docs/[0-9a-f]{40}|mysql/mysql-server/mysql-[0-9]+\.[0-9]+\.[0-9]+)(?:/[A-Za-z0-9_-][A-Za-z0-9._-]*)+')
def immutable_source(name, url):
    if name.startswith('sql/'): require(PINNED_SQL_URL.fullmatch(url) is not None, 'mutable SQL source URL: '+name)

def verify(root, inputs, revision):
    require(re.fullmatch(r'[0-9a-f]{40}',revision) is not None,'invalid caller revision')
    ledger=obj(root/'docs/research/editor14/source-ledger.json')['sources']
    # Hash identities are anchored in code, independently of the mutable ledger.
    require(ledger == SOURCES, 'source ledger identity')
    checked={}
    for name, entry in sorted(ledger.items()):
        require(not name.startswith('/') and all(x not in ('','.','..') for x in name.split('/')), 'invalid source path')
        immutable_source(name, entry['url'])
        actual=digest(read(inputs/name)); require(actual==entry['sha256'],'source hash: '+name); checked[name]=actual
    pkg=obj(inputs/'public/excalidraw-0.18.1-declarations/package.json')
    require(pkg['version']=='0.18.1' and pkg['peerDependencies']['react']=='^17.0.2 || ^18.2.0 || ^19.0.0','editor peer mismatch')
    for name,version in [('react','19.1.0'),('react-dom','19.1.0'),('fastify','5.6.1')]:
        p=obj(inputs/('public/'+name+'_'+version+'.json')); require(p['version']==version and ('/'+name+'/-/') in p['dist']['tarball'],'package identity '+name)
    require(obj(inputs/'public/react-dom_19.1.0.json')['peerDependencies']['react']=='^19.1.0','react-dom peer')
    pins=obj(root/'docs/research/feasibility-pins.json')['packages'][0]
    require(pins['version']=='0.18.1','invalid editor pin')
    for entry in pins['checks']:
        name='public/excalidraw-0.18.1-declarations/'+entry['path'].removeprefix('package/').replace('/','--')
        require(name in ledger and entry['sha256']==ledger[name]['sha256'],'declaration pin')
    matrix=obj(root/'docs/research/editor13/evaluated-matrix.json')
    clauses={c['clause']:c for c in matrix['clauses']}
    for key,tokens in {'hooks':['0.18.1'],'read-only':['0.18.1'],'serialization':['0.18.1'],'extensions':['0.18.1'],'web stack':['19.1.0','5.9.3','5.6.1'],'database':['8.4.7','11.8.3']}.items():
        require(all(t in clauses[key]['evaluated_versions'] for t in tokens),'matrix pin '+key)
        require('runtime fully proven' not in clauses[key]['result_and_limit'].lower(),'unsupported runtime claim '+key)
    return {'status':'pass','caller_revision':revision,'source_hashes':checked,'scope':'identity and listed negative claim checks only; semantic comparison inspection-only; no runtime or license approval'}

def publish(path,data,interrupt=False):
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.verify14-')
    try:
        with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        if interrupt: raise InterruptedError('before replacement')
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=pathlib.Path,required=True); p.add_argument('--inputs',type=pathlib.Path,required=True); p.add_argument('--revision',required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
    try: publish(a.output,verify(a.root,a.inputs,a.revision)); print('PASS bounded identity checks'); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print('FAIL',str(e),file=sys.stderr); return 1

# Fixed approved input identities and acquisition URLs.
SOURCES = {'public/react_19.1.0.json': {'sha256': 'f93e69ad3ae948242a4ca5c8c0171c49025ab0920f682e83c1cb74352051b2e5', 'url': 'https://registry.npmjs.org/react/19.1.0'}, 'public/react-dom_19.1.0.json': {'sha256': '1f93b2f67602e72d5b20306a10b3bbf8c0bf7f0163a55a54f502a91479e68f88', 'url': 'https://registry.npmjs.org/react-dom/19.1.0'}, 'public/fastify_5.6.1.json': {'sha256': '37a0c494bddaabefad5600d9218b455e40a17c2e9812742f94fba2243c3e0b15', 'url': 'https://registry.npmjs.org/fastify/5.6.1'}, 'public/_excalidraw-excalidraw_0.18.1.json': {'sha256': '70bd551ab5451d46b533692f28c659de9d364bc2c4872131ac95fb8b0b4412f2', 'url': 'https://registry.npmjs.org/@excalidraw%2fexcalidraw/0.18.1'}, 'public/excalidraw-0.18.1-declarations/package.json': {'sha256': '402f54fc7de128b25d22bd4d905fb46dbcdbe2ce6efee567d4da0fc79a29aab1', 'url': 'https://registry.npmjs.org/@excalidraw/excalidraw/-/excalidraw-0.18.1.tgz'}, 'public/excalidraw-0.18.1-declarations/dist--types--excalidraw--index.d.ts': {'sha256': '90729dab4b90b24477773dd263aa8b51bbd62afa45f003795d084828a1e1e8e6', 'url': 'https://registry.npmjs.org/@excalidraw/excalidraw/-/excalidraw-0.18.1.tgz'}, 'public/excalidraw-0.18.1-declarations/dist--types--excalidraw--types.d.ts': {'sha256': '61681bd17da86a0b811242e83cd8e1f6c7f168a14806c8ca587390e24815486a', 'url': 'https://registry.npmjs.org/@excalidraw/excalidraw/-/excalidraw-0.18.1.tgz'}, 'public/fastify-v5.6.1-migration.md': {'sha256': '429f4425dfd0fcff3137d3dc8effb4bb783bc93d9baf602532243dbb234a8836', 'url': 'https://raw.githubusercontent.com/fastify/fastify/v5.6.1/docs/Guides/Migration-Guide-V5.md'}, 'public/fastify-v5.6.1-typescript.md': {'sha256': '25436f3a03044b3cbfeb6af4bc5032fd43e996789961a01c8703afeb3898b363', 'url': 'https://raw.githubusercontent.com/fastify/fastify/v5.6.1/docs/Reference/TypeScript.md'}, 'public/fastify-v5.6.1-validation.md': {'sha256': 'f7b980759f4b2f93c4a2f3ebbd7aef80d254dfc758246eee2e36ee4460505d8d', 'url': 'https://raw.githubusercontent.com/fastify/fastify/v5.6.1/docs/Reference/Validation-and-Serialization.md'}, 'sql/mariadb-json.md': {'sha256': '41e7be802639147132a00ebb0aeff069fa243e903929724e82f5fd0862b19993', 'url': 'https://raw.githubusercontent.com/mariadb-corporation/mariadb-docs/f1d0c1c733efc86dbc685b5943a9ca01b0ae678b/server/reference/data-types/string-data-types/json.md'}, 'sql/mariadb-11.8.3.md': {'sha256': '6147e9c8a361925cf7132dc3db39b2846e4731267813eb4d61cbaa58797e98d7', 'url': 'https://raw.githubusercontent.com/mariadb-corporation/mariadb-docs/7c033de04c329f643143f76cf086915d6a4c61d4/release-notes/community-server/11.8/11.8.3.md'}, 'sql/mysql-json_binary.h': {'sha256': '3530a084dd02113cc21e28e11bb0b339237582de0767ae28d9e9c4de388211ef', 'url': 'https://raw.githubusercontent.com/mysql/mysql-server/mysql-8.4.7/sql-common/json_binary.h'}, 'sql/mysql-version': {'sha256': '57cae9a5de0371789fad603f90c5fb9391245ccb10655e3d689ce138134f690a', 'url': 'https://raw.githubusercontent.com/mysql/mysql-server/mysql-8.4.7/MYSQL_VERSION'}}
if __name__=='__main__': sys.exit(main())
