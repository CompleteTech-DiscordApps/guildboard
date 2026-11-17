#!/usr/bin/env python3
"""Independent offline acceptance of the installed architecture gate.

Run: python3 -B scripts/verification/verify_architecture_controls.py --base /path/to/engineering20 --installed /path/to/initial-install --tmp /writable/scratch --revision <full-caller-supplied-sha>
Use the 8f75 pre-install and 556d initial-install trees. Candidate fixtures are disposable copies.
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, platform, re, shutil, stat, sys, tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PIN = '8f75fdb398dfb48d577135ee08f295a4c4f634b6'
POL = 'docs/architecture-controls/'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
# The protected inventory includes every basename, including generated-looking names.
# Bounds apply globally, including empty directories; stable checkout is required.
MAX_ENTRIES = 10000
MAX_DIRS = 5000
MAX_DEPTH = 64
MAX_CONTENT = 128 * 1024 * 1024
EXTRA = ('docs/architecture-controls/baseline.json', 'docs/architecture-controls/traceability.json',
         'docs/architecture-controls/decisions.json', 'docs/architecture-controls/bootstrap.json',
         'scripts/architecture-controls/check.py', 'scripts/verification/verify_architecture_controls.py',
         'tests/architecture-controls/test_gate.py', '.github/workflows/architecture-controls.yml')

def projection(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    def stamp(st):
        return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    def scan():
        files = {}; dirs = {}; entries = 0
        rootfd = os.open(root, flags)
        def walk(parent, name, path, depth):
            nonlocal entries
            if depth > MAX_DEPTH: raise ValueError('projection depth limit')
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            fd = os.open(name, flags, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode) or stamp(info) != stamp(before): raise ValueError('unstable directory: '+path)
                names = sorted(os.listdir(fd))
                dirs[path] = (stamp(info), tuple(names))
                if len(dirs) > MAX_DIRS: raise ValueError('projection directory limit')
                entries += len(names)
                if entries > MAX_ENTRIES: raise ValueError('projection entry limit')
                for child in names:
                    childpath = path+'/'+child
                    st = os.stat(child, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode): walk(fd, child, childpath, depth+1)
                    elif stat.S_ISREG(st.st_mode): files[childpath] = stamp(st)
                    else: raise ValueError('nonregular projection entry: '+childpath)
                if (names != sorted(os.listdir(fd)) or stamp(os.fstat(fd)) != stamp(info) or
                    stamp(os.stat(name, dir_fd=parent, follow_symlinks=False)) != stamp(info)):
                    raise ValueError('directory changed: '+path)
            finally: os.close(fd)
        try:
            for path in g.ROOTS:
                parts = path.split('/'); parent = rootfd; opened = []
                try:
                    for part in parts[:-1]:
                        before = os.stat(part, dir_fd=parent, follow_symlinks=False)
                        fd = os.open(part, flags, dir_fd=parent); opened.append((parent, part, fd, stamp(before)))
                        if stamp(os.fstat(fd)) != stamp(before): raise ValueError('unstable ancestor')
                        parent = fd
                    walk(parent, parts[-1], path, len(parts))
                    for par, part, fd, before in opened:
                        if stamp(os.fstat(fd)) != before or stamp(os.stat(part, dir_fd=par, follow_symlinks=False)) != before: raise ValueError('ancestor changed')
                finally:
                    for _, _, fd, _ in reversed(opened): os.close(fd)
        finally: os.close(rootfd)
        return files, dirs
    files, before = scan()
    names = set(files) | {name for name in (*g.FIXED, *EXTRA) if os.path.lexists(root/name)}
    contents = {}; total = 0
    def capture(name):
        nonlocal total
        if name not in contents:
            data = g.read(root, name)
            total += len(data)
            if total > MAX_CONTENT: raise ValueError('projection content limit')
            contents[name] = data
    for name in sorted(names): capture(name)
    for name in ('docs/architecture-controls/traceability.json', 'docs/architecture-controls/decisions.json'):
        if name not in contents: continue
        data = json.loads(contents[name])
        if name.endswith('traceability.json'):
            for catalog in ('interfaces', 'controls'):
                for entry in data[catalog].values():
                    for ref in entry['evidence']: capture(ref)
        else:
            for record in data['records']:
                for ref in (*record['controls'], *record['test_evidence']): capture(ref)
    after_files, after = scan()
    if files != after_files or before != after: raise ValueError('projection changed during capture')
    # Re-read to detect changes between capture and the final membership scan.
    for name, data in contents.items():
        if g.read(root, name) != data: raise ValueError('projection file changed: '+name)
    final_files, final = scan()
    if files != final_files or before != final: raise ValueError('projection changed during validation')
    return contents

def snapshot(root):
    return {name: hashlib.sha256(data).hexdigest() for name, data in projection(root).items()}

def copy_projection(root, target):
    contents = projection(root)  # capture and validate everything before writing
    target = Path(target)
    if target.exists() or target.is_symlink(): raise FileExistsError(str(target))
    staging = Path(tempfile.mkdtemp(prefix='.projection-', dir=target.parent))
    try:
        for name, data in contents.items():
            path = staging/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        os.rename(staging, target)
    finally:
        if staging.exists(): shutil.rmtree(staging)

def revision(value):
    if not re.fullmatch(r'[0-9a-f]{40}', value): raise argparse.ArgumentTypeError('revision must be a lowercase full 40-character SHA')
    return value
def save(p, x): p.write_text(json.dumps(x, indent=2)+'\n')
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--tmp', type=Path, required=True)
    parser.add_argument('--revision', type=revision, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode=True
    global g
    spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/architecture-controls/check.py'); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    sources = {path: snapshot(path) for path in (ROOT, args.base, args.installed)}
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
        def historical_bootstrap():
            if g.bootstrap(args.base, args.installed, PIN) != 1:
                raise AssertionError('historical installation must introduce exactly one boundary')
        run('actual first install', historical_bootstrap)
        run('wrong first install base identity', lambda: reject(
            lambda: g.bootstrap(args.base, args.installed, '0' * 40)
        ))
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
    def source_trees_unchanged():
        if any(snapshot(path) != before for path, before in sources.items()):
            raise AssertionError('source modified')
    run('source trees unchanged', source_trees_unchanged)
    print('SUMMARY cases=%d passed=%d failed=%d'%(count,count-len(failures),len(failures)))
    return bool(failures)
if __name__=='__main__': sys.exit(main())
