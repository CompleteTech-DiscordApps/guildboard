#!/usr/bin/env python3
"""Offline independent checks of issue 13 research inputs; no runtime claims."""
import argparse, hashlib, json, os, pathlib, stat, sys, tempfile

def read(path):
    # Refuse special files and final symlinks before opening; nonblocking also protects races.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('not regular: '+str(path))
        with os.fdopen(fd, 'rb', closefd=False) as f:
            data=f.read(4_000_001)
        if len(data)>4_000_000: raise ValueError('oversize')
        return data
    finally: os.close(fd)

def digest(data): return hashlib.sha256(data).hexdigest()
def obj(path): return json.loads(read(path))
def require(test, message):
    if not test: raise ValueError(message)
def verify(root, public, sql, ledger):
    hashes=obj(ledger)['files']
    require(len(hashes)==10,'expected ten publisher inputs')
    for name, expected in hashes.items(): require(digest(read(public/name))==expected,'publisher hash: '+name)
    pins=obj(root/'docs/research/feasibility-pins.json')['packages'][0]
    for entry in pins['checks']:
        name='excalidraw-0.18.1-declarations/'+entry['path'].replace('package/','').replace('/','--')
        require(digest(read(public/name))==entry['sha256'],'declaration pin: '+name)
    pkg=obj(public/'excalidraw-0.18.1-declarations/package.json')
    require(pkg['version']==pins['version'] and pkg['peerDependencies']['react']=='^17.0.2 || ^18.2.0 || ^19.0.0','editor peer mismatch')
    for name, version in [('react','19.1.0'),('react-dom','19.1.0'),('fastify','5.6.1')]:
        p=obj(public/(name+'_'+version+'.json')); require(p['version']==version and ('/'+name+'/-/') in p['dist']['tarball'], 'package identity '+name)
    require(obj(public/'react-dom_19.1.0.json')['peerDependencies']['react']=='^19.1.0','react-dom peer')
    types=read(public/'excalidraw-0.18.1-declarations/dist--types--excalidraw--types.d.ts').decode()
    index=read(public/'excalidraw-0.18.1-declarations/dist--types--excalidraw--index.d.ts').decode()
    for term in ['onChange','onPointerUpdate','viewModeEnabled','updateScene','addFiles','renderEmbeddable','onDuplicate']:
        require(term in types,'missing declaration '+term)
    require('serializeAsJSON' in index,'serialization export')
    receipts=obj(sql/'source-receipts.json')
    for source in receipts['sources']:
        if source['status']=='retrieved-primary-publisher-bytes':
            b=read(sql/source['file']); require(len(b)==source['bytes'] and digest(b)==source['sha256'],'SQL receipt '+source['file'])
    require(b'LONGTEXT' in read(sql/'mariadb-json.md'), 'MariaDB JSON semantics')
    require(b'8.4.7' in read(sql/'mysql-version') or all(x in read(sql/'mysql-version') for x in [b'MYSQL_VERSION_MAJOR=8',b'MYSQL_VERSION_MINOR=4',b'MYSQL_VERSION_PATCH=7']), 'MySQL version')
    require(b'JSON' in read(sql/'mysql-json_binary.h'), 'MySQL source')
    excerpts=obj(sql/'mysql-web-primary-excerpts.json'); require('validation' in str(excerpts).lower(), 'MySQL excerpt')
    matrix=obj(root/'docs/research/editor13/evaluated-matrix.json')
    clauses={c['clause']:c for c in matrix['clauses']}
    for key, tokens in {'hooks':['0.18.1'], 'read-only':['0.18.1'], 'serialization':['0.18.1'], 'extensions':['0.18.1'], 'web stack':['19.1.0','5.9.3','5.6.1'], 'database':['8.4.7','11.8.3']}.items():
        require(all(t in clauses[key]['evaluated_versions'] for t in tokens),'matrix pin '+key)
        require('unproven' in clauses[key]['result_and_limit'] or 'only' in clauses[key]['result_and_limit'] or 'differs' in clauses[key]['result_and_limit'], 'unsupported claim '+key)
    for path in ['docs/adr/0004-editor-and-database-selection.md','docs/research/editor13/comparison.md']:
        text=read(root/path).decode().lower()
        for token in (['server','mariadb','runtime'] if 'comparison' in path else ['controlled experiment','server','mariadb','historical']):
            require(token in text, path+' missing '+token)
    return {'status':'pass','publisher_inputs':len(hashes),'sql_raw_sources':sum(s['status']=='retrieved-primary-publisher-bytes' for s in receipts['sources']), 'scope':'static checks only'}

def publish(path, data, interrupt=False):
    fd, temp=tempfile.mkstemp(dir=path.parent, prefix='.verify14-')
    try:
        with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        if interrupt: raise InterruptedError('before replacement')
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=pathlib.Path,required=True); p.add_argument('--public',type=pathlib.Path,required=True); p.add_argument('--sql',type=pathlib.Path,required=True); p.add_argument('--ledger',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
    try: publish(a.output,verify(a.root,a.public,a.sql,a.ledger)); print('PASS static identity and bounded checks'); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print('FAIL',str(e),file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
