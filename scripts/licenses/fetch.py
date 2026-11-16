#!/usr/bin/env python3
"""Fetch exact reviewed lock artifacts, bounded and integrity checked, without execution."""
import base64
import hashlib
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
from check import Invalid, LIMIT, obj, read

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Invalid('redirect forbidden')

def fetch(root, output, opener=None):
    inv = obj(read(root, 'docs/licenses/inventory.json'))
    lock = obj(read(root, 'package-lock.json'))
    if hashlib.sha256(read(root, 'package-lock.json')).hexdigest() != inv['inputs']['package-lock.json']:
        raise Invalid('changed lock')
    components = inv['components']
    if not isinstance(components, list) or not components or len(components) > 1000: raise Invalid('invalid components')
    opener = opener or urllib.request.build_opener(NoRedirect())
    seen = set()
    for c in components:
        name, url, integrity, artifact = (c[x] for x in ('name', 'source', 'integrity', 'artifact'))
        p = lock['packages']['node_modules/' + name]
        u = urllib.parse.urlsplit(url)
        if u.scheme != 'https' or u.netloc != 'registry.npmjs.org' or u.query or u.fragment or p.get('resolved') != url or p.get('integrity') != integrity:
            raise Invalid('untrusted source or digest')
        if not isinstance(artifact, str) or not artifact.endswith('.tgz') or '/' in artifact or artifact in seen: raise Invalid('invalid artifact')
        seen.add(artifact)
        with opener.open(url, timeout=30) as response:
            data = response.read(LIMIT + 1)
        if len(data) > LIMIT or 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode() != integrity:
            raise Invalid('artifact integrity or size')
        path = Path(output) / artifact
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f: f.write(data)
        print('FETCHED ' + name + ' sha256=' + hashlib.sha256(data).hexdigest())

if __name__ == '__main__':
    try:
        if len(sys.argv) != 3: raise Invalid('usage: fetch.py ROOT EMPTY_OUTPUT_DIRECTORY')
        fetch(sys.argv[1], sys.argv[2])
    except (Invalid, OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        print('BLOCKED: ' + str(e), file=sys.stderr); sys.exit(1)
