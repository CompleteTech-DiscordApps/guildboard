import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('verifier', ROOT / 'scripts/verification/verify_architecture.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in v.BASELINE:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
    def tearDown(self):
        self.tmp.cleanup()
    def test_baseline(self):
        self.assertIn('PASS', v.verify(self.root))
    def test_architecture_reversals_and_omissions(self):
        p = self.root / 'docs/architecture.md'
        original = p.read_text()
        mutations = [
            ('B --> C', 'B --> DB'),
            ('atomic state + revision + receipt + outbox + audit commit', 'ACK before commit'),
            ('Revocation ordered first suppresses subsequent queued releases', 'Revocation permits subsequent queued releases'),
            ('never replay the operation into the restored document', 'replay the operation into the restored document'),
            ('Public clients cannot directly reach SQL or assets', 'Public assets are allowed'),
            ('external ingress, proxy-to-service hop and private data plane', 'external ingress'),
            ('C --> S[(Private assets: quarantine and finalized objects)]', ''),
            ('D-->>C: durable commit\n    C->>C: serialized protected release check\n    C-->>A: ACK only if release authorized', 'C-->>A: ACK only if release authorized\n    D-->>C: durable commit'),
            ('[ADR 0002](adr/0002-server-authority-and-interactions.md)', '[ADR 0002](missing.md)'),
        ]
        for old, new in mutations:
            with self.subTest(old=old):
                self.assertIn(old, original)
                p.write_text(original.replace(old, new, 1))
                with self.assertRaises(v.VerificationError): v.verify(self.root)
    def test_fixture_nested_malformed_and_scenario_reversal(self):
        p = self.root / 'docs/specifications/fixtures/GB-T0-01-02-interactions.json'
        original = json.loads(p.read_text())
        for change in ('malformed', 'reversal', 'missing_reference'):
            obj = json.loads(json.dumps(original))
            if change == 'malformed': obj['scenarios'][0]['contract_scenarios'] = {'bad': [None]}
            elif change == 'reversal': obj['scenarios'][0]['expected'] = 'ACK before commit'
            else: obj['scenarios'][0]['contract_scenarios'] = []
            p.write_text(json.dumps(obj))
            with self.subTest(change=change), self.assertRaises(v.VerificationError): v.verify(self.root)
    def test_missing_prerequisite_and_invalid_config(self):
        (self.root / next(iter(v.BASELINE))).unlink()
        with self.assertRaises(v.VerificationError): v.verify(self.root)
        with self.assertRaises(v.VerificationError): v.verify(None)
        self.assertEqual(v.main(['--root', str(self.root / 'missing')]), 1)
    def test_interruption_is_not_success(self):
        def stop(): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): v.verify(self.root, stop)
        old = v.verify
        try:
            v.verify = lambda root: (_ for _ in ()).throw(KeyboardInterrupt())
            self.assertEqual(v.main(['--root', str(self.root)]), 130)
        finally: v.verify = old

if __name__ == '__main__': unittest.main()
