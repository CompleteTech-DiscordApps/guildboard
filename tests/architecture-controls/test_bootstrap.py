import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bootstrap_gate', ROOT / 'scripts/architecture-controls/check.py')
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.base = Path(self.tmp.name)/'base'; self.head = Path(self.tmp.name)/'head'
        shutil.copytree(ROOT, self.base); shutil.copytree(ROOT, self.head)
        (self.base/'scripts/architecture-controls/check.py').unlink()
        (self.base/'docs/architecture-controls/baseline.json').unlink()
        (self.base/'.github/workflows/architecture-controls.yml').unlink()
        self.manifest = self.head/'docs/architecture-controls/bootstrap.json'
        self.data = {'version':1, 'base_sha':g.BOOTSTRAP_SHA, 'boundaries':g.inventory(self.base), 'review':'independent review and protected merge required'}
        self.save()
    def tearDown(self): self.tmp.cleanup()
    def save(self): self.manifest.write_text(json.dumps(self.data))
    def runcheck(self): return g.bootstrap(self.base,self.head,g.BOOTSTRAP_SHA)
    def test_valid_and_wrong_sha(self):
        self.assertEqual(self.runcheck(),0)
        with self.assertRaises(g.Invalid): g.bootstrap(self.base,self.head,'0'*40)
    def test_witness_and_base_mutation(self):
        self.data['boundaries']['apps/api/README.md']='0'*64; self.save()
        with self.assertRaises(g.Invalid): self.runcheck()
        self.data['boundaries']=g.inventory(self.base); self.save()
        (self.base/'apps/api/README.md').write_text('changed')
        with self.assertRaises(g.Invalid): self.runcheck()
    def test_existing_gate(self):
        (self.base/'scripts/architecture-controls/check.py').write_text('x')
        with self.assertRaises(g.Invalid): self.runcheck()
    def test_head_baseline_is_not_approval(self):
        (self.head/'apps/api/README.md').write_text('changed')
        (self.head/'docs/architecture-controls/baseline.json').write_text(json.dumps({'version':1,'boundaries':g.inventory(self.head)}))
        with self.assertRaises(g.Invalid): self.runcheck()
        with self.assertRaises((g.Invalid,OSError)): g.check(self.base,self.head)
    def test_missing_malformed_and_interrupted(self):
        self.manifest.write_text('{')
        with self.assertRaises(ValueError): self.runcheck()
        self.manifest.unlink()
        with self.assertRaises(g.Invalid): self.runcheck()
        self.save(); before=self.manifest.read_bytes()
        with mock.patch.object(g,'check_trace',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): self.runcheck()
        self.assertEqual(before,self.manifest.read_bytes())
    def test_read_rejects_unsafe_files_and_paths(self):
        with self.assertRaises(g.Invalid): g.read(self.head,'../outside')
        f=self.head/'fifo'; os.mkfifo(f)
        with self.assertRaises(g.Invalid): g.read(self.head,'fifo')
        (self.head/'link').symlink_to('apps',target_is_directory=True)
        with self.assertRaises(g.Invalid): g.read(self.head,'link/api/README.md')
        (self.head/'leaf').symlink_to('apps/api/README.md')
        with self.assertRaises(g.Invalid): g.read(self.head,'leaf')
        with self.assertRaises(g.Invalid): g.read(self.head,'apps')
    def test_growth_is_bounded_and_closed(self):
        real_read=g.os.read
        def growing(fd, n): return b'x'*n
        with mock.patch.object(g.os,'read',side_effect=growing):
            with self.assertRaises(g.Invalid): g.read(self.head,'apps/api/README.md')
        self.assertTrue(real_read)

    def test_directory_replacement_and_symlink_during_inventory(self):
        original = g.os.listdir
        target = self.head/'apps/api'
        fired = []
        def swap(fd):
            names = original(fd)
            if not fired and 'README.md' in names and 'package.json' in names:
                fired.append(True)
                target.rename(target.with_name('api-old'))
                target.symlink_to('api-old', target_is_directory=True)
            return names
        with mock.patch.object(g.os, 'listdir', side_effect=swap):
            with self.assertRaises(g.Invalid): g.inventory(self.head)
        self.assertTrue(fired)

    def test_file_replacement_during_inventory(self):
        original = g.os.read
        target = self.head/'apps/api/README.md'
        fired = []
        def replace(fd, size):
            data = original(fd, size)
            if not fired and data.startswith(target.read_bytes()[:32]) and target.read_bytes():
                fired.append(True)
                target.rename(target.with_name('README.old'))
                target.write_text('replacement')
            return data
        with mock.patch.object(g.os, 'read', side_effect=replace):
            with self.assertRaises(g.Invalid): g.inventory(self.head)
        self.assertTrue(fired)
