"""Offline tests for scripts/verification/check_licenses.py (GB-T0.02.02.T1, #16).

Most cases run the checker on temporary fixtures. RepositoryDataCases is the one
real-data regression check: it runs the gate over both default lockfiles with the
committed exceptions file. A legitimate lockfile or exception change must update that
data in the same change; the test is drift detection, not a unit test.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / 'scripts' / 'verification' / 'check_licenses.py'
POLICY_DOC = REPO / 'docs' / 'license-supply-chain-policy.md'
WORKFLOW = REPO / '.github' / 'workflows' / 'license-policy.yml'
TASK_DOC = REPO / 'docs' / 'workstreams' / 'T0.md'

_spec = importlib.util.spec_from_file_location('check_licenses', CHECKER)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

INTEGRITY = 'sha512-' + 'A' * 86 + '=='
OTHER_INTEGRITY = 'sha512-' + 'B' * 86 + '=='
PROHIBITED_SPELLINGS = (
    'GPL', 'GPLv2', 'GPLv3', 'GPL2', 'GPL-2.0-only', 'GPL-3.0-or-later', 'GPL-2.0+',
    'LGPL', 'LGPLv3', 'LGPL-2.1-only', 'LGPL-3.0-or-later', 'AGPL', 'AGPLv3', 'AGPL-3.0-only',
    'SSPL', 'SSPL-1.0', 'BUSL', 'BUSL-1.0', 'BUSL-1.1', 'CC-BY-NC-4.0',
    'NOASSERTION', 'UNLICENSED', 'UNKNOWN',
    'MIT OR GPLv3', '(MIT OR GPL-3.0-only)', 'Apache-2.0 AND LGPL-2.1-only', 'MIT AND AGPLv3',
)


def pkg(version='1.0.0', license_value='MIT', **extra):
    entry = {'version': version, 'resolved': 'https://registry.npmjs.org/x.tgz', 'integrity': INTEGRITY}
    if license_value is not None:
        entry['license'] = license_value
    entry.update(extra)
    return entry


def without(entry, *fields):
    return {key: value for key, value in entry.items() if key not in fields}


def lockfile(packages, version=3):
    base = {'': {'name': 'fixture', 'version': '0.0.0', 'devDependencies': {}, 'workspaces': ['apps/*']},
            'apps/api': {'name': '@fixture/api', 'version': '0.0.0'},
            'node_modules/@fixture/api': {'resolved': 'apps/api', 'link': True}}
    base.update(packages)
    return {'name': 'fixture', 'lockfileVersion': version, 'requires': True, 'packages': base}


class CheckerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding='utf-8')
        else:
            path.write_text(json.dumps(content, indent=2), encoding='utf-8')
        return name

    def exceptions(self, entries):
        return self.write('exceptions.json', {'schema_version': 1, 'exceptions': entries})

    def run_checker(self, lockfile_names, exceptions_name='absent-exceptions.json'):
        proc = subprocess.run(
            [sys.executable, str(CHECKER), '--exceptions', exceptions_name, *lockfile_names],
            cwd=self.dir, capture_output=True, text=True, timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr


class PolicyCases(CheckerCase):
    def test_positive_case_passes(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/a': pkg('1.0.0', 'MIT'),
            'node_modules/b': pkg('2.0.0', 'Apache-2.0'),
            'node_modules/c': pkg('3.0.0', '(BSD-2-Clause OR ISC)'),
            'node_modules/d': pkg('4.0.0', 'BlueOak-1.0.0'),
        }))
        code, out, err = self.run_checker([name])
        self.assertEqual(code, 0, out + err)
        self.assertIn('result: PASS (0 finding(s))', out)
        self.assertIn('skipped-first-party=3', out)  # root, workspace package and workspace link

    def test_missing_license_fails_and_cannot_be_excepted(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('missing or unknown license', out)
        exc = self.exceptions([{'name': 'a', 'version': '1.0.0', 'license': 'MIT', 'reason': 'x'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1, 'missing license must never be excepted')

    def test_null_and_empty_license_fail(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/a': pkg('1.0.0', ''),
            'node_modules/b': pkg('1.0.0', None),
        }))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertEqual(out.count('missing or unknown license'), 2)

    def test_prohibited_spellings_fail_without_exception(self):
        for spelling in PROHIBITED_SPELLINGS:
            with self.subTest(license=spelling):
                name = self.write('package-lock.json', lockfile({'node_modules/g': pkg('3.0.0', spelling)}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1, out)
                self.assertIn('prohibited license', out)

    def test_prohibited_license_cannot_be_excepted(self):
        name = self.write('package-lock.json', lockfile({'node_modules/g': pkg('3.0.0', 'GPLv3')}))
        exc = self.exceptions([{'name': 'g', 'version': '3.0.0', 'license': 'GPLv3', 'reason': 'x'}])
        code, out, err = self.run_checker([name], exc)
        self.assertEqual(code, 2, 'an exception naming a prohibited license is an input error')
        self.assertIn('cannot be excepted', err)

    def test_unknown_literal_is_prohibited(self):
        name = self.write('package-lock.json', lockfile({'node_modules/u': pkg('1.0.0', 'UNKNOWN')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('prohibited license', out)

    def test_unknown_identifier_is_review_required_and_needs_exception(self):
        name = self.write('package-lock.json', lockfile({'node_modules/w': pkg('1.0.0', 'WTFPL')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('review-required license', out)
        exc = self.exceptions([{'name': 'w', 'version': '1.0.0', 'license': 'WTFPL', 'reason': 'owner pending'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 0, out)
        self.assertIn('excepted review-required license', out)

    def test_malformed_spdx_expression_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/m': pkg('1.0.0', 'MIT OR')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('malformed license', out)

    def test_non_string_license_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/o': pkg('1.0.0', {'type': 'MIT'})}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('malformed license', out)

    def test_third_party_without_integrity_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/n': without(pkg('1.0.0', 'MIT'), 'integrity')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('missing integrity', out)
        self.assertIn('third-party-without-integrity=1', out)
        self.assertIn('result: FAIL (1 finding(s))', out)

    def test_third_party_with_empty_or_non_string_integrity_fails(self):
        for value in ('', 5):
            with self.subTest(integrity=value):
                name = self.write('package-lock.json', lockfile({'node_modules/n': pkg('1.0.0', 'MIT', integrity=value)}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1, out)
                self.assertIn('missing integrity', out)

    def test_missing_integrity_is_not_bridged_by_override(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': without(pkg('1.0.0', None), 'integrity')}))
        exc = self.write('exceptions.json', {'schema_version': 1, 'exceptions': [],
                                             'verified_license_overrides': [override_entry('a', '1.0.0')]})
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('missing integrity', out)
        self.assertIn('missing or unknown license', out)

    def test_unexpected_install_path_fails(self):
        name = self.write('package-lock.json', lockfile({'vendor/x': pkg('1.0.0', 'MIT')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('unexpected install path', out)

    def test_nested_node_modules_inside_vendor_is_unexpected(self):
        name = self.write('package-lock.json', lockfile({'vendor/node_modules/y': pkg('1.0.0', 'MIT')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('unexpected install path', out)
        self.assertIn('vendor/node_modules/y', out)

    def test_traversal_in_install_path_is_unexpected_even_when_prohibited(self):
        for key in ('apps/../../vendor/x', 'node_modules/../x', 'node_modules/a/../../evil', '/abs/node_modules/x',
                    'node_modules/..', 'node_modules/.', 'node_modules/a/node_modules/..'):
            with self.subTest(key=key):
                name = self.write('package-lock.json', lockfile({key: pkg('1.0.0', 'GPL-3.0-only')}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1)
                self.assertIn('unexpected install path', out)
                self.assertNotIn('prohibited license', out)

    def test_nested_node_modules_path_is_third_party(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/a/node_modules/@s/b': pkg('1.0.0', 'Zlib'),
        }))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1, out)
        self.assertIn('third-party=1', out)
        self.assertIn('node_modules/a/node_modules/@s/b [@s/b@1.0.0] review-required license', out)
        self.assertNotIn('unexpected install path', out)

    def test_workspace_entry_must_be_a_known_workspace_path(self):
        cases = {
            'tools/ghost': without(pkg('1.0.0', None), 'resolved', 'integrity'),  # no declared workspace glob
            'apps/api-extra/nested': {'version': '1.0.0'},  # nested below a workspace glob
        }
        for key, entry in cases.items():
            with self.subTest(key=key):
                name = self.write('package-lock.json', lockfile({key: entry}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1)
                self.assertIn('unexpected install path', out)

    def test_workspace_entry_with_resolved_or_integrity_is_unexpected(self):
        for extra in ({'resolved': 'https://example.invalid/x.tgz'}, {'integrity': INTEGRITY}):
            with self.subTest(extra=extra):
                name = self.write('package-lock.json', lockfile({'apps/api': {'name': '@fixture/api', 'version': '0.0.0', **extra}}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1)
                self.assertIn('workspace entry must not carry resolved or integrity', out)

    def test_link_must_point_at_a_present_workspace(self):
        cases = {
            'escapes lockfile': {'resolved': '../../outside', 'link': True},
            'target absent': {'resolved': 'apps/missing', 'link': True},
            'not a workspace dir': {'resolved': 'vendor/y', 'link': True},
            'link outside node_modules': {'resolved': 'apps/api', 'link': True},
        }
        for label, entry in cases.items():
            with self.subTest(case=label):
                key = 'apps/link-here' if label == 'link outside node_modules' else 'node_modules/@fixture/bad'
                name = self.write('package-lock.json', lockfile({key: entry}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1)
                self.assertIn('unexpected install path', out)

    def test_link_to_present_workspace_is_skipped(self):
        name = self.write('package-lock.json', lockfile({}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 0, out)
        self.assertIn('skipped-first-party=3', out)

    def test_aliased_package_is_classified_by_real_name(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/alias': pkg('1.0.0', 'Zlib', name='real-pkg'),
        }))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('node_modules/alias [real-pkg@1.0.0] review-required license', out)
        exc = self.exceptions([{'name': 'real-pkg', 'version': '1.0.0', 'license': 'Zlib', 'reason': 'x'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 0, out)

    def test_exception_under_alias_path_name_does_not_apply(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/alias': pkg('1.0.0', 'Zlib', name='real-pkg'),
        }))
        exc = self.exceptions([{'name': 'alias', 'version': '1.0.0', 'license': 'Zlib', 'reason': 'x'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('stale exception', out)

    def test_aliased_prohibited_license_is_prohibited(self):
        name = self.write('package-lock.json', lockfile({
            'node_modules/alias': pkg('1.0.0', 'GPL-3.0-only', name='real-gpl'),
        }))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('prohibited license', out)

    def test_invalid_alias_name_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/alias': pkg('1.0.0', 'MIT', name=5)}))
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('invalid name', err)

    def test_malformed_json_is_input_error(self):
        name = self.write('package-lock.json', '{"lockfileVersion": 3, "packages": {')
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('malformed JSON', err)

    def test_duplicate_key_is_input_error(self):
        name = self.write('package-lock.json', '{"lockfileVersion": 3, "lockfileVersion": 3, "packages": {"": {}}}')
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('duplicate key', err)

    def test_nan_and_infinity_are_input_errors(self):
        for token in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(token=token):
                name = self.write('package-lock.json', '{"lockfileVersion": 3, "packages": {"": {"x": %s}}}' % token)
                code, _, err = self.run_checker([name])
                self.assertEqual(code, 2)
                self.assertIn('malformed JSON', err)

    def test_deeply_nested_json_is_input_error_not_traceback(self):
        depth = 100000
        name = self.write('package-lock.json', '[' * depth + ']' * depth)
        code, out, err = self.run_checker([name])
        self.assertEqual(code, 2, err)
        self.assertIn('nested too deeply', err)
        self.assertNotIn('Traceback', err)

    def test_oversized_input_is_input_error(self):
        (self.dir / 'huge.json').write_bytes(b' ' * (check.MAX_INPUT_BYTES + 1))
        code, out, err = self.run_checker(['huge.json'])
        self.assertEqual(code, 2)
        self.assertIn('input too large', err)
        self.assertNotIn('Traceback', err)

    def test_missing_file_is_input_error(self):
        code, _, err = self.run_checker(['no-such-lockfile.json'])
        self.assertEqual(code, 2)
        self.assertIn('missing file', err)

    def test_unsupported_lockfile_version_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg()}, version=1))
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('unsupported lockfileVersion', err)

    def test_empty_packages_map_is_input_error(self):
        name = self.write('package-lock.json', {'lockfileVersion': 3, 'packages': {}})
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('missing packages map', err)

    def test_entry_without_version_is_input_error(self):
        broken = lockfile({'node_modules/a': {'license': 'MIT'}})
        name = self.write('package-lock.json', broken)
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('lacks a version', err)

    def test_malformed_exceptions_file_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg()}))
        bad = self.write('bad.json', {'schema_version': 1, 'exceptions': [{'name': 'a', 'version': '1.0.0', 'license': 'MIT'}]})
        code, _, err = self.run_checker([name], bad)
        self.assertEqual(code, 2)
        self.assertIn('must have exactly', err)

    def test_missing_exceptions_file_is_read_as_none_and_noted(self):
        name = self.write('package-lock.json', lockfile({'node_modules/z': pkg('1.0.0', 'Zlib')}))
        code, out, _ = self.run_checker([name], 'no-such-exceptions.json')
        self.assertEqual(code, 1, 'a review-required package still fails without an exceptions file')
        self.assertIn('file absent, so no exceptions or verified overrides apply', out)


class InstallPathAndIntegrityCases(CheckerCase):
    def test_workspace_patterns_cannot_cover_node_modules_or_match_everything(self):
        for patterns in (['node_modules/*'], ['apps/*', 'node_modules/*'], ['node_modules/**'],
                         ['*'], ['**'], ['../*'], ['apps/../node_modules/*'], ['/abs/*'], ['node_modules\\*']):
            with self.subTest(patterns=patterns):
                data = lockfile({'node_modules/evil': pkg('1.0.0', 'GPL-3.0-only')})
                data['packages']['']['workspaces'] = patterns
                name = self.write('package-lock.json', data)
                code, out, err = self.run_checker([name])
                self.assertEqual(code, 2, out + err)
                self.assertIn('unsafe workspaces pattern', err)

    def test_integrity_format_is_checked_for_lockfile_entries(self):
        self.assertTrue(check.valid_integrity(INTEGRITY))
        self.assertTrue(check.valid_integrity('sha384-' + 'A' * 64))
        self.assertTrue(check.valid_integrity('sha256-' + 'A' * 43 + '='))
        malformed = ['md5-' + 'A' * 22 + '==', 'sha1-' + 'A' * 27 + '=', 'sha512-', 'sha512-' + 'A' * 88,
                     'sha256-' + 'A' * 44, 'sha384-' + 'A' * 60, 'sha512-' + '!' * 86 + '==',
                     INTEGRITY + 'x', 'not an integrity value', '   ', INTEGRITY + ' bogus']
        for value in malformed:
            with self.subTest(integrity=value):
                self.assertFalse(check.valid_integrity(value))
                name = self.write('package-lock.json', lockfile({'node_modules/n': pkg('1.0.0', 'MIT', integrity=value)}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1, out)
                self.assertIn('malformed integrity', out)
                self.assertNotIn('missing integrity', out)

    def test_backslash_install_path_is_unexpected_even_when_prohibited(self):
        for key in ('node_modules/..\\evil', 'node_modules/a\\b'):
            with self.subTest(key=key):
                name = self.write('package-lock.json', lockfile({key: pkg('1.0.0', 'GPL-3.0-only')}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1, out)
                self.assertIn('unexpected install path', out)
                self.assertNotIn('prohibited license', out)

    def test_workspace_local_install_is_third_party_by_real_name(self):
        name = self.write('package-lock.json', lockfile({'apps/api/node_modules/x': pkg('1.0.0', 'MIT')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 0, out)
        self.assertIn('third-party=1', out)
        self.assertNotIn('unexpected install path', out)
        name = self.write('package-lock.json', lockfile({'apps/api/node_modules/@s/y': pkg('2.0.0', 'GPL-3.0-only')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1, out)
        self.assertIn('apps/api/node_modules/@s/y [@s/y@2.0.0] prohibited license', out)
        self.assertNotIn('unexpected install path', out)

    def test_nested_install_under_unknown_prefix_stays_unexpected(self):
        for key in ('vendor/api/node_modules/x', 'tools/api/node_modules/x', 'apps/node_modules/x',
                    'apps/api/node_modules/../x', 'apps/../node_modules/x'):
            with self.subTest(key=key):
                name = self.write('package-lock.json', lockfile({key: pkg('1.0.0', 'MIT')}))
                code, out, _ = self.run_checker([name])
                self.assertEqual(code, 1, out)
                self.assertIn('unexpected install path', out)


class DocumentWordingCases(unittest.TestCase):
    def test_missing_exceptions_wording_matches_the_real_output(self):
        phrase = 'file absent, so no exceptions or verified overrides apply'
        policy = POLICY_DOC.read_text(encoding='utf-8')
        for label, text in (('policy doc', policy), ('checker docstring', check.__doc__)):
            with self.subTest(label=label):
                self.assertNotIn('prints a NOTE', text)
                self.assertIn(phrase, text)

    def test_policy_documents_the_lockfile_defaults_and_filter_rule(self):
        text = POLICY_DOC.read_text(encoding='utf-8')
        self.assertIn('DEFAULT_LOCKFILES', text)
        self.assertIn('`paths` filters', text)


class SpdxExpressionCases(unittest.TestCase):
    def rank(self, text):
        return check.classify_expression(text)

    def test_single_identifiers(self):
        self.assertEqual(self.rank('MIT'), check.OK)
        self.assertEqual(self.rank('Zlib'), check.REVIEW_RANK)
        self.assertEqual(self.rank('GPL-2.0-or-later'), check.PROHIBITED_RANK)

    def test_prohibited_spellings_are_prohibited(self):
        for spelling in PROHIBITED_SPELLINGS:
            if spelling.startswith('(') or ' ' in spelling:
                continue
            with self.subTest(license=spelling):
                self.assertEqual(self.rank(spelling), check.PROHIBITED_RANK)

    def test_policy_prohibited_literals_are_prohibited(self):
        for literal in ('NOASSERTION', 'UNLICENSED', 'UNKNOWN', 'SSPL', 'BUSL-1.1', 'CC-BY-NC-SA-4.0'):
            with self.subTest(license=literal):
                self.assertEqual(self.rank(literal), check.PROHIBITED_RANK)

    def test_lgpl_is_prohibited_not_review(self):
        self.assertEqual(self.rank('LGPL-2.1-only'), check.PROHIBITED_RANK)
        self.assertEqual(self.rank('lgpl-3.0-or-later'), check.PROHIBITED_RANK)

    def test_unknown_identifiers_default_to_review(self):
        for ident in ('Elastic-2.0', 'LicenseRef-internal', 'WTFPL', 'Artistic-2.0'):
            with self.subTest(license=ident):
                self.assertEqual(self.rank(ident), check.REVIEW_RANK)

    def test_or_takes_most_restrictive_branch(self):
        self.assertEqual(self.rank('MIT OR Apache-2.0'), check.OK)
        self.assertEqual(self.rank('(MPL-2.0 OR Apache-2.0)'), check.REVIEW_RANK)
        self.assertEqual(self.rank('MIT OR GPL-2.0-only'), check.PROHIBITED_RANK)
        self.assertEqual(self.rank('MIT OR GPLv3'), check.PROHIBITED_RANK)

    def test_and_takes_most_restrictive_term(self):
        self.assertEqual(self.rank('(MIT OR Apache-2.0) AND ISC'), check.OK)
        self.assertEqual(self.rank('(MIT AND Zlib)'), check.REVIEW_RANK)
        self.assertEqual(self.rank('MIT AND GPL-3.0-or-later'), check.PROHIBITED_RANK)

    def test_with_allowed_exceptions_is_at_least_review(self):
        self.assertEqual(self.rank('MIT WITH LLVM-exception'), check.REVIEW_RANK)
        self.assertEqual(self.rank('Apache-2.0 WITH GCC-exception-3.1'), check.REVIEW_RANK)
        self.assertEqual(self.rank('MIT WITH classpath-exception-2.0'), check.REVIEW_RANK)
        self.assertEqual(self.rank('GPL-2.0-only WITH Classpath-exception-2.0'), check.PROHIBITED_RANK)

    def test_with_unlisted_exception_is_malformed(self):
        for text in ('MIT WITH Foo-exception', 'MIT WITH GPL-3.0-only', '(MIT OR ISC) WITH LLVM-exception'):
            with self.subTest(text=text):
                self.assertIsNone(self.rank(text))

    def test_identifier_matching_is_case_insensitive(self):
        self.assertEqual(self.rank('mit and isc'), check.OK)
        self.assertEqual(self.rank('zlib'), check.REVIEW_RANK)
        self.assertEqual(self.rank('agpl-3.0-only'), check.PROHIBITED_RANK)

    def test_malformed_expressions_return_none(self):
        for text in ['', 'MIT OR', '(MIT', 'MIT)', 'MIT MIT', 'MIT/Apache-2.0', 'MIT WITH', '()', 'AND MIT']:
            with self.subTest(text=text):
                self.assertIsNone(self.rank(text))

    def test_deep_nesting_is_malformed_not_a_crash(self):
        self.assertIsNone(self.rank('(' * 5000 + 'MIT' + ')' * 5000))


class ExceptionCases(CheckerCase):
    def test_exception_honoured_only_for_pinned_version(self):
        name = self.write('package-lock.json', lockfile({'node_modules/pako': pkg('2.0.3', '(MIT AND Zlib)')}))
        exc = self.exceptions([{'name': 'pako', 'version': '2.0.3', 'license': '(MIT AND Zlib)', 'reason': 'pinned'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 0, out)
        self.assertIn('excepted review-required', out)

        other = self.write('other-lock.json', lockfile({'node_modules/pako': pkg('2.0.4', '(MIT AND Zlib)')}))
        code, out, _ = self.run_checker([other], exc)
        self.assertEqual(code, 1)
        self.assertIn('review-required license', out)
        self.assertIn('stale exception', out)

    def test_exception_requires_exact_license_string(self):
        name = self.write('package-lock.json', lockfile({'node_modules/pako': pkg('2.0.3', '(MIT AND Zlib)')}))
        exc = self.exceptions([{'name': 'pako', 'version': '2.0.3', 'license': 'Zlib', 'reason': 'wrong'}])
        code, _, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)

    def test_stale_exception_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', 'MIT')}))
        exc = self.exceptions([{'name': 'gone', 'version': '9.9.9', 'license': 'Unlicense', 'reason': 'old'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('stale exception', out)

    def test_prohibited_exception_license_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', 'MIT')}))
        for license_value in ('GPL-3.0-only', 'MIT OR GPLv3', 'LGPL-2.1-only', 'BUSL-1.1', 'UNKNOWN'):
            with self.subTest(license=license_value):
                exc = self.exceptions([{'name': 'a', 'version': '1.0.0', 'license': license_value, 'reason': 'x'}])
                code, out, err = self.run_checker([name], exc)
                self.assertEqual(code, 2, out)
                self.assertIn('cannot be excepted', err)
                self.assertNotIn('stale exception', out)

    def test_malformed_exception_license_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', 'MIT')}))
        exc = self.exceptions([{'name': 'a', 'version': '1.0.0', 'license': 'MIT OR', 'reason': 'x'}])
        code, _, err = self.run_checker([name], exc)
        self.assertEqual(code, 2)
        self.assertIn('not a well-formed SPDX expression', err)

    def test_duplicate_exception_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/z': pkg('1.0.0', 'Zlib')}))
        entry = {'name': 'z', 'version': '1.0.0', 'license': 'Zlib', 'reason': 'x'}
        exc = self.exceptions([entry, dict(entry)])
        code, _, err = self.run_checker([name], exc)
        self.assertEqual(code, 2)
        self.assertIn('duplicate exception', err)

    def test_non_string_scope_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', 'MIT')}))
        exc = self.write('exceptions.json', {'schema_version': 1, 'exceptions': [], 'scope': 5})
        code, _, err = self.run_checker([name], exc)
        self.assertEqual(code, 2)
        self.assertIn('scope must be a string', err)


class PolicyDocumentCases(unittest.TestCase):
    def sections(self):
        text = POLICY_DOC.read_text(encoding='utf-8')
        found = {}
        current = None
        for line in text.splitlines():
            if line.startswith('## '):
                current = line[3:].strip()
                found[current] = []
            elif current is not None and line.startswith('- '):
                found[current].extend(re.findall(r'`([^`]+)`', line))
        return found

    def test_policy_sets_match_checker(self):
        sections = self.sections()
        allowed = [t for k, v in sections.items() if k.startswith('Allowed SPDX') for t in v]
        review = [t for t in sections['Review-required'] if re.match(r'^[A-Za-z0-9.+\-]+$', t)]
        prohibited = [t for t in sections['Prohibited'] if not t.endswith('*')]
        prefixes = [t[:-1] for t in sections['Prohibited'] if t.endswith('*')]
        self.assertEqual(sorted(allowed), sorted(check.ALLOWED))
        self.assertEqual(sorted(review), sorted(check.REVIEW))
        self.assertEqual(sorted(prohibited), sorted(check.PROHIBITED_EXACT))
        self.assertEqual(sorted(prefixes), sorted(check.PROHIBITED_PREFIXES))

    def test_with_exception_list_matches_checker(self):
        text = POLICY_DOC.read_text(encoding='utf-8')
        for name in check.WITH_EXCEPTIONS:
            self.assertIn(f'`{name}`', text)

    def test_policy_states_the_integrity_rule_the_gate_enforces(self):
        text = POLICY_DOC.read_text(encoding='utf-8')
        self.assertIn('must carry an `integrity` value', text)
        self.assertIn('fails', text)


USES_LINE = re.compile(r'^\s*(?:-\s+)?uses:\s*(\S+)', re.MULTILINE)
FULL_SHA_REF = re.compile(r'[^@\s]+@[0-9a-f]{40}')
WORKFLOW_PATH_ITEM = re.compile(r"(?m)^\s+- '([^']+)'\s*$")


def uses_refs(text):
    return USES_LINE.findall(text)


def unpinned_refs(refs):
    return [ref for ref in refs if not FULL_SHA_REF.fullmatch(ref)]


class WorkflowCases(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding='utf-8')

    def test_triggers_cover_lockfiles_checker_exceptions_and_workflow(self):
        for needle in ('pull_request:', 'push:', 'branches: [main]', "'package-lock.json'", "'research-fixtures/canvas/package-lock.json'",
                       'scripts/verification/check_licenses.py',
                       'docs/evidence/license-exceptions.json',
                       '.github/workflows/license-policy.yml'):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)
        self.assertNotIn('pull_request_target', self.text)

    def test_permissions_are_read_only_and_no_secrets(self):
        self.assertRegex(self.text, r'(?m)^permissions:\n  contents: read\n')
        self.assertNotRegex(self.text, r'write')
        self.assertNotIn('secrets.', self.text)

    def test_checkout_is_pinned_without_persisted_credentials(self):
        self.assertIn('actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1', self.text)
        self.assertIn('persist-credentials: false', self.text)

    def test_every_uses_line_is_pinned_to_a_full_sha(self):
        refs = uses_refs(self.text)
        self.assertTrue(refs, 'no uses: lines were found to check')
        self.assertEqual(unpinned_refs(refs), [])

    def test_an_unpinned_uses_line_anywhere_in_the_workflow_is_detected(self):
        mutated = self.text + '\n      - uses: actions/setup-python@v5\n'
        self.assertEqual(unpinned_refs(uses_refs(mutated)), ['actions/setup-python@v5'])

    def test_path_filters_name_exactly_the_checker_default_lockfiles(self):
        lockfiles = {item for item in WORKFLOW_PATH_ITEM.findall(self.text) if item.endswith('package-lock.json')}
        self.assertEqual(lockfiles, set(check.DEFAULT_LOCKFILES))

    def test_runs_gate_on_ubuntu_with_timeout(self):
        self.assertIn('runs-on: ubuntu-latest', self.text)
        self.assertRegex(self.text, r'(?m)^\s+timeout-minutes: \d+')
        self.assertIn('run: python3 scripts/verification/check_licenses.py', self.text)


class RepositoryDataCases(unittest.TestCase):
    """Real-data regression check: the committed gate over both default lockfiles.

    Runs with default lockfile paths so a root-only exception is never reported stale.
    PASS here is not approval: the committed exceptions remain pending owner review.
    """

    def test_committed_lockfiles_pass_gate(self):
        proc = subprocess.run(
            [sys.executable, str(CHECKER), '--exceptions', str(REPO / 'docs' / 'evidence' / 'license-exceptions.json')],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        out, err = proc.stdout, proc.stderr
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertIn('lockfile: package-lock.json', out)
        self.assertIn('lockfile: research-fixtures/canvas/package-lock.json', out)
        self.assertIn('result: PASS (0 finding(s))', out)
        self.assertNotIn('missing or unknown license', out)
        self.assertIn('node_modules/fuzzy [fuzzy@0.1.3] verified override applied', out)
        self.assertIn('node_modules/khroma [khroma@2.1.0] verified override applied', out)
        self.assertIn('excepted review-required', out)  # pending owner review, not approval


OVERRIDE_LICENSE_CASES = ('GPL-3.0-only', 'GPLv3', 'LGPL-2.1-only', 'AGPLv3', 'SSPL', 'BUSL-1.1',
                          'UNKNOWN', 'NOASSERTION', 'UNLICENSED', 'MIT OR GPLv3')


def override_entry(name='a', version='1.0.0', integrity=INTEGRITY, license_value='MIT', **changes):
    entry = {
        'name': name, 'version': version, 'integrity': integrity, 'license': license_value,
        'evidence': {'kind': 'npm-tarball-file-sha256', 'source': 'https://registry.npmjs.org/x.tgz',
                     'file': 'package/LICENSE', 'sha256': 'a' * 64, 'verified_at': '2026-11-16'},
        'reason': 'test evidence',
    }
    entry.update(changes)
    return entry


class VerifiedOverrideCases(CheckerCase):
    def overrides_file(self, overrides, exceptions=(), name='exceptions.json'):
        return self.write(name, {'schema_version': 1, 'exceptions': list(exceptions),
                                 'verified_license_overrides': list(overrides)})

    def test_matching_override_clears_missing_license(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry()])
        code, out, err = self.run_checker([name], exc)
        self.assertEqual(code, 0, out + err)
        self.assertIn('verified override applied', out)
        self.assertIn('verified-overrides-applied=1', out)
        self.assertIn('result: PASS (0 finding(s))', out)

    def test_override_license_is_classified_under_policy_sets(self):
        name = self.write('package-lock.json', lockfile({'node_modules/z': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry('z', license_value='Zlib')])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('review-required license', out)
        excepted = self.overrides_file([override_entry('z', license_value='Zlib')],
                                       exceptions=[{'name': 'z', 'version': '1.0.0', 'license': 'Zlib', 'reason': 'owner pending'}],
                                       name='excepted.json')
        code, out, _ = self.run_checker([name], excepted)
        self.assertEqual(code, 0, out)
        self.assertIn('excepted review-required license', out)

    def test_missing_license_without_matching_override_still_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        other = self.overrides_file([override_entry('b', '1.0.0')])
        code, out, _ = self.run_checker([name], other)
        self.assertEqual(code, 1)
        self.assertIn('missing or unknown license', out)
        self.assertIn('verified override not applied', out)  # the override for b matches nothing

    def test_override_for_other_version_does_not_apply(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.1', None)}))
        exc = self.overrides_file([override_entry('a', '1.0.0')])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('missing or unknown license', out)

    def test_stale_override_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry('a', '1.0.0'), override_entry('gone', '9.9.9')])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('[gone@9.9.9] verified override not applied: matches no scanned package', out)

    def test_integrity_mismatch_fails(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry('a', '1.0.0', integrity=OTHER_INTEGRITY)])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('a verified override exists for this name and version but its integrity differs', out)
        self.assertIn('[a@1.0.0] verified override not applied: the lockfile integrity', out)
        self.assertIn('result: FAIL (2 finding(s))', out)

    def test_override_ignored_when_lockfile_declares_license(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', 'ISC')}))
        exc = self.overrides_file([override_entry('a', '1.0.0')])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)
        self.assertIn('lockfile already declares a license', out)

    def test_empty_license_string_is_never_overridden(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', '')}))
        exc = self.overrides_file([override_entry('a', '1.0.0')])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1, out)
        self.assertNotIn('verified override applied', out)
        self.assertIn('missing or unknown license', out)

    def test_null_license_is_overridden_only_with_matching_integrity(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry('a', '1.0.0', integrity=OTHER_INTEGRITY)])
        code, _, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1)

    def test_override_never_applies_to_prohibited_license(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        for license_value in OVERRIDE_LICENSE_CASES:
            with self.subTest(license=license_value):
                exc = self.overrides_file([override_entry('a', '1.0.0', license_value=license_value)])
                code, out, err = self.run_checker([name], exc)
                self.assertEqual(code, 2, out + err)
                self.assertIn('cannot be overridden', err)

    def test_malformed_override_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        bad_cases = {
            'extra field': override_entry(extra='x'),
            'missing reason': {k: v for k, v in override_entry().items() if k != 'reason'},
            'missing evidence field': override_entry(evidence={'kind': 'k', 'source': 's', 'file': 'f', 'sha256': 'a' * 64}),
            'short sha256': override_entry(evidence={'kind': 'k', 'source': 's', 'file': 'f', 'sha256': 'a' * 63, 'verified_at': '2026-11-16'}),
            'uppercase sha256': override_entry(evidence={'kind': 'k', 'source': 's', 'file': 'f', 'sha256': 'A' * 64, 'verified_at': '2026-11-16'}),
            'impossible date': override_entry(evidence={'kind': 'k', 'source': 's', 'file': 'f', 'sha256': 'a' * 64, 'verified_at': '2026-13-40'}),
            'compact date': override_entry(evidence={'kind': 'k', 'source': 's', 'file': 'f', 'sha256': 'a' * 64, 'verified_at': '20261116'}),
            'md5 integrity': override_entry(integrity='md5-' + 'A' * 22 + '=='),
            'malformed license': override_entry(license_value='MIT OR'),
            'blank name': override_entry(name='  '),
        }
        for label, entry in bad_cases.items():
            with self.subTest(case=label):
                exc = self.overrides_file([entry])
                code, _, err = self.run_checker([name], exc)
                self.assertEqual(code, 2, err)
                self.assertIn('verified_license_overrides', err)

    def test_duplicate_override_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.overrides_file([override_entry('a', '1.0.0'), override_entry('a', '1.0.0')])
        code, _, err = self.run_checker([name], exc)
        self.assertEqual(code, 2)
        self.assertIn('duplicate', err)

    def test_overrides_must_be_a_list(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        exc = self.write('exceptions.json', {'schema_version': 1, 'exceptions': [], 'verified_license_overrides': {}})
        code, _, err = self.run_checker([name], exc)
        self.assertEqual(code, 2)
        self.assertIn('must be a list', err)


if __name__ == '__main__':
    unittest.main()
