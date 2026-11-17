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


class CleanupOwnership(unittest.TestCase):
    OWNED_ID = 'a' * 64
    REPLACEMENT_ID = 'b' * 64

    def run_cleanup(self, inspected_id, remove_race=False, owner_matches=True, still_present=False):
        process = OwnedProcess()
        calls = []
        live = {}

        def check_output(command, **kwargs):
            if command[0] == 'git':
                return 'fixture-head\n'
            if command[1:] == ['context', 'show']:
                return 'test-context\n'
            self.assertEqual(command[-5:], ['ps', '-a', '--no-trunc', '--format', '{{.ID}}'])
            return '\n'.join(live)

        def run(command, **kwargs):
            calls.append(command)
            if 'cp' in command:
                Path(command[-1]).write_bytes(b'screenshot')
            if command[3:5] == ['container', 'inspect']:
                name = command[-1]
                live[inspected_id] = name
                info = {'Id': inspected_id, 'Config': {'Labels': {
                    'tech.complete.guildboard.t7.run': name if owner_matches else 'foreign'}}}
                if remove_race:
                    del live[inspected_id]
                    live[self.REPLACEMENT_ID] = name
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps([info]))
            if command[3:5] == ['rm', '--force']:
                target = command[-1]
                if not still_present:
                    # Docker accepts a mutable name too. Using it would remove the replacement.
                    matching = next((key for key, name in live.items() if name == target), target)
                    removed = live.pop(matching, None)
                    return subprocess.CompletedProcess(command, int(removed is None))
                return subprocess.CompletedProcess(command, 1)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence.json'
            with patch.object(sys, 'argv', ['probe', '--output', str(output)]), \
                 patch.object(PROBE.platform, 'platform', return_value='test-platform'), \
                 patch.object(PROBE.subprocess, 'check_output', side_effect=check_output), \
                 patch.object(PROBE.subprocess, 'run', side_effect=run), \
                 patch.object(PROBE.subprocess, 'Popen', return_value=process), \
                 contextlib.redirect_stdout(io.StringIO()):
                exit_code = PROBE.main()
            report = json.loads(output.read_text())
        return exit_code, report, [call[-1] for call in calls if call[3:5] == ['rm', '--force']], live

    def test_auto_remove_then_name_reuse_preserves_replacement(self):
        code, report, targets, live = self.run_cleanup(self.OWNED_ID, remove_race=True)
        self.assertEqual(code, 0)
        self.assertTrue(report['owned_container_absent'])
        self.assertEqual(targets, [self.OWNED_ID])
        self.assertEqual(live, {self.REPLACEMENT_ID: report['container']})

    def test_invalid_inspected_id_blocks_removal(self):
        for value in (None, 'a' * 12, 'g' * 64, '-' + 'a' * 63):
            with self.subTest(value=value):
                code, report, targets, _ = self.run_cleanup(value)
                self.assertEqual(code, 1)
                self.assertIn('full container ID', report['cleanup_error'])
                self.assertEqual(targets, [])

    def test_foreign_ownership_blocks_removal(self):
        code, report, targets, _ = self.run_cleanup(self.OWNED_ID, owner_matches=False)
        self.assertEqual(code, 1)
        self.assertIn('exact ownership label', report['cleanup_error'])
        self.assertEqual(targets, [])

    def test_owned_id_present_after_failed_remove_blocks_report(self):
        code, report, targets, live = self.run_cleanup(self.OWNED_ID, still_present=True)
        self.assertEqual(code, 1)
        self.assertFalse(report['owned_container_absent'])
        self.assertEqual(targets, [self.OWNED_ID])
        self.assertIn(self.OWNED_ID, live)


class UnconfirmedCleanup(unittest.TestCase):
    def exercise(self, startup_observed, reap_timeout):
        process = OwnedProcess()
        if not startup_observed:
            process.stdout = io.StringIO()
        docker_names = []
        name_at_launch = None

        def launch(command, **kwargs):
            nonlocal name_at_launch
            name_at_launch = command[command.index('--name') + 1]
            return process

        def check_output(command, **kwargs):
            if command[0] == 'git':
                return 'fixture-head\n'
            if command[1:] == ['context', 'show']:
                return 'test-context\n'
            self.assertEqual(command[-4:], ['ps', '-a', '--format', '{{.Names}}'])
            listed = '\n'.join(docker_names)
            if not startup_observed:
                # Model the daemon registering an in-flight create after taking the listing snapshot.
                docker_names.append(name_at_launch)
            return listed

        def run(command, **kwargs):
            if command[3:5] == ['container', 'inspect']:
                self.assertEqual(docker_names, [])
                return subprocess.CompletedProcess(command, 1, stdout='')
            self.assertNotIn('rm', command)
            if 'cp' in command:
                Path(command[-1]).write_bytes(b'screenshot')
            return subprocess.CompletedProcess(command, 0)

        timeout = subprocess.TimeoutExpired('docker run', 5)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence.json'
            with patch.object(sys, 'argv', ['probe', '--output', str(output)]), \
                 patch.object(PROBE.subprocess, 'check_output', side_effect=check_output), \
                 patch.object(PROBE.subprocess, 'run', side_effect=run), \
                 patch.object(PROBE.subprocess, 'Popen', side_effect=launch), \
                 patch.object(process, 'wait', side_effect=timeout if reap_timeout else None, return_value=0) as wait, \
                 patch.object(process, 'kill', create=True) as kill, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(PROBE.main(), 1)
            report = json.loads(output.read_text())
        self.assertTrue(report['container_name_absent_at_check'])
        self.assertIsNone(report['owned_container_absent'])
        self.assertEqual(report['result'], 'blocked-or-failed')
        if reap_timeout:
            self.assertEqual(wait.call_count, 2)
            kill.assert_called_once_with()
            self.assertIn('not reaped', report['cleanup_error'])
            self.assertIn('timed out', report['process_cleanup_error'])
        else:
            self.assertEqual(docker_names, [report['container']])
            self.assertIn('startup was not observed', report['cleanup_error'])

    def test_empty_listing_can_precede_late_registration(self):
        self.exercise(startup_observed=False, reap_timeout=False)

    def test_empty_listing_does_not_confirm_cleanup_after_reap_timeout(self):
        self.exercise(startup_observed=True, reap_timeout=True)


class ReportPublicationFailures(unittest.TestCase):
    def exercise(self, partial, cleanup_unconfirmed=False):
        process = OwnedProcess()
        if cleanup_unconfirmed:
            process.stdout = io.StringIO()
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
                 patch.object(PROBE.subprocess, 'Popen', return_value=process) as launch, \
                 patch.object(Path, 'write_bytes', write), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(PROBE.main(), 1)
            summary = json.loads(stdout.getvalue())
            self.assertIn('injected report write failure', summary['report_write_error'])
            if cleanup_unconfirmed:
                self.assertIn('startup was not observed', summary['cleanup_error'])
                self.assertIsNone(summary['owned_container_absent'])
                invoked = launch.call_args.args[0]
                invocation_name = invoked[invoked.index('--name') + 1]
                self.assertEqual(summary['container'], invocation_name)
                self.assertEqual(summary['ownership_label'], invoked[invoked.index('--label') + 1])
                self.assertEqual(summary['context_sha256'], hashlib.sha256(b'test-context').hexdigest())
                self.assertNotIn('context', summary)
            self.assertEqual(output.read_text(), old_report)
            self.assertEqual(old_image.read_bytes(), b'old screenshot')
            self.assertEqual(list(Path(directory).glob('.t7-report-*')), [])
            self.assertTrue(process.terminated)

    def test_failure_before_report_open(self):
        self.exercise(False)

    def test_partial_report_write_failure(self):
        self.exercise(True)

    def test_write_failure_still_reports_cleanup_error(self):
        self.exercise(False, cleanup_unconfirmed=True)


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
