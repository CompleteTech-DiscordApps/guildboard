#!/usr/bin/env python3
"""Offline identity/peer inspection, not a semantic or runtime test."""
import argparse, hashlib, json, os, pathlib, tempfile

HASHES = {
'react_19.1.0.json':'f93e69ad3ae948242a4ca5c8c0171c49025ab0920f682e83c1cb74352051b2e5',
'react-dom_19.1.0.json':'1f93b2f67602e72d5b20306a10b3bbf8c0bf7f0163a55a54f502a91479e68f88',
'fastify_5.6.1.json':'37a0c494bddaabefad5600d9218b455e40a17c2e9812742f94fba2243c3e0b15',
'_excalidraw-excalidraw_0.18.1.json':'70bd551ab5451d46b533692f28c659de9d364bc2c4872131ac95fb8b0b4412f2',
'excalidraw-0.18.1-declarations/package.json':'402f54fc7de128b25d22bd4d905fb46dbcdbe2ce6efee567d4da0fc79a29aab1',
'excalidraw-0.18.1-declarations/dist--types--excalidraw--index.d.ts':'90729dab4b90b24477773dd263aa8b51bbd62afa45f003795d084828a1e1e8e6',
'excalidraw-0.18.1-declarations/dist--types--excalidraw--types.d.ts':'61681bd17da86a0b811242e83cd8e1f6c7f168a14806c8ca587390e24815486a',
'fastify-v5.6.1-migration.md':'429f4425dfd0fcff3137d3dc8effb4bb783bc93d9baf602532243dbb234a8836',
'fastify-v5.6.1-typescript.md':'25436f3a03044b3cbfeb6af4bc5032fd43e996789961a01c8703afeb3898b363',
'fastify-v5.6.1-validation.md':'f7b980759f4b2f93c4a2f3ebbd7aef80d254dfc758246eee2e36ee4460505d8d'}

def inspect(root):
    root = pathlib.Path(root)
    data = {}
    for name, expected in HASHES.items():
        path = root / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('hash mismatch: ' + name)
        data[name] = raw
    def obj(name): return json.loads(data[name])
    e = obj('_excalidraw-excalidraw_0.18.1.json')
    p = obj('excalidraw-0.18.1-declarations/package.json')
    peers = {'react':'^17.0.2 || ^18.2.0 || ^19.0.0','react-dom':'^17.0.2 || ^18.2.0 || ^19.0.0'}
    if e['version'] != '0.18.1' or p['version'] != '0.18.1' or e['peerDependencies'] != peers or p['peerDependencies'] != peers:
        raise ValueError('Excalidraw identity or peers mismatch')
    if obj('react_19.1.0.json')['version'] != '19.1.0' or obj('react-dom_19.1.0.json')['peerDependencies'] != {'react':'^19.1.0'} or obj('react-dom_19.1.0.json')['version'] != '19.1.0' or obj('fastify_5.6.1.json')['version'] != '5.6.1':
        raise ValueError('candidate identity or peers mismatch')
    return {'status':'static identity and declared peer comparison passed', 'files':HASHES, 'react_19_1_0_satisfies_reviewed_peers':True, 'runtime_tested':False}

def write_result(path, result):
    path = pathlib.Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.editor13-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(result, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.evidence); write_result(args.output, result)
    except (OSError, ValueError, KeyError, TypeError) as e:
        parser.exit(1, 'probe failed: '+str(e)+'\n')
    print(result['status'])
if __name__ == '__main__': main()
