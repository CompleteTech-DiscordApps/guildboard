#!/usr/bin/env python3
"""Check reviewed npm inputs and installed notice bytes; never publish an approval."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

LIMIT = 20_000_000
class Invalid(Exception):
    pass

def read(root, path):
    p = Path(path)
    if p.is_absolute() or not p.parts or any(x in ('.', '..') for x in p.parts):
        raise Invalid('unsafe path')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(root, flags | os.O_DIRECTORY)
    try:
        for part in p.parts[:-1]:
            next_fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(p.parts[-1], flags, dir_fd=fd)
        try:
            st = os.fstat(file_fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > LIMIT:
                raise Invalid('nonregular or oversized: ' + str(p))
            with os.fdopen(file_fd, 'rb') as f:
                file_fd = -1
                data = f.read(LIMIT + 1)
            if len(data) > LIMIT: raise Invalid('oversized: ' + str(p))
            return data
        finally:
            if file_fd != -1: os.close(file_fd)
    finally:
        os.close(fd)

def obj(data):
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d: raise Invalid('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(data, object_pairs_hook=unique)

def check(root, modules, artifacts):
    inv = obj(read(root, 'docs/licenses/inventory.json'))
    if not isinstance(inv, dict) or inv.get('schema') != 1 or not isinstance(inv.get('inputs'), dict) or not isinstance(inv.get('components'), list) or not inv.get('unresolved'):
        raise Invalid('invalid inventory')
    inputs = inv['inputs']
    expected = {'package.json', 'package-lock.json'}
    for parent in ('apps', 'packages'):
        base = Path(root) / parent
        if base.is_symlink() or not base.is_dir(): raise Invalid('missing workspace directory')
        children = list(base.iterdir())
        if len(children) > 1000: raise Invalid('too many workspaces')
        for child in children:
            if child.is_symlink(): raise Invalid('workspace symlink')
            if child.is_dir() and (child / 'package.json').exists(): expected.add(parent + '/' + child.name + '/package.json')
    if set(inputs) != expected: raise Invalid('workspace manifest inventory mismatch')
    for path, digest in inputs.items():
        if not isinstance(digest, str) or hashlib.sha256(read(root, path)).hexdigest() != digest: raise Invalid('changed input: ' + path)
    lock = obj(read(root, 'package-lock.json'))
    if lock.get('lockfileVersion') != 3 or not isinstance(lock.get('packages'), dict): raise Invalid('unsupported lock')
    packages = {}
    for k, v in lock['packages'].items():
        if not isinstance(k, str) or not isinstance(v, dict): raise Invalid('invalid lock entry')
        if k.startswith('node_modules/'):
            if v.get('link') is True:
                if set(v) - {'resolved', 'link'} or v.get('resolved', '') + '/package.json' not in expected: raise Invalid('invalid workspace link: ' + k)
            else:
                packages[k] = v
        elif k != '' and k + '/package.json' not in expected:
            raise Invalid('unknown lock entry: ' + k)

    components = inv['components']
    if len(components) > 1000 or any(not isinstance(c, dict) or not isinstance(c.get('name'), str) for c in components): raise Invalid('invalid components')
    byname = {c['name']: c for c in components}
    if len(byname) != len(components) or set(packages) != {'node_modules/' + n for n in byname}: raise Invalid('component inventory mismatch')
    direct = set()
    for path in expected - {'package-lock.json'}:
        manifest = obj(read(root, path))
        for field in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'):
            deps = manifest.get(field, {})
            if not isinstance(deps, dict): raise Invalid('invalid dependencies')
            if any(not isinstance(k, str) or not isinstance(v, str) for k, v in deps.items()): raise Invalid('invalid dependency entry')
            direct.update(deps)
    if not direct.issubset(set(byname) | {obj(read(root, p)).get('name') for p in expected if p.endswith('/package.json')}): raise Invalid('unresolved direct dependency')
    for path, entry in packages.items():
        for field in ('dependencies', 'optionalDependencies', 'peerDependencies'):
            deps = entry.get(field, {})
            if not isinstance(deps, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in deps.items()):
                raise Invalid('invalid lock dependencies: ' + path)
            for dep in deps:
                if 'node_modules/' + dep not in packages:
                    raise Invalid('unresolved lock dependency: ' + dep)
    for name, c in byname.items():
        p = packages['node_modules/' + name]
        if not isinstance(p, dict): raise Invalid('invalid package')
        if c.get('relationship') != ('direct' if name in direct else 'transitive') or c.get('use') != 'build' or c.get('runtime') != 'not established': raise Invalid('unreviewed classification: '+name)
        if c.get('spdx') not in ('MIT', 'Apache-2.0') or any(c.get(a) != p.get(b) or not c.get(a) for a,b in [('version','version'),('source','resolved'),('integrity','integrity'),('spdx','license')]): raise Invalid('unreviewed metadata: '+name)
        artifact = c.get('artifact')
        if not isinstance(artifact, str) or '/' in artifact or not artifact.endswith('.tgz'): raise Invalid('invalid artifact path')
        actual = 'sha512-' + base64.b64encode(hashlib.sha512(read(artifacts, artifact)).digest()).decode()
        if actual != c.get('integrity'): raise Invalid('changed artifact: '+name)
        notices = c.get('notices')
        if not isinstance(notices, list) or not notices: raise Invalid('missing notices: '+name)
        paths = set()
        for notice in notices:
            if not isinstance(notice, dict) or not isinstance(notice.get('path'), str) or not notice['path'].startswith(name + '/') or notice['path'] in paths: raise Invalid('invalid notice')
            paths.add(notice['path'])
            if hashlib.sha256(read(modules, notice['path'])).hexdigest() != notice.get('sha256'): raise Invalid('changed notice: '+notice['path'])
        if name == 'typescript' and not {name + '/LICENSE.txt', name + '/ThirdPartyNoticeText.txt'}.issubset(paths): raise Invalid('missing TypeScript third-party notice')
    return len(components)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.')
    p.add_argument('--node-modules', required=True)
    p.add_argument('--artifacts', required=True, help='directory of exact npm tarballs named in inventory')
    args = p.parse_args()
    try:
        n = check(args.root, args.node_modules, args.artifacts)
    except (Invalid, OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as e:
        print('BLOCKED: ' + str(e), file=sys.stderr); return 1
    print(f'CHECKED: {n} reviewed npm records and notice bytes; distribution remains blocked pending artifact review')
    return 0
if __name__ == '__main__': sys.exit(main())
