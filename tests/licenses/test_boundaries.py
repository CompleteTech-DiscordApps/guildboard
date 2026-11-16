import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts/licenses'
sys.path.insert(0, str(SCRIPTS))
import check
import fetch

class Boundaries(unittest.TestCase):
    def test_fifo_and_symlink_fail_without_blocking(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkfifo(Path(d)/'fifo')
            (Path(d)/'link').symlink_to('fifo')
            for path in ('fifo', 'link'):
                with self.assertRaises((check.Invalid, OSError)): check.read(d, path)

    def test_fetch_injected_bytes_and_rejections(self):
        class Opener:
            def __init__(self, data): self.data = data
            def open(self, url, timeout): return io.BytesIO(self.data)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'docs/licenses').mkdir(parents=True); (root/'out').mkdir()
            digest='sha512-'+base64.b64encode(hashlib.sha512(b'bytes').digest()).decode()
            url='https://registry.npmjs.org/a/-/a-1.tgz'
            lock={'packages':{'node_modules/a':{'resolved':url,'integrity':digest}}}
            raw=json.dumps(lock).encode(); (root/'package-lock.json').write_bytes(raw)
            inv={'inputs':{'package-lock.json':hashlib.sha256(raw).hexdigest()},'components':[{'name':'a','source':url,'integrity':digest,'artifact':'a.tgz'}]}
            def save(): (root/'docs/licenses/inventory.json').write_text(json.dumps(inv))
            save(); fetch.fetch(root,root/'out',Opener(b'bytes'))
            self.assertEqual((root/'out/a.tgz').read_bytes(),b'bytes')
            (root/'out/a.tgz').unlink()
            with self.assertRaises(check.Invalid): fetch.fetch(root,root/'out',Opener(b'bad'))
            inv['components'][0]['source']='https://evil.example/a'; save()
            with self.assertRaises(check.Invalid): fetch.fetch(root,root/'out',Opener(b'bytes'))
            self.assertEqual(list((root/'out').iterdir()), [])

    def test_nested_unknown_and_missing_lock_dependency(self):
        from test_check import PolicyCheck, digest
        case=PolicyCheck(); case.setUp()
        try:
            p=case.root/'package-lock.json'; original=json.loads(p.read_text())
            for mutate in (lambda lock: lock['packages'].update({'node_modules/a/node_modules/b': {}}),
                           lambda lock: lock['packages'].update({'mystery': {}}),
                           lambda lock: lock['packages']['node_modules/a'].update({'dependencies': {'missing':'1'}}),
                           lambda lock: lock['packages'].update({'node_modules/a': []})):
                lock=json.loads(json.dumps(original)); mutate(lock); p.write_text(json.dumps(lock))
                case.inv['inputs']['package-lock.json']=digest(p.read_bytes()); case.save(); case.blocked()
        finally: case.tearDown()

class ArchiveChecks(unittest.TestCase):
    def test_archive_notice_mismatch_and_duplicate_block(self):
        import check_archives
        import tarfile
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'docs/licenses').mkdir(parents=True); (root/'modules/a').mkdir(parents=True); (root/'artifacts').mkdir()
            (root/'modules/a/LICENSE').write_bytes(b'notice')
            def archive(contents):
                out=io.BytesIO()
                with tarfile.open(fileobj=out,mode='w:gz') as tar:
                    for data in contents:
                        info=tarfile.TarInfo('package/LICENSE'); info.size=len(data); tar.addfile(info,io.BytesIO(data))
                raw=out.getvalue(); (root/'artifacts/a.tgz').write_bytes(raw)
                inv={'components':[{'name':'a','artifact':'a.tgz','integrity':'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode(),'notices':[{'path':'a/LICENSE','sha256':hashlib.sha256(b'notice').hexdigest()}]}]}
                (root/'docs/licenses/inventory.json').write_text(json.dumps(inv))
            archive([b'notice']); check_archives.check_archives(root,root/'modules',root/'artifacts')
            for content in ([b'wrong'],[b'notice',b'notice']):
                archive(content)
                with self.assertRaises(check.Invalid): check_archives.check_archives(root,root/'modules',root/'artifacts')
