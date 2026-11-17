"""Offline checks of the GB-T9.S1 declarative handoff and fixture expectations."""

import itertools
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / 'docs' / 'specifications'
FIXTURE = SPEC_DIR / 'fixtures' / 'GB-T9-S1-scenarios.json'
SPECIFICATION = SPEC_DIR / 'GB-T9-S1-security-privacy-contract.md'
WORKSTREAM = ROOT / 'docs' / 'workstreams' / 'T9.md'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate fixture field: {key}')
        result[key] = value
    return result


class T9SecurityPrivacyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
        cls.specification = SPECIFICATION.read_text(encoding='utf-8')
        cls.workstream = WORKSTREAM.read_text(encoding='utf-8')

    def test_fixture_is_explicitly_synthetic_and_versioned(self):
        self.assertEqual(
            {'version', 'contract', 'kind', 'scenarios', 'receiptLookupMatrix',
             'releaseMatrix', 'historicalReceipt'},
            self.fixture.keys(),
        )
        self.assertIs(type(self.fixture['version']), int)
        self.assertEqual(1, self.fixture['version'])
        self.assertEqual('GB-T9.S1', self.fixture['contract'])
        self.assertEqual('declarative_synthetic', self.fixture['kind'])

    def test_scenario_shape_and_unique_ids(self):
        seen = set()
        scenarios = self.fixture['scenarios']
        self.assertTrue(1 <= len(scenarios) <= 64)
        for scenario in scenarios:
            with self.subTest(case=scenario.get('id')):
                self.assertEqual(
                    {'id', 'research', 'verificationIssues', 'inputs', 'requiredObservations'},
                    scenario.keys(),
                )
                self.assertRegex(scenario['id'], r'^[a-z][a-z_]{0,63}$')
                self.assertNotIn(scenario['id'], seen)
                seen.add(scenario['id'])
                for field in ('inputs', 'requiredObservations'):
                    self.assertIsInstance(scenario[field], str)
                    self.assertTrue(1 <= len(scenario[field]) <= 512)
                issues = scenario['verificationIssues']
                self.assertTrue(issues)
                self.assertEqual(sorted(set(issues)), issues)
                self.assertTrue(all(type(issue) is int for issue in issues))

    def test_trace_reaches_every_threat_and_native_verifier(self):
        build_to_verify = {
            296: 297, 299: 300, 303: 304, 306: 307,
            310: 311, 313: 314, 317: 318, 320: 321,
        }
        scenarios = self.fixture['scenarios']
        self.assertEqual({f'A{n:02}' for n in range(1, 12)}, {s['research'] for s in scenarios})
        self.assertEqual(set(build_to_verify.values()), {
            issue for scenario in scenarios for issue in scenario['verificationIssues']
        })
        dependencies = (ROOT / 'planning' / 'DEPENDENCIES.md').read_text(encoding='utf-8')
        for build, verify in build_to_verify.items():
            with self.subTest(verification=verify):
                native_dependency = [
                    line for line in dependencies.splitlines()
                    if f'/issues/{verify})' in line and f'/issues/{build})' in line
                ]
                self.assertEqual(1, len(native_dependency))
                self.assertIn(f'#{build} → #{verify}', self.specification)

    def test_receipt_denial_matrix_has_no_lookup_or_observable_effect(self):
        matrix = self.fixture['receiptLookupMatrix']
        expected_denials = ['UNAUTHENTICATED', 'NOT_FOUND', 'FORBIDDEN', 'DEPENDENCY_UNAVAILABLE']
        self.assertEqual(expected_denials, matrix['denials'])
        self.assertEqual(['absent', 'matching', 'mismatching'], matrix['storedStates'])
        self.assertEqual(
            {'receiptLookup', 'digestLookup', 'protectedOutput', 'durableChange', 'settlesUnknown'},
            matrix['denialEffects'].keys(),
        )
        for reason, state in itertools.product(matrix['denials'], matrix['storedStates']):
            with self.subTest(reason=reason, receipt=state):
                for field, effect in matrix['denialEffects'].items():
                    self.assertIs(effect, False, field)

    def test_release_matrix_covers_every_protected_output_and_both_orders(self):
        matrix = self.fixture['releaseMatrix']
        self.assertEqual(
            ['ack', 'receipt', 'digest_result', 'live_event', 'replay_event',
             'snapshot_metadata', 'snapshot_chunk', 'asset_metadata', 'asset_chunk',
             'export_metadata', 'export_chunk'],
            matrix['kinds'],
        )
        self.assertEqual(
            ['session_revoke', 'session_expiry', 'membership_invalid', 'membership_stale',
             'read_policy_change', 'time_unavailable', 'fence_unavailable'],
            matrix['authorityLoss'],
        )
        self.assertEqual({'release_first', 'authority_loss_first'}, matrix['orders'].keys())
        for kind, cause, order in itertools.product(
            matrix['kinds'], matrix['authorityLoss'], matrix['orders'],
        ):
            with self.subTest(kind=kind, cause=cause, order=order):
                expectation = matrix['orders'][order]
                self.assertEqual({'firstRelease', 'laterRelease'}, expectation.keys())
                self.assertIs(expectation['firstRelease'], order == 'release_first')
                self.assertIs(expectation['laterRelease'], False)
        self.assertIs(matrix['committedAck']['durableAcceptanceSurvives'], True)
        self.assertIs(matrix['committedAck']['deniedAckSettlesUnknown'], False)

    def test_historical_receipt_settles_only_original_operation(self):
        receipt = self.fixture['historicalReceipt']
        self.assertEqual(
            {'settlesHistoricalOperation', 'clearsSameOperationPendingRetry',
             'appliesPayloadToActiveLineage', 'marksActiveLineageSaved',
             'requiresAuthorizedActiveRejoin', 'requiresValidatedActiveSnapshotOrTail'},
            receipt.keys(),
        )
        for field, expected in (
            ('settlesHistoricalOperation', True),
            ('clearsSameOperationPendingRetry', True),
            ('appliesPayloadToActiveLineage', False),
            ('marksActiveLineageSaved', False),
            ('requiresAuthorizedActiveRejoin', True),
            ('requiresValidatedActiveSnapshotOrTail', True),
        ):
            with self.subTest(observation=field):
                self.assertIs(receipt[field], expected)

    def test_workstream_and_specification_link_to_exact_artifacts(self):
        self.assertIn(f'](../specifications/{SPECIFICATION.name})', self.workstream)
        self.assertIn(f'](../specifications/fixtures/{FIXTURE.name})', self.workstream)
        self.assertIn(f'](fixtures/{FIXTURE.name})', self.specification)
        self.assertIn('issues/293#issuecomment-6962774500', self.specification)


if __name__ == '__main__':
    unittest.main()
