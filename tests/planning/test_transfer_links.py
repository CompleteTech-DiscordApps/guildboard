"""Offline transfer-link preview and apply tests."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts/github-bootstrap'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('transfer_links', SCRIPTS / 'apply_transfer_links.py')
transfer = importlib.util.module_from_spec(spec)
with mock.patch.object(sys, 'dont_write_bytecode'):
    spec.loader.exec_module(transfer)

OLD = 'https://github.com/CompleteDotTech/guildboard'
NEW = 'https://github.com/CompleteTech-DiscordApps/guildboard'
ENDPOINT = 'repos/CompleteTech-DiscordApps/guildboard/issues/42'
BODY = f'<!-- guildboard-id:GB-TEST -->\n- [ ] keep label [link]({OLD}/issues/8#history).\n'
ITEM = {
    'id': 'GB-TEST', 'github': {'number': 42, 'id': 'synthetic-node'},
    'body_hash': hashlib.sha256(BODY.encode()).hexdigest(),
}


def response(body=BODY, **fields):
    return {'number': 42, 'node_id': 'synthetic-node', 'body': body, **fields}


class TransferLinkTests(unittest.TestCase):
    def test_rewrites_only_the_exact_repository_in_url_tokens(self):
        body = (BODY + f'Other: {OLD}-fork/issues/8\n'
                f'Nested: https://example.test/?to={OLD}/issues/8\n'
                f'Canonical: {NEW}/blob/main/README.md\n'
                'Prose: CompleteDotTech/guildboard\n')
        self.assertEqual(transfer.rewrite(body), body.replace(f']({OLD}/', f']({NEW}/'))

    def test_preview_only_reads(self):
        with mock.patch.object(transfer, 'api', return_value=response()) as api:
            self.assertEqual(transfer.process(42, ITEM, False), 'would_update')
        api.assert_called_once_with(ENDPOINT, redact_failure=True)

    def test_apply_rereads_and_patches_only_body_then_resumes_without_writes(self):
        updated = BODY.replace(OLD, NEW)
        with mock.patch.object(transfer, 'api', side_effect=[
            response(), response(), response(updated), response(updated),
        ]) as api:
            self.assertEqual(transfer.process(42, ITEM, True), 'updated')
            self.assertEqual(transfer.process(42, ITEM, True), 'no_transfer_links')
        self.assertEqual(api.call_args_list, [
            mock.call(ENDPOINT, redact_failure=True),
            mock.call(ENDPOINT, redact_failure=True),
            mock.call(ENDPOINT, 'PATCH', {'body': updated}, redact_failure=True),
            mock.call(ENDPOINT, redact_failure=True),
        ])

    def test_edited_or_wrong_issue_never_patches(self):
        for issue, result in (
            (response(BODY + 'edited'), 'skipped_edited'),
            (response(BODY + '<!-- guildboard-id:GB-OTHER -->\n'), 'skipped_identity'),
            (response(BODY.replace('GB-TEST', 'GB-OTHER')), 'skipped_identity'),
            ({**response(), 'number': 43}, 'skipped_identity'),
            ({**response(), 'node_id': 'another-node'}, 'skipped_identity'),
            (response(pull_request={}), 'skipped_identity'),
        ):
            with self.subTest(result=result), mock.patch.object(transfer, 'api', return_value=issue) as api:
                self.assertEqual(transfer.process(42, ITEM, True), result)
                api.assert_called_once()

    def test_edit_between_reads_never_patches(self):
        with mock.patch.object(transfer, 'api', side_effect=[response(), response(BODY + 'edited')]) as api:
            self.assertEqual(transfer.process(42, ITEM, True), 'skipped_changed_since_read')
        self.assertEqual(api.call_count, 2)

    def test_batch_limit_and_manifest_identity_are_checked_before_transport(self):
        with mock.patch.object(transfer, 'api') as request, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                transfer.main([flag for i in range(11) for flag in ('--issue', str(i + 1))])
            self.assertEqual(transfer.main(['--issue', '99999', '--apply']), 1)
            request.assert_not_called()

    def test_failed_patch_stops_batch_without_logs_or_raw_response(self):
        import api

        original = subprocess.CompletedProcess([], 0, stdout=json.dumps(response()), stderr='')
        failure = subprocess.CompletedProcess([], 1, stdout='synthetic-sensitive-body',
                                              stderr='synthetic-sensitive-error')
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            planning = root / 'planning'
            planning.mkdir()
            state = planning / 'github-state.json'
            state.write_text(json.dumps({'repo': transfer.REPOSITORY}))
            manifest = planning / 'guildboard-backlog.json'
            manifest.write_text(json.dumps({'repository': transfer.REPOSITORY, 'items': [
                ITEM, {**ITEM, 'id': 'GB-SECOND', 'github': {'number': 43, 'id': 'second-node'}},
            ]}))
            with mock.patch.multiple(transfer, ROOT=root, STATE=state), \
                    mock.patch.object(api, 'ROOT', root), \
                    mock.patch.object(api.subprocess, 'run', side_effect=[original, original, failure]) as request, \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(transfer.main(['--issue', '42', '--issue', '43', '--apply']), 1)
            self.assertEqual(sorted(p.name for p in planning.iterdir()), ['github-state.json', 'guildboard-backlog.json'])
        self.assertEqual(request.call_count, 3)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(
            stderr.getvalue(),
            'Transfer link batch stopped at issue #42: request or response could not be confirmed.\n',
        )
