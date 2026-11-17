#!/usr/bin/env python3
"""Offline license gate for npm package-lock.json files (GB-T0.02.02.T1, #16).

Reads the lockfile(s) and the exceptions file only. It makes no network calls,
does not read installed license texts or tarballs, and does not establish legal
clearance. A verified license override (exceptions file, key
verified_license_overrides) supplies a license only for a lockfile entry that has
no license field and whose name, exact version and integrity all match. It records
evidence, not legal sign-off.
Policy: docs/license-supply-chain-policy.md. Run from the repository root.

Input handling: a missing exceptions file is not an error. It is read as no
exceptions and no verified overrides, which only makes the gate stricter; the run
says so on its `exceptions:` summary line, which reads `file absent, so no exceptions or verified overrides apply`. A missing, unreadable, larger-than-16-MiB, malformed or
deeply nested lockfile or exceptions file is an input error.

Exit status: 0 pass; 1 policy findings (prohibited, missing or unknown license,
malformed license expression, review-required package without an exception,
third-party package without integrity, unexpected install path, stale exception,
verified override not applied); 2 input error (missing, unreadable, oversized,
malformed or deeply nested lockfile or exceptions file, unsupported
lockfileVersion, malformed verified override, an override or exception naming a
prohibited license, or an exception whose license is not a well-formed SPDX
expression).
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys

DEFAULT_LOCKFILES = ('package-lock.json', 'research-fixtures/canvas/package-lock.json')
DEFAULT_EXCEPTIONS = 'docs/evidence/license-exceptions.json'
SUPPORTED_LOCKFILE_VERSIONS = (2, 3)
MAX_INPUT_BYTES = 16 * 1024 * 1024

ALLOWED = ('0BSD', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'BlueOak-1.0.0', 'CC0-1.0', 'ISC', 'MIT')
REVIEW = ('MPL-2.0', 'Python-2.0', 'Unlicense', 'Zlib')
PROHIBITED_EXACT = ('NOASSERTION', 'UNKNOWN', 'UNLICENSED')
PROHIBITED_PREFIXES = ('AGPL', 'BUSL', 'CC-BY-NC', 'GPL', 'LGPL', 'SSPL')
WITH_EXCEPTIONS = ('Classpath-exception-2.0', 'GCC-exception-3.1', 'LLVM-exception')

OK, REVIEW_RANK, PROHIBITED_RANK = 0, 1, 2
RANK_LABEL = {OK: 'allowed', REVIEW_RANK: 'review-required', PROHIBITED_RANK: 'prohibited'}

_ALLOWED_U = {x.upper() for x in ALLOWED}
_REVIEW_U = {x.upper() for x in REVIEW}
_PROHIBITED_U = {x.upper() for x in PROHIBITED_EXACT}
_PREFIXES_U = tuple(x.upper() for x in PROHIBITED_PREFIXES)
_WITH_EXCEPTIONS_L = {x.lower() for x in WITH_EXCEPTIONS}

_TOKEN = re.compile(r'\(|\)|[^\s()]+')
_IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+\-]*$')
_OPERATORS = ('AND', 'OR', 'WITH')
_EXCEPTION_KEYS = {'name', 'version', 'license', 'reason'}
OVERRIDES_KEY = 'verified_license_overrides'
_OVERRIDE_KEYS = {'name', 'version', 'integrity', 'license', 'evidence', 'reason'}
_EVIDENCE_KEYS = {'kind', 'source', 'file', 'sha256', 'verified_at'}
_SRI_TOKEN = re.compile(r'(sha512|sha384|sha256)-(\S+)')
_SRI_DECODED_BYTES = {'sha512': 64, 'sha384': 48, 'sha256': 32}
_SHA256_HEX = re.compile(r'[0-9a-f]{64}')
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
# Install paths: node_modules/<name> with optional nested node_modules/<name> segments.
_INSTALL_KEY = re.compile(r'node_modules/(?:@[^/]+/)?[^/]+(?:/node_modules/(?:@[^/]+/)?[^/]+)*')
_PACKAGE_NAME = re.compile(r'(?:@[^/\s]+/)?[^/\s]+')
_WORKSPACE_GLOB = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)/\*')
_WORKSPACE_SEGMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
_WORKSPACE_UNSAFE = ('node_modules', '..')


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
    """Validate an SPDX expression; return [(identifier or None, carries_WITH)]."""
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
        ident, parenthesized = parse_atom()
        if is_op(peek(), 'WITH'):
            if parenthesized:
                raise SpdxError('WITH applies to a license identifier, not to a parenthesized expression')
            take()
            exception = take()
            if exception.lower() not in _WITH_EXCEPTIONS_L:
                raise SpdxError('WITH exception is not one of the allowed SPDX exceptions')
            terms.append((ident, True))
        else:
            terms.append((ident, False))

    def parse_atom():
        token = take()
        if token == '(':
            parse_or()
            if take() != ')':
                raise SpdxError('unbalanced parentheses')
            return None, True
        if token == ')' or token.upper() in _OPERATORS or not _IDENT.match(token):
            raise SpdxError('invalid license identifier')
        return token, False

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
            raw = handle.read(MAX_INPUT_BYTES + 1)
    except FileNotFoundError:
        raise InputError(f'missing file: {path}')
    except OSError as exc:
        raise InputError(f'cannot read {path}: {exc.strerror}')
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError(f'input too large (over {MAX_INPUT_BYTES} bytes): {path}')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_reject_constant)
    except RecursionError:
        raise InputError(f'malformed JSON in {path}: nested too deeply')
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
        rank = classify_expression(values['license'])
        if rank is None:
            raise InputError(f'exception #{index} in {path}: license is not a well-formed SPDX expression')
        if rank == PROHIBITED_RANK:
            raise InputError(f'exception #{index} in {path}: prohibited license {values["license"]!r} cannot be excepted')
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
        if not valid_integrity(values['integrity']):
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


def _sri_token_ok(token):
    match = _SRI_TOKEN.fullmatch(token)
    if not match:
        return False
    algorithm, digest = match.groups()
    try:
        raw = base64.b64decode(digest, validate=True)
    except ValueError:
        return False
    return len(raw) == _SRI_DECODED_BYTES[algorithm]


def valid_integrity(value):
    """True when value is one or more whitespace-separated sha512-, sha384- or sha256- SRI tokens
    whose base64 decodes to that algorithm's digest length."""
    if not isinstance(value, str):
        return False
    tokens = value.split()
    return bool(tokens) and all(_sri_token_ok(token) for token in tokens)


def nested_install_name(key, dirs):
    """Package name for a workspace-local install `<dir>/<name>/node_modules/...`, or None.

    The prefix must be a declared workspace dir followed by one plain segment; the rest of
    the path is judged by install_name exactly like a root-level install path.
    """
    parts = key.split('/')
    if (len(parts) < 4 or parts[0] not in dirs or parts[2] != 'node_modules'
            or parts[1] == 'node_modules' or not _WORKSPACE_SEGMENT.fullmatch(parts[1])):
        return None
    return install_name('/'.join(parts[2:]))


def install_name(key):
    """Package name for an exact node_modules install path, or None for any other path."""
    if '\\' in key or not _INSTALL_KEY.fullmatch(key):
        return None
    if any(part in ('', '.', '..') for part in key.split('/')):
        return None
    name = key.rsplit('node_modules/', 1)[1]
    return name if _PACKAGE_NAME.fullmatch(name) else None


def workspace_dirs(root_entry):
    """Directories named by the root entry's workspaces globs (exactly `dir/*`).

    A pattern that could reach node_modules, climb out of the tree, be absolute, use a
    backslash or match everything is an input error, not an ignored pattern.
    """
    patterns = root_entry.get('workspaces', [])
    if not isinstance(patterns, list):
        return set()
    dirs = set()
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        if (any(bad in pattern for bad in _WORKSPACE_UNSAFE) or '\\' in pattern
                or pattern.startswith(('/', '*')) or not pattern.strip('*')):
            raise InputError(f'unsafe workspaces pattern {pattern!r} in the root entry: node_modules, '
                             'parent segments, absolute paths, backslashes and wildcard-only patterns are not allowed')
        match = _WORKSPACE_GLOB.fullmatch(pattern)
        if match:
            dirs.add(match.group(1))
    return dirs


def is_workspace_path(key, dirs):
    head, _, segment = key.rpartition('/')
    return head in dirs and bool(_WORKSPACE_SEGMENT.fullmatch(segment))


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
                       'missing-integrity': 0, 'malformed-integrity': 0, 'unexpected-path': 0}
        self.lines = []
        self.failures = 0

    def add(self, severity, key, label, category, detail):
        if severity == 'FAIL':
            self.failures += 1
        self.lines.append(f'  {severity} {self.path} {key} [{label}] {category}: {detail}')

    def unexpected(self, key, detail):
        self.counts['unexpected-path'] += 1
        self.add('FAIL', key, '?', 'unexpected install path', detail)


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
    root_entry = packages.get('') if isinstance(packages.get(''), dict) else {}
    dirs = workspace_dirs(root_entry)

    report = LockfileReport(path, version)
    for key in sorted(packages):
        entry = packages[key]
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise InputError(f'malformed lockfile entry in {path}')
        report.entries += 1
        if key == '':
            report.skipped += 1
            continue
        if entry.get('link') is True:
            target = entry.get('resolved')
            if (install_name(key) is not None and isinstance(target, str)
                    and is_workspace_path(target, dirs) and target in packages):
                report.skipped += 1
            else:
                report.unexpected(key, 'link must sit at a node_modules path and point at a workspace that is present in this lockfile')
            continue
        if is_workspace_path(key, dirs):
            if 'resolved' in entry or 'integrity' in entry:
                report.unexpected(key, 'workspace entry must not carry resolved or integrity')
            else:
                report.skipped += 1
            continue
        path_name = install_name(key)
        if path_name is None:
            path_name = nested_install_name(key, dirs)
        if path_name is None:
            report.unexpected(key, 'entry is not an exact node_modules install path and is not a known workspace')
            continue
        version_text = entry.get('version')
        if not isinstance(version_text, str) or not version_text:
            raise InputError(f'malformed lockfile entry in {path}: {key} lacks a version')
        # npm aliases record the real package name in `name`; classify by that name.
        name = entry.get('name', path_name)
        if not isinstance(name, str) or not _PACKAGE_NAME.fullmatch(name):
            raise InputError(f'malformed lockfile entry in {path}: {key} has an invalid name')
        report.third_party += 1
        label = f'{name}@{version_text}'
        integrity = entry.get('integrity')
        has_integrity = isinstance(integrity, str) and integrity != ''
        if not has_integrity:
            report.no_integrity += 1
            report.counts['missing-integrity'] += 1
            report.add('FAIL', key, label, 'missing integrity',
                       'third-party package has no integrity value; every registry package must pin one')
        elif not valid_integrity(integrity):
            report.counts['malformed-integrity'] += 1
            report.add('FAIL', key, label, 'malformed integrity',
                       'integrity must be sha512-, sha384- or sha256- SRI tokens whose base64 decodes to the digest length')
        declared = _has_license(entry)
        index.record(name, version_text, integrity if has_integrity else None, declared)
        if declared:
            rank, text, detail = license_status(entry)
        else:
            override, candidates = index.match(name, version_text, integrity if has_integrity else None)
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
        exceptions_absent = not os.path.exists(args.exceptions)
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
    absent_note = '; file absent, so no exceptions or verified overrides apply' if exceptions_absent else ''
    print(f'exceptions: {args.exceptions} ({len(exceptions)} entries{absent_note})')
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
