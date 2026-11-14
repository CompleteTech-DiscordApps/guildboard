"""Offline regression tests for the roadmap CI validator, not product acceptance."""
import copy
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts/github-bootstrap'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('roadmap_validate', SCRIPTS / 'validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
MANIFEST = json.loads((ROOT / 'planning/guildboard-backlog.json').read_text())
SCHEMA = json.loads((ROOT / 'planning/project-schema.json').read_text())


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.manifest = copy.deepcopy(MANIFEST)
        self.schema = copy.deepcopy(SCHEMA)

    def validate(self):
        return validator.validate_manifest(self.manifest, self.schema)

    def fails_with(self, text):
        result = self.validate()
        self.assertEqual(result['result'], 'fail')
        self.assertTrue(any(text in error for error in result['errors']), result['errors'])
        return result

    def test_current_manifest_and_input_immutability(self):
        before = copy.deepcopy(self.manifest)
        result = self.validate()
        self.assertEqual(result['result'], 'pass', result['errors'])
        self.assertEqual(result['item_count'], 471)
        self.assertEqual(result['native_relationships_expected'], 457)
        self.assertEqual(result['max_depth'], 5)
        self.assertEqual(self.manifest, before)
        self.assertEqual(self.validate(), result)

    def test_missing_parent_reports_failure_without_dereference(self):
        self.manifest['items'][1]['parent_id'] = 'missing'
        result = self.fails_with('nonexistent parent missing')
        self.assertIsNone(result['max_depth'])

    def test_missing_dependency_reports_failure_without_dereference(self):
        self.manifest['items'][2]['dependencies'] = ['missing']
        result = self.fails_with("invalid dependency 'missing'")
        self.assertEqual(result['longest_prerequisite_chain'], [])

    def test_duplicate_identity_never_silently_overwrites(self):
        self.manifest['items'].append(copy.deepcopy(self.manifest['items'][0]))
        self.fails_with('duplicate stable ID')

    def test_parent_cycle_has_explicit_diagnostic(self):
        a, b = self.manifest['items'][:2]
        a['parent_id'] = b['id']
        result = self.fails_with('hierarchy cycle:')
        self.assertIsNone(result['max_depth'])

    def test_blocking_cycle_has_explicit_diagnostic(self):
        a, b = self.manifest['items'][1:3]
        a['dependencies'] = [b['id']]
        result = self.fails_with('blocking cycle:')
        self.assertEqual(result['longest_prerequisite_chain'], [])

    def test_self_links_are_rejected(self):
        item = self.manifest['items'][1]
        item['parent_id'] = item['id']
        item['dependencies'] = [item['id']]
        self.fails_with('hierarchy cycle:')
        self.fails_with('invalid dependency')

    def test_duplicate_dependencies_are_rejected(self):
        self.manifest['items'][2]['dependencies'] *= 2
        self.fails_with('duplicate dependency')

    def test_missing_mvp_gate_is_a_report_not_keyerror(self):
        self.manifest['items'] = [x for x in self.manifest['items'] if x['id'] != 'GB-T13.G1']
        self.fails_with('missing MVP approval gate')

    def test_empty_manifest_is_a_report_not_max_error(self):
        self.manifest['items'] = []
        self.fails_with('expected 14 workstreams')

    def test_malformed_top_level_shapes(self):
        for invalid in (None, [], '', 3, {}, {'items': None}, {'items': {}}):
            with self.subTest(invalid=invalid):
                self.assertEqual(validator.validate_manifest(invalid, self.schema)['result'], 'fail')

    def test_malformed_items_and_ids(self):
        for invalid in (None, [], '', 3, {}, {'id': []}, {'id': ''}, {'id': '   '}):
            with self.subTest(invalid=invalid):
                self.manifest['items'] = [invalid]
                self.assertEqual(self.validate()['result'], 'fail')

    def test_malformed_item_properties(self):
        for key in ('parent_id', 'fields', 'labels', 'dependencies', 'milestone',
                    'workstream', 'work_type', 'acceptance_criteria', 'expected_tests'):
            for invalid in ({}, [], None, 42, False):
                with self.subTest(key=key, invalid=invalid):
                    self.manifest = copy.deepcopy(MANIFEST)
                    item = self.manifest['items'][1]
                    item[key] = invalid
                    if key == 'parent_id' and invalid is None:
                        # A Research item is not allowed to become a root.
                        expected = 'orphan'
                    elif key in ('labels', 'dependencies') and invalid == []:
                        continue  # Empty arrays are valid when no entries are required.
                    else:
                        expected = None
                    result = self.validate()
                    self.assertEqual(result['result'], 'fail', (key, invalid))
                    if expected:
                        self.assertTrue(any(expected in e for e in result['errors']))

    def test_malformed_list_entries(self):
        for key in ('labels', 'dependencies', 'acceptance_criteria', 'expected_tests'):
            for invalid in (None, [], {}, 42, False, ''):
                with self.subTest(key=key, invalid=invalid):
                    self.manifest = copy.deepcopy(MANIFEST)
                    self.manifest['items'][1][key] = [invalid]
                    self.assertEqual(self.validate()['result'], 'fail')

    def test_missing_required_item_keys(self):
        for key in ('parent_id', 'fields', 'labels', 'dependencies', 'milestone',
                    'workstream', 'work_type', 'acceptance_criteria', 'expected_tests'):
            with self.subTest(key=key):
                self.manifest = copy.deepcopy(MANIFEST)
                del self.manifest['items'][1][key]
                self.assertEqual(self.validate()['result'], 'fail')

    def test_malformed_schema(self):
        for invalid in (None, [], {}, {'Tier': None}):
            with self.subTest(invalid=invalid):
                self.assertEqual(validator.validate_manifest(self.manifest, invalid)['result'], 'fail')
        for invalid in ('bad', [], [None], [{}]):
            self.schema['Tier'] = invalid
            self.fails_with('schema: missing/invalid Tier')

    def test_broad_parent_cannot_be_ready(self):
        self.manifest['items'][0]['fields']['Readiness'] = 'Ready'
        self.fails_with('broad parent marked ready')

    def test_dependency_classification_and_readiness(self):
        item = self.manifest['items'][2]
        item['fields']['Readiness'] = 'Ready'
        item['fields']['Dependency Status'] = 'Unblocked'
        self.fails_with('incorrectly ready with unresolved blockers')
        self.fails_with('contradictory dependency classification')

    def test_cross_tier_parent_and_redundant_labels(self):
        self.manifest['items'][1]['workstream'] = 'T1'
        self.manifest['items'][1]['labels'].append('priority: urgent')
        self.fails_with('unexpected cross-tier parent')
        self.fails_with('redundant priority/status label')

    def test_mvp_cannot_depend_on_later_milestone(self):
        next(x for x in self.manifest['items'] if x['id'] == 'GB-T13.G1')['milestone'] = 'M4 — Later'
        self.fails_with('MVP approval depends on a later release phase')

    def test_fanout_limit(self):
        for i in range(101):
            item = copy.deepcopy(self.manifest['items'][1])
            item['id'] = f'extra-{i}'
            self.manifest['items'].append(item)
        self.fails_with('exceeds sub-issue fanout')

    def test_long_graphs_do_not_depend_on_python_recursion_limit(self):
        graph = {str(i): [str(i - 1)] if i else [] for i in range(1500)}
        errors = []
        paths = validator.graph_paths(graph, 'blocking', errors)
        self.assertEqual(len(paths['1499']), 1500)
        self.assertEqual(errors, [])
        graph['0'] = ['1499']
        self.assertIsNone(validator.graph_paths(graph, 'blocking', errors))
        self.assertIn('blocking cycle:', errors[-1])

    def test_hierarchy_depth_limit(self):
        for index in range(2, 11):
            self.manifest['items'][index]['parent_id'] = self.manifest['items'][index - 1]['id']
        self.fails_with('hierarchy too deep')


class ReportWriteTests(unittest.TestCase):
    def test_concurrent_writers_publish_their_own_report(self):
        # Force both writers to finish staging before either publishes. Then
        # observe each publication, without imposing a general winner policy.
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            staged = threading.Barrier(2)
            first_published = threading.Event()
            observed = {}
            original_replace = os.replace
            first = {'result': 'fail', 'errors': ['invalid manifest']}
            second = {'result': 'pass', 'errors': []}

            def replace(path, destination, **kwargs):
                staged.wait(timeout=10)
                if threading.current_thread().name == 'invalid':
                    try:
                        result = original_replace(path, destination, **kwargs)
                        observed['invalid'] = json.loads(report.read_text())
                        return result
                    finally:
                        first_published.set()
                self.assertTrue(first_published.wait(timeout=10))
                result = original_replace(path, destination, **kwargs)
                observed['valid'] = json.loads(report.read_text())
                return result

            def write(name, value):
                threading.current_thread().name = name
                validator.save_report(report, value)

            with mock.patch.object(os, 'replace', replace):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    pending = [pool.submit(write, 'invalid', first),
                               pool.submit(write, 'valid', second)]
                    for future in pending:
                        future.result(timeout=15)
            self.assertEqual(observed, {'invalid': first, 'valid': second})
            self.assertEqual(json.loads(report.read_text()), second)
            self.assertEqual(list(Path(directory).iterdir()), [report])

    def test_failed_publication_cleans_staging_and_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            previous = '{"result":"pass","previous":true}'
            report.write_text(previous)
            with mock.patch.object(os, 'replace', side_effect=OSError('replace denied')):
                with self.assertRaisesRegex(OSError, 'replace denied'):
                    validator.save_report(report, {'result': 'fail'})
            self.assertEqual(report.read_text(), previous)
            self.assertEqual(list(Path(directory).iterdir()), [report])


class CliTests(unittest.TestCase):
    def run_cli(self, manifest_text, schema_text=None, report_name='report.json'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            schema = root / 'schema.json'
            report = root / report_name
            manifest.write_text(manifest_text)
            schema.write_text(schema_text if schema_text is not None else json.dumps(SCHEMA))
            report.write_text('{"result":"pass","stale":true}')
            proc = subprocess.run([sys.executable, str(SCRIPTS / 'validate.py'), '--manifest',
                                   str(manifest), '--schema', str(schema), '--report', str(report)],
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.stderr, '')
            self.assertEqual(json.loads(proc.stdout), json.loads(report.read_text()))
            self.assertNotIn('stale', json.loads(report.read_text()))
            return proc.returncode, json.loads(proc.stdout)

    def test_cli_success(self):
        code, report = self.run_cli(json.dumps(MANIFEST))
        self.assertEqual(code, 0)
        self.assertEqual(report['result'], 'pass')

    def test_cli_report_input_aliases_preserve_manifest_and_schema(self):
        for source_name in ('manifest.json', 'schema.json'):
            for alias_kind in ('same_path', 'symlink', 'hardlink'):
                for manifest_text in (json.dumps(MANIFEST), 'broken JSON'):
                    with self.subTest(source=source_name, alias=alias_kind,
                                      valid=manifest_text != 'broken JSON'):
                        with tempfile.TemporaryDirectory() as directory:
                            root = Path(directory)
                            manifest = root / 'manifest.json'
                            schema = root / 'schema.json'
                            manifest.write_text(manifest_text)
                            schema.write_text(json.dumps(SCHEMA))
                            before = {p: p.read_bytes() for p in (manifest, schema)}
                            source = root / source_name
                            report = root / 'alias.json'
                            if alias_kind == 'same_path':
                                report = source
                            elif alias_kind == 'symlink':
                                report.symlink_to(source)
                            else:
                                report.hardlink_to(source)
                            proc = subprocess.run(
                                [sys.executable, str(SCRIPTS / 'validate.py'),
                                 '--manifest', str(manifest), '--schema', str(schema),
                                 '--report', str(report)], capture_output=True,
                                text=True, timeout=15)
                            self.assertEqual(proc.returncode, 1)
                            self.assertEqual(proc.stderr, '')
                            result = json.loads(proc.stdout)
                            self.assertEqual(result['result'], 'fail')
                            self.assertIn('report must not alias', result['errors'][0])
                            for path, contents in before.items():
                                self.assertEqual(path.read_bytes(), contents)
                            self.assertEqual(report.read_bytes(), before[source])
                            if alias_kind == 'symlink':
                                self.assertTrue(report.is_symlink())
                            else:
                                self.assertTrue(report.samefile(source))

    @unittest.skipUnless(hasattr(os, 'mkfifo') and Path('/proc/self/fd').is_dir(), 'requires Linux procfs and FIFO')
    def test_cli_parent_symlink_retarget_keeps_pinned_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'inputs'
            output = root / 'output'
            inputs.mkdir()
            output.mkdir()
            schema = inputs / 'schema.json'
            schema.write_text(json.dumps(SCHEMA))
            before = schema.read_bytes()
            fifo = root / 'manifest.fifo'
            os.mkfifo(fifo)
            link = root / 'report-directory'
            link.symlink_to(output, target_is_directory=True)
            proc = subprocess.Popen([sys.executable, str(SCRIPTS / 'validate.py'),
                                     '--manifest', str(fifo), '--schema', str(schema),
                                     '--report', str(link / 'schema.json')],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # The reader opens the FIFO only after pinning and checking the destination.
                with fifo.open('w') as writer:
                    link.unlink()
                    link.symlink_to(inputs, target_is_directory=True)
                    writer.write(json.dumps(MANIFEST))
                stdout, stderr = proc.communicate(timeout=15)
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertEqual(json.loads(stdout)['result'], 'pass')
                self.assertEqual(schema.read_bytes(), before)
                self.assertEqual(json.loads((output / 'schema.json').read_text()), json.loads(stdout))
                self.assertEqual(list(output.glob('.roadmap-*.tmp')), [])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()

    @unittest.skipUnless(hasattr(os, 'O_PATH') and hasattr(os, 'geteuid') and os.geteuid() != 0,
                         'requires unprivileged Linux user')
    def test_cli_writes_to_searchable_writable_directory_without_read_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            output.mkdir(mode=0o300)
            report = output / 'report.json'
            try:
                proc = subprocess.run([sys.executable, str(SCRIPTS / 'validate.py'),
                                       '--report', str(report)], capture_output=True,
                                      text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual(json.loads(report.read_text()), json.loads(proc.stdout))
                self.assertEqual(json.loads(proc.stdout)['result'], 'pass')
            finally:
                output.chmod(0o700)
            self.assertEqual(list(output.iterdir()), [report])

    def test_concurrent_cli_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.json'
            command = [sys.executable, str(SCRIPTS / 'validate.py'), '--report', str(report)]
            writers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True) for _ in range(8)]
            outputs = []
            for writer in writers:
                stdout, stderr = writer.communicate(timeout=30)
                self.assertEqual(writer.returncode, 0, stderr)
                outputs.append(json.loads(stdout))
            self.assertIn(json.loads(report.read_text()), outputs)
            self.assertTrue(all(output['result'] == 'pass' for output in outputs))
            self.assertEqual(list(root.glob('.roadmap-*.tmp')), [])

    def test_cli_long_valid_report_basename_replaces_previous_report(self):
        # The destination itself fits Linux NAME_MAX; staging must not append
        # randomness to that basename and exceed the filesystem limit.
        for source, expected in ((json.dumps(MANIFEST), 'pass'),
                                 ('broken JSON', 'fail')):
            with self.subTest(result=expected):
                code, report = self.run_cli(source, report_name='r' * 251)
                self.assertEqual(report['result'], expected)
                self.assertEqual(code, int(expected == 'fail'))

    def test_cli_invalid_relationship_replaces_previous_pass(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['items'][1]['parent_id'] = 'missing'
        code, report = self.run_cli(json.dumps(manifest))
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'fail')
        self.assertTrue(any('nonexistent parent' in e for e in report['errors']))

    def test_cli_invalid_json_and_duplicate_keys_replace_previous_pass(self):
        for source in ('broken JSON', '{"items":[],"items":[]}', '[' * 1200):
            with self.subTest(source=source[:50]):
                code, report = self.run_cli(source)
                self.assertEqual(code, 1)
                self.assertEqual(report['result'], 'fail')
                self.assertTrue(report['errors'][0].startswith('input:'))

    def test_cli_invalid_schema_replaces_previous_pass(self):
        code, report = self.run_cli(json.dumps(MANIFEST), '{}')
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'fail')

    def test_cli_lone_surrogate_diagnostics_replace_previous_pass(self):
        for surrogate in ('\ud800', '\udfff'):
            with self.subTest(surrogate=repr(surrogate)):
                manifest = copy.deepcopy(MANIFEST)
                manifest['items'][1]['parent_id'] = surrogate
                code, report = self.run_cli(json.dumps(manifest))
                self.assertEqual(code, 1)
                self.assertEqual(report['result'], 'fail')
                self.assertTrue(any('nonexistent parent ' + surrogate == error.split(': ', 1)[-1]
                                    for error in report['errors']), report['errors'])

    def test_import_has_no_reporting_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = f'import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import validate; print("imported")'
            proc = subprocess.run([sys.executable, '-c', code], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, 'imported\n')
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cli_nameless_report_paths_return_json_failure(self):
        for report_path in ('.', Path.cwd().anchor):
            with self.subTest(report_path=report_path):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS / 'validate.py'), '--report', str(report_path)],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(proc.stderr, '')
                report = json.loads(proc.stdout)
                self.assertEqual(report['result'], 'fail')
                self.assertTrue(any(error.startswith('cannot write validation report:')
                                    for error in report['errors']), report)


if __name__ == '__main__':
    unittest.main()
