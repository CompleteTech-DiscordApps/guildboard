#!/usr/bin/env python3
"""Independent offline acceptance of the installed architecture gate.

Run: python3 -B scripts/verification/verify_architecture_controls.py --base /path/to/engineering20 --tmp /writable/scratch
The base must be the actual first-install 8f75 tree. Fixtures are disposable copies.
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, platform, re, shutil, stat, sys, tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PIN = '8f75fdb398dfb48d577135ee08f295a4c4f634b6'
POL = 'docs/architecture-controls/'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
# Projection deliberately omits checkout metadata, dependencies and generated output.
EXCLUDE = {'.git', 'node_modules', 'dist', '__pycache__'}
EXTRA = ('docs/architecture-controls/baseline.json', 'docs/architecture-controls/traceability.json',
         'docs/architecture-controls/decisions.json', 'docs/architecture-controls/bootstrap.json',
         'scripts/architecture-controls/check.py', 'scripts/verification/verify_architecture_controls.py',
         'tests/architecture-controls/test_gate.py',
         '.github/workflows/architecture-controls.yml')

def projection(root):
    names = set()
    def walk(path):
        if path.name in EXCLUDE: return
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            entries = sorted(path.iterdir())
            if len(entries) > g.MAX_FILES: raise ValueError('too many entries')
            for entry in entries: walk(entry)
        elif stat.S_ISREG(info.st_mode):
            names.add(path.relative_to(root).as_posix())
            if len(names) > g.MAX_FILES: raise ValueError('too many files')
        else: raise ValueError('nonregular projection entry: '+str(path))
    for name in g.ROOTS:
        walk(root/name)
    for name in (*g.FIXED, *EXTRA):
        if os.path.lexists(root/name): names.add(name)
    # Include all evidence named by the gate's trace and decision catalogs.
    for name in ('docs/architecture-controls/traceability.json', 'docs/architecture-controls/decisions.json'):
        if name not in names: continue
        data = json.loads(g.read(root, name))
        if name.endswith('traceability.json'):
            for catalog in ('interfaces', 'controls'):
                for entry in data[catalog].values(): names.update(entry['evidence'])
        else:
            for record in data['records']:
                names.update(record['controls']); names.update(record['test_evidence'])
    return {name: g.read(root, name) for name in sorted(names)}

def snapshot(root):
    return {name: hashlib.sha256(data).hexdigest() for name, data in projection(root).items()}

def copy_projection(root, target):
    contents = projection(root)  # validate everything before writing the fixture
    target.mkdir(parents=True)
    for name, data in contents.items():
        path = target/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)

def revision(value):
    if not re.fullmatch(r'[0-9a-f]{40}', value): raise argparse.ArgumentTypeError('revision must be a lowercase full 40-character SHA')
    return value
def save(p, x): p.write_text(json.dumps(x, indent=2)+'\n')
def main():
    a=argparse.ArgumentParser(); a.add_argument('--base',type=Path,required=True); a.add_argument('--tmp',type=Path,required=True); a.add_argument('--revision',type=revision,required=True); args=a.parse_args()
    sys.dont_write_bytecode=True
    global g
    spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/architecture-controls/check.py'); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    original=snapshot(ROOT); base_original=snapshot(args.base)
    failures=[]; count=0
    print('revision='+args.revision+'; base='+PIN+'; identity=caller-supplied, not independently Git verified')
    print('harness_sha256='+digest(Path(__file__))+'; gate_sha256='+digest(ROOT/'scripts/architecture-controls/check.py'))
    print('platform='+platform.platform()+'; python='+sys.version.replace('\n',' '))
    with tempfile.TemporaryDirectory(dir=args.tmp, prefix='accept31-') as temp:
        temp=Path(temp); head=temp/'head'; copy_projection(ROOT,head)
        def reset():
            shutil.rmtree(head); copy_projection(ROOT,head)
        def run(name, fn):
            nonlocal count
            count+=1
            try: fn(); print('PASS '+name)
            except Exception as e: failures.append(name); print('FAIL '+name+': '+repr(e))
        def reject(fn):
            try: fn()
            except (g.Invalid, OSError, ValueError, KeyError, TypeError): return
            raise AssertionError('invalid input accepted')
        def check(): return g.check(ROOT,head)
        def seal():
            # Calculate witness independently from known baseline paths and file bytes.
            p=head/POL/'baseline.json'; data=json.loads(p.read_text()); names=set(data['boundaries'])
            names={n for n in names if (head/n).is_file()}
            for folder in ('apps','packages','database','infra/godaddy'):
                names.update(str(p.relative_to(head)) for p in (head/folder).rglob('*') if p.is_file())
            data['boundaries']={n:digest(head/n) for n in sorted(names)}; save(p,data)
        def record(path, old, new):
            p=head/POL/'decisions.json'; x=json.loads(p.read_text()); x['records'].append(dict(id='DEC-9001',revision=1,boundary=path,old_sha256=old,new_sha256=new,rationale='Explain the impact to reviewers',alternatives=['Retain existing boundary'],controls=['docs/security/GB-T0-04-02-threat-model.md'],test_evidence=['tests/architecture-controls/test_gate.py'])); save(p,x)
        def changed():
            p='apps/api/README.md'; old=digest(ROOT/p); (head/p).write_bytes((head/p).read_bytes()+b'\nacceptance change\n'); seal(); return p,old,digest(head/p)
        run('installed self comparison',lambda: (_ for _ in ()).throw(AssertionError()) if check()!=0 else None)
        run('actual first install',lambda: (_ for _ in ()).throw(AssertionError()) if g.bootstrap(args.base,ROOT,PIN)!=1 else None)
        run('wrong first install base identity',lambda: reject(lambda:g.bootstrap(args.base,ROOT,'0'*40)))
        def alteration():
            p,o,n=changed(); reject(check); record(p,o,n); assert check()==1
            f=head/POL/'decisions.json'; orig=json.loads(f.read_text())
            for key,value in [('old_sha256','0'*64),('new_sha256','0'*64),('rationale',''),('alternatives',[]),('controls',[]),('test_evidence',['missing-evidence'])]:
                x=json.loads(json.dumps(orig)); x['records'][-1][key]=value; save(f,x); reject(check)
            save(f,orig)
        run('byte change and exact decision fields',alteration); reset()
        def addremove():
            a='apps/api/package.json'; b='apps/api/renamed.md'; old=digest(head/a); (head/a).rename(head/b); seal(); reject(check)
            record(a,old,None); reject(check); record(b,None,old); assert check()==2
        # distinct record identities for rename
        def rename():
            a='apps/api/package.json'; b='apps/api/renamed.md'; old=digest(head/a); (head/a).rename(head/b); seal(); reject(check)
            record(a,old,None); reject(check)
            f=head/POL/'decisions.json'; x=json.loads(f.read_text()); x['records'][-1]['id']='DEC-9002'; save(f,x)
            record(b,None,old); assert check()==2
        run('rename requires removal and addition decisions',rename); reset()
        for kind in ('add','remove'):
            def mutation(kind=kind):
                p='apps/api/new-boundary.txt' if kind=='add' else 'apps/api/package.json'; old=digest(head/p)
                if kind=='add': (head/p).write_text('new boundary')
                else: (head/p).unlink()
                seal(); reject(check); record(p,old,digest(head/p)); assert check()==1
            run(kind+' boundary',mutation); reset()
        def missing(): (head/POL/'baseline.json').unlink(); reject(check)
        run('missing policy',missing); reset()
        def malformed(): (head/POL/'traceability.json').write_text('{'); reject(check)
        run('malformed json',malformed); reset()
        def unknown():
            p=head/POL/'traceability.json'; x=json.loads(p.read_text()); x['unexpected']=True; save(p,x); reject(check)
        run('unknown policy shape',unknown); reset()
        for kind in ('symlink','fifo','oversize'):
            def unsafe(kind=kind):
                p=head/'apps/api/unsafe';
                if kind=='symlink': p.symlink_to('README.md')
                elif kind=='fifo': os.mkfifo(p)
                else: p.write_bytes(b'x'*(4*1024*1024+1))
                reject(check)
            run('reject '+kind,unsafe); reset()
        def interrupted():
            before=snapshot(head); out=io.StringIO(); err=io.StringIO()
            with patch.object(g.os,'read',side_effect=OSError('simulated interrupted read')), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): reject(check)
            assert not out.getvalue() and not err.getvalue() and snapshot(head)==before
        run('read interruption no success output or writes',interrupted)
        def trace_mutation(key,rid,val):
            p=head/POL/'traceability.json'; x=json.loads(p.read_text()); x['requirements'][rid][key].remove(val); save(p,x); reject(check)
        for key,rid,val in [('use_cases','R01','UC01'),('interactions','R05','I09'),('canonical_acceptance','R05','F10')]:
            run('trace missing '+key,lambda key=key,rid=rid,val=val:trace_mutation(key,rid,val)); reset()
        def unrelated():
            p=head/POL/'traceability.json'; x=json.loads(p.read_text()); x['requirements']['R05']['interactions'].append('I10'); x['requirements']['R05']['canonical_acceptance'].append('F15'); save(p,x); reject(check)
        run('unrelated valid interaction and FID together',unrelated); reset()
    run('source trees unchanged',lambda: (None if snapshot(ROOT)==original and snapshot(args.base)==base_original else (_ for _ in ()).throw(AssertionError('source modified'))))
    print('SUMMARY cases=%d passed=%d failed=%d'%(count,count-len(failures),len(failures)))
    return bool(failures)
if __name__=='__main__': sys.exit(main())
