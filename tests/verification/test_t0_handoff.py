"""Offline checks for the '## T0 integration and handoff' section of docs/workstreams/T0.md.

Stdlib only, repository-root relative, no network. Run from the repository root:
    python3 -I -B -m unittest discover -s tests/verification -v
"""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
T0_PATH = ROOT / 'docs' / 'workstreams' / 'T0.md'
SECTION_HEADING = '## T0 integration and handoff'
REQUIRED_SUBSECTIONS = ('Accepted contracts', 'Operator and contributor steps', 'Evidence', 'Status')
CLASSES = ('SUPPORTED', 'PLANNED', 'UNRESOLVED')
ALLOWED_HANDLE = 'CompleteDotTech'
FORBIDDEN_PATTERNS = (r'accepted\s+by', r'approved\s+by', r'production[\s-]+ready', r'fully\s+verified')
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
HANDLE_RE = re.compile(r'(?<![\w.])@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)')
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')
CODE_RE = re.compile(r'`([^`\n]+)`')
EVIDENCE_NAME_RE = re.compile(r'(?:docs/evidence/|\.\./evidence/)([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)')
EVIDENCE_OR_TEST_RE = re.compile(r'(?:docs/evidence/|\.\./evidence/)[A-Za-z0-9_.-]+|tests/[\w./-]+\.(?:py|mjs|js)')
COMMAND_PREFIXES = ('python3 ', 'python ', 'node ', 'npm ')
CITABLE_SUFFIXES = ('.md', '.yml', '.yaml', '.json', '.py', '.mjs', '.js')
# Mutation samples are built at runtime so the test file itself holds no contact details.
MUTANT_EMAIL = 'mutant' + '@' + 'example.invalid'
MUTANT_HANDLE = '@' + 'mutant-handle'


def split_section(text):
    """Return (section, outside). Raises ValueError unless the heading appears exactly once."""
    lines = text.split('\n')
    starts = [i for i, line in enumerate(lines) if line.rstrip() == SECTION_HEADING]
    if len(starts) != 1:
        raise ValueError(f'expected exactly one {SECTION_HEADING!r}, found {len(starts)}')
    start = starts[0]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith('## '):
            end = j
            break
    return '\n'.join(lines[start:end]), '\n'.join(lines[:start] + lines[end:])


def check_subsections(section):
    return [f'missing subsection: {name}' for name in REQUIRED_SUBSECTIONS
            if not re.search(r'^### ' + re.escape(name) + r'[ \t]*$', section, re.M)]


def github_slug(heading):
    slug = re.sub(r'[^\w\- ]', '', heading.strip().lower())
    return slug.replace(' ', '-')


def heading_slugs(path):
    slugs, in_fence = set(), False
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('```'):
            in_fence = not in_fence
            continue
        m = None if in_fence else re.match(r'#{1,6}\s+(.*?)\s*#*\s*$', line)
        if m:
            slugs.add(github_slug(m.group(1)))
    return slugs


def resolve_target(target, base_dir, self_path):
    path_part, _, anchor = target.partition('#')
    resolved = (base_dir / unquote(path_part)).resolve() if path_part else self_path.resolve()
    return resolved, anchor


def check_links(section, base_dir=T0_PATH.parent, root=ROOT, self_path=T0_PATH):
    errors = []
    for _label, target in LINK_RE.findall(section):
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        resolved, anchor = resolve_target(target, base_dir, self_path)
        if not resolved.is_file():
            errors.append(f'broken link: {target}')
            continue
        if resolved != root.resolve() and root.resolve() not in resolved.parents:
            errors.append(f'link escapes repository: {target}')
            continue
        if anchor and resolved.suffix == '.md' and anchor.lower() not in heading_slugs(resolved):
            errors.append(f'missing anchor: {target}')
    return errors


def check_evidence_names(section, root=ROOT):
    names = sorted(set(EVIDENCE_NAME_RE.findall(section)))
    errors = [] if names else ['no docs/evidence file named in section']
    errors += [f'named evidence file missing: docs/evidence/{n}' for n in names
               if not (root / 'docs' / 'evidence' / n).is_file()]
    return errors


def table_rows(text):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith('|') and s.endswith('|')):
            continue
        cells = [c.strip() for c in s[1:-1].split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
            continue
        rows.append((line, cells))
    return rows


def status_rows(section):
    m = re.search(r'^### Status[ \t]*$', section, re.M)
    if not m:
        return None
    return [(line, cells) for line, cells in table_rows(section[m.end():]) if cells[0] != 'Class']


def check_status_table(section):
    rows = status_rows(section)
    if rows is None:
        return ['missing Status subsection']
    errors, seen = [], set()
    for _line, cells in rows:
        cls = cells[0].strip('*').strip()
        if cls in CLASSES:
            seen.add(cls)
        else:
            errors.append(f'unknown status class: {cls!r}')
    errors += [f'no {cls} row' for cls in CLASSES if cls not in seen]
    return errors


def check_supported_rows(section):
    errors = []
    for line, cells in status_rows(section) or []:
        if cells[0].strip('*').strip() == 'SUPPORTED' and not EVIDENCE_OR_TEST_RE.search(line):
            errors.append(f'SUPPORTED row cites no evidence or test file: {cells[1][:60] if len(cells) > 1 else line[:60]}')
    return errors


def check_identities(section):
    errors = [f'email address present in section' for _ in EMAIL_RE.findall(section)]
    errors += [f'handle not allowed: @{h}' for h in HANDLE_RE.findall(section) if h != ALLOWED_HANDLE]
    return errors


def check_forbidden_phrases(section):
    return [f'forbidden claim phrase matched: {p}' for p in FORBIDDEN_PATTERNS
            if re.search(p, section, re.I)]


def normalize(text):
    return ' '.join(text.split())


def package_scripts(root=ROOT):
    return set(json.loads((root / 'package.json').read_text(encoding='utf-8')).get('scripts', {}))


def allowlist_sources(section, outside, root=ROOT, self_path=T0_PATH):
    """Normalized text of the outside-section T0 record plus every repository file the section links to."""
    texts = [outside]
    for _label, target in LINK_RE.findall(section):
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        resolved, _anchor = resolve_target(target, self_path.parent, self_path)
        if (resolved.is_file() and resolved.suffix in CITABLE_SUFFIXES
                and resolved not in (self_path.resolve(), Path(__file__).resolve())):
            texts.append(resolved.read_text(encoding='utf-8'))
    return [normalize(t) for t in texts]


def check_commands(section, outside, root=ROOT):
    errors, scripts = [], package_scripts(root)
    sources = allowlist_sources(section, outside, root)
    for span in CODE_RE.findall(section):
        cmd = normalize(span)
        if not cmd.startswith(COMMAND_PREFIXES):
            continue
        tokens = cmd.split(' ')
        if cmd.startswith('npm run '):
            if len(tokens) != 3 or tokens[2] not in scripts:
                errors.append(f'npm script not defined in package.json: {cmd}')
            continue
        for tok in tokens:
            if '/' in tok and not any(ch in tok for ch in '$"\''):
                if not (root / tok).exists():
                    errors.append(f'path does not exist: {tok} (in {cmd})')
        if not any(cmd in src for src in sources):
            errors.append(f'command not found in cited files: {cmd}')
    return errors


class T0HandoffSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section, cls.outside = split_section(T0_PATH.read_text(encoding='utf-8'))

    def test_section_present_once_with_required_subsections(self):
        self.assertEqual([], check_subsections(self.section))

    def test_existing_top_level_structure_preserved(self):
        for heading in ('## Research question', '## Required contract', '## Capability scope', '## Evidence and handoff'):
            self.assertIn(heading, self.outside)

    def test_relative_links_resolve_including_anchors(self):
        self.assertTrue(LINK_RE.search(self.section))
        self.assertEqual([], check_links(self.section))

    def test_every_named_evidence_file_exists(self):
        self.assertEqual([], check_evidence_names(self.section))

    def test_supported_rows_cite_evidence_or_tests(self):
        self.assertEqual([], check_supported_rows(self.section))

    def test_status_table_has_all_three_classes(self):
        self.assertEqual([], check_status_table(self.section))

    def test_no_identities_other_than_maintainer_handle(self):
        self.assertEqual([], check_identities(self.section))

    def test_no_forbidden_claim_phrases(self):
        self.assertEqual([], check_forbidden_phrases(self.section))

    def test_listed_commands_exist_in_allowlist(self):
        self.assertEqual([], check_commands(self.section, self.outside))


class T0HandoffMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section, cls.outside = split_section(T0_PATH.read_text(encoding='utf-8'))

    def assertMutated(self, original, mutated):
        self.assertNotEqual(original, mutated, 'mutation did not change the section')

    def test_broken_link_is_detected(self):
        m = self.section.replace('](../evidence/', '](../evidence/MISSING-', 1)
        self.assertMutated(self.section, m)
        self.assertTrue(check_links(m))

    def test_broken_anchor_is_detected(self):
        m = self.section.replace('#interaction-architecture-gb-t00102t1', '#no-such-heading', 1)
        self.assertMutated(self.section, m)
        self.assertTrue(check_links(m))

    def test_missing_subsection_is_detected(self):
        m = re.sub(r'^### Operator and contributor steps[ \t]*\n', '', self.section, count=1, flags=re.M)
        self.assertMutated(self.section, m)
        self.assertTrue(check_subsections(m))

    def test_supported_row_without_evidence_is_detected(self):
        lines = self.section.split('\n')
        idx = next(i for i, line in enumerate(lines) if line.startswith('| SUPPORTED |'))
        lines[idx] = '| SUPPORTED | Mutated claim | no file cited |'
        m = '\n'.join(lines)
        self.assertMutated(self.section, m)
        self.assertTrue(check_supported_rows(m))

    def test_added_email_is_detected(self):
        m = self.section + f'\nContact: {MUTANT_EMAIL}\n'
        self.assertTrue(check_identities(m))

    def test_added_foreign_handle_is_detected(self):
        m = self.section + f'\nSee {MUTANT_HANDLE}.\n'
        self.assertTrue(check_identities(m))

    def test_production_ready_claim_is_detected(self):
        m = self.section + '\nThe foundation is production ready.\n'
        self.assertTrue(check_forbidden_phrases(m))

    def test_fully_verified_claim_is_detected(self):
        m = self.section + '\nT0 is fully verified.\n'
        self.assertTrue(check_forbidden_phrases(m))

    def test_unknown_npm_script_is_detected(self):
        m = self.section.replace('`npm run lint`', '`npm run deploy`', 1)
        self.assertMutated(self.section, m)
        self.assertTrue(check_commands(m, self.outside))

    def test_nonexistent_script_path_is_detected(self):
        m = self.section + '\n`python3 scripts/does-not-exist.py`\n'
        self.assertTrue(check_commands(m, self.outside))

    def test_unlisted_command_form_is_detected(self):
        m = self.section + '\n`python3 scripts/verification/check_licenses.py --strict-deploy`\n'
        self.assertTrue(check_commands(m, self.outside))

    def test_nonexistent_evidence_name_is_detected(self):
        m = self.section + '\n`docs/evidence/NOT-THERE.json`\n'
        self.assertTrue(check_evidence_names(m))


if __name__ == '__main__':
    unittest.main()
