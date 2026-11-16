#!/usr/bin/env python3
"""Acquire a complete verified cache; this does not assess license clearance.

Requires a stable filesystem: descriptor checks are not a privileged snapshot.
"""
import argparse
import base64
import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import urllib.parse
import urllib.request

from check import Invalid, Reader, validate_structure

MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_COMPONENTS = 1000
TIMEOUT = 30

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Invalid('redirect forbidden')

def _require(condition, message):
    if not condition:
        raise Invalid(message)

def _url(url):
    _require(isinstance(url, str) and len(url) <= 2048, 'invalid URL')
    u = urllib.parse.urlsplit(url)
    _require(u.scheme == 'https' and u.netloc == 'registry.npmjs.org' and
             url.startswith('https://registry.npmjs.org/') and not u.query and
             not u.fragment and '?' not in url and '#' not in url and
             re.fullmatch(r'/[A-Za-z0-9@._~/-]+', u.path) is not None and
             all(p not in ('', '.', '..') for p in u.path[1:].split('/')),
             'untrusted URL')

def _parent(output):
    path = os.fspath(output)
    _require(isinstance(path, str) and path and '\x00' not in path, 'invalid output')
    parts = path.split('/')
    _require(parts[-1] not in ('', '.', '..') and all(p != '..' for p in parts), 'invalid output path')
    name = parts.pop()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    chain = []
    fd = os.open('/' if path.startswith('/') else '.', flags)
    chain.append((None, None, fd, None))
    try:
        for part in parts:
            if part in ('', '.'): continue
            before = os.stat(part, dir_fd=fd, follow_symlinks=False)
            _require(stat.S_ISDIR(before.st_mode), 'unsafe output ancestor')
            child = os.open(part, flags, dir_fd=fd)
            chain.append((fd, part, child, (before.st_dev, before.st_ino)))
            _check_chain(chain)
            fd = child
        return chain, name
    except BaseException:
        for _, _, f, _ in reversed(chain): os.close(f)
        raise

def _check_chain(chain):
    for parent, name, fd, ident in chain:
        if parent is not None:
            a = os.stat(name, dir_fd=parent, follow_symlinks=False)
            b = os.fstat(fd)
            _require(stat.S_ISDIR(a.st_mode) and (a.st_dev, a.st_ino) == ident == (b.st_dev, b.st_ino), 'output ancestor changed')

def _publish(parent, stage, name):
    # renameat2 is required for no-replace publication; fail closed if unavailable.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None: raise Invalid('atomic no-replace rename unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(stage), parent, os.fsencode(name), 1):
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))

def fetch(root, output, opener=None):
    evidence = validate_structure(root)
    r = Reader(root)
    try:
        inv = r.json('docs/licenses/inventory.json', 2 * 1024 * 1024)
        lock = r.json('package-lock.json')
        _require(all(r.hashes[p] == evidence['hashes'][p] for p in r.hashes), 'input changed after validation')
    finally: r.close()
    components = inv['components']; packages = lock['packages']
    external = {p for p, v in packages.items() if 'node_modules/' in p and not v.get('link', False)}
    _require(isinstance(components, dict) and 0 < len(components) <= MAX_COMPONENTS and set(components) == external, 'invalid components')
    items = []
    for p, c in sorted(components.items()):
        a = c['artifact']; entry = packages[p]; url = entry.get('resolved'); sri = entry.get('integrity')
        _url(url)
        _require(url == a['url'] and sri == a['integrity'] and isinstance(sri, str) and sri.startswith('sha512-'), 'lock artifact mismatch')
        try: raw = base64.b64decode(sri[7:], validate=True)
        except (ValueError, TypeError): raise Invalid('invalid SRI') from None
        _require(len(raw) == 64 and base64.b64encode(raw).decode() == sri[7:], 'invalid SRI')
        sha = a['archive_sha256']; filename = hashlib.sha256(p.encode()).hexdigest() + '.tgz'
        _require(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha) and a['cache_filename'] == filename, 'invalid archive identity')
        items.append((p, url, raw, sha, filename))
    chain, name = _parent(output); parent = chain[-1][2]; stage = None; stagefd = None; stage_id = None; created = []
    try:
        try: os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError: pass
        else: raise Invalid('output already exists')
        stage = '.license-fetch-' + secrets.token_hex(16)
        os.mkdir(stage, 0o700, dir_fd=parent)
        stage_id = os.stat(stage, dir_fd=parent, follow_symlinks=False)
        stagefd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        stage_id = os.fstat(stagefd)
        opener = opener if opener is not None else urllib.request.build_opener(NoRedirect())
        total = 0; results = []
        for p, url, sri, sha, filename in items:
            h512 = hashlib.sha512(); h256 = hashlib.sha256(); size = 0
            with opener.open(url, timeout=TIMEOUT) as response:
                _require(response.geturl() == url, 'unexpected response URL')
                fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stagefd)
                created.append(filename)
                with os.fdopen(fd, 'wb') as out:
                    _require(stat.S_ISREG(os.fstat(out.fileno()).st_mode), 'unsafe output file')
                    while True:
                        chunk = response.read(min(65536, MAX_FILE + 1 - size, MAX_TOTAL + 1 - total))
                        _require(isinstance(chunk, bytes) and len(chunk) <= min(65536, MAX_FILE + 1 - size, MAX_TOTAL + 1 - total), 'invalid response stream')
                        if not chunk: break
                        size += len(chunk); total += len(chunk)
                        _require(size <= MAX_FILE and total <= MAX_TOTAL, 'archive byte limit exceeded')
                        h512.update(chunk); h256.update(chunk); out.write(chunk)
            _require(h512.digest() == sri and h256.hexdigest() == sha, 'archive digest mismatch')
            results.append({'lock_path': p, 'filename': filename, 'bytes': size, 'sha256': sha})
        _check_chain(chain)
        st = os.stat(stage, dir_fd=parent, follow_symlinks=False)
        _require(stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == (stage_id.st_dev, stage_id.st_ino), 'staging directory changed')
        _publish(parent, stage, name); stage = None
        return {'artifacts': results, 'count': len(results), 'bytes': total}
    finally:
        if stagefd is not None:
            for filename in created:
                if stage is not None:
                    try: os.unlink(filename, dir_fd=stagefd)
                    except FileNotFoundError: pass
            os.close(stagefd)
        if stage is not None:
            try:
                st = os.stat(stage, dir_fd=parent, follow_symlinks=False)
                if stage_id is not None and (st.st_dev, st.st_ino) == (stage_id.st_dev, stage_id.st_ino): os.rmdir(stage, dir_fd=parent)
            except FileNotFoundError: pass
        for _, _, fd, _ in reversed(chain): os.close(fd)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try: print(json.dumps(fetch(args.root, args.output), sort_keys=True))
    except (Invalid, OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        print('BLOCKED: ' + str(e)[:300], file=sys.stderr); return 1
    return 0

if __name__ == '__main__': sys.exit(main())
