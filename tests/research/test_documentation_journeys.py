import copy
import hashlib
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
        manifest_path = Path('docs/research/documentation-journeys.json')
        self.manifest = json.loads((ROOT / manifest_path).read_text())
        self.source_paths = {item['path'] for journey in self.manifest['journeys']
                             for step in journey['steps'] for item in step['evidence']}
        snapshot = tempfile.TemporaryDirectory()
        self.addCleanup(snapshot.cleanup)
        self.snapshot = Path(snapshot.name)
        # Historical source bytes are verified separately against the pinned Git tree.
        # Unit tests exercise the same manifest shape with deterministic local content.
        digests = {}
        for relative in self.source_paths:
            content = f'synthetic journey evidence for {relative}\n'.encode()
            source = self.snapshot / relative
            self.assertTrue(source.resolve().is_relative_to(self.snapshot.resolve()), relative)
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(content)
            digests[relative] = hashlib.sha256(content).hexdigest()
        for journey in self.manifest['journeys']:
            for step in journey['steps']:
                for item in step['evidence']:
                    item['sha256'] = digests[item['path']]
        target = self.snapshot / manifest_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.manifest))

    def check_error(self, fragment):
        errors, _ = module.audit(self.snapshot, self.manifest)
        self.assertTrue(any(fragment in x for x in errors), errors)

    def write_snapshot(self, root, manifest):
        for relative in self.source_paths:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.snapshot / relative, target)
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

    def test_complete_snapshot(self):
        errors, counts = module.audit(self.snapshot, self.manifest)
        self.assertEqual(errors, [])
        self.assertEqual(counts, {'documented': 1, 'partial': 3, 'blocked': 8})
        report = self.run_cli(self.snapshot)
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(json.loads(report.stdout), {'evidence_valid': True, 'step_counts': counts,
                                                     'errors': [], 'product_verified': False})

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
            (root / 'escape').symlink_to(self.snapshot / 'README.md')
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
        with patch.object(sys, 'argv', ['audit', '--root', str(self.snapshot)]), \
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
                errors, _ = module.audit(self.snapshot, manifest)
                self.assertTrue(errors)

    def test_unknown_state(self):
        self.manifest['journeys'][0]['steps'][0]['state'] = 'verified'
        self.check_error('unknown step state')


if __name__ == '__main__':
    unittest.main()
