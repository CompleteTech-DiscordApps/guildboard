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


if __name__ == '__main__':
    unittest.main()
