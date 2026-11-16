"""In-process archive identity and adversarial parser tests."""
import base64
import gzip
import hashlib
import io
import json
import os
import shutil
import contextlib
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/licenses'))
import check_archives as archive

def sha(data): return hashlib.sha256(data).hexdigest()
def tar(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as t:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name); info.type = kind; info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return out.getvalue()

def regular(name, data): return (name, data, tarfile.REGTYPE)

class ArchiveChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root/'docs/licenses/notices').mkdir(parents=True)
        (self.root/'cache').mkdir()
        self.path = 'node_modules/parent/node_modules/@types/a'
        self.manifest = b'{"name":"@types/a","version":"1.0.0"}'
        self.notice = b'notice'; self.url = 'https://registry.example/a.tgz'
        self.entries = [regular('a/package.json', self.manifest), regular('a/LICENSE', self.notice)]
        self.component = {'actual_package_name':'@types/a', 'version':'1.0.0', 'manifest_archive_path':'a/package.json', 'manifest_sha256':sha(self.manifest), 'notices':[{'archive_path':'a/LICENSE','sha256':sha(self.notice),'bytes':len(self.notice)}]}
        (self.root/'docs/licenses/notices'/ (sha(self.notice)+'.txt')).write_bytes(self.notice)
    def save(self, raw=None):
        raw = raw if raw is not None else gzip.compress(tar(self.entries))
        filename = sha(self.path.encode())+'.tgz'; (self.root/'cache'/filename).write_bytes(raw)
        artifact = {'url':self.url,'integrity':'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode(), 'archive_sha256':sha(raw), 'cache_filename':filename}
        self.component['artifact'] = artifact
        (self.root/'docs/licenses/inventory.json').write_text(json.dumps({'components':{self.path:self.component}}))
        (self.root/'package-lock.json').write_text(json.dumps({'packages':{self.path:{'resolved':self.url,'integrity':artifact['integrity']}}}))
    def verify(self):
        # Synthetic parser fixtures do not satisfy the real structure contract.
        hashes = {str(p.relative_to(self.root)): sha(p.read_bytes()) for p in (self.root/'docs/licenses').rglob('*') if p.is_file()}
        hashes['package-lock.json'] = sha((self.root/'package-lock.json').read_bytes())
        with patch.object(archive.check, 'validate_structure', return_value={'hashes': hashes}):
            return archive.verify_archives(self.root, self.root/'cache')
    def test_exact_identity_nested_and_types_root(self):
        self.save(); self.assertEqual(self.verify()['counts'], {'components':1,'notices':1})
    def test_identity_mismatches(self):
        for field in ('sri', 'sha', 'manifest', 'notice', 'retained', 'url'):
            with self.subTest(field=field):
                self.setUp(); self.save()
                invpath=self.root/'docs/licenses/inventory.json'; inv=json.loads(invpath.read_text()); c=inv['components'][self.path]
                if field=='sri':
                    c['artifact']['integrity']='sha512-invalid'; lock=json.loads((self.root/'package-lock.json').read_text()); lock['packages'][self.path]['integrity']='sha512-invalid'; (self.root/'package-lock.json').write_text(json.dumps(lock))
                elif field=='sha': c['artifact']['archive_sha256']='0'*64
                elif field=='manifest': c['manifest_sha256']='0'*64
                elif field=='notice': c['notices'][0]['bytes']+=1
                elif field=='retained': (self.root/'docs/licenses/notices'/ (sha(self.notice)+'.txt')).write_bytes(b'changed')
                else: c['artifact']['url']='https://wrong.example/'
                invpath.write_text(json.dumps(inv))
                with self.assertRaises(archive.Invalid): self.verify()
    def test_bad_members(self):
        for extra in (regular('a/LICENSE',b'x'), regular('../escape',b'x'), ('a/link',b'',tarfile.SYMTYPE), ('a/device',b'',tarfile.CHRTYPE), regular('a/./x',b''), regular('a\\x',b'')):
            with self.subTest(extra=extra):
                self.save(gzip.compress(tar(self.entries+[extra])))
                with self.assertRaises(archive.Invalid): self.verify()
    def test_limits_and_invalid_extensions(self):
        raw=tar(self.entries)
        with patch.object(archive, 'MAX_ARCHIVE', 100):
            with self.assertRaises(archive.Invalid): archive.unpack_gzip(gzip.compress(raw))
        with patch.object(archive, 'MAX_MEMBERS', 1):
            with self.assertRaises(archive.Invalid): archive.scan(raw, [])
        with patch.object(archive, 'MAX_SELECTED', 1):
            with self.assertRaises(archive.Invalid): archive.scan(raw, ['a/LICENSE'])
        for payload, kind in ((b'bad',tarfile.XHDTYPE), (b'x'*65537,tarfile.XHDTYPE), (b'x'*65537,tarfile.GNUTYPE_LONGNAME)):
            with self.subTest(kind=kind, length=len(payload)):
                with self.assertRaises(archive.Invalid): archive.scan(tar([( 'extension',payload,kind)]+self.entries), [])
        for malformed in (raw[:600], raw[:-512]+b'X'*512, b'X'+raw[1:]):
            with self.assertRaises(archive.Invalid): archive.scan(malformed, [])
        with self.assertRaises(archive.Invalid): archive.unpack_gzip(gzip.compress(raw)+b'junk')

class ValidatedInputChecks(unittest.TestCase):
    """Exercise real structural validation against the copied candidate and cache."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'source'
        shutil.copytree(Path(__file__).resolve().parents[2], self.root)
        self.cache = Path(os.environ['LICENSE16_ARTIFACT_FIXTURE'])
        self.validate = archive.check.validate_structure

    def test_matching_inventory_lock_rewrite_after_validation(self):
        def replace(root):
            evidence = self.validate(root)
            ip = self.root/'docs/licenses/inventory.json'; lp = self.root/'package-lock.json'
            inv = json.loads(ip.read_text()); lock = json.loads(lp.read_text())
            p = next(iter(inv['components'])); url = 'https://attacker.example/changed.tgz'
            inv['components'][p]['artifact']['url'] = url; lock['packages'][p]['resolved'] = url
            ip.write_text(json.dumps(inv)); lp.write_text(json.dumps(lock))
            return evidence
        with patch.object(archive.check, 'validate_structure', side_effect=replace):
            with self.assertRaisesRegex(archive.Invalid, 'input changed after validation'):
                archive.verify_archives(self.root, self.cache)
        with self.assertRaises(archive.Invalid): self.validate(self.root)

    def test_retained_notice_replaced_after_validation(self):
        def replace(root):
            evidence = self.validate(root)
            inv = json.loads((self.root/'docs/licenses/inventory.json').read_text())
            component = next(c for c in inv['components'].values() if c['notices'])
            notice = self.root/'docs/licenses/notices'/(component['notices'][0]['sha256']+'.txt')
            notice.write_bytes(b'replaced')
            return evidence
        with patch.object(archive.check, 'validate_structure', side_effect=replace):
            with self.assertRaisesRegex(archive.Invalid, 'input changed after validation'):
                archive.verify_archives(self.root, self.cache)

    def test_missing_and_symlink_cache_are_bounded_and_close_source(self):
        link = Path(self.temp.name)/'link'; link.symlink_to(self.cache, target_is_directory=True)
        real_reader = archive.check.Reader
        for cache in (Path(self.temp.name)/'missing', link):
            opened = []
            def reader(root):
                result = real_reader(root); opened.append(result); return result
            with self.subTest(cache=cache), patch.object(archive.check, 'Reader', side_effect=reader):
                with self.assertRaises(archive.Invalid): archive.verify_archives(self.root, cache)
                self.assertTrue(opened); self.assertTrue(all(not r.chain for r in opened))
            stderr = io.StringIO()
            with patch.object(sys, 'argv', ['check_archives.py', '--root', str(self.root), '--artifacts', str(cache)]), contextlib.redirect_stderr(stderr):
                self.assertEqual(archive.main(), 1)
            self.assertTrue(stderr.getvalue().startswith('BLOCKED: ')); self.assertLessEqual(len(stderr.getvalue()), 510)
            self.assertNotIn('Traceback', stderr.getvalue())

    def test_opened_readers_close_on_read_failure(self):
        real_reader = archive.check.Reader; opened = []
        def reader(root):
            result = real_reader(root); opened.append(result)
            if Path(root) == self.cache:
                def fail(*args, **kwargs): raise OSError('simulated cache read failure')
                result.read = fail
            return result
        with patch.object(archive.check, 'Reader', side_effect=reader):
            with self.assertRaisesRegex(archive.Invalid, 'simulated cache read failure'):
                archive.verify_archives(self.root, self.cache)
        self.assertGreaterEqual(len(opened), 2); self.assertTrue(all(not r.chain for r in opened))

if __name__ == '__main__': unittest.main()
