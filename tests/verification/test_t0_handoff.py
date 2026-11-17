"""Offline checks for the '## T0 integration and handoff' section of docs/workstreams/T0.md.

Stdlib only, repository-root relative, no network. Run from the repository root:
    python3 -I -B -m unittest discover -s tests/verification -v
Every check returns a list of error strings; mutation tests call checks on altered text.
"""
import json
import os
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
T0_PATH = ROOT / 'docs' / 'workstreams' / 'T0.md'
SECTION_HEADING = '## T0 integration and handoff'
DISCLAIMER = ('This section does not claim independent review, native CI, protected merge '
              'or acceptance of issue #32 or #458.')
REQUIRED_SUBSECTIONS = ('Contracts and recorded status', 'Operator and contributor steps',
                        'Evidence', 'Deliverable disposition', 'Status')
CLASSES = ('SUPPORTED', 'PLANNED', 'UNRESOLVED')
FORBIDDEN_PATTERNS = (
    r'accepted\s+by', r'approved\s+by', r'production[\s-]+ready', r'fully\s+verified',
    r'for\s+each\s+T0\s+deliverable', r'await\s+native\s+CI', r'pending\s+actual\s+native\s+CI',
    r'local\s+configuration\s+test\s+run', r'local\s+suite\s+and\s+harness',
)
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
HANDLE_RE = re.compile(r'(?<![\w.])@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)')
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')
CODE_RE = re.compile(r'`([^`\n]+)`')
EVIDENCE_NAME_RE = re.compile(r'(?:docs/evidence/|\.\./evidence/)([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)')
EVIDENCE_OR_TEST_RE = re.compile(r'(?:docs/evidence/|\.\./evidence/)[A-Za-z0-9_.-]+|tests/[\w./-]+\.(?:py|mjs|js)')
STATUS_LINK_RE = re.compile(r'\]\((\.\./(?:adr|specifications)/[^)\s#]+?\.md)\)\s*\((?:status:\s*)?([^()]*)\)')
STATUS_LINE_RE = re.compile(r'^Status:[ \t]*(.+)$', re.M)
REQUIRED_STATUS_FILES = ('0001-', '0002-', '0003-', '0004-', 'GB-T0-S1-system-contract.md')
COMMAND_PREFIXES = ('python3 ', 'python ', 'node ', 'npm ', 'npx ', 'bash ', 'sh ', 'make ', 'git ', 'pip ', 'gh ')
HARDENING_FLAGS = ('-I', '-B')
TOPIC_WORDS = ('discord', 'godaddy', 'vps', 'database', 'runtime')
REQUIRED_PR_REFS = ('PR #481', 'PR #501', 'PR #502', 'PR #503', 'PR #504')
TOOLING_FILE = 'config-tooling-2026-10-24.json'
TOOLING_PHRASE = 'records no test run'
REQUIRED_PHRASES = (
    '`python -m unittest discover -s tests/planning -v`',
    '`python3 -m unittest discover -s tests/planning -v`',
    'setup-python provides `python`',
)
REVISION_PINS = (
    ('GB-T0-01-01-V1-raw-results.json', 'source_candidate_sha'),
    ('GB-T0-01-01-V1-requirements-acceptance.json', 'source_revision'),
    ('GB-T0-01-02-V1-raw-results.json', 'source_revision_supplied'),
    ('GB-T0-02-01-V1-editor-feasibility-acceptance.json', 'tested_revision'),
    ('GB-T0-02-02-V1-license-acceptance.json', 'tested_revision'),
    ('GB-T0-03-01-V1-engineering-acceptance.json', 'source_revision'),
    ('GB-T0-03-02-V1-config-acceptance.json', 'tested_product_revision'),
    ('GB-T0-04-01-V1-governance-acceptance.json', 'tested_revision'),
    ('GB-T0-04-02-V1-architecture-controls-acceptance.json', 'tested_revision'),
)
# Each SUPPORTED row is pinned by a unique substring of its Item cell to the exact set of
# link targets it may cite. Adding, dropping or repointing evidence fails the suite.
SUPPORTED_PINS = {
    'Offline license gate': {
        '../evidence/GB-T0-02-02-V1-raw-results.txt',
        '../../tests/verification/test_license_policy.py'},
    'Requirements and use-case definition check': {
        '../evidence/GB-T0-01-01-V1-requirements-acceptance.json',
        '../../tests/verification/test_requirements_acceptance.py',
        'https://github.com/CompleteTech-DiscordApps/guildboard/pull/503#issuecomment-6920512927',
        'https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43894850314'},
    'Architecture artifact digest check': {
        '../evidence/GB-T0-01-02-V1-raw-results.json',
        '../evidence/GB-T0-01-02-V1-architecture-acceptance.json',
        '../../tests/verification/test_architecture_acceptance.py'},
    'Editor research static checks': {
        '../evidence/GB-T0-02-01-V1-raw-results.txt',
        '../../tests/verification/test_editor_feasibility.py'},
    'Engineering boundary and build checks': {
        '../evidence/GB-T0-03-01-V1-raw-results.txt',
        '../../tests/engineering/boundaries.test.mjs'},
    'Configuration parser contract': {
        '../evidence/GB-T0-03-02-V1-config-acceptance.json'},
    'Configuration failure-path runner checks': {
        'https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43891156976',
        'https://github.com/CompleteTech-DiscordApps/guildboard/pull/502#issuecomment-6920049139'},
    'Architecture-controls offline gate': {
        '../evidence/GB-T0-04-02-V1-raw-results.txt',
        '../../tests/architecture-controls/test_gate.py'},
    'Governance wording, routing': {
        '../evidence/GB-T0-04-01-V1-raw-results.txt',
        '../../tests/verification/test_governance_policy.py'},
    'Planning manifest validation': {
        '../../tests/planning/test_validate.py',
        '../../scripts/github-bootstrap/validate.py'},
}
REQUIRED_ITEM_WORDS = {'Requirements and use-case definition check': 'successor'}
# Open items that must stay as UNRESOLVED rows (matched against the whole row text).
REQUIRED_UNRESOLVED = (
    'GB-T0.S1 header', 'Configuration records disagree', 'Requirements verification (#7)',
    'Architecture artifact verification (#10)', 'Engineering verification (#21)',
    'Editor independent verification (#14)', 'License verification (#17)',
    'Governance verification (#28)', 'Architecture controls (#30)',
    'Full configuration facade (#23)', 'pako', 'fuzzy', 'project-overview.jpg', 'One maintainer',
    'Discord iframe and proxy behavior', 'Node commands in steps 9 and 10',
    'Editor adoption is not accepted', 'ADR 0002 needs fresh', 'Semantic design review',
    'Threat model review', 'Issue #32 and #458',
)


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


def normalize(text):
    return ' '.join(text.split())


def subsection(section, name):
    m = re.search(r'^### ' + re.escape(name) + r'[ \t]*$', section, re.M)
    if not m:
        return None
    nxt = re.search(r'^### ', section[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(section)
    return section[m.end():end]


def check_subsections(section):
    return [f'missing subsection: {name}' for name in REQUIRED_SUBSECTIONS
            if subsection(section, name) is None]


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


def check_links(section, base_dir=T0_PATH.parent, root=ROOT, self_path=T0_PATH):
    errors = []
    for _label, target in LINK_RE.findall(section):
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        path_part, _, anchor = target.partition('#')
        resolved = (base_dir / unquote(path_part)).resolve() if path_part else self_path.resolve()
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
    body = subsection(section, 'Status')
    if body is None:
        return None
    return [(line, cells) for line, cells in table_rows(body) if cells and cells[0] != 'Class']


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


def check_supported(section):
    rows = status_rows(section)
    if rows is None:
        return ['missing Status subsection']
    errors, matched = [], set()
    supported = [(line, cells) for line, cells in rows if cells[0].strip('*').strip() == 'SUPPORTED']
    if len(supported) != len(SUPPORTED_PINS):
        errors.append(f'expected {len(SUPPORTED_PINS)} SUPPORTED rows, found {len(supported)}')
    for line, cells in supported:
        item = cells[1] if len(cells) > 1 else ''
        key = next((k for k in SUPPORTED_PINS if k in item), None)
        if key is None:
            errors.append(f'SUPPORTED row has no pinned item: {item[:70]!r}')
            continue
        if key in matched:
            errors.append(f'duplicate SUPPORTED row for {key!r}')
        matched.add(key)
        if key in REQUIRED_ITEM_WORDS and REQUIRED_ITEM_WORDS[key] not in item:
            errors.append(f'SUPPORTED row {key!r} must state {REQUIRED_ITEM_WORDS[key]!r}')
        clean = re.sub(r'\([^()]*\)', '', item).lower()
        errors += [f'SUPPORTED row {key!r} names unverified topic: {w}' for w in TOPIC_WORDS
                   if re.search(r'\b' + w + r'\b', clean)]
        targets = [t for _label, t in LINK_RE.findall(line)]
        plain = EVIDENCE_OR_TEST_RE.findall(LINK_RE.sub(r'\1', line))
        errors += [f'SUPPORTED row {key!r} has unlinked evidence or test path: {p}' for p in plain]
        if not targets:
            errors.append(f'SUPPORTED row {key!r} cites no evidence or test link')
        errors += [f'SUPPORTED row {key!r} links unpinned target: {t}'
                   for t in targets if t not in SUPPORTED_PINS[key]]
        errors += [f'SUPPORTED row {key!r} lost pinned target: {t}'
                   for t in sorted(SUPPORTED_PINS[key]) if t not in targets]
    errors += [f'no SUPPORTED row for pinned item {k!r}' for k in SUPPORTED_PINS if k not in matched]
    return errors


def check_unresolved(section):
    rows = status_rows(section)
    if rows is None:
        return ['missing Status subsection']
    unresolved = [line for line, cells in rows if cells[0].strip('*').strip() == 'UNRESOLVED']
    return [f'no UNRESOLVED row mentions {k!r}' for k in REQUIRED_UNRESOLVED
            if not any(k in line for line in unresolved)]


def norm_status(text):
    return ' '.join(text.replace('*', '').split()).lower()


def check_status_quotes(section, root=ROOT, base_dir=T0_PATH.parent):
    """Each ADR/spec status quoted in the section must be a leading part of that file's Status line."""
    errors, found = [], set()
    for target, quote in STATUS_LINK_RE.findall(section):
        path = (base_dir / target).resolve()
        if not path.is_file() or (root.resolve() not in path.parents):
            errors.append(f'status link is not a repository file: {target}')
            continue
        key = next((k for k in REQUIRED_STATUS_FILES if path.name.startswith(k) or path.name.endswith(k)), None)
        if key:
            found.add(key)
        m = STATUS_LINE_RE.search(path.read_text(encoding='utf-8'))
        if not m:
            errors.append(f'no Status line in {target}')
            continue
        status, q = norm_status(m.group(1)), norm_status(quote)
        if not q or not (status.startswith(q) and (len(status) == len(q) or status[len(q)] in '.,;')):
            errors.append(f'quoted status {quote.strip()!r} differs from the Status line of {path.name}')
    errors += [f'no quoted status for required file {k}' for k in REQUIRED_STATUS_FILES if k not in found]
    return errors


def bullets(text):
    blocks, cur = [], None
    for line in text.split('\n'):
        if line.startswith('- '):
            if cur is not None:
                blocks.append(cur)
            cur = line
        elif not line.strip():
            if cur is not None:
                blocks.append(cur)
            cur = None
        elif cur is not None:
            cur += ' ' + line.strip()
    if cur is not None:
        blocks.append(cur)
    return blocks


def check_revisions(section, root=ROOT):
    """Each record's own revision field must be quoted in the Evidence bullet that names the record."""
    body = subsection(section, 'Evidence')
    if body is None:
        return ['missing Evidence subsection']
    blocks, errors = bullets(body), []
    for name, key in REVISION_PINS:
        path = root / 'docs' / 'evidence' / name
        if not path.is_file():
            errors.append(f'record missing: {name}')
            continue
        try:
            value = json.loads(path.read_text(encoding='utf-8')).get(key)
        except (ValueError, AttributeError) as exc:
            errors.append(f'record unreadable: {name}: {exc}')
            continue
        if not isinstance(value, str):
            errors.append(f'record has no string field {key}: {name}')
            continue
        naming = [b for b in blocks if name in b]
        if not naming:
            errors.append(f'no Evidence bullet names {name}')
        elif not any(value in b for b in naming):
            errors.append(f'{name}: {key} {value} is not quoted in its Evidence bullet')
    tooling = [b for b in blocks if TOOLING_FILE in b]
    if not any(TOOLING_PHRASE in b for b in tooling):
        errors.append(f'Evidence bullet for {TOOLING_FILE} does not state that it {TOOLING_PHRASE}')
    return errors


def check_identities(section):
    errors = ['email address present in section' for _ in EMAIL_RE.findall(section)]
    errors += [f'handle not allowed: @{h}' for h in HANDLE_RE.findall(section)]
    return errors


def check_forbidden_phrases(section):
    return [f'forbidden claim phrase matched: {p}' for p in FORBIDDEN_PATTERNS
            if re.search(p, section, re.I)]


def check_disclaimer(section):
    return [] if normalize(DISCLAIMER) in normalize(section) else ['disclaimer sentence missing']


def check_deliverables(section):
    body = subsection(section, 'Deliverable disposition')
    if body is None:
        return ['missing Deliverable disposition subsection']
    return [f'Deliverable disposition lacks {ref}' for ref in REQUIRED_PR_REFS if ref not in body]


def check_phrases(section):
    return [f'required phrase missing: {p}' for p in REQUIRED_PHRASES if p not in section]


def canon(text):
    tokens = normalize(text.replace('`', ' ')).split(' ')
    return ' '.join('python' if t == 'python3' else t for t in tokens if t not in HARDENING_FLAGS)


def allowlist(root=ROOT):
    """Canonical text of workflow and Markdown files other than T0.md (and this test, which is .py)."""
    texts = []
    t0 = T0_PATH.resolve()
    for base, dirs, files in os.walk(root):
        # Only repository content counts: skip every hidden directory except .github
        # (for example untracked .recovery/ working files, which may hold symlink loops).
        dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__') and (not d.startswith('.') or d == '.github')]
        for name in files:
            p = Path(base) / name
            if p.is_symlink():
                continue
            try:
                if p.resolve() == t0:
                    continue
                rel = p.relative_to(root).parts
                if name.endswith('.md') or (rel[0] == '.github' and name.endswith(('.yml', '.yaml'))):
                    texts.append(canon(p.read_text(encoding='utf-8', errors='replace')))
            except OSError:
                continue
    return texts


def check_commands(section, root=ROOT):
    errors = []
    scripts = set(json.loads((root / 'package.json').read_text(encoding='utf-8')).get('scripts', {}))
    sources = allowlist(root)
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
            if tok.startswith('/') or any(ch in tok for ch in '<$"\''):
                continue
            if '/' in tok and not (root / tok).exists():
                errors.append(f'path does not exist: {tok} (in {cmd})')
        pattern = re.compile(r'(?:^| )' + re.escape(canon(cmd)) + r'(?= |$)')
        if not any(pattern.search(src) for src in sources):
            errors.append(f'command not found in workflow or doc allowlist: {cmd}')
    return errors


CHECKS = (check_subsections, check_links, check_evidence_names, check_status_table, check_supported,
          check_unresolved, check_status_quotes, check_revisions, check_identities,
          check_forbidden_phrases, check_disclaimer, check_deliverables, check_phrases, check_commands)


def run_check(check, section):
    """Run a check; an exception becomes an error string so self-tests report failures, not errors."""
    try:
        return check(section)
    except Exception as exc:  # noqa: BLE001 - converted to a reported failure
        return [f'check raised {type(exc).__name__}: {exc}']


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
        self.assertEqual([], check_links(self.section))

    def test_every_named_evidence_file_exists(self):
        self.assertEqual([], check_evidence_names(self.section))

    def test_status_table_has_all_three_classes(self):
        self.assertEqual([], check_status_table(self.section))

    def test_supported_rows_match_pinned_evidence(self):
        self.assertEqual([], check_supported(self.section))

    def test_required_unresolved_rows_present(self):
        self.assertEqual([], check_unresolved(self.section))

    def test_quoted_adr_and_spec_statuses_match_files(self):
        self.assertEqual([], check_status_quotes(self.section))

    def test_quoted_revisions_match_record_fields(self):
        self.assertEqual([], check_revisions(self.section))

    def test_no_identities_or_handles(self):
        self.assertEqual([], check_identities(self.section))

    def test_no_forbidden_claim_phrases(self):
        self.assertEqual([], check_forbidden_phrases(self.section))

    def test_disclaimer_present(self):
        self.assertEqual([], check_disclaimer(self.section))

    def test_deliverables_list_merged_prs(self):
        self.assertEqual([], check_deliverables(self.section))

    def test_planning_step_names_both_runner_forms(self):
        self.assertEqual([], check_phrases(self.section))

    def test_listed_commands_match_workflow_or_doc_allowlist(self):
        self.assertEqual([], check_commands(self.section))

    def test_checks_report_instead_of_raising_on_empty_text(self):
        for check in CHECKS:
            errors = run_check(check, '')
            self.assertFalse(any(e.startswith('check raised') for e in errors), check.__name__)


class T0HandoffMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section, cls.outside = split_section(T0_PATH.read_text(encoding='utf-8'))

    def replaced(self, old, new, count=1):
        if old not in self.section:
            return None
        return self.section.replace(old, new, count)

    def row_replaced(self, key, old, new):
        lines = self.section.split('\n')
        hits = [i for i, line in enumerate(lines) if line.startswith('| ') and key in line]
        if len(hits) != 1 or old not in lines[hits[0]]:
            return None
        lines[hits[0]] = lines[hits[0]].replace(old, new, 1)
        return '\n'.join(lines)

    def row_deleted(self, key):
        lines = self.section.split('\n')
        kept = [line for line in lines if not (line.startswith('| UNRESOLVED') and key in line)]
        return None if len(kept) == len(lines) else '\n'.join(kept)

    def assertDetected(self, mutated, check, label):
        self.assertIsNotNone(mutated, f'mutation target not found: {label}')
        self.assertNotEqual(self.section, mutated, f'mutation changed nothing: {label}')
        self.assertTrue(run_check(check, mutated), f'not detected: {label}')

    def test_s1_status_quote_upgraded_is_detected(self):
        self.assertDetected(self.replaced('(status: proposed, not accepted and not an implementation authorization)', '(status: accepted)'), check_status_quotes, 'S1 upgraded')

    def test_s1_status_quote_removed_is_detected(self):
        self.assertDetected(self.replaced(' (status: proposed, not accepted and not an implementation authorization)', ''), check_status_quotes, 'S1 quote removed')

    def test_adr_0002_status_upgrade_is_detected(self):
        self.assertDetected(self.replaced('(status: proposed)', '(status: accepted)'), check_status_quotes, 'ADR 0002 upgraded')

    def test_adr_0003_status_upgrade_is_detected(self):
        self.assertDetected(self.replaced('(status: selected within delegated section authority for issue #30)', '(status: accepted)'), check_status_quotes, 'ADR 0003 upgraded')

    def test_adr_0004_status_upgrade_is_detected(self):
        self.assertDetected(self.replaced('section decision for a controlled experiment, 2026-11-16. Does not authorize installation or deployment', 'accepted for installation and deployment'), check_status_quotes, 'ADR 0004 upgraded')

    def test_stale_config_failure_row_is_detected(self):
        m = self.section + '\n| UNRESOLVED | Configuration failure-path checks await native CI execution | [config](../evidence/GB-T0-03-02-V1-config-acceptance.json) |\n'
        self.assertDetected(m, check_forbidden_phrases, 'stale config row')

    def test_generic_each_deliverable_claim_is_detected(self):
        self.assertDetected(self.section + '\nReview remains open for each T0 deliverable.\n', check_forbidden_phrases, 'generic claim')

    def test_config_tooling_described_as_test_run_is_detected(self):
        self.assertDetected(self.replaced(TOOLING_PHRASE, 'records the configuration test run'), check_revisions, 'tooling as test run')

    def test_config_tooling_cited_as_supported_evidence_is_detected(self):
        m = self.row_replaced('Configuration parser contract', '[config acceptance]', '[config tooling](../evidence/config-tooling-2026-10-24.json); [config acceptance]')
        self.assertDetected(m, check_supported, 'tooling as SUPPORTED evidence')

    def test_requirements_successor_pin_removed_is_detected(self):
        m = self.row_replaced('Requirements and use-case definition check', 'https://github.com/CompleteTech-DiscordApps/guildboard/pull/503#issuecomment-6920512927', 'https://example.invalid/none')
        self.assertDetected(m, check_supported, 'successor pin removed')

    def test_supported_row_repointed_to_wrong_record_is_detected(self):
        m = self.row_replaced('Offline license gate', '../evidence/GB-T0-02-02-V1-raw-results.txt', '../evidence/GB-T0-04-01-V1-raw-results.txt')
        self.assertDetected(m, check_supported, 'license row repointed')

    def test_supported_row_citing_nonexistent_test_is_detected(self):
        m = self.row_replaced('Offline license gate', '../../tests/verification/test_license_policy.py', '../../tests/verification/test_missing.py')
        self.assertDetected(m, check_supported, 'nonexistent test cited')

    def test_discord_supported_row_is_detected(self):
        m = self.section + '\n| SUPPORTED | Discord iframe and GoDaddy VPS deployment verified | [raw results](../evidence/GB-T0-02-02-V1-raw-results.txt) |\n'
        self.assertDetected(m, check_supported, 'Discord SUPPORTED row')

    def test_topic_word_in_supported_row_is_detected(self):
        m = self.row_replaced('Planning manifest validation', 'Planning manifest validation', 'Planning manifest validation in the database')
        self.assertDetected(m, check_supported, 'database topic in SUPPORTED row')

    def test_swapped_license_revision_is_detected(self):
        self.assertDetected(self.replaced('a6c887ebcc0116f35666af382aa065ea1c593b98', '79a3185accf34792dffa369a11c9d6142e86cb35', 10), check_revisions, 'license SHA swapped')

    def test_swapped_config_revision_is_detected(self):
        self.assertDetected(self.replaced('6ca5b24d4fc42a9f38bbbc1786f99d817be0f6af', '8342d46b43dfb1dd6fac5c35c32dcd132128d086', 10), check_revisions, 'config SHA swapped')

    def test_planning_runner_note_removed_is_detected(self):
        self.assertDetected(self.replaced('where setup-python provides `python`', 'where the runner provides it'), check_phrases, 'python note removed')

    def test_disclaimer_deleted_is_detected(self):
        self.assertDetected(self.replaced(DISCLAIMER, ''), check_disclaimer, 'disclaimer deleted')

    def test_unresolved_s1_header_row_deleted_is_detected(self):
        self.assertDetected(self.row_deleted('GB-T0.S1 header'), check_unresolved, 'S1 header row deleted')

    def test_unresolved_architecture_controls_row_deleted_is_detected(self):
        self.assertDetected(self.row_deleted('Architecture controls (#30)'), check_unresolved, 'controls row deleted')

    def test_unresolved_semantic_review_row_deleted_is_detected(self):
        self.assertDetected(self.row_deleted('Semantic design review'), check_unresolved, 'semantic row deleted')

    def test_deliverable_pr_reference_removed_is_detected(self):
        self.assertDetected(self.replaced('PR #502', 'PR 502', -1), check_deliverables, 'PR #502 removed')

    def test_command_outside_allowlist_is_detected(self):
        self.assertDetected(self.section + '\n`bash scripts/deploy.sh`\n', check_commands, 'bash deploy command')

    def test_unlisted_flag_on_real_command_is_detected(self):
        self.assertDetected(self.section + '\n`python3 scripts/verification/check_licenses.py --strict-deploy`\n', check_commands, 'unlisted flag')

    def test_unknown_npm_script_is_detected(self):
        self.assertDetected(self.replaced('`npm run lint`', '`npm run deploy`'), check_commands, 'unknown npm script')

    def test_nonexistent_script_path_is_detected(self):
        self.assertDetected(self.section + '\n`python3 scripts/does-not-exist.py`\n', check_commands, 'missing script')

    def test_added_email_is_detected(self):
        self.assertDetected(self.section + '\nContact: mutant@example.invalid\n', check_identities, 'email')

    def test_added_handle_is_detected(self):
        self.assertDetected(self.section + '\nSee @mutant-handle.\n', check_identities, 'handle')

    def test_production_ready_claim_is_detected(self):
        self.assertDetected(self.section + '\nThe foundation is production ready.\n', check_forbidden_phrases, 'production ready')

    def test_broken_link_is_detected(self):
        self.assertDetected(self.replaced('](../evidence/', '](../evidence/MISSING-'), check_links, 'broken link')

    def test_broken_anchor_is_detected(self):
        self.assertDetected(self.replaced('#evidence-and-handoff', '#no-such-heading'), check_links, 'broken anchor')

    def test_missing_subsection_is_detected(self):
        m = re.sub(r'^### Deliverable disposition[ \t]*\n', '', self.section, count=1, flags=re.M)
        self.assertDetected(m, check_subsections, 'subsection removed')

    def test_nonexistent_evidence_name_is_detected(self):
        self.assertDetected(self.section + '\n`docs/evidence/NOT-THERE.json`\n', check_evidence_names, 'missing evidence name')



class AllowlistRobustnessTests(unittest.TestCase):
    def test_allowlist_ignores_hidden_dirs_and_symlink_loops(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'docs').mkdir()
            (root / 'docs' / 'a.md').write_text('run `python3 x.py`\n', encoding='utf-8')
            hidden = root / '.recovery' / 'scratch'
            hidden.mkdir(parents=True)
            (hidden / 'loop.md').symlink_to(hidden / 'loop.md')
            (hidden / 'secret.md').write_text('python3 hidden.py\n', encoding='utf-8')
            texts = allowlist(root)
            self.assertTrue(any('x.py' in x for x in texts))
            self.assertFalse(any('hidden.py' in x for x in texts))


if __name__ == '__main__':
    unittest.main()
