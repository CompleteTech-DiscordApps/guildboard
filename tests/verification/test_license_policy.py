"""Offline tests for scripts/verification/check_licenses.py (GB-T0.02.02.T1, #16)."""

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

_spec = importlib.util.spec_from_file_location('check_licenses', CHECKER)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

INTEGRITY = 'sha512-' + 'A' * 86 + '=='


def pkg(version='1.0.0', license_value='MIT', **extra):
    entry = {'version': version, 'resolved': 'https://registry.npmjs.org/x.tgz', 'integrity': INTEGRITY}
    if license_value is not None:
        entry['license'] = license_value
    entry.update(extra)
    return entry


def lockfile(packages, version=3):
    base = {'': {'name': 'fixture', 'version': '0.0.0', 'devDependencies': {}},
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

    def test_prohibited_license_fails_even_with_exception(self):
        name = self.write('package-lock.json', lockfile({'node_modules/g': pkg('3.0.0', 'GPL-3.0-only')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('prohibited license', out)
        exc = self.exceptions([{'name': 'g', 'version': '3.0.0', 'license': 'GPL-3.0-only', 'reason': 'x'}])
        code, out, _ = self.run_checker([name], exc)
        self.assertEqual(code, 1, 'prohibited licenses must not be excepted')

    def test_unknown_literal_is_prohibited(self):
        name = self.write('package-lock.json', lockfile({'node_modules/u': pkg('1.0.0', 'UNKNOWN')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('prohibited license', out)

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

    def test_unexpected_install_path_fails(self):
        name = self.write('package-lock.json', lockfile({'vendor/x': pkg('1.0.0', 'MIT')}))
        code, out, _ = self.run_checker([name])
        self.assertEqual(code, 1)
        self.assertIn('unexpected install path', out)

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

    def test_missing_file_is_input_error(self):
        code, _, err = self.run_checker(['no-such-lockfile.json'])
        self.assertEqual(code, 2)
        self.assertIn('missing file', err)

    def test_unsupported_lockfile_version_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg()}, version=1))
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('unsupported lockfileVersion', err)

    def test_entry_without_version_is_input_error(self):
        broken = lockfile({'node_modules/a': {'license': 'MIT'}})
        name = self.write('package-lock.json', broken)
        code, _, err = self.run_checker([name])
        self.assertEqual(code, 2)
        self.assertIn('lacks a name or version', err)

    def test_malformed_exceptions_file_is_input_error(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg()}))
        bad = self.write('bad.json', {'schema_version': 1, 'exceptions': [{'name': 'a', 'version': '1.0.0', 'license': 'MIT'}]})
        code, _, err = self.run_checker([name], bad)
        self.assertEqual(code, 2)
        self.assertIn('must have exactly', err)


class SpdxExpressionCases(unittest.TestCase):
    def rank(self, text):
        return check.classify_expression(text)

    def test_single_identifiers(self):
        self.assertEqual(self.rank('MIT'), check.OK)
        self.assertEqual(self.rank('Zlib'), check.REVIEW_RANK)
        self.assertEqual(self.rank('GPL-2.0-or-later'), check.PROHIBITED_RANK)

    def test_or_takes_most_restrictive_branch(self):
        self.assertEqual(self.rank('MIT OR Apache-2.0'), check.OK)
        self.assertEqual(self.rank('(MPL-2.0 OR Apache-2.0)'), check.REVIEW_RANK)
        self.assertEqual(self.rank('MIT OR GPL-2.0-only'), check.PROHIBITED_RANK)

    def test_and_takes_most_restrictive_term(self):
        self.assertEqual(self.rank('(MIT OR Apache-2.0) AND ISC'), check.OK)
        self.assertEqual(self.rank('(MIT AND Zlib)'), check.REVIEW_RANK)
        self.assertEqual(self.rank('MIT AND GPL-3.0-or-later'), check.PROHIBITED_RANK)

    def test_with_exception_is_at_least_review(self):
        self.assertEqual(self.rank('MIT WITH LLVM-exception'), check.REVIEW_RANK)
        self.assertEqual(self.rank('GPL-2.0-only WITH Classpath-exception-2.0'), check.PROHIBITED_RANK)

    def test_identifier_matching_is_case_insensitive(self):
        self.assertEqual(self.rank('mit and isc'), check.OK)
        self.assertEqual(self.rank('lgpl-2.1-only'), check.REVIEW_RANK)

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


OTHER_INTEGRITY = 'sha512-' + 'B' * 86 + '=='
REAL_EXCEPTIONS = REPO / 'docs' / 'evidence' / 'license-exceptions.json'
REAL_CANVAS_LOCK = REPO / 'research-fixtures' / 'canvas' / 'package-lock.json'


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

    def test_override_never_applies_to_prohibited_license(self):
        name = self.write('package-lock.json', lockfile({'node_modules/a': pkg('1.0.0', None)}))
        for license_value in ('GPL-3.0-only', 'UNKNOWN', 'MIT OR GPL-2.0-only', 'AGPL-3.0-or-later'):
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

    def test_committed_overrides_clear_canvas_findings(self):
        code, out, err = self.run_checker_real()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('missing or unknown license', out)
        self.assertIn('node_modules/fuzzy [fuzzy@0.1.3] verified override applied', out)
        self.assertIn('node_modules/khroma [khroma@2.1.0] verified override applied', out)
        self.assertIn('excepted review-required', out)  # pending owner review, not approval

    def run_checker_real(self):
        proc = subprocess.run(
            [sys.executable, str(CHECKER), '--exceptions', str(REAL_EXCEPTIONS), str(REAL_CANVAS_LOCK)],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr


if __name__ == '__main__':
    unittest.main()
