"""Offline regression tests for the restricted repository audit."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts/github-bootstrap'
with patch.object(sys, 'path', [str(SCRIPTS), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        'repository_integrity', SCRIPTS / 'repository_integrity.py'
    )
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)


REPOSITORY = 'example/fixture'
MANIFEST = {'repository': REPOSITORY, 'items': []}
INCIDENT = {'issue': 1, 'kind': 'resolved_incident', 'reason': 'Synthetic incident review.'}
TRACKER = {'issue': 2, 'kind': 'campaign_tracking', 'reason': 'Synthetic tracking review.'}


def issue(number, state='open', body=None, **fields):
    return {'number': number, 'state': state, 'body': body, **fields}


class RepositoryIntegrityTests(unittest.TestCase):
    def inspect(self, rows, dispositions=None, manifest=MANIFEST, nodes=()):
        with patch.object(audit, 'api', return_value=rows) as rest:
            with patch.object(audit, 'gql', return_value={'nodes': nodes}) as graphql:
                count, findings, reviewed = audit.audit_repository(manifest, dispositions or {})
        rest.assert_called_once_with(f'repos/{REPOSITORY}/issues?state=all&per_page=100&page=1')
        if not nodes:
            graphql.assert_not_called()
        return count, findings, reviewed

    def test_reviewed_closed_incident_and_active_tracker_are_reported(self):
        count, findings, reviewed = self.inspect(
            [issue(2), issue(1, 'closed')], {1: INCIDENT, 2: TRACKER}
        )
        self.assertEqual(count, 2)
        self.assertEqual(findings, [])
        self.assertEqual(reviewed, [
            {**INCIDENT, 'state': 'closed'}, {**TRACKER, 'state': 'open'},
        ])

    def test_reopened_incident_fails_and_closed_tracker_passes(self):
        _, findings, reviewed = self.inspect(
            [issue(1), issue(2, 'closed')], {1: INCIDENT, 2: TRACKER}
        )
        self.assertEqual(findings, [
            {'issue': 1, 'kind': 'disposition_state_mismatch', 'state': 'open'},
        ])
        self.assertEqual(reviewed, [{**TRACKER, 'state': 'closed'}])

    def test_unknown_issues_fail_even_when_closed_and_pull_requests_are_ignored(self):
        count, findings, reviewed = self.inspect([
            issue(3, 'closed'),
            issue(4),
            issue(5, pull_request={}),
        ])
        self.assertEqual(count, 2)
        self.assertEqual([(row['issue'], row['kind']) for row in findings], [
            (3, 'needs_triage'), (4, 'needs_triage'),
        ])
        self.assertEqual(reviewed, [])

    def test_missing_issue_and_malformed_roadmap_marker_fail(self):
        _, findings, reviewed = self.inspect(
            [issue(2, body='<!-- guildboard-id: GB-TEST -->'), issue(1, pull_request={})],
            {1: INCIDENT, 2: TRACKER},
        )
        self.assertEqual(findings, [
            {'issue': 2, 'kind': 'disposition_has_roadmap_marker'},
            {'issue': 1, 'kind': 'disposition_issue_missing'},
        ])
        self.assertEqual(reviewed, [])

    def test_disposition_cannot_skip_canonical_roadmap_checks(self):
        item = {
            'id': 'GB-T0.G1', 'work_type': 'Epic', 'parent_id': 'GB-T0',
            'dependencies': ['GB-T0.01'], 'labels': ['required'],
        }
        manifest = {**MANIFEST, 'items': [item]}
        node = {
            'id': 'test-node', 'parent': None, 'blockedBy': {'nodes': [{'id': 'other', 'state': 'OPEN'}]},
            'subIssues': {'nodes': [{'state': 'OPEN'}]},
        }
        _, findings, reviewed = self.inspect(
            [issue(1, 'closed', '<!-- guildboard-id:GB-T0.G1 -->',
                   node_id='test-node', labels=[], milestone=None)],
            {1: INCIDENT}, manifest, [node],
        )
        self.assertEqual([row['kind'] for row in findings], [
            'disposition_has_roadmap_marker',
            'missing_section', 'missing_section', 'missing_label', 'missing_milestone',
            'parent_mismatch', 'missing_native_dependency', 'premature_parent_closure',
            'premature_release_gate',
        ])
        self.assertEqual(reviewed, [])

    def test_invalid_configuration_is_rejected(self):
        invalid = [
            json.dumps({'repository': 'example/another', 'issues': [INCIDENT]}),
            json.dumps({'repository': REPOSITORY, 'issues': [INCIDENT, INCIDENT]}),
            json.dumps({'repository': REPOSITORY, 'issues': [{**INCIDENT, 'issue': True}]}),
            json.dumps({'repository': REPOSITORY, 'issues': [{**INCIDENT, 'kind': 'unknown'}]}),
            json.dumps({'repository': REPOSITORY, 'issues': [{**INCIDENT, 'reason': ' '}]}),
            '{"repository":"example/fixture","issues":[],"issues":[]}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'dispositions.json'
            for content in invalid:
                with self.subTest(content=content):
                    config.write_text(content, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        audit.load_dispositions(config, REPOSITORY)

    def test_invalid_configuration_fails_without_querying_github(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            planning = root / 'planning'
            (planning / 'audit').mkdir(parents=True)
            (planning / 'guildboard-backlog.json').write_text(json.dumps(MANIFEST), encoding='utf-8')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'api') as rest:
                with patch('builtins.print'):
                    self.assertTrue(audit.main())
            rest.assert_not_called()
            report = json.loads((planning / 'audit/repository-integrity.json').read_text())
            self.assertEqual(report['result'], 'needs_attention')
            self.assertEqual(report['findings'][0]['kind'], 'invalid_disposition_configuration')


if __name__ == '__main__':
    unittest.main()
