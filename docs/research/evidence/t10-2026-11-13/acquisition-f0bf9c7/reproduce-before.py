"""Reproduce old acquisition failures with explicit executable provenance."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--nginx-binary', required=True)
parser.add_argument('--output-directory', required=True, type=Path)
args = parser.parse_args()
os.environ['T10_NGINX_BINARY'] = args.nginx_binary
root, out = Path.cwd(), args.output_directory
out.mkdir(parents=True, exist_ok=True)
revision = '9802c81b2ef1031798c8155990484eb0f9cf8999'
harness_revision = 'f0bf9c78cfaccd17e4b8f423039760b661427435'
sha256 = lambda data: hashlib.sha256(data).hexdigest()
def require(condition, message):
    if not condition:
        raise RuntimeError(message)


original_spec, original_io = importlib.util.spec_from_file_location, io.StringIO
reports, imports = [], []

def load(name, path):
    spec = original_spec(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Capture(original_io):
    def getvalue(self):
        value = super().getvalue()
        try:
            report = json.loads(value)
        except (ValueError, TypeError):
            return value
        if isinstance(report, dict) and report.get('failure', {}).get('signal') and not getattr(self, 'recorded', False):
            self.recorded = True
            reports.append(report)
        return value

with tempfile.TemporaryDirectory(prefix='t10-old-implementation-') as directory:
    extracts, provenance = {}, {}
    for key, source in [('probe', 'scripts/research/t10-nginx-probe.py'),
                        ('capture', 'scripts/research/t10-capture-sources.py')]:
        blob = subprocess.check_output(['git', 'show', revision + ':' + source])
        path = Path(directory) / (key + '.py')
        path.write_bytes(blob)
        require(path.read_bytes() == blob, "Extracted implementation differs from Git blob")
        extracts[key] = path
        provenance[key] = {'git_revision': revision, 'git_path': source,
                           'git_blob_oid': subprocess.check_output(['git', 'rev-parse', revision + ':' + source], text=True).strip(),
                           'executed_source_sha256': sha256(blob), 'extracted_path': str(path)}
    harness_path = root / 'tests/research/t10-test-nginx-probe.py'
    harness_blob = subprocess.check_output(['git', 'show', harness_revision + ':tests/research/t10-test-nginx-probe.py'])
    require(harness_path.read_bytes() == harness_blob, 'Harness differs from exact recorded revision')
    tests = load('acquisition_tests', harness_path)
    tests.PROBE = load('oldprobe', extracts['probe'])
    tests.PROBE.ROOT = root
    require(tests.PROBE.run_local.__code__.co_filename == str(extracts['probe']), 'Loaded probe code filename differs from verified extract')
    require(tests.PROBE.run_local.__globals__ is tests.PROBE.__dict__, 'Loaded probe globals differ from verified module')
    imports.append({'module': 'tests.PROBE', 'loaded_file': tests.PROBE.__file__,
                    'function_code_file': tests.PROBE.run_local.__code__.co_filename})
    def redirect_spec(name, path, *a, **kw):
        if name == 'capture_spawn':
            path = extracts['capture']
            imports.append({'module': name, 'loaded_file': str(path)})
        return original_spec(name, path, *a, **kw)
    names = ['test_first_signal_after_nginx_spawn_before_assignment_reaps_owned_group',
             'test_first_signal_after_fetch_spawn_before_assignment_reaps_owned_child',
             'test_first_signal_after_local_acquisition_before_registration_closes_resources']
    output = original_io()
    with mock.patch.object(importlib.util, 'spec_from_file_location', side_effect=redirect_spec), mock.patch.object(io, 'StringIO', Capture):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.TestSuite(tests.CancellationRegression(n) for n in names))
    (out / 'before-verified.log').write_text(output.getvalue())
    require(result.testsRun == 3 and len(result.failures) == 3 and not result.errors and not result.skipped, 'Unexpected regression outcome; require three failures and no errors/skips')
    require(len(reports) == 3, 'Unexpected owner report count; require three reports')
    payload = {'executed_implementation_revision': revision,
               'checkout_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'metadata_caveat': 'Owner report tested_sha reads git HEAD in ROOT; fixture_hashes read current ROOT files. Those fields describe the checkout, not dynamically imported implementation. Executed implementation is identified by provenance below.',
               'executed_modules': provenance, 'import_mapping': imports,
               'test_harness': {'revision': harness_revision, 'git_path': 'tests/research/t10-test-nginx-probe.py', 'sha256': sha256(harness_blob)},
               'shared_fixture_inputs': {p: {'sha256': sha256((root / p).read_bytes()), 'identical_to_old_revision': (root / p).read_bytes() == subprocess.check_output(['git', 'show', revision + ':' + p])} for p in ['scripts/research/t10-proxy-fixture.py', 'docs/research/t10-nginx-probe.conf']},
               'monkeypatches': ['tests.PROBE replaced by oldprobe loaded from verified old Git blob; ROOT points to checkout for unchanged shared fixtures.', 'spec_from_file_location maps only capture_spawn to verified old capture Git blob.', 'Popen wrappers in exact new test harness create real children then signal before returning the handle; captured resources are rescued in finally.', 'Other local-resource wrappers signal after creation before assignment; StringIO wrapper records owner reports without modifying them.'],
               'outcome': {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skips': len(result.skipped)},
               'reports': reports,
               'rescue': 'Only handles captured by the test harness authorize cleanup; each test finally kills/reaps/closes its owned resources.'}
    (out / 'before-verified.json').write_text(json.dumps(payload, indent=2) + '\n')
print('Verified exact old implementation: three expected acquisition failures, resources rescued.')
