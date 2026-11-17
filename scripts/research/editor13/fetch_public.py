#!/usr/bin/env python3
"""Fetch pinned public inputs without installing or executing packages.

Registry metadata is reconstructed in the historical npm-view representation;
its byte hash must still match. Registry changes therefore fail closed.
"""
import argparse, gzip, hashlib, importlib.util, io, json, pathlib, sys, tarfile
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('feasibility', HERE.parent / 'probe_feasibility.py')
feasibility = importlib.util.module_from_spec(spec); spec.loader.exec_module(feasibility)
spec = importlib.util.spec_from_file_location('editor13_probe', HERE / 'probe.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
ROOT = HERE.parents[2]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('redirect rejected')

opener = urllib.request.build_opener(NoRedirect())
def fetch(url, limit):
    if not (url.startswith('https://registry.npmjs.org/') or url.startswith('https://raw.githubusercontent.com/fastify/fastify/v5.6.1/docs/')):
        raise ValueError('unapproved URL')
    with opener.open(urllib.request.Request(url, headers={'Accept-Encoding':'identity','User-Agent':'guildboard-editor13-probe'}), timeout=30) as response:
        if response.geturl() != url: raise ValueError('unexpected final URL')
        return feasibility.read_bounded(response, limit)

def run(out):
    out.mkdir(parents=True, exist_ok=False)
    entries = [
        ('react_19.1.0.json','https://registry.npmjs.org/react/19.1.0'),
        ('react-dom_19.1.0.json','https://registry.npmjs.org/react-dom/19.1.0'),
        ('fastify_5.6.1.json','https://registry.npmjs.org/fastify/5.6.1'),
        ('_excalidraw-excalidraw_0.18.1.json','https://registry.npmjs.org/@excalidraw%2fexcalidraw/0.18.1')]
    data = {}
    for name, url in entries:
        metadata = json.loads(fetch(url, 4 * 1024 * 1024))
        # Match the old npm-view selected fields and order, retaining its hash.
        selected = {k:metadata[k] for k in ('version','engines','peerDependencies','dist') if k in metadata}
        dist = selected['dist']
        selected['dist'] = {k:dist[k] for k in ('shasum','tarball','fileCount','integrity','signatures','unpackedSize') if k in dist}
        data[name] = (json.dumps(selected, indent=2, ensure_ascii=False) + '\n').encode()
    for short, path in [('migration','Guides/Migration-Guide-V5.md'), ('typescript','Reference/TypeScript.md'), ('validation','Reference/Validation-and-Serialization.md')]:
        data['fastify-v5.6.1-' + short + '.md'] = fetch('https://raw.githubusercontent.com/fastify/fastify/v5.6.1/docs/' + path, 128 * 1024)
    pins = json.loads((ROOT / 'docs/research/feasibility-pins.json').read_text())['packages'][0]
    archive = fetch(pins['tarball'], feasibility.MAX_ARCHIVE)
    feasibility.inspect_archive(archive, pins)
    # Repeat bounded decompression only after the shared inspector validated the
    # archive integrity, every member, duplicates, selected types and hashes.
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        expanded = feasibility.read_bounded(stream, feasibility.MAX_UNPACKED)
    wanted = {'package/package.json':'package.json', 'package/dist/types/excalidraw/index.d.ts':'dist--types--excalidraw--index.d.ts', 'package/dist/types/excalidraw/types.d.ts':'dist--types--excalidraw--types.d.ts'}
    with tarfile.open(fileobj=io.BytesIO(expanded), mode='r|') as tar:
        for member in tar:
            if member.name in wanted:
                data['excalidraw-0.18.1-declarations/' + wanted[member.name]] = feasibility.read_bounded(tar.extractfile(member), feasibility.MAX_SELECTED)
    if set(data) != set(probe.HASHES): raise ValueError('incomplete public inputs')
    for name, raw in data.items():
        if hashlib.sha256(raw).hexdigest() != probe.HASHES[name]: raise ValueError('historical hash mismatch: ' + name)
    for name, raw in data.items():
        target = out / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    print('public source bytes match historical hashes; run probe separately')

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output-dir', required=True); args = parser.parse_args()
    try: run(pathlib.Path(args.output_dir))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        parser.exit(1, 'public input unavailable or changed: ' + str(error) + '\n')
if __name__ == '__main__': main()
