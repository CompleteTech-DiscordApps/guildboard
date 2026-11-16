"""Synthetic behavior tests; these do not validate publisher bytes."""
import hashlib, importlib.util, json, os, pathlib, tempfile, unittest
from unittest.mock import patch
P = pathlib.Path(__file__).resolve().parents[3] / 'scripts/research/editor13/probe.py'
spec = importlib.util.spec_from_file_location('editor13_probe', P)
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / 'evidence'; self.root.mkdir()
        peers = {'react':'^17.0.2 || ^18.2.0 || ^19.0.0','react-dom':'^17.0.2 || ^18.2.0 || ^19.0.0'}
        values = {name: b'synthetic' for name in probe.HASHES}
        for name, obj in {
            'react_19.1.0.json': {'version':'19.1.0'},
            'react-dom_19.1.0.json': {'version':'19.1.0','peerDependencies':{'react':'^19.1.0'}},
            'fastify_5.6.1.json': {'version':'5.6.1'},
            '_excalidraw-excalidraw_0.18.1.json': {'version':'0.18.1','peerDependencies':peers},
            'excalidraw-0.18.1-declarations/package.json': {'version':'0.18.1','peerDependencies':peers},
        }.items(): values[name] = json.dumps(obj).encode()
        for name, data in values.items():
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.hashes = {n:hashlib.sha256(v).hexdigest() for n,v in values.items()}
        self.patcher = patch.object(probe, 'HASHES', self.hashes); self.patcher.start(); self.addCleanup(self.patcher.stop)
    def test_synthetic_identity_and_peers(self):
        self.assertFalse(probe.inspect(self.root)['runtime_tested'])
    def test_missing_corrupt_substitution(self):
        p = self.root / 'react_19.1.0.json'; original = p.read_bytes(); p.unlink()
        with self.assertRaises(OSError): probe.inspect(self.root)
        for value in (original + b' ', (self.root / 'react-dom_19.1.0.json').read_bytes()):
            p.write_bytes(value)
            with self.assertRaises(ValueError): probe.inspect(self.root)
    def test_fifo_and_symlinks_rejected(self):
        p = self.root / 'react_19.1.0.json'; p.unlink(); os.mkfifo(p)
        with self.assertRaises(ValueError): probe.inspect(self.root)
        p.unlink(); p.symlink_to(self.root / 'react-dom_19.1.0.json')
        with self.assertRaises(OSError): probe.inspect(self.root)
        d = self.root / 'excalidraw-0.18.1-declarations'; d.rename(self.root / 'real'); d.symlink_to(self.root / 'real', target_is_directory=True)
        with self.assertRaises(OSError): probe.read_input(self.root, 'excalidraw-0.18.1-declarations/package.json')
    def test_growth_rejected(self):
        original = probe.os.read; target = self.root / 'react_19.1.0.json'; changed = False
        def grow(fd, count):
            nonlocal changed
            data = original(fd, count)
            if data and not changed:
                changed = True
                with target.open('ab') as f: f.write(b'x')
            return data
        with patch.object(probe.os, 'read', side_effect=grow):
            with self.assertRaises(ValueError): probe.read_input(self.root, 'react_19.1.0.json')
    def test_interrupted_write_preserves_previous_result(self):
        out = pathlib.Path(self.tmp.name) / 'result.json'; out.write_text('{"previous":true}')
        with patch.object(probe.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): probe.write_result(out, {'new':True})
        self.assertEqual(json.loads(out.read_text()), {'previous':True})
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ['evidence','result.json'])
if __name__ == '__main__': unittest.main()
