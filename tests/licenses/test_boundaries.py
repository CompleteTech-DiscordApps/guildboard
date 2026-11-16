"""In-process archive identity and adversarial parser tests."""
import base64
import gzip
import hashlib
import io
import json
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
        with patch.object(archive.check, 'validate_structure'):
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

if __name__ == '__main__': unittest.main()
