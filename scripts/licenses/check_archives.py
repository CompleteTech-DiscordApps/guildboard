#!/usr/bin/env python3
"""Compare reviewed installed notices to notices in integrity-checked npm archives."""
import base64
import hashlib
import io
import sys
import tarfile
from check import Invalid, LIMIT, obj, read

def check_archives(root, modules, artifacts):
    inv = obj(read(root, 'docs/licenses/inventory.json'))
    for c in inv['components']:
        data = read(artifacts, c['artifact'])
        if 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode() != c['integrity']:
            raise Invalid('changed archive: ' + c['name'])
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            members = []
            total = 0
            for member in archive:
                total += member.size
                if len(members) >= 50000 or total > 100_000_000: raise Invalid('archive expansion limit')
                members.append(member)
            for notice in c['notices']:
                suffix = notice['path'][len(c['name'])+1:]
                matches = [m for m in members if m.name.endswith('/' + suffix) and m.name.count('/') == 1]
                if len(matches) != 1 or not matches[0].isfile() or matches[0].size > LIMIT:
                    raise Invalid('invalid archive notice: ' + notice['path'])
                file = archive.extractfile(matches[0])
                data = file.read(LIMIT+1)
                installed = read(modules, notice['path'])
                if data != installed or hashlib.sha256(data).hexdigest() != notice['sha256']:
                    raise Invalid('archive notice mismatch: ' + notice['path'])
        print('MATCHED ' + c['name'] + ' ' + str(len(c['notices'])) + ' notice(s)')

if __name__ == '__main__':
    try:
        if len(sys.argv) != 4: raise Invalid('usage: check_archives.py ROOT MODULES ARTIFACTS')
        check_archives(*sys.argv[1:])
    except (Invalid, OSError, ValueError, TypeError, KeyError, AttributeError, tarfile.TarError, EOFError) as e:
        print('BLOCKED: ' + str(e), file=sys.stderr); sys.exit(1)
