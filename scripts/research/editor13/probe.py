#!/usr/bin/env python3
"""Offline identity/peer inspection, not a semantic or runtime test."""
import argparse, hashlib, json, os, pathlib, tempfile, stat

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

MAX_INPUT = 2 * 1024 * 1024

def read_input(root, name):
    # Open every component without following links; FIFOs must never block.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fds, links = [], []
    try:
        parts = pathlib.Path(root).absolute().parts
        fd = os.open(parts[0], flags | os.O_DIRECTORY); fds.append(fd)
        for part in (*parts[1:], *name.split('/')):
            if part in ('', '.', '..'):
                raise ValueError('invalid input component')
            is_last = part == name.split('/')[-1] and len(fds) == len(parts) + len(name.split('/')) - 1
            parent = fd
            fd = os.open(part, flags | (0 if is_last else os.O_DIRECTORY), dir_fd=parent)
            fds.append(fd); links.append((parent, part, fd))
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_INPUT:
            raise ValueError('input is not a bounded regular file: ' + name)
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, MAX_INPUT + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            if size > MAX_INPUT: raise ValueError('input exceeds limit: ' + name)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != before.st_size:
            raise ValueError('input changed while reading: ' + name)
        for parent, part, opened in links:
            current = os.stat(part, dir_fd=parent, follow_symlinks=False)
            opened_stat = os.fstat(opened)
            if (current.st_dev, current.st_ino) != (opened_stat.st_dev, opened_stat.st_ino):
                raise ValueError('input component changed: ' + name)
        return b''.join(chunks)
    finally:
        for fd in reversed(fds): os.close(fd)

def inspect(root):
    data = {}
    for name, expected in HASHES.items():
        raw = read_input(root, name)
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
