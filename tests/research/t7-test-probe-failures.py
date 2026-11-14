"""Failure-report regressions; no Docker daemon or browser is required."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('t7_probe', ROOT / 'scripts/research/t7-browser-probe.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class OwnedProcess:
    """Supply the three successful MCP replies before the copy failure."""
    def __init__(self):
        replies = [
            {'id': 1, 'result': {'serverInfo': {'name': 'test-double'}}},
            {'id': 2, 'result': {'tools': [{'name': 'browser_run_code'}]}},
            {'id': 3, 'result': {'content': [{'type': 'text', 'text': '### Result\n{"result":"pass"}'}]}},
        ]
        self.stdout = io.StringIO(''.join(json.dumps(reply) + '\n' for reply in replies))
        self.stdin = io.StringIO()
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        return 0


class FailureReports(unittest.TestCase):
    def run_failure(self, failure_stage, stderr=None):
        process = OwnedProcess()
        calls = []

        def check_output(command, **kwargs):
            if command[0] == 'git':
                return 'fixture-head\n'
            if command[1:] == ['context', 'show']:
                if failure_stage == 'discovery':
                    raise FileNotFoundError('docker unavailable')
                return 'test-context\n'
            self.assertIn('ps', command)
            return ''

        def run(command, **kwargs):
            calls.append(command)
            if 'image' in command and failure_stage == 'image':
                raise subprocess.CalledProcessError(1, command, stderr=stderr)
            if 'cp' in command:
                raise subprocess.CalledProcessError(1, command, stderr=stderr)
            # The owned process was removed before cleanup inspection.
            return subprocess.CompletedProcess(command, 1 if 'container' in command else 0, stdout='')

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence.json'
            with patch.object(sys, 'argv', ['probe', '--output', str(output)]), \
                 patch.object(PROBE.platform, 'platform', return_value='test-platform'), \
                 patch.object(PROBE.subprocess, 'check_output', side_effect=check_output), \
                 patch.object(PROBE.subprocess, 'run', side_effect=run), \
                 patch.object(PROBE.subprocess, 'Popen', return_value=process) as popen, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(PROBE.main(), 1)
            report = json.loads(output.read_text())
        self.assertEqual(report['result'], 'blocked-or-failed')
        self.assertTrue(report['owned_container_absent'])
        self.assertNotIn('screenshot_sha256', report)
        if failure_stage == 'copy':
            self.assertTrue(process.terminated)
            self.assertEqual(report['browser_result']['result'], 'pass')
            self.assertTrue(any('cp' in command for command in calls))
            self.assertTrue(any('container' in command for command in calls))
        else:
            popen.assert_not_called()
            self.assertNotIn('browser_result', report)
        return report

    def test_missing_docker_persists_report(self):
        self.assertEqual(self.run_failure('discovery')['error_type'], 'FileNotFoundError')

    def test_image_failure_text_stderr(self):
        self.assertEqual(self.run_failure('image', 'image unavailable')['command_stderr'], 'image unavailable')

    def test_image_failure_no_stderr(self):
        self.assertIsNone(self.run_failure('image')['command_stderr'])

    def test_copy_failure_bytes_stderr(self):
        self.assertEqual(self.run_failure('copy', b'copy failed')['command_stderr'], 'copy failed')

    def test_copy_failure_non_utf8_stderr(self):
        self.assertEqual(self.run_failure('copy', b'copy failed: \xff')['command_stderr'], 'copy failed: \ufffd')


class ReportPublicationFailures(unittest.TestCase):
    def exercise(self, partial):
        process = OwnedProcess()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence.json'
            old_image = Path(directory) / 'old.png'
            old_image.write_bytes(b'old screenshot')
            old_report = json.dumps({'result': 'pass', 'screenshot_path': str(old_image),
                                     'screenshot_sha256': hashlib.sha256(old_image.read_bytes()).hexdigest()})
            output.write_text(old_report)
            original_write = Path.write_bytes
            def write(path, data):
                if path.name == 'report.json':
                    if partial:
                        original_write(path, data[:10])
                    raise OSError('injected report write failure')
                return original_write(path, data)
            def check_output(command, **kwargs):
                if command[0] == 'git': return 'fixture-head\n'
                if command[1:] == ['context', 'show']: return 'test-context\n'
                return ''
            def run(command, **kwargs):
                if 'cp' in command: Path(command[-1]).write_bytes(b'new screenshot')
                return subprocess.CompletedProcess(command, 1 if 'container' in command else 0, stdout='')
            with patch.object(sys, 'argv', ['probe', '--output', str(output)]), \
                 patch.object(PROBE.subprocess, 'check_output', side_effect=check_output), \
                 patch.object(PROBE.subprocess, 'run', side_effect=run), \
                 patch.object(PROBE.subprocess, 'Popen', return_value=process), \
                 patch.object(Path, 'write_bytes', write), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(PROBE.main(), 1)
            self.assertEqual(output.read_text(), old_report)
            self.assertEqual(old_image.read_bytes(), b'old screenshot')
            self.assertEqual(list(Path(directory).glob('.t7-report-*')), [])
            self.assertTrue(process.terminated)

    def test_failure_before_report_open(self):
        self.exercise(False)

    def test_partial_report_write_failure(self):
        self.exercise(True)


class CliStartupReports(unittest.TestCase):
    def run_cli_failure(self, mode):
        with tempfile.TemporaryDirectory(dir=ROOT if mode == 'missing-repository' else None) as directory:
            root = Path(directory)
            script = root / 'scripts/research/t7-browser-probe.py'
            script.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'scripts/research/t7-browser-probe.py', script)
            for relative in ['docs/research/t7-outline-prototype.html', 'tests/research/t7-browser-checks.js']:
                if mode == 'missing-html' and relative.endswith('.html'):
                    continue
                if mode == 'missing-checks' and relative.endswith('.js'):
                    continue
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('standalone test fixture')
            env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            # A malformed gitfile stops parent discovery even inside a checkout.
            (root / '.git').write_text('not a gitdir')
            env['GIT_CEILING_DIRECTORIES'] = str(root)
            guard = root / 'guard-bin'
            guard.mkdir()
            docker = guard / 'docker'
            marker = root / 'docker-called'
            docker.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise SystemExit(99)\n')
            docker.chmod(0o755)
            env['PATH'] = str(guard) + os.pathsep + env.get('PATH', '')
            if mode == 'missing-git':
                env['PATH'] = str(guard)
            output = root / 'output/evidence.json'
            result = subprocess.run([sys.executable, str(script), '--output', str(output)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(output.exists(), result.stderr)
            report = json.loads(output.read_text())
            self.assertFalse(marker.exists(), 'startup test invoked Docker')
        self.assertEqual(report['result'], 'blocked-or-failed')
        self.assertTrue(report['owned_container_absent'])
        self.assertNotIn('browser_result', report)
        self.assertNotIn('tested_head', report)
        self.assertLessEqual(len(report['error']), 4000)
        self.assertEqual(report['stage'], 'read-fixtures' if mode in ('missing-html', 'missing-checks') else 'git-discovery')
        return report

    def test_cli_without_git_executable(self):
        self.assertEqual(self.run_cli_failure('missing-git')['error_type'], 'FileNotFoundError')

    def test_cli_outside_git_repository(self):
        self.assertEqual(self.run_cli_failure('missing-repository')['error_type'], 'CalledProcessError')

    def test_cli_missing_html_fixture(self):
        self.assertEqual(self.run_cli_failure('missing-html')['error_type'], 'FileNotFoundError')

    def test_cli_missing_browser_checks(self):
        self.assertEqual(self.run_cli_failure('missing-checks')['error_type'], 'FileNotFoundError')


class CliScreenshotPublication(unittest.TestCase):
    def exercise(self, fail_copy):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'scripts/research/t7-browser-probe.py'
            script.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'scripts/research/t7-browser-probe.py', script)
            for relative in ('docs/research/t7-outline-prototype.html', 'tests/research/t7-browser-checks.js'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            historical = root / 'docs/research/t7-fixture.png'
            historical.write_bytes(b'historical evidence')
            output = root / 'out/evidence.json'
            output.parent.mkdir()
            screenshot = output.with_name(output.name + '.png')
            screenshot.write_bytes(b'previous evidence')
            fake_bin = root / 'bin'
            fake_bin.mkdir()
            git = fake_bin / 'git'
            git.write_text('#!' + sys.executable + "\nprint('fixture-head')\n")
            git.chmod(0o755)
            docker = fake_bin / 'docker'
            docker.write_text('#!' + sys.executable + "\n" + r"""
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
if args == ['context', 'show']:
    print('test-context')
elif 'image' in args:
    pass
elif 'run' in args:
    for line in sys.stdin:
        request = json.loads(line)
        if 'id' not in request:
            continue
        method = request['method']
        result = ({'serverInfo': {'name': 'fake'}} if method == 'initialize' else
                  {'tools': [{'name': 'browser_run_code'}]} if method == 'tools/list' else
                  {'content': [{'type': 'text', 'text': '### Result\n{"result":"pass"}'}]})
        print(json.dumps({'id': request['id'], 'result': result}), flush=True)
elif 'cp' in args:
    pathlib.Path(args[-1]).write_bytes(b'partial' if os.environ['FAIL_COPY'] == '1' else b'new screenshot')
    if os.environ['FAIL_COPY'] == '1':
        print('copy failed', file=sys.stderr)
        sys.exit(1)
elif 'inspect' in args:
    sys.exit(1)
elif 'ps' in args:
    pass
else:
    sys.exit(2)
""")
            docker.chmod(0o755)
            env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            env.update(PATH=str(fake_bin), FAKE_LOG=str(root / 'docker.log'), FAIL_COPY=str(int(fail_copy)))
            result = subprocess.run([sys.executable, str(script), '--output', str(output)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=20)
            report = json.loads(output.read_text())
            self.assertEqual(result.returncode, int(fail_copy), result.stderr)
            self.assertEqual(historical.read_bytes(), b'historical evidence')
            self.assertEqual(screenshot.read_bytes(), b'previous evidence')
            self.assertEqual(list(output.parent.glob('.t7-screenshot-*')), [])
            self.assertTrue(report['owned_container_absent'])
            calls = [json.loads(line) for line in (root / 'docker.log').read_text().splitlines()]
            self.assertTrue(any('container' in call and 'inspect' in call for call in calls))
            self.assertTrue(any('ps' in call for call in calls))
            if fail_copy:
                self.assertEqual(report['stage'], 'screenshot-copy')
                self.assertEqual(report['result'], 'blocked-or-failed')
                self.assertNotIn('screenshot_sha256', report)
            else:
                self.assertEqual(report['result'], 'pass')
                published = Path(report['screenshot_path'])
                self.assertNotEqual(published, screenshot)
                self.assertEqual(published.read_bytes(), b'new screenshot')
                self.assertEqual(report['screenshot_sha256'], hashlib.sha256(b'new screenshot').hexdigest())

    def test_partial_copy_preserves_existing_evidence(self):
        self.exercise(True)

    def test_success_publishes_new_screenshot(self):
        self.exercise(False)


if __name__ == '__main__':
    unittest.main()
