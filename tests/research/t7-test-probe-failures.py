"""Failure-report regressions; no Docker daemon or browser is required."""
import contextlib
import importlib.util
import io
import json
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


if __name__ == '__main__':
    unittest.main()
