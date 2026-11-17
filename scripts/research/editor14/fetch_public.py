#!/usr/bin/env python3
"""Fetch the accepted public inputs; SQL documents stay outside the repository."""
import argparse, hashlib, importlib.util, json, pathlib, sys, urllib.request
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
old=module('editor13_fetch',HERE.parent/'editor13/fetch_public.py')
verify=module('editor14_verify',ROOT/'scripts/verification/verify_editor_feasibility.py')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('redirect rejected')
def run(out):
    out.mkdir(parents=True,exist_ok=False)
    pins=json.loads((ROOT/'docs/research/feasibility-pins.json').read_text())['packages'][0]
    if pins['tarball'] != 'https://registry.npmjs.org/@excalidraw/excalidraw/-/excalidraw-0.18.1.tgz': raise ValueError('unapproved archive URL')
    old.run(out/'public')
    (out/'sql').mkdir()
    opener=urllib.request.build_opener(NoRedirect())
    for name,entry in verify.SOURCES.items():
        if not name.startswith('sql/'): continue
        url=entry['url']
        with opener.open(urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'guildboard-editor14'}),timeout=30) as response:
            if response.geturl()!=url: raise ValueError('unexpected redirect')
            raw=response.read(4_000_001)
        if len(raw)>4_000_000 or hashlib.sha256(raw).hexdigest()!=entry['sha256']: raise ValueError('SQL source unavailable or changed: '+name)
        (out/name).write_bytes(raw)
    print('14 source inputs fetched and hash checked')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=pathlib.Path,required=True); a=p.parse_args()
    try: run(a.output_dir)
    except (OSError,ValueError,KeyError,TypeError) as e: p.exit(1,'public input unavailable or changed: '+str(e)+'\n')
if __name__=='__main__': main()
