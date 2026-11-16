import importlib.util, json, pathlib, shutil, tempfile, unittest
from unittest.mock import patch
P = pathlib.Path(__file__).resolve().parents[3] / 'scripts/research/editor13/probe.py'
spec = importlib.util.spec_from_file_location('editor13_probe', P); probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
EVIDENCE = pathlib.Path(__file__).resolve().parents[6] / 'editor13-primary-evidence'

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / 'evidence'; shutil.copytree(EVIDENCE, self.root)
    def test_real_publisher_bytes_and_peers(self):
        self.assertFalse(probe.inspect(self.root)['runtime_tested'])
    def test_missing_and_corrupt_and_substitution(self):
        p = self.root / 'react_19.1.0.json'; original = p.read_bytes()
        p.unlink()
        with self.assertRaises(OSError): probe.inspect(self.root)
        p.write_bytes(original + b' ')
        with self.assertRaises(ValueError): probe.inspect(self.root)
        p.write_bytes((self.root / 'react-dom_19.1.0.json').read_bytes())
        with self.assertRaises(ValueError): probe.inspect(self.root)
    def test_interrupted_write_preserves_previous_result(self):
        out = pathlib.Path(self.tmp.name) / 'result.json'; out.write_text('{"previous":true}')
        with patch.object(probe.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): probe.write_result(out, {'new':True})
        self.assertEqual(json.loads(out.read_text()), {'previous':True})
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ['evidence','result.json'])
if __name__ == '__main__': unittest.main()
