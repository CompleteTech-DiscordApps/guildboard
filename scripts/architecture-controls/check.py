#!/usr/bin/env python3
"""Offline structural change gate. No writes; review semantics separately."""
import argparse
import hashlib
import json
import os
import stat
import re
import sys
from pathlib import Path

FIXED = ('docs/architecture.md', 'docs/specifications/GB-T0-S1-system-contract.md', 'docs/specifications/fixtures/GB-T0-S1-scenarios.json', 'docs/specifications/fixtures/GB-T0-01-02-interactions.json', 'docs/requirements/GB-T0-01-01-requirements.md', 'docs/requirements/fixtures/GB-T0-01-01-use-cases.json', 'docs/adr/0001-editor-activity-vps-direction.md', 'docs/adr/0002-server-authority-and-interactions.md', 'docs/security/GB-T0-04-02-threat-model.md')
ROOTS = ('apps', 'packages', 'database', 'infra/godaddy')
MAX_FILE = 4 * 1024 * 1024
MAX_FILES = 2000
HASH = re.compile(r'^[0-9a-f]{64}$')

class Invalid(Exception): pass

def require(ok, message):
    if not ok: raise Invalid(message)

def read(root, name):
    require(isinstance(name, str) and name and not name.startswith('/') and all(x not in ('', '.', '..') for x in name.split('/')), 'invalid path')
    parts = name.split('/')
    fds = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(root, flags); fds.append(fd)
        for part in parts[:-1]:
            fd = os.open(part, flags, dir_fd=fd); fds.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd); fds.append(fd)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), 'not a regular file: ' + name)
        require(info.st_size <= MAX_FILE, 'file too large: ' + name)
        chunks = []; total = 0
        while total <= MAX_FILE:
            chunk = os.read(fd, min(65536, MAX_FILE + 1 - total))
            if not chunk: break
            chunks.append(chunk); total += len(chunk)
        require(total <= MAX_FILE, 'file too large: ' + name)
        after = os.fstat(fd)
        require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and total == info.st_size, 'file changed while reading: ' + name)
        return b''.join(chunks)
    except OSError as e:
        raise Invalid('cannot safely read ' + name + ': ' + str(e)) from e
    finally:
        for fd in reversed(fds): os.close(fd)

def load(root, name):
    def unique(pairs):
        d = {}
        for k, v in pairs:
            require(k not in d, 'duplicate key: ' + k)
            d[k] = v
        return d
    return json.loads(read(root, name), object_pairs_hook=unique)

def exact(obj, keys, label):
    require(type(obj) is dict and set(obj) == set(keys), 'invalid shape: ' + label)

def inventory(root, allow_missing=False):
    paths = {p for p in FIXED if not allow_missing or os.path.lexists(root / p)}
    for name in ROOTS:
        folder = root / name
        require(folder.is_dir() and not folder.is_symlink(), 'missing boundary root: ' + name)
        for p in folder.rglob('*'):
            require(not p.is_symlink(), 'symlink in boundary: ' + str(p))
            if p.is_file(): paths.add(p.relative_to(root).as_posix())
            else: require(p.is_dir(), 'nonregular boundary entry: ' + str(p))
            require(len(paths) <= MAX_FILES, 'too many boundary files')
    return {p: hashlib.sha256(read(root, p)).hexdigest() for p in sorted(paths)}

def baseline(root):
    x = load(root, 'docs/architecture-controls/baseline.json')
    exact(x, ('version', 'boundaries'), 'baseline')
    require(type(x['version']) is int and x['version'] == 1 and type(x['boundaries']) is dict, 'invalid baseline')
    require(x['boundaries'] == inventory(root), 'baseline does not match its tree')
    return x['boundaries']

def nonempty(s): return isinstance(s, str) and bool(s.strip()) and len(s) <= 4000

def check_trace(root):
    t = load(root, 'docs/architecture-controls/traceability.json')
    exact(t, ('version', 'requirements', 'interfaces', 'controls'), 'trace')
    require(type(t['version']) is int and t['version'] == 1, 'invalid trace version')
    cases = load(root, FIXED[5])['cases']
    interactions = load(root, FIXED[3])['scenarios']
    canonical = load(root, FIXED[2])
    # Canonical IDs are referenced through the accepted interaction fixture.
    all_f = {s['id'] for s in canonical['scenarios']}
    require(type(t['interfaces']) is dict and type(t['controls']) is dict, 'invalid catalogs')
    for catalog in (t['interfaces'], t['controls']):
        require(bool(catalog), 'empty catalog')
        for k, v in catalog.items():
            require(nonempty(k), 'invalid catalog id')
            exact(v, ('description', 'evidence'), 'catalog entry')
            require(nonempty(v['description']) and type(v['evidence']) is list and v['evidence'], 'invalid catalog entry')
            for p in v['evidence']: read(root, p)
    expected = {f'R{i:02}' for i in range(1, 9)}
    require(type(t['requirements']) is dict and set(t['requirements']) == expected, 'missing or unknown requirement')
    require({c['id'] for c in cases} == {f'UC{i:02}' for i in range(1, 21)}, 'invalid canonical use cases')
    for rid, entry in t['requirements'].items():
        exact(entry, ('use_cases', 'interfaces', 'controls', 'interactions', 'canonical_acceptance'), rid)
        expected_uc = {c['id'] for c in cases if rid in c['requirements']}
        expected_i = {i['id'] for i in interactions if set(i['use_cases']) & expected_uc}
        expected_f = {f for i in interactions if i['id'] in expected_i for f in i['contract_scenarios']}
        for key, valid in [('use_cases', expected_uc), ('interactions', expected_i), ('canonical_acceptance', expected_f)]:
            v = entry[key]
            require(type(v) is list and len(v) == len(set(v)) and set(v) == valid, rid + ' invalid ' + key)
        require(expected_f <= all_f, 'unknown canonical acceptance')
        for key in ('interfaces', 'controls'):
            v = entry[key]
            require(type(v) is list and v and len(v) == len(set(v)) and set(v) <= set(t[key]), rid + ' invalid ' + key)

def check(base, current, old=None):
    old, new = baseline(base) if old is None else old, baseline(current)
    check_trace(current)
    records = load(current, 'docs/architecture-controls/decisions.json')
    exact(records, ('version', 'records'), 'decisions')
    require(type(records['version']) is int and records['version'] == 1 and type(records['records']) is list, 'invalid decisions')
    changes = {p: (old.get(p), new.get(p)) for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
    matched = set()
    identities = set()
    for rec in records['records']:
        exact(rec, ('id', 'revision', 'boundary', 'old_sha256', 'new_sha256', 'rationale', 'alternatives', 'controls', 'test_evidence'), 'decision')
        require(isinstance(rec['id'], str) and re.fullmatch(r'DEC-[0-9]{4}', rec['id']) and type(rec['revision']) is int and rec['revision'] > 0, 'invalid decision identity')
        identity = (rec['id'], rec['revision'])
        require(identity not in identities, 'duplicate decision revision')
        identities.add(identity)
        require(nonempty(rec['rationale']) and type(rec['alternatives']) is list and rec['alternatives'] and all(nonempty(x) for x in rec['alternatives']), 'invalid decision rationale')
        for key in ('controls', 'test_evidence'):
            require(type(rec[key]) is list and rec[key] and all(isinstance(p, str) for p in rec[key]), 'missing decision evidence')
            for p in rec[key]: read(current, p)
        for h in (rec['old_sha256'], rec['new_sha256']): require(h is None or isinstance(h, str) and HASH.fullmatch(h), 'invalid hash')
        p = rec['boundary']
        require(isinstance(p, str), 'invalid boundary')
        if p in changes and changes[p] == (rec['old_sha256'], rec['new_sha256']): matched.add(p)
    require(matched == set(changes), 'undocumented boundaries: ' + ', '.join(sorted(set(changes) - matched)))
    return len(changes)

BOOTSTRAP_SHA = '6e219f930a12a372b6cbec8e81feb542a030fb65'

def bootstrap(base, current, base_sha):
    require(base_sha == BOOTSTRAP_SHA, 'wrong bootstrap base SHA')
    for name in ('scripts/architecture-controls/check.py', 'docs/architecture-controls/baseline.json', '.github/workflows/architecture-controls.yml'):
        require(not os.path.lexists(base / name), 'base already has gate: ' + name)
    manifest = load(current, 'docs/architecture-controls/bootstrap.json')
    exact(manifest, ('version', 'base_sha', 'boundaries', 'review'), 'bootstrap manifest')
    require(manifest['version'] == 1 and type(manifest['version']) is int and manifest['base_sha'] == BOOTSTRAP_SHA, 'invalid bootstrap manifest')
    require(manifest['review'] == 'independent review and protected merge required', 'missing review requirement')
    require(type(manifest['boundaries']) is dict and manifest['boundaries'] == inventory(base, allow_missing=True), 'bootstrap witness mismatch')
    return check(base, current, manifest['boundaries'])

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--base', required=True); parser.add_argument('--current', required=True); parser.add_argument('--bootstrap-base-sha')
    a = parser.parse_args()
    try:
        base, current = Path(a.base).resolve(strict=True), Path(a.current).resolve(strict=True)
        count = bootstrap(base, current, a.bootstrap_base_sha) if a.bootstrap_base_sha is not None else check(base, current)
        print(f'PASS: {count} changed boundary file(s); semantic review required')
        return 0
    except (Invalid, OSError, ValueError, KeyError, TypeError, RecursionError) as e:
        print('FAIL: ' + str(e), file=sys.stderr); return 1
if __name__ == '__main__': sys.exit(main())
