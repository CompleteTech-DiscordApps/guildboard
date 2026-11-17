#!/usr/bin/env python3
"""Offline license gate for npm package-lock.json files (GB-T0.02.02.T1, #16).

Reads the lockfile(s) and the exceptions file only. It makes no network calls,
does not read installed license texts or tarballs, and does not establish legal
clearance. A verified license override (exceptions file, key
verified_license_overrides) supplies a license only for a lockfile entry that has
no license field and whose name, exact version and integrity all match. It records
evidence, not legal sign-off.
Policy: docs/license-supply-chain-policy.md. Run from the repository root.

Exit status: 0 pass; 1 policy findings (prohibited, missing or unknown license,
malformed license expression, unexcepted review-required package, unexpected
install path, stale exception, verified override not applied); 2 input error
(missing, unreadable or malformed lockfile or exceptions file, unsupported
lockfileVersion, malformed verified override, or an override naming a prohibited
license).
"""

import argparse
import datetime
import json
import re
import sys

DEFAULT_LOCKFILES = ('package-lock.json', 'research-fixtures/canvas/package-lock.json')
DEFAULT_EXCEPTIONS = 'docs/evidence/license-exceptions.json'
SUPPORTED_LOCKFILE_VERSIONS = (2, 3)

ALLOWED = ('0BSD', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'BlueOak-1.0.0', 'CC0-1.0', 'ISC', 'MIT')
REVIEW = ('LGPL-2.0-only', 'LGPL-2.0-or-later', 'LGPL-2.1-only', 'LGPL-2.1-or-later',
          'LGPL-3.0-only', 'LGPL-3.0-or-later', 'MPL-2.0', 'Python-2.0', 'Unlicense', 'Zlib')
PROHIBITED_EXACT = ('BUSL-1.1', 'NOASSERTION', 'UNKNOWN', 'UNLICENSED')
PROHIBITED_PREFIXES = ('AGPL-', 'CC-BY-NC', 'GPL-', 'SSPL-')

OK, REVIEW_RANK, PROHIBITED_RANK = 0, 1, 2
RANK_LABEL = {OK: 'allowed', REVIEW_RANK: 'review-required', PROHIBITED_RANK: 'prohibited'}

_ALLOWED_U = {x.upper() for x in ALLOWED}
_REVIEW_U = {x.upper() for x in REVIEW}
_PROHIBITED_U = {x.upper() for x in PROHIBITED_EXACT}
_PREFIXES_U = tuple(x.upper() for x in PROHIBITED_PREFIXES)

_TOKEN = re.compile(r'\(|\)|[^\s()]+')
_IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+\-]*$')
_OPERATORS = ('AND', 'OR', 'WITH')
_EXCEPTION_KEYS = {'name', 'version', 'license', 'reason'}
OVERRIDES_KEY = 'verified_license_overrides'
_OVERRIDE_KEYS = {'name', 'version', 'integrity', 'license', 'evidence', 'reason'}
_EVIDENCE_KEYS = {'kind', 'source', 'file', 'sha256', 'verified_at'}
_INTEGRITY = re.compile(r'(sha512|sha384|sha256)-[A-Za-z0-9+/]+={0,2}')
_SHA256_HEX = re.compile(r'[0-9a-f]{64}')
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


class InputError(Exception):
    """Unreadable, missing or malformed input; the run cannot be trusted."""


class SpdxError(ValueError):
    """License expression is not a well-formed SPDX expression."""


def classify_identifier(ident):
    upper = ident.upper()
    if upper in _ALLOWED_U:
        return OK
    if upper in _REVIEW_U:
        return REVIEW_RANK
    if upper in _PROHIBITED_U or upper.startswith(_PREFIXES_U):
        return PROHIBITED_RANK
    # Conservative default: any identifier not known to the policy needs review.
    return REVIEW_RANK


def parse_expression(text):
    """Validate an SPDX expression; return [(identifier, carries_WITH)]."""
    tokens = _TOKEN.findall(text)
    if not tokens:
        raise SpdxError('empty expression')
    terms = []
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        token = peek()
        if token is None:
            raise SpdxError('unexpected end of expression')
        pos += 1
        return token

    def is_op(token, op):
        return token is not None and token.upper() == op

    def parse_or():
        parse_and()
        while is_op(peek(), 'OR'):
            take()
            parse_and()

    def parse_and():
        parse_with()
        while is_op(peek(), 'AND'):
            take()
            parse_with()

    def parse_with():
        base = parse_atom()
        if is_op(peek(), 'WITH'):
            take()
            exception = take()
            if exception in ('(', ')') or exception.upper() in _OPERATORS or not _IDENT.match(exception):
                raise SpdxError('invalid WITH exception')
            base = (base, True)
        else:
            base = (base, False)
        terms.append(base)

    def parse_atom():
        token = take()
        if token == '(':
            parse_or()
            if take() != ')':
                raise SpdxError('unbalanced parentheses')
            return None
        if token == ')' or token.upper() in _OPERATORS or not _IDENT.match(token):
            raise SpdxError('invalid license identifier')
        return token

    parse_or()
    if pos != len(tokens):
        raise SpdxError('trailing tokens in expression')
    return terms


def classify_expression(text):
    """Most restrictive rank over every term; OR/AND never select a branch."""
    try:
        terms = parse_expression(text)
    except (SpdxError, RecursionError):
        return None
    rank = OK
    for ident, with_exception in terms:
        term_rank = classify_identifier(ident) if ident is not None else OK
        if with_exception:
            term_rank = max(term_rank, REVIEW_RANK)
        rank = max(rank, term_rank)
    return rank


def _reject_constant(token):
    raise ValueError(f'non-finite JSON constant {token}')


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key!r}')
        result[key] = value
    return result


def read_json(path):
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
    except FileNotFoundError:
        raise InputError(f'missing file: {path}')
    except OSError as exc:
        raise InputError(f'cannot read {path}: {exc.strerror}')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f'malformed JSON in {path}: {exc}')


def load_exceptions(path):
    """Return {(name, version, license): reason}; a missing file means none."""
    try:
        data = read_json(path)
    except InputError as exc:
        if str(exc).startswith('missing file:'):
            return {}
        raise
    if not isinstance(data, dict) or not {'schema_version', 'exceptions'} <= set(data) <= {'schema_version', 'exceptions', 'scope', OVERRIDES_KEY}:
        raise InputError(f'malformed exceptions file: {path}')
    if 'scope' in data and not isinstance(data['scope'], str):
        raise InputError(f'exceptions scope must be a string: {path}')
    if data['schema_version'] != 1 or not isinstance(data['exceptions'], list):
        raise InputError(f'unsupported exceptions schema: {path}')
    table = {}
    for index, item in enumerate(data['exceptions']):
        if not isinstance(item, dict) or set(item) != _EXCEPTION_KEYS:
            raise InputError(f'exception #{index} in {path} must have exactly {sorted(_EXCEPTION_KEYS)}')
        values = {}
        for field in sorted(_EXCEPTION_KEYS):
            value = item[field]
            if not isinstance(value, str) or not value.strip():
                raise InputError(f'exception #{index} in {path}: {field} must be a non-empty string')
            values[field] = value.strip()
        key = (values['name'], values['version'], values['license'])
        if key in table:
            raise InputError(f'duplicate exception #{index} in {path}')
        table[key] = values['reason']
    return table


def _string_field(value, where, field):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f'{where}: {field} must be a non-empty string')
    return value.strip()


def load_overrides(path):
    """Return verified overrides as dicts; a missing file or absent key means none."""
    try:
        data = read_json(path)
    except InputError as exc:
        if str(exc).startswith('missing file:'):
            return []
        raise
    if not isinstance(data, dict):
        raise InputError(f'malformed exceptions file: {path}')
    raw = data.get(OVERRIDES_KEY, [])
    if not isinstance(raw, list):
        raise InputError(f'{OVERRIDES_KEY} must be a list: {path}')
    overrides = []
    keys = set()
    for position, item in enumerate(raw):
        where = f'{OVERRIDES_KEY} #{position} in {path}'
        if not isinstance(item, dict) or set(item) != _OVERRIDE_KEYS:
            raise InputError(f'{where} must have exactly {sorted(_OVERRIDE_KEYS)}')
        values = {field: _string_field(item[field], where, field)
                  for field in ('name', 'version', 'integrity', 'license', 'reason')}
        evidence_raw = item['evidence']
        if not isinstance(evidence_raw, dict) or set(evidence_raw) != _EVIDENCE_KEYS:
            raise InputError(f'{where}: evidence must have exactly {sorted(_EVIDENCE_KEYS)}')
        evidence = {field: _string_field(evidence_raw[field], where, f'evidence.{field}')
                    for field in sorted(_EVIDENCE_KEYS)}
        if not _INTEGRITY.fullmatch(values['integrity']):
            raise InputError(f'{where}: integrity must be an sha512-, sha384- or sha256- SRI value')
        if not _SHA256_HEX.fullmatch(evidence['sha256']):
            raise InputError(f'{where}: evidence.sha256 must be 64 lowercase hex digits')
        if not _ISO_DATE.fullmatch(evidence['verified_at']):
            raise InputError(f'{where}: evidence.verified_at must be YYYY-MM-DD')
        try:
            datetime.date.fromisoformat(evidence['verified_at'])
        except ValueError:
            raise InputError(f'{where}: evidence.verified_at is not a valid date')
        rank = classify_expression(values['license'])
        if rank is None:
            raise InputError(f'{where}: license is not a well-formed SPDX expression')
        if rank == PROHIBITED_RANK:
            raise InputError(f'{where}: prohibited license {values["license"]!r} cannot be overridden')
        key = (values['name'], values['version'], values['integrity'])
        if key in keys:
            raise InputError(f'duplicate {OVERRIDES_KEY} #{position} in {path}')
        keys.add(key)
        overrides.append({'name': values['name'], 'version': values['version'],
                          'integrity': values['integrity'], 'license': values['license'],
                          'evidence': evidence, 'key': key})
    return overrides


def _has_license(entry):
    return 'license' in entry and entry['license'] is not None


def license_status(entry):
    """Return (rank or None, text, detail) for one package entry."""
    if 'license' not in entry or entry['license'] is None:
        return None, '', 'no license field'
    value = entry['license']
    if not isinstance(value, str):
        return 'malformed', repr(type(value).__name__), 'license field is not a string'
    text = value.strip()
    if not text:
        return None, '', 'empty license field'
    rank = classify_expression(text)
    if rank is None:
        return 'malformed', text, 'not a well-formed SPDX expression'
    return rank, text, RANK_LABEL[rank]


class OverrideIndex:
    """Matches verified overrides to lockfile entries that carry no license field."""

    def __init__(self, overrides):
        self.overrides = overrides
        self.by_name_version = {}
        for item in overrides:
            self.by_name_version.setdefault((item['name'], item['version']), []).append(item)
        self.applied = set()
        self.seen = {}

    def record(self, name, version, integrity, declared):
        self.seen.setdefault((name, version), []).append((integrity, declared))

    def match(self, name, version, integrity):
        candidates = self.by_name_version.get((name, version), [])
        for item in candidates:
            if integrity and item['integrity'] == integrity:
                return item, candidates
        return None, candidates

    def stale_details(self):
        found = []
        for item in self.overrides:
            if item['key'] in self.applied:
                continue
            observed = self.seen.get((item['name'], item['version']), [])
            if any(value == item['integrity'] and declared for value, declared in observed):
                detail = 'the lockfile already declares a license for this exact integrity, so the override is not used'
            elif observed:
                detail = 'the lockfile integrity for this name and version differs from the override'
            else:
                detail = 'matches no scanned package that lacks a license field'
            found.append((item, detail))
        return found


class LockfileReport:
    def __init__(self, path, version):
        self.path = path
        self.version = version
        self.entries = 0
        self.skipped = 0
        self.third_party = 0
        self.no_integrity = 0
        self.overridden = 0
        self.counts = {'allowed': 0, 'excepted': 0, 'review-required': 0,
                       'prohibited': 0, 'missing-license': 0, 'malformed-license': 0,
                       'unexpected-path': 0}
        self.lines = []
        self.failures = 0

    def add(self, severity, key, label, category, detail):
        if severity == 'FAIL':
            self.failures += 1
        self.lines.append(f'  {severity} {self.path} {key} [{label}] {category}: {detail}')


def scan_lockfile(path, exceptions, used, index):
    data = read_json(path)
    if not isinstance(data, dict):
        raise InputError(f'malformed lockfile (top level is not an object): {path}')
    version = data.get('lockfileVersion')
    if isinstance(version, bool) or version not in SUPPORTED_LOCKFILE_VERSIONS:
        raise InputError(f'unsupported lockfileVersion in {path}: {version!r} (need 2 or 3 with packages map)')
    packages = data.get('packages')
    if not isinstance(packages, dict) or not packages:
        raise InputError(f'malformed lockfile (missing packages map): {path}')

    report = LockfileReport(path, version)
    for key in sorted(packages):
        entry = packages[key]
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise InputError(f'malformed lockfile entry in {path}')
        report.entries += 1
        if key == '' or entry.get('link') is True:
            report.skipped += 1
            continue
        if 'node_modules/' not in key:
            if key.startswith(('apps/', 'packages/')) and 'resolved' not in entry and 'integrity' not in entry:
                report.skipped += 1
                continue
            report.counts['unexpected-path'] += 1
            report.add('FAIL', key, '?', 'unexpected install path', 'entry is outside node_modules and is not a workspace')
            continue
        name = key.rsplit('node_modules/', 1)[1]
        version_text = entry.get('version')
        if not name or not isinstance(version_text, str) or not version_text:
            raise InputError(f'malformed lockfile entry in {path}: {key} lacks a name or version')
        report.third_party += 1
        label = f'{name}@{version_text}'
        integrity = entry.get('integrity')
        if not integrity:
            report.no_integrity += 1
        declared = _has_license(entry)
        index.record(name, version_text, integrity, declared)
        if declared:
            rank, text, detail = license_status(entry)
        else:
            override, candidates = index.match(name, version_text, integrity)
            if override is None:
                report.counts['missing-license'] += 1
                detail = 'no license field'
                if candidates:
                    detail += ('; a verified override exists for this name and version '
                               'but its integrity differs from the lockfile')
                report.add('FAIL', key, label, 'missing or unknown license', detail)
                continue
            index.applied.add(override['key'])
            report.overridden += 1
            evidence = override['evidence']
            rank, text, detail = classify_expression(override['license']), override['license'], 'verified override'
            report.lines.append(f'  NOTE {path} {key} [{label}] verified override applied: license {text!r} '
                                f'({evidence["kind"]}, {evidence["file"]}, sha256 {evidence["sha256"]}, '
                                f'verified_at {evidence["verified_at"]}); evidence only, not legal sign-off')
        if rank == OK:
            report.counts['allowed'] += 1
        elif rank == REVIEW_RANK:
            exception_key = (name, version_text, text)
            if exception_key in exceptions:
                used.add(exception_key)
                report.counts['excepted'] += 1
                report.lines.append(f'  NOTE {path} {key} [{label}] excepted review-required '
                                    f'license {text!r}: {exceptions[exception_key]}')
            else:
                report.counts['review-required'] += 1
                report.add('FAIL', key, label, 'review-required license',
                           f'{text!r} is not allowed without an exception for this exact version')
        elif rank == PROHIBITED_RANK:
            report.counts['prohibited'] += 1
            report.add('FAIL', key, label, 'prohibited license', repr(text))
        elif rank == 'malformed':
            report.counts['malformed-license'] += 1
            report.add('FAIL', key, label, 'malformed license', f'{text!r}: {detail}')
        else:
            report.counts['missing-license'] += 1
            report.add('FAIL', key, label, 'missing or unknown license', detail)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline license gate for package-lock.json files (GB-T0.02.02.T1).')
    parser.add_argument('--exceptions', default=DEFAULT_EXCEPTIONS,
                        help='version-pinned exceptions file (default: %(default)s)')
    parser.add_argument('lockfiles', nargs='*',
                        help='lockfiles to check (default: %s)' % ' '.join(DEFAULT_LOCKFILES))
    args = parser.parse_args(argv)
    lockfiles = args.lockfiles or list(DEFAULT_LOCKFILES)

    try:
        exceptions = load_exceptions(args.exceptions)
        overrides = load_overrides(args.exceptions)
        used = set()
        index = OverrideIndex(overrides)
        reports = [scan_lockfile(path, exceptions, used, index) for path in lockfiles]
    except InputError as exc:
        print(f'input error: {exc}', file=sys.stderr)
        return 2

    failures = sum(report.failures for report in reports)
    print('license policy check: GB-T0.02.02.T1 (docs/license-supply-chain-policy.md)')
    print(f'policy sets: allowed={len(ALLOWED)} review-listed={len(REVIEW)} '
          f'prohibited-exact={len(PROHIBITED_EXACT)} prohibited-prefixes={len(PROHIBITED_PREFIXES)}')
    print(f'exceptions: {args.exceptions} ({len(exceptions)} entries)')
    print(f'verified overrides: {args.exceptions} ({len(overrides)} entries, {len(index.applied)} applied)')
    for report in reports:
        print(f'lockfile: {report.path} (lockfileVersion {report.version})')
        print(f'  entries={report.entries} skipped-first-party={report.skipped} third-party={report.third_party}')
        print('  ' + ' '.join(f'{name}={count}' for name, count in report.counts.items()))
        print(f'  third-party-without-integrity={report.no_integrity} verified-overrides-applied={report.overridden}')
    stale = sorted(set(exceptions) - used)
    print('details:')
    for report in reports:
        for line in report.lines:
            print(line)
    for name, version_text, text in stale:
        failures += 1
        print(f'  FAIL {args.exceptions} [{name}@{version_text}] stale exception: '
              f'license {text!r} matches no scanned package version')
    for item, detail in index.stale_details():
        failures += 1
        print(f'  FAIL {args.exceptions} [{item["name"]}@{item["version"]}] verified override not applied: {detail}')
    print(f'result: {"FAIL" if failures else "PASS"} ({failures} finding(s))')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
