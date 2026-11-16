#!/usr/bin/env python3
"""Verify cached archive identity; successful verification is not clearance.

Limits per archive: 64 MiB compressed (Reader budget), 128 MiB expanded, 50,000 headers,
4096-byte paths, 64 path components, 64 KiB extension metadata, and
8 MiB per selected file. Archives are parsed without extracting or executing.
A stable checkout/cache is required, as for check.Reader.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import tarfile
import zlib

# Load the checker beside this script, never a similarly named ambient module.
import importlib.util
_spec = importlib.util.spec_from_file_location('_license_structure_checker', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check.py'))
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)
Invalid = check.Invalid
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_METADATA = 65536
MAX_MEMBERS = 50000
MAX_PATH = 4096
MAX_DEPTH = 64
MAX_SELECTED = 8 * 1024 * 1024

def require(condition, message):
    if not condition: raise Invalid(message)

def unpack_gzip(raw):
    try:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = d.decompress(raw, MAX_ARCHIVE + 1)
        require(len(out) <= MAX_ARCHIVE and not d.unconsumed_tail, 'gzip expansion limit')
        require(d.eof and not d.unused_data, 'truncated or trailing gzip data')
        return out
    except zlib.error as e:
        raise Invalid('invalid gzip') from e

def valid_path(name, directory=False):
    if directory and name.endswith('/'): name = name[:-1]
    check.path_parts(name)
    require(len(name.encode('utf-8')) <= MAX_PATH and len(name.split('/')) <= MAX_DEPTH, 'archive path limit')
    return name

def pax(data):
    result = {}; offset = 0
    while offset < len(data):
        space = data.find(b' ', offset)
        require(space > offset and data[offset:space].isdigit(), 'invalid PAX length')
        n = int(data[offset:space]); end = offset + n
        require(n > space-offset+2 and end <= len(data) and data[end-1:end] == b'\n', 'invalid PAX record')
        record = data[space+1:end-1]; require(b'=' in record, 'invalid PAX record')
        k, v = record.split(b'=', 1)
        try: k = k.decode('utf-8'); v = v.decode('utf-8')
        except UnicodeError as e: raise Invalid('invalid PAX encoding') from e
        require(k and k not in result, 'duplicate PAX key'); result[k] = v; offset = end
    return result

def scan(data, wanted):
    pos = count = 0; seen = set(); selected = {}; pending = {}; longname = None
    while True:
        require(pos + 512 <= len(data), 'truncated tar header')
        block = data[pos:pos+512]; pos += 512
        if block == bytes(512):
            require(pos + 512 <= len(data) and data[pos:pos+512] == bytes(512) and not any(data[pos:]), 'invalid tar trailer')
            require(not pending and longname is None, 'orphan extension')
            break
        count += 1; require(count <= MAX_MEMBERS, 'tar member limit')
        try: info = tarfile.TarInfo.frombuf(block, 'utf-8', 'strict')
        except (tarfile.TarError, ValueError, UnicodeError) as e: raise Invalid('invalid tar header') from e
        size = info.size; require(type(size) is int and 0 <= size <= MAX_ARCHIVE, 'invalid tar size')
        end = pos + size; padded = pos + ((size + 511)//512)*512
        require(padded <= len(data), 'truncated tar payload')
        if info.type in (tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME):
            require(size <= MAX_METADATA, 'tar metadata limit')
            payload = data[pos:end]
            if info.type == tarfile.XHDTYPE:
                require(not pending, 'duplicate PAX extension'); pending = pax(payload)
                require(not any(k in pending for k in ('size', 'linkpath')), 'unsupported PAX override')
            else:
                require(longname is None and payload.endswith(b'\0'), 'invalid GNU longname')
                try: longname = payload[:-1].decode('utf-8')
                except UnicodeError as e: raise Invalid('invalid GNU longname') from e
            pos = padded; continue
        require(info.type in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE), 'unsupported tar member')
        require(not info.linkname, 'tar link forbidden')
        valid_path(info.name, info.isdir())
        path = pending.get('path', longname if longname is not None else info.name)
        require(not (longname is not None and 'path' in pending and pending['path'] != longname), 'conflicting extension paths')
        path = valid_path(path, info.isdir()); pending = {}; longname = None
        require(path not in seen, 'duplicate archive path'); seen.add(path)
        if path in wanted:
            require(info.isfile() and size <= MAX_SELECTED, 'invalid selected member')
            selected[path] = data[pos:end]
        pos = padded
    require(set(selected) == set(wanted), 'missing selected member')
    return selected

def verify_archives(root, artifacts):
    check.validate_structure(root)
    source = check.Reader(root); cache = check.Reader(artifacts)
    try:
        inv = source.json('docs/licenses/inventory.json', 2 * 1024 * 1024)
        lock = source.json('package-lock.json')['packages']
        notices = 0
        for path, component in sorted(inv['components'].items()):
            artifact = component['artifact']; entry = lock[path]
            require(artifact['url'] == entry['resolved'] and artifact['integrity'] == entry['integrity'], 'lock artifact mismatch: '+path)
            filename = hashlib.sha256(path.encode()).hexdigest() + '.tgz'
            require(artifact['cache_filename'] == filename, 'cache name mismatch: '+path)
            # Reader's aggregate budget is reset per artifact; each read remains bounded and stable.
            cache.total = 0
            raw = cache.read(filename, MAX_ARCHIVE)
            require(artifact['integrity'] == 'sha512-' + base64.b64encode(hashlib.sha512(raw).digest()).decode(), 'SRI mismatch: '+path)
            require(hashlib.sha256(raw).hexdigest() == artifact['archive_sha256'], 'archive hash mismatch: '+path)
            wanted = [component['manifest_archive_path']] + [n['archive_path'] for n in component['notices']]
            require(len(set(wanted)) == len(wanted), 'duplicate selected path: '+path)
            files = scan(unpack_gzip(raw), wanted)
            manifest = files[component['manifest_archive_path']]
            require(hashlib.sha256(manifest).hexdigest() == component['manifest_sha256'], 'manifest hash mismatch: '+path)
            obj = json.loads(manifest.decode('utf-8'), object_pairs_hook=check.pairs, parse_constant=lambda _: (_ for _ in ()).throw(Invalid('invalid JSON constant')))
            require(isinstance(obj, dict) and obj.get('name') == component['actual_package_name'] and obj.get('version') == component['version'], 'manifest identity mismatch: '+path)
            for n in component['notices']:
                content = files[n['archive_path']]
                require(len(content) == n['bytes'] and hashlib.sha256(content).hexdigest() == n['sha256'], 'notice identity mismatch: '+path)
                retained = source.read('docs/licenses/notices/'+n['sha256']+'.txt')
                require(content == retained, 'retained notice mismatch: '+path); notices += 1
        return {'archive_identity_verified': True, 'clearance': False, 'counts': {'components': len(inv['components']), 'notices': notices}}
    except (OSError, KeyError, TypeError, UnicodeError, ValueError) as e:
        if isinstance(e, Invalid): raise
        raise Invalid('archive verification failed: '+str(e)[:300]) from e
    finally:
        source.close(); cache.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--artifacts', required=True)
    args = parser.parse_args()
    try: print(json.dumps(verify_archives(args.root, args.artifacts), sort_keys=True))
    except Invalid as e:
        print('BLOCKED: '+str(e)[:500], file=sys.stderr); return 1
    return 0

if __name__ == '__main__': sys.exit(main())
