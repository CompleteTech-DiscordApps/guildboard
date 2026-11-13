import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('journeys', ROOT / 'scripts/research/audit_documentation_journeys.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class JourneyAuditTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / 'docs/research/documentation-journeys.json').read_text())

    def check_error(self, fragment):
        errors, _ = module.audit(ROOT, self.manifest)
        self.assertTrue(any(fragment in x for x in errors), errors)

    def write_snapshot(self, root, manifest):
        original = json.loads((ROOT / 'docs/research/documentation-journeys.json').read_text())
        sources = {item['path'] for journey in original['journeys']
                   for step in journey['steps'] for item in step['evidence']}
        for relative in sources:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        target = root / 'docs/research/documentation-journeys.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest))

    def run_cli(self, root):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/research/audit_documentation_journeys.py'),
                               '--root', str(root)], capture_output=True, text=True, timeout=10)

    def assert_invalid_cli(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.strip(), result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report['evidence_valid'], False)
        self.assertIs(report['product_verified'], False)
        self.assertEqual(result.stderr, '')
        return report

    def test_real_snapshot(self):
        errors, counts = module.audit(ROOT, self.manifest)
        self.assertEqual(errors, [])
        self.assertEqual(sum(counts.values()), 12)
        self.assertGreater(counts['blocked'], 0)  # valid research does not mean usable journeys

    def test_boolean_schema_tag_is_not_version_one(self):
        self.manifest['schema_version'] = True
        self.check_error('unsupported manifest schema')

    def test_boolean_schema_tag_cli_returns_invalid_evidence(self):
        self.manifest['schema_version'] = True
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_snapshot(root, self.manifest)
            report = self.assert_invalid_cli(self.run_cli(root))
            self.assertIn('unsupported manifest schema', report['errors'])

    def test_missing_persona(self):
        self.manifest['journeys'].pop()
        self.check_error('all four')

    def test_duplicate_persona(self):
        self.manifest['journeys'].append(copy.deepcopy(self.manifest['journeys'][0]))
        self.check_error('duplicate')

    def test_evidence_drift(self):
        self.manifest['journeys'][0]['steps'][0]['evidence'][0]['sha256'] = '0' * 64
        self.check_error('evidence changed')

    def test_evidence_missing(self):
        self.manifest['journeys'][0]['steps'][0]['evidence'][0]['path'] = 'nonexistent.md'
        self.check_error('missing evidence')

    def test_traversal_and_absolute_paths(self):
        for path in ('../README.md', '/etc/passwd'):
            with self.subTest(path=path):
                self.manifest['journeys'][0]['steps'][0]['evidence'][0]['path'] = path
                self.check_error('escapes repository')

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'escape').symlink_to(ROOT / 'README.md')
            self.manifest['journeys'][0]['steps'][0]['evidence'][0]['path'] = 'escape'
            errors, _ = module.audit(root, self.manifest)
            self.assertIn('evidence path escapes repository', errors)

    def test_real_symlink_loop_cli_returns_invalid_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.manifest['journeys'][0]['steps'][0]['evidence'][0]['path'] = 'loop'
            self.write_snapshot(root, self.manifest)
            (root / 'loop').symlink_to('loop')
            report = self.assert_invalid_cli(self.run_cli(root))
            self.assertIn('path cannot be resolved', report['error'])

    def test_unrelated_internal_runtime_error_is_not_suppressed(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['audit', '--root', str(ROOT)]), \
                patch.object(module.hashlib, 'sha256', side_effect=RuntimeError('internal bug')), \
                redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, 'internal bug'):
                module.main()
        self.assertEqual(output.getvalue(), '')

    def test_no_evidence_or_validation(self):
        step = self.manifest['journeys'][0]['steps'][0]
        step['evidence'] = []
        step['next_validation'] = ''
        self.check_error('requires evidence')
        self.check_error('missing next_validation')

    def test_malformed_shapes_fail_closed(self):
        for manifest in (None, [], {}, {'schema_version': 2}, {'schema_version': 1, 'journeys': None},
                         {'schema_version': 1, 'journeys': [None, {'persona': [], 'steps': [None]}]}):
            with self.subTest(manifest=manifest):
                errors, _ = module.audit(ROOT, manifest)
                self.assertTrue(errors)

    def test_unknown_state(self):
        self.manifest['journeys'][0]['steps'][0]['state'] = 'verified'
        self.check_error('unknown step state')


if __name__ == '__main__':
    unittest.main()
