"""Negative acceptance of the offline verifier, not platform fault tests."""
import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('verifier', ROOT / 'scripts/verification/verify_requirements.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        for name in (v.DOC, v.FIX, 'docs/specifications/GB-T0-S1-system-contract.md', 'planning/MVP-ACCEPTANCE.md', 'planning/MILESTONES.md', 'docs/adr/0001-editor-activity-vps-direction.md'):
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        self.addCleanup(self.temp.cleanup)

    def mutate_fixture(self, edit):
        path = self.root / v.FIX
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data))

    def test_baseline(self):
        self.assertEqual(v.check(self.root)['status'], 'pass')

    def test_unknown_requirement(self):
        self.mutate_fixture(lambda d: d['cases'][0]['requirements'].append('R99'))
        self.assertEqual(v.check(self.root)['status'], 'fail')

    def test_duplicate_case(self):
        self.mutate_fixture(lambda d: d['cases'][1].update(id='UC01'))
        self.assertEqual(v.check(self.root)['status'], 'fail')

    def test_missing_mandatory_scope(self):
        path = self.root / v.DOC
        path.write_text(path.read_text().replace('foreign and unknown resources have the same public not-found outcome', 'foreign resources are handled'))
        self.assertEqual(v.check(self.root)['status'], 'fail')

    def test_reviewed_case_fields_are_pinned(self):
        for field in ('actor', 'preconditions', 'action', 'expected'):
            with self.subTest(field=field):
                path = self.root / v.FIX
                original = path.read_text()
                self.mutate_fixture(lambda d: d['cases'][8].update({field: 'Release protected ACK and receipt to revoked reader.'}))
                self.assertEqual(v.check(self.root)['status'], 'fail')
                path.write_text(original)

    def test_review_mutations_and_objective_definitions(self):
        path = self.root / v.DOC
        original = path.read_text()
        mutations = [
            ('a prior revocation suppresses later releases', 'a prior revocation allows later releases'),
            ('total scheduled minutes >=99.5%', 'total scheduled minutes <99.5%'),
            ('all valid submitted attempts in the window', 'only successful attempts in the window'),
            ('250 attempts/second aggregate', '251 attempts/second aggregate'),
            ('all 200 reconnect attempts', 'all 199 reconnect attempts'),
            ('p95 <=250 ms', 'p95 >=250 ms'),
            ('An error, timeout, missing ACK', 'An error is ignored, timeout, missing ACK'),
        ]
        for old, new in mutations:
            with self.subTest(old=old):
                self.assertIn(old, original)
                path.write_text(original.replace(old, new))
                self.assertEqual(v.check(self.root)['status'], 'fail')
        path.write_text(original)

    def test_malformed_nested_types_cli_controlled(self):
        script = self.root / 'scripts/verification/verify_requirements.py'
        script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/verification/verify_requirements.py', script)
        path = self.root / v.FIX
        original = path.read_text()
        mutations = [lambda d: d['cases'][8].update(requirements=[{}]),
                     lambda d: d['cases'][8].update(requirements=None),
                     lambda d: d['cases'][8].update(requirements='R04'),
                     lambda d: d['cases'][8].update(expected={}),
                     lambda d: d['cases'].__setitem__(8, []),
                     lambda d: d.update(cases={})]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                path.write_text(original)
                self.mutate_fixture(mutate)
                run = subprocess.run([sys.executable, str(script)], text=True, capture_output=True)
                self.assertEqual(run.returncode, 1)
                self.assertIn(json.loads(run.stdout)['status'], ('fail', 'incomplete'))
                self.assertNotIn('Traceback', run.stderr)

    def test_cli_unavailable_input(self):
        script = self.root / 'scripts/verification/verify_requirements.py'
        script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/verification/verify_requirements.py', script)
        (self.root / v.FIX).unlink()
        run = subprocess.run([sys.executable, str(script)], text=True, capture_output=True)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)['status'], 'incomplete')
        self.assertNotIn('Traceback', run.stderr)

    def test_unavailable_input(self):
        (self.root / v.FIX).unlink()
        with self.assertRaises(v.VerificationError):
            v.check(self.root)

    def test_invalid_configuration(self):
        with self.assertRaises(v.VerificationError):
            v.check(self.root, {'version': 2})

    def test_interruption_has_no_success_report(self):
        def interrupted():
            raise KeyboardInterrupt()
        with patch.object(v, 'check', side_effect=lambda: v.check_original(self.root, interrupt=interrupted), create=True):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(v.main(), 1)
            result = json.loads(output.getvalue())
            self.assertEqual(result['status'], 'incomplete')
            self.assertFalse(result['checks_complete'])

    def test_wrong_traceability(self):
        self.mutate_fixture(lambda d: d['cases'][0].update(requirements=['R08']))
        self.assertEqual(v.check(self.root)['status'], 'fail')

    def test_false_fixture_evidence_label(self):
        self.mutate_fixture(lambda d: d.update(status='executed'))
        self.assertEqual(v.check(self.root)['status'], 'fail')

v.check_original = v.check
if __name__ == '__main__':
    unittest.main()
