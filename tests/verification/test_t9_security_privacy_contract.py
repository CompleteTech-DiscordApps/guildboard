"""Offline checks of the GB-T9.S1 declarative handoff and fixture expectations."""

from copy import deepcopy
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch


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
             'releaseMatrix', 'historicalReceipt', 'stageNegatives', 'postLookupDenial',
             'malformedCommand', 'internalRecords', 'recovery'},
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
            ['ack', 'receipt', 'digest_result', 'lineage_changed', 'live_event', 'replay_event',
             'snapshot_metadata', 'snapshot_chunk', 'asset_metadata', 'asset_chunk',
             'export_metadata', 'export_chunk'],
            matrix['kinds'],
        )
        self.assertEqual(
            ['session_revoke', 'session_expiry', 'membership_invalid', 'membership_stale',
             'read_policy_change', 'time_unavailable', 'fence_unavailable',
             'policy_stale', 'policy_unavailable', 'time_stale'],
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
             'requiresAuthorizedActiveRejoin', 'requiresValidatedCompleteActiveSnapshot',
             'requiresContiguousTailIfNeeded', 'advancesOnPartialOrGappedTransfer'},
            receipt.keys(),
        )
        for field, expected in (
            ('settlesHistoricalOperation', True),
            ('clearsSameOperationPendingRetry', True),
            ('appliesPayloadToActiveLineage', False),
            ('marksActiveLineageSaved', False),
            ('requiresAuthorizedActiveRejoin', True),
            ('requiresValidatedCompleteActiveSnapshot', True),
            ('requiresContiguousTailIfNeeded', True),
            ('advancesOnPartialOrGappedTransfer', False),
        ):
            with self.subTest(observation=field):
                self.assertIs(receipt[field], expected)

    def assertExactJSON(self, expected, actual, path='$'):
        self.assertIs(type(actual), type(expected), path)
        if isinstance(expected, dict):
            self.assertEqual(expected.keys(), actual.keys(), path)
            for key, value in expected.items():
                self.assertExactJSON(value, actual[key], f'{path}.{key}')
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), path)
            for index, (value, observed) in enumerate(zip(expected, actual)):
                self.assertExactJSON(value, observed, f'{path}[{index}]')
        else:
            self.assertEqual(expected, actual, path)

    def test_commit_and_egress_have_separate_typed_denials(self):
        unavailable = ['policy_stale', 'policy_unavailable', 'time_stale', 'time_unavailable',
                       'fence_unavailable']
        self.assertExactJSON({
            'commit': {
                'FORBIDDEN': ['fresh_scoped_read_only'],
                'POLICY_STALE': ['proven_generation_mismatch'],
                'DEPENDENCY_UNAVAILABLE': unavailable,
            },
            'commitAcceptedEffects': False,
            'egressProtectedOutput': False,
            'egress': {
                'FORBIDDEN': ['read_denied_after_lookup'],
                'DEPENDENCY_UNAVAILABLE': unavailable,
            },
        }, self.fixture['stageNegatives'])

    def test_post_lookup_denial_covers_all_prepared_branches(self):
        matrix = self.fixture['postLookupDenial']
        self.assertEqual(set(self.fixture['receiptLookupMatrix']['storedStates']), matrix['prepared'].keys())
        self.assertExactJSON({
            'prepared': {
                'absent': 'LINEAGE_CHANGED', 'matching': 'receipt',
                'mismatching': 'IDEMPOTENCY_CONFLICT',
            },
            'prelookupAuthorized': True,
            'authorityLossImmediatelyBeforeEgress': True,
            'sameNormalizedOutcomeForSameDenial': True,
            'protectedOutput': False,
            'additionalDurableEffects': False,
            'priorAcceptedCommitSurvives': True,
            'settlesUnknown': False,
        }, matrix)

    def test_malformed_command_rejects_before_lookup_or_effects(self):
        self.assertExactJSON({
            'INVALID_MESSAGE': {
                'unknown_field': {'add': {'unknownFixtureField': False}},
                'duplicate_field': {'repeat': 'operationId'},
                'unknown_kind': {'set': {'kind': 'UNREGISTERED_FIXTURE_KIND'}},
                'invalid_id': {'set': {'operationId': 'fixture-not-a-uuid'}},
                'noncanonical_counter': {'set': {'baseRevision': '01'}},
                'counter_above_uint64': {'set': {'baseRevision': str(1 << 64)}},
            },
            'UNSUPPORTED_VERSION': {'unsupported_version': {'set': {'version': 2}}},
            'onlySafeRejection': True, 'digestLookup': False, 'receiptLookup': False,
            'protectedOutput': False, 'durableEffects': False,
        }, self.fixture['malformedCommand'])

    def test_closed_records_fail_with_typed_results(self):
        self.assertExactJSON({
            'kinds': ['deletion_job', 'audit_event', 'release_evidence', 'exception',
                      'retention_exception'],
            'INVALID_RECORD': ['missing_field', 'unknown_field', 'duplicate_field',
                               'wrong_type', 'wrong_scope', 'unregistered_value'],
            'UNSUPPORTED_RECORD_VERSION': ['unsupported_version'],
            'DEPENDENCY_UNAVAILABLE': ['required_registry_unavailable',
                                       'required_authority_unavailable', 'required_time_unavailable'],
            'acceptsInvalidOrUnverifiableRecord': False,
        }, self.fixture['internalRecords'])

    def test_restore_and_audit_have_independent_coverage_checks(self):
        self.assertExactJSON({
            'restoreExposes': {'current_complete_reconciled': True, 'missing': False,
                               'stale': False, 'gapped': False, 'later_deletion_unapplied': False},
            'auditVerifies': {'anchored_complete': True, 'anchor_missing': False,
                              'anchor_unavailable': False, 'anchor_stale': False,
                              'checkpointed_truncation': False,
                              'accepted_active_tail_truncation': False},
            'auditAcceptsUnanchoredAppendedSuffix': False,
        }, self.fixture['recovery'])

    def test_contract_checks_reject_scalar_type_mutations(self):
        def boolean_paths(record, prefix=()):
            for key, value in record.items():
                path = (*prefix, key)
                if isinstance(value, dict):
                    yield from boolean_paths(value, path)
                elif type(value) is bool:
                    yield path, int(value)

        checks = {
            'stageNegatives': self.test_commit_and_egress_have_separate_typed_denials,
            'postLookupDenial': self.test_post_lookup_denial_covers_all_prepared_branches,
            'malformedCommand': self.test_malformed_command_rejects_before_lookup_or_effects,
            'internalRecords': self.test_closed_records_fail_with_typed_results,
            'recovery': self.test_restore_and_audit_have_independent_coverage_checks,
        }
        for section, check in checks.items():
            mutations = list(boolean_paths(self.fixture[section]))
            if section == 'malformedCommand':
                mutations.extend([
                    (('UNSUPPORTED_VERSION', 'unsupported_version', 'set', 'version'), 2.0),
                    (('INVALID_MESSAGE', 'noncanonical_counter', 'set', 'baseRevision'), 1),
                    (('INVALID_MESSAGE', 'counter_above_uint64', 'set', 'baseRevision'), 1 << 64),
                ])
            for path, replacement in mutations:
                with self.subTest(section=section, path=path, replacement=replacement):
                    mutated = deepcopy(self.fixture)
                    record = mutated[section]
                    for key in path[:-1]:
                        record = record[key]
                    record[path[-1]] = replacement
                    with patch.object(self, 'fixture', mutated), self.assertRaises(AssertionError) as failure:
                        check()
                    self.assertIn('$.' + '.'.join(path), str(failure.exception))

    def test_refined_cases_trace_to_native_verifiers(self):
        by_id = {case['id']: case for case in self.fixture['scenarios']}
        for case, issues in {
            'commit_order': [300], 'commit_dependencies': [300], 'receipt_release_denial': [300],
            'malformed_command': [300, 307], 'internal_records': [311, 314, 321],
            'delete_restore': [311], 'audit_integrity': [314, 318],
        }.items():
            with self.subTest(case=case):
                self.assertEqual(issues, by_id[case]['verificationIssues'])

    def test_workstream_and_specification_link_to_exact_artifacts(self):
        self.assertIn(f'](../specifications/{SPECIFICATION.name})', self.workstream)
        self.assertIn(f'](../specifications/fixtures/{FIXTURE.name})', self.workstream)
        self.assertIn(f'](fixtures/{FIXTURE.name})', self.specification)
        self.assertIn('issues/293#issuecomment-6962774500', self.specification)


if __name__ == '__main__':
    unittest.main()
