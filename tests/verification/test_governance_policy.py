"""Offline governance policy checks (GB-T0.04.01.T1, #27).

Each clause is checked by a function over text. Repository tests run the functions on the
committed files; NegativeMutationTests feed weakened or extended text into the same functions
and assert that they fail. The checks confirm required sections, headings and key phrases,
the absence of listed forbidden weakenings, and the identity and issue-template surfaces.
They cannot prove the semantic quality of the wording, that anyone reviews, that CI runs, or
that an issue is claimed or assigned in practice. Stdlib only; paths are resolved from this
file; runs under python3 -I.
"""

import re
import tempfile
import unicodedata
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAINTAINER = '@CompleteDotTech'
MAINTAINER_NAME = 'CompleteDotTech'
GOVERNANCE = 'GOVERNANCE.md'
CONTRIBUTING = 'CONTRIBUTING.md'
CONDUCT = 'CODE_OF_CONDUCT.md'
CODEOWNERS = '.github/CODEOWNERS'
PR_TEMPLATE = '.github/pull_request_template.md'
SECURITY = 'SECURITY.md'
README = 'README.md'
ISSUE_TEMPLATE_DIR = '.github/ISSUE_TEMPLATE'
TASK_DOC = 'docs/workstreams/T0.md'
TASK_HEADING = 'GB-T0.04.01.T1 governance and contribution policy (#27)'
BACKLOG_HEADING = 'Issue ownership and backlog visibility'
# Every file in which an approver, contact or handle could be invented. T0 is scanned by its section.
IDENTITY_FILES = (GOVERNANCE, CONTRIBUTING, CONDUCT, CODEOWNERS, PR_TEMPLATE, SECURITY, README)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*\S)\s*$')
BULLET_RE = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+')
# Any assignment key in any form (assignees, assignee, assign, assigned, assigned_to, owner): block, list item, quoted, inline flow or front matter.
ASSIGNEES_KEY_RE = re.compile(r'(?<![\w-])["\']?(?:assignees?|assign|assigned|assigned_to|owner)["\']?\s*:', re.IGNORECASE)
# Any assignee word or auto-assign hint in any template file.
ASSIGN_HINT_RE = re.compile(r'\bassignees?\b|auto-?assign|autoassign', re.IGNORECASE)

# Needles are matched against norm(text): lower case, '→' written as '->', whitespace collapsed.
# Regex needles therefore must be lower case.
GOVERNANCE_TOP_NEEDLES = [
    'The currently known repository maintainer is @CompleteDotTech.',
    'No other contributors or approvers have been assigned.',
]
GOVERNANCE_CLAUSES = {
    'Maintainers': [
        '@CompleteDotTech', 'the only known repository maintainer',
        'no other maintainers, contributors or approvers', 'explicit recorded appointment',
        'CODEOWNERS'],
    'Review roles': [
        'CONTRIBUTING.md', 'to security expertise', 'to realtime and canvas expertise',
        'to data expertise', 'to platform expertise', 'do not create reviewers or approvals',
        'not waived by Project status'],
    'Decision escalation': [
        'contributor -> issue or ADR discussion -> maintainer review',
        'a contributor raises a scope, behavior, acceptance or sequencing question on the issue',
        'escalated to maintainer review by @CompleteDotTech',
        re.compile(r'decision is recorded in the (?:issue|adr|pr)'),
        'Escalated: scope and sequencing disputes', 'CODE_OF_CONDUCT.md', 'SECURITY.md',
        'no response time is committed', 'no other decision-maker is named'],
    'Contributor conduct': [
        'CODE_OF_CONDUCT.md', re.compile(r'(?:reported|raised|sent) privately|private (?:path|channel)'),
        'must not carry sensitive details', 'documented by the maintainer'],
}
# Forbidden weakenings per GOVERNANCE section (backlog section is handled by check_governance_backlog).
# Timeframe counts: digits, number words (forty-eight, seventy-two) or vague quantities.
NUMBER_WORDS = ('one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|'
                'sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred')
NUM = (r'(?:\d+(?:\.\d+)?|(?:' + NUMBER_WORDS + r')(?:[ -](?:one|two|three|four|five|six|seven|eight|nine))?'
       r'|a few|a couple of|several|a|an)')
UNIT = r'(?:business\s+|working\s+|calendar\s+)?(?:hours?|hrs?|days?|weeks?)\b'
# Response-time phrasing. Shared by escalation, conduct, security and whole-file GOVERNANCE/CONTRIBUTING checks.
RESPONSE_TIME_FORBIDDEN = [
    re.compile(r'\bwithin\s+(?:\d+|[a-z]+(?:-[a-z]+)?)\s+(?:business\s+|working\s+|calendar\s+)?(?:hours?|days?|weeks?)\b'),
    re.compile(r'\bwithin\s+(?:a\s+few|several|a\s+couple\s+of)\s+(?:business\s+)?(?:hours?|days?|weeks?)\b'),
    re.compile(r'\b(?:given|provided|delivered|issued|sent)\s+in\s+(?:\d+|[a-z]+(?:-[a-z]+)?)\s+(?:business\s+|working\s+)?(?:hours?|days?|weeks?)\b'),
    re.compile(r'\b(?:within|in|by|under|inside|less\s+than|fewer\s+than)\s+(?:(?:under|about|around|less\s+than|fewer\s+than)\s+)?' + NUM + r'[\s-]+' + UNIT),
    re.compile(r'\b' + NUM + r'-(?:hours?|hrs?|days?|weeks?)\b'),
    re.compile(r'\b\d+\s*(?:h|hrs?|hours?)\b'),
    re.compile(r'\bnext\s+(?:business\s+|working\s+|calendar\s+)?day\b'),
    'turnaround', 'response time of', 'respond within',
]
# Whole GOVERNANCE and CONTRIBUTING text also rejects the SLA keyword. CONDUCT and SECURITY do not
# (SECURITY.md truthfully says that a dedicated response SLA has not been established).
SLA_ITEMS = RESPONSE_TIME_FORBIDDEN + [re.compile(r'\bsla\b'), re.compile(r'\bservice[ -]level\b')]
ESCALATION_FORBIDDEN = [
    re.compile(r'\b(?:committee|board|steering|team)s?\b'),
    'approved by',
]
CONDUCT_PUBLIC_RE = re.compile(r'conduct (?:concerns?|reports?)[^.]*\b(?:publicly|in public)\b')
# A sentence that names a reporting channel must not also name a public one (lower case; applied to norm()).
CONDUCT_CHANNEL_TRIGGER_RE = re.compile(r'\b(?:report|reports|reported|reporting|raise|raised|raising|submit|submitted|send|sent|file|filed|channel|contact|comment|comments|commented|route|routed|path)\b')
CONDUCT_PUBLIC_TERM_RE = re.compile(
    r'\bpublic(?:ly)?\b|\bissue threads?\b|\bdiscussion (?:boards?|threads?)\b|\bcomment publicly\b'
    r'|\bdiscord\b|\bslack\b|\bgithub discussions?\b|\bgithub issues?\b|\bopen (?:a |an |the )?(?:github )?issues?\b'
    r'|\bpublic forums?\b')
# Named people in review or approval roles, without an @ handle. Role words are case-insensitive;
# names are capitalised (one or two words). NAME_STOP removes common capitalised sentence starts.
NAME_CORE = r'(?P<name>[A-Z][a-z]+(?![a-z])(?:[ \t]+[A-Z][a-z]+(?![a-z]))?)'
ROLE_WORDS = (r'(?i:reviewer[ \t]+of[ \t]+record|security[ \t]+reviewers?|second[ \t]+maintainers?|'
              r'final[ \t]+approvers?|maintainers?|reviewers?|approvers?|owners?|delegates?|approved)')
NAMED_ROLE_RE = re.compile(r'\b' + ROLE_WORDS + r'(?:[ \t]*:[ \t]*|[ \t]+(?i:is|by)[ \t]+|[ \t]+)(?!@)' + NAME_CORE + r'(?![ \t]+[a-z])')
NAME_VERB_RE = re.compile(r'\b' + NAME_CORE + r'[ \t]+(?:(?i:reviews|approves)\b'
                          r'|(?i:is)[ \t]+(?:(?i:also)[ \t]+)?(?i:a|the)[ \t]+(?:(?i:second|final)[ \t]+)?(?i:maintainer|reviewer|approver)s?\b)')
REVIEW_BY_RE = re.compile(r'\b(?i:reviews?|approvals?)[ \t]+(?i:are|is)[ \t]+(?:(?i:performed|done|given|handled|provided)[ \t]+)?(?i:by)[ \t]+' + NAME_CORE)
NAME_STOP = frozenset({
    'The', 'This', 'These', 'Those', 'That', 'Each', 'Every', 'All', 'Any', 'No', 'None', 'Not', 'Only', 'Also',
    'Maintainer', 'Maintainers', 'Reviewer', 'Reviewers', 'Approver', 'Approvers', 'Owner', 'Owners', 'Delegate', 'Delegates',
    'Contributor', 'Contributors', 'Review', 'Reviews', 'Approval', 'Approvals', 'Approved', 'Changes', 'Reports', 'Report',
    'Security', 'Project', 'Release', 'Releases', 'Issue', 'Issues', 'Pull', 'Roles', 'Role', 'Functional',
    'Second', 'Final', 'Escalated', 'Conduct', 'Enforcement', 'Participation', 'Community', 'Versions',
    'Work', 'Assignment', 'Leaving', 'Unassigned', 'Assigned', 'Do', 'Include', 'Never', 'Public', 'Private'})
NAMED_PERSON_RE = re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+,?[ \t]+(?:reviewer|approver|delegate)s?\b')
GOVERNANCE_FORBIDDEN = {
    'Maintainers': [re.compile(r'anyone (?:may|can) (?:approve|merge)')],
    'Decision escalation': ESCALATION_FORBIDDEN,
    'Contributor conduct': [CONDUCT_PUBLIC_RE],
}
# A forbidden item is excused only when a negation governs it: the nearest preceding negation in the same
# sentence, at most NEGATION_WINDOW_WORDS words away, with no clause break or conjunction between them.
NEGATION_RE = re.compile(r"\b(?:no|not|never|nor|without|cannot|neither|none)\b|n't\b")
NEGATION_BREAK_RE = re.compile(r"[,;:()]|\b(?:and|or|but|while|although|yet|then|so|that|which)\b")
NEGATION_WINDOW_WORDS = 4


def clause_sentences(text):
    """Sentences of a whole document: hard-wrapped lines are joined; bullets and headings are units of their own."""
    out, buf = [], []

    def flush():
        if buf:
            out.extend(p for p in re.split(r'(?<=[.!?])\s+', norm(' '.join(buf))) if p.strip())
            buf.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
        elif HEADING_RE.match(line):
            flush()
            out.append(norm(line))
        elif BULLET_RE.match(line):
            flush()
            buf.append(BULLET_RE.sub('', line, count=1))
        else:
            buf.append(line)
    flush()
    return out


def is_negated(sentence, start):
    """True when a negation governs the match starting at `start` (see NEGATION_WINDOW_WORDS)."""
    prefix = sentence[:start]
    found = list(NEGATION_RE.finditer(prefix))
    if not found:
        return False
    between = prefix[found[-1].end():]
    return not NEGATION_BREAK_RE.search(between) and len(between.split()) <= NEGATION_WINDOW_WORDS


def unnegated_hits(text, items, label):
    """Every occurrence of a forbidden item that no negation governs is an error. Sentence-level, whole text."""
    errors = []
    for sentence in clause_sentences(text):
        for item in items:
            pattern = item if isinstance(item, re.Pattern) else re.compile(re.escape(norm(item)))
            for m in pattern.finditer(sentence):
                if not is_negated(sentence, m.start()):
                    errors.append(f'{label}: forbidden {_label(item)} present: {sentence[:90]!r}')
    return errors


def sla_errors(text, label):
    return unnegated_hits(text, SLA_ITEMS, label)


BACKLOG_NEEDLES = [
    'maintainer coordination', 'no owner until a maintainer records the claim',
    '`.github/issue_template/`', '`assignees:`', 'auto-assign']
# One structured predicate per required property; each must be satisfied by some sentence.
BACKLOG_PROPERTIES = [
    ('assignment never hides backlog',
     re.compile(r'\bassign\w*\b.*\b(?:never|does not|do not)\s+hides?\b.*\bbacklog\b')),
    ('assigned issues stay visible in the live Project backlog',
     re.compile(r'\bassigned\b.*\bvisible\b.*\bproject backlog\b')),
    ('unassigned issues stay visible as unassigned',
     re.compile(r'\bunassigned\b.*\bvisible\b.*\bunassigned\b')),
    ('leaving an issue unassigned is intentional',
     re.compile(r'\bunassigned\b[^.]*\bis intentional\b')),
]
CONTRIB_BACKLOG_RE = re.compile(r'\bunassigned (?:backlog|issues?)\b.*\bis intentional\b')
# Weakenings that must never appear in the backlog section (GOVERNANCE) or the CONTRIBUTING intro.
BACKLOG_FORBIDDEN = [
    'may hide', 'hidden', 'removed from', 'archive', 'not intentional',
    'not visible', 'no longer visible', 'invisible', 'not shown', 'cannot be seen',
    'deleted', 'purged', 'expire', 'closed after', 'removed after', 'auto-close', 'stale',
    'must be assigned', 'must have an owner', 'every issue must',
    'excluded from', 'filtered out', 'moved out of', 'not listed', 'cleaned up']

CONTRIBUTING_HEADINGS = ('Definition of Ready', 'Definition of Done', 'Review')
DOR_NEEDLES = [
    'requirements and scope are bounded', 'acceptance is testable', 'contracts exist',
    'prerequisite native blockers are satisfied', 'validation is defined',
    'mocked platform checks are not real discord or vps verification',
]
DOD_NEEDLES = [
    'deliverable exists', 'applicable tests pass', 'documentation are updated',
    'actual review is complete', 'relevant pr is merged', 'post-merge/platform checks are evidenced',
    'close only when criteria are met',
]
DOD_FORBIDDEN = ['may be skipped', 'review is optional', 'review may be waived', 'actual review is optional']
REVIEW_NEEDLES = [
    'security expertise', 'realtime and canvas expertise', 'data expertise',
    'platform expertise', 'do not invent contributors or approvals',
]
PR_NEEDLES = [
    '## Validation and evidence',
    'State exact commands, revision/environment, results and limitations',
    '## Security and compatibility',
    '- [ ] Acceptance criteria verified',
    '- [ ] Documentation updated',
    '- [ ] Required functional/security review complete',
    '- [ ] No credentials or private board data included',
    'Distinguish mocks from real Discord/GoDaddy evidence',
]
CONDUCT_NEEDLES = [
    'Report conduct concerns privately', 'contact method published on the maintainer',
    'Do not post sensitive details publicly', 'Maintainer: @CompleteDotTech',
]
TASK_NEEDLES = [
    '`python3 -B -m unittest discover -s tests/verification -v`',
    '[isolated qualification bootstrap](#executable-qualification)',
    '`python3 scripts/github-bootstrap/validate.py`',
    '`python3 -I scripts/verification/check_licenses.py`',
    'of this deliverable are not claimed',
    'cannot prove the semantic quality of the wording',
]
TASK_FORBIDDEN = ['assert each clause', 'prove each clause', 'proves each clause']


def read(rel):
    return (REPO / rel).read_text(encoding='utf-8')


def norm(text):
    return ' '.join(text.replace('→', '->').lower().split())


def _found(item, haystack):
    if isinstance(item, re.Pattern):
        return item.search(haystack) is not None
    return norm(item) in haystack


def _label(item):
    return item.pattern if isinstance(item, re.Pattern) else repr(item)


def missing(text, needles, label):
    haystack = norm(text)
    return [f'{label}: missing {_label(n)}' for n in needles if not _found(n, haystack)]


def forbidden_errors(text, items, label):
    haystack = norm(text)
    return [f'{label}: forbidden {_label(i)} present' for i in items if _found(i, haystack)]


def heading_names(text):
    names = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            names.append(m.group(2).strip())
    return names


def duplicate_headings(text):
    seen, dups = set(), []
    for name in heading_names(text):
        if name in seen and name not in dups:
            dups.append(name)
        seen.add(name)
    return dups


def dup_errors(text, label):
    return [f'{label}: duplicate heading {h!r}' for h in duplicate_headings(text)]


def sections(text):
    """Map heading text to its body. Use with dup_errors: a duplicated heading is a failure, never 'last one wins'."""
    found, current, body = {}, None, []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if current is not None:
                found[current] = '\n'.join(body)
            current, body = m.group(2).strip(), []
        elif current is not None:
            body.append(line)
    if current is not None:
        found[current] = '\n'.join(body)
    return found


def missing_section(text, heading, needles, label):
    if heading in duplicate_headings(text):
        return [f'{label}: duplicate heading {heading!r}']
    body = sections(text).get(heading)
    if body is None:
        return [f'{label}: missing heading {heading!r}']
    return missing(body, needles, f'{label} section {heading!r}')


def forbidden_in_section(text, heading, items, label):
    if heading in duplicate_headings(text):
        return [f'{label}: duplicate heading {heading!r}']
    body = sections(text).get(heading)
    if body is None:
        return [f'{label}: missing heading {heading!r}']
    return forbidden_errors(body, items, f'{label} section {heading!r}')


def sentences(text):
    out = []
    for line in text.splitlines():
        line = BULLET_RE.sub('', line).strip()
        for part in re.split(r'(?<=[.!?])\s+', line):
            if part.strip():
                out.append(norm(part))
    return out


def preamble(text):
    """Text between the first heading (the title) and the next heading."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING_RE.match(line)), len(lines)) + 1
    out = []
    for line in lines[start:]:
        if HEADING_RE.match(line):
            break
        out.append(line)
    return '\n'.join(out)


def check_governance_backlog(text):
    label = f'{GOVERNANCE} {BACKLOG_HEADING!r}'
    if BACKLOG_HEADING in duplicate_headings(text):
        return [f'{GOVERNANCE}: duplicate heading {BACKLOG_HEADING!r}']
    body = sections(text).get(BACKLOG_HEADING)
    if body is None:
        return [f'{GOVERNANCE}: missing heading {BACKLOG_HEADING!r}']
    sents = sentences(body)
    errors = []
    for prop, pattern in BACKLOG_PROPERTIES:
        if not any(pattern.search(s) for s in sents):
            errors.append(f'{label}: no sentence states that {prop}')
    errors += unnegated_hits(body, BACKLOG_FORBIDDEN, label)
    errors += missing(body, BACKLOG_NEEDLES, label)
    return errors


def check_contributing_backlog(text):
    intro = preamble(text)
    errors = []
    if not any(CONTRIB_BACKLOG_RE.search(s) for s in sentences(intro)):
        errors.append(f'{CONTRIBUTING}: no sentence states that unassigned backlog is intentional')
    errors += unnegated_hits(intro, BACKLOG_FORBIDDEN, CONTRIBUTING)
    return errors


def check_backlog_visibility(governance_text, contributing_text):
    return check_governance_backlog(governance_text) + check_contributing_backlog(contributing_text)


def check_governance(text):
    errors = dup_errors(text, GOVERNANCE)
    errors += missing(text, GOVERNANCE_TOP_NEEDLES, GOVERNANCE)
    for heading, needles in GOVERNANCE_CLAUSES.items():
        errors += missing_section(text, heading, needles, GOVERNANCE)
    for heading, items in GOVERNANCE_FORBIDDEN.items():
        errors += forbidden_in_section(text, heading, items, GOVERNANCE)
    errors += sla_errors(text, GOVERNANCE)
    errors += check_governance_backlog(text)
    errors += public_report_channel_errors(sections(text).get('Contributor conduct', ''), GOVERNANCE)
    errors += named_person_errors(text, GOVERNANCE)
    return errors


def check_contributing(text):
    errors = dup_errors(text, CONTRIBUTING)
    errors += missing(text, ['GOVERNANCE.md'], CONTRIBUTING)
    errors += missing_section(text, 'Definition of Ready', DOR_NEEDLES, CONTRIBUTING)
    errors += missing_section(text, 'Definition of Done', DOD_NEEDLES, CONTRIBUTING)
    errors += forbidden_in_section(text, 'Definition of Done', DOD_FORBIDDEN, CONTRIBUTING)
    errors += missing_section(text, 'Review', REVIEW_NEEDLES, CONTRIBUTING)
    errors += sla_errors(text, CONTRIBUTING)
    errors += check_contributing_backlog(text)
    errors += named_person_errors(text, CONTRIBUTING)
    return errors


def public_report_channel_errors(text, label):
    errors = []
    for sentence in sentences(text):
        if CONDUCT_CHANNEL_TRIGGER_RE.search(sentence) and CONDUCT_PUBLIC_TERM_RE.search(sentence):
            errors.append(f'{label}: public channel named alongside conduct reporting: {sentence[:90]!r}')
    return errors


def named_person_errors(text, label):
    found = [m.group(0) for pattern in (NAMED_ROLE_RE, NAME_VERB_RE, REVIEW_BY_RE) for m in pattern.finditer(text)
             if m.group('name').split()[0] not in NAME_STOP]
    found += [m.group(0) for m in NAMED_PERSON_RE.finditer(text)]
    return [f'{label}: named review or approval role without @ handle: {item!r}' for item in found]


def check_conduct(text):
    return (dup_errors(text, CONDUCT)
            + missing(text, CONDUCT_NEEDLES, CONDUCT)
            + forbidden_errors(text, [CONDUCT_PUBLIC_RE], CONDUCT)
            + unnegated_hits(text, RESPONSE_TIME_FORBIDDEN, CONDUCT)
            + public_report_channel_errors(text, CONDUCT)
            + named_person_errors(text, CONDUCT))


def check_security(text):
    return (dup_errors(text, SECURITY)
            + unnegated_hits(text, RESPONSE_TIME_FORBIDDEN, SECURITY)
            + named_person_errors(text, SECURITY))


def check_pr_template(text):
    return missing(text, PR_NEEDLES, PR_TEMPLATE)


def check_task_record(text):
    return (dup_errors(text, TASK_DOC)
            + missing_section(text, TASK_HEADING, TASK_NEEDLES, TASK_DOC)
            + forbidden_in_section(text, TASK_HEADING, TASK_FORBIDDEN, TASK_DOC))


def task_section(text):
    return sections(text).get(TASK_HEADING, '')


def check_codeowners(text):
    errors, rules = [], 0
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) < 2:
            errors.append(f'{CODEOWNERS}:{number}: rule has no owner')
            continue
        rules += 1
        if parts[1:] != [MAINTAINER]:
            errors.append(f'{CODEOWNERS}:{number}: owners must be exactly {MAINTAINER}, got {parts[1:]}')
    if rules == 0:
        errors.append(f'{CODEOWNERS}: no rules')
    if not re.search(r'^\*\s+@CompleteDotTech\s*$', text, re.MULTILINE):
        errors.append(f'{CODEOWNERS}: missing catch-all "* {MAINTAINER}" rule')
    return errors


def check_issue_templates(templates):
    """templates maps a relative file name (any extension, or none) to its text."""
    if not templates:
        return ['issue templates: none found']
    errors = []
    for name, text in sorted(templates.items()):
        if ASSIGNEES_KEY_RE.search(text):
            errors.append(f'{name}: assignment key present (any form)')
        if ASSIGN_HINT_RE.search(text):
            errors.append(f'{name}: assignee or auto-assign hint present')
    return errors


# GitHub issue-template locations: the directories, plus legacy single-file templates in .github/, the root and docs/.
ISSUE_TEMPLATE_DIRS = ('.github/ISSUE_TEMPLATE', '.github/issue_template')
LEGACY_TEMPLATE_FOLDERS = ('.github', '', 'docs')


def load_templates(root=REPO):
    """Return {repo-relative posix path: text} for every issue-template file GitHub may read."""
    paths = []
    for rel in ISSUE_TEMPLATE_DIRS:
        base = root / rel
        if base.is_dir():
            paths += [p for p in base.rglob('*') if p.is_file()]
    for rel in LEGACY_TEMPLATE_FOLDERS:
        folder = root / rel
        if folder.is_dir():
            paths += [p for p in folder.iterdir() if p.is_file() and p.name.lower().startswith('issue_template.')]
    templates = {}
    for path in sorted(set(paths)):
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        templates[path.relative_to(root).as_posix()] = text
    return templates


def is_at_lookalike(ch):
    return ch == '@' or 'COMMERCIAL AT' in unicodedata.name(ch, '')


def _allowed_handle_at(text, i):
    """True only for the exact ASCII handle, not part of an email, path, team or longer token."""
    before = text[i - 1] if i > 0 else ' '
    if before.isalnum() or before in '_.@/-' or unicodedata.category(before) == 'Cf':
        return False
    rest = text[i + 1:]
    if not rest.startswith(MAINTAINER_NAME):
        return False
    after = rest[len(MAINTAINER_NAME):len(MAINTAINER_NAME) + 2]
    if not after:
        return True
    nxt = after[0]
    if nxt.isalnum() or nxt in '_-/' or unicodedata.category(nxt) == 'Cf':
        return False
    return not (nxt == '.' and len(after) > 1 and after[1].isalnum())


def check_identity_surface(name, text):
    errors = [f'{name}: email address present ({m.group(0)!r})' for m in EMAIL_RE.finditer(text)]
    for i, ch in enumerate(text):
        if not is_at_lookalike(ch):
            continue
        where = f'{name}: at-sign U+{ord(ch):04X} at offset {i}'
        if ch != '@':
            errors.append(f'{where} is a lookalike, not ASCII "@"')
        elif not _allowed_handle_at(text, i):
            errors.append(f'{where} is not the exact handle {MAINTAINER}')
    return errors


def identity_files_text():
    files = {rel: read(rel) for rel in IDENTITY_FILES}
    files[TASK_DOC] = task_section(read(TASK_DOC))
    for name, text in load_templates().items():
        files[name] = text
    return files


class RepositoryGovernanceTests(unittest.TestCase):
    def test_governance_clauses_present_and_unforbidden(self):
        self.assertEqual(check_governance(read(GOVERNANCE)), [])

    def test_backlog_visibility_clause(self):
        self.assertEqual(check_backlog_visibility(read(GOVERNANCE), read(CONTRIBUTING)), [])

    def test_contributing_definition_of_ready_done_and_review(self):
        self.assertEqual(check_contributing(read(CONTRIBUTING)), [])

    def test_code_of_conduct_private_reporting(self):
        self.assertEqual(check_conduct(read(CONDUCT)), [])

    def test_codeowners_contains_only_known_maintainer(self):
        self.assertEqual(check_codeowners(read(CODEOWNERS)), [])

    def test_issue_templates_never_assign(self):
        templates = load_templates()
        self.assertTrue(templates, 'no issue templates found; check would be vacuous')
        self.assertIn(f'{ISSUE_TEMPLATE_DIR}/config.yml', templates)
        self.assertEqual(check_issue_templates(templates), [])

    def test_pr_template_review_and_evidence_checklist(self):
        self.assertEqual(check_pr_template(read(PR_TEMPLATE)), [])

    def test_identity_surface_no_emails_only_maintainer_handles(self):
        for name, text in identity_files_text().items():
            with self.subTest(file=name):
                self.assertEqual(check_identity_surface(name, text), [])

    def test_workstream_record_has_commands_and_limits(self):
        self.assertEqual(check_task_record(read(TASK_DOC)), [])

    def test_security_response_time_and_role_text(self):
        self.assertEqual(check_security(read(SECURITY)), [])


def templates_under(files):
    """Write files at repo-relative paths under a temporary root and load them with the real loader."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        return load_templates(root)


def mutate(text, old, new=''):
    if text.count(old) != 1:
        raise AssertionError(f'mutation target must occur once, found {text.count(old)}: {old!r}')
    return text.replace(old, new, 1)


def templates_from(files):
    """Write files under a temporary issue-template directory and load them with the real loader."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / ISSUE_TEMPLATE_DIR
        for rel, text in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        return load_templates(Path(tmp))


BACKLOG_WEAKENINGS = [
    ('assignment may hide backlog',
     'Assignment never hides backlog', 'Assignment may hide backlog'),
    ('assigned issue removed from the live backlog',
     'an assigned issue stays visible in the live Project backlog',
     'an assigned issue is removed from the live Project backlog'),
    ('unassigned issues archived',
     'unassigned issues stay visible as unassigned',
     'unassigned issues may be archived out of the Project'),
    ('unassigned leaving marked not intentional',
     'Leaving an issue unassigned is intentional.',
     'Leaving an issue unassigned is not intentional; unassigned issues are hidden.'),
    ('removal rule appended',
     'Leaving an issue unassigned is intentional.',
     'Leaving an issue unassigned is intentional. Unassigned issues older than 30 days are closed and removed from the Project.'),
    ('whole visibility rule replaced',
     'Assignment never hides backlog: an assigned issue stays visible in the live Project backlog, '
     'and unassigned issues stay visible as unassigned. Leaving an issue unassigned is intentional.',
     'Work is tracked in the Project.'),
    ('every issue must have an owner',
     'An issue has no owner until a maintainer records the claim.',
     'Every issue must have an owner.'),
    ('no-owner-until-claim sentence removed',
     'An issue has no owner until a maintainer records the claim.', ''),
]
CONTRIB_BACKLOG_WEAKENINGS = [
    ('unassigned backlog cleaned up', 'unassigned backlog is intentional', 'unassigned backlog is cleaned up'),
    ('all backlog must be assigned', 'unassigned backlog is intentional', 'all backlog must be assigned'),
    ('unassigned backlog not intentional', 'unassigned backlog is intentional', 'unassigned backlog is not intentional'),
]


class NegativeMutationTests(unittest.TestCase):
    """Each mutation removes or adds one documented requirement; the same checks must fail."""

    def test_baseline_passes_the_same_checks(self):
        self.assertEqual(check_governance(read(GOVERNANCE)), [])
        self.assertEqual(check_backlog_visibility(read(GOVERNANCE), read(CONTRIBUTING)), [])
        self.assertEqual(check_contributing(read(CONTRIBUTING)), [])
        self.assertEqual(check_conduct(read(CONDUCT)), [])
        self.assertEqual(check_codeowners(read(CODEOWNERS)), [])
        self.assertEqual(check_issue_templates(load_templates()), [])
        self.assertEqual(check_pr_template(read(PR_TEMPLATE)), [])
        self.assertEqual(check_task_record(read(TASK_DOC)), [])
        self.assertEqual(check_identity_surface(SECURITY, read(SECURITY)), [])
        self.assertEqual(check_security(read(SECURITY)), [])

    # --- 1. backlog visibility (structured sentence checks + forbidden weakenings) ---

    def test_backlog_weakenings_fail_governance(self):
        governance, contributing = read(GOVERNANCE), read(CONTRIBUTING)
        for label, old, new in BACKLOG_WEAKENINGS:
            with self.subTest(weakening=label):
                mutated = mutate(governance, old, new)
                self.assertTrue(check_backlog_visibility(mutated, contributing))

    def test_contributing_backlog_weakenings_fail(self):
        governance, contributing = read(GOVERNANCE), read(CONTRIBUTING)
        for label, old, new in CONTRIB_BACKLOG_WEAKENINGS:
            with self.subTest(weakening=label):
                mutated = mutate(contributing, old, new)
                self.assertTrue(check_backlog_visibility(governance, mutated))

    def test_reworded_backlog_sentence_still_passes(self):
        mutated = mutate(read(GOVERNANCE),
                         'Assignment never hides backlog: an assigned issue stays visible in the live Project backlog',
                         'Assigning an issue never hides it from the backlog: an assigned issue remains visible '
                         'in the live Project backlog')
        self.assertEqual(check_backlog_visibility(mutated, read(CONTRIBUTING)), [])

    def test_arrow_rewording_still_passes(self):
        mutated = read(GOVERNANCE).replace('->', '→')
        self.assertEqual(check_governance(mutated), [])

    # --- 2. template scan (every file, any extension, front matter, inline flow, hints) ---

    def test_assignees_key_added_to_bug_template_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml')
        self.assertTrue(check_issue_templates({'bug.yml': 'assignees: [CompleteDotTech]\n' + bug}))

    def test_indented_assignees_key_in_list_item_fails(self):
        feature = read(f'{ISSUE_TEMPLATE_DIR}/feature.yml')
        mutated = mutate(feature, 'labels: ["type: feature"]', 'labels: ["type: feature"]\n  - assignees: CompleteDotTech')
        self.assertTrue(check_issue_templates({'feature.yml': mutated}))

    def test_yaml_extension_template_with_assignees_fails(self):
        templates = templates_from({'bug.yml': read(f'{ISSUE_TEMPLATE_DIR}/bug.yml'),
                                    'task.yaml': 'name: Task\nassignees: alice\n'})
        self.assertIn(f'{ISSUE_TEMPLATE_DIR}/task.yaml', templates)
        self.assertTrue(any('task.yaml' in e for e in check_issue_templates(templates)))

    def test_markdown_front_matter_assignees_fails(self):
        templates = templates_from({'task.md': '---\nname: Task\nassignees: alice\n---\nBody\n'})
        self.assertTrue(check_issue_templates(templates))

    def test_inline_flow_assignees_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml') + '\nextra: {assignees: alice}\n'
        self.assertTrue(check_issue_templates({'bug.yml': bug}))

    def test_quoted_assignees_key_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml') + '\n"assignees": ["alice"]\n'
        self.assertTrue(check_issue_templates({'bug.yml': bug}))

    def test_extensionless_template_with_assignees_fails(self):
        templates = templates_from({'task': 'assignees: alice\n'})
        self.assertTrue(check_issue_templates(templates))

    def test_auto_assign_hint_in_template_fails(self):
        feature = read(f'{ISSUE_TEMPLATE_DIR}/feature.yml') + '\n# auto-assign: on\n'
        self.assertTrue(check_issue_templates({'feature.yml': feature}))

    def test_assignees_in_config_yml_fails(self):
        config = read(f'{ISSUE_TEMPLATE_DIR}/config.yml') + '\nassignees: alice\n'
        self.assertTrue(any('config.yml' in e for e in check_issue_templates({'config.yml': config})))

    def test_nested_template_file_is_scanned(self):
        templates = templates_from({'nested/task.yml': 'assignees: alice\n'})
        self.assertTrue(check_issue_templates(templates))

    # --- 3. identity surface (exact handle only; no emails; lookalike at-signs) ---

    def test_email_added_to_governance_fails(self):
        self.assertTrue(check_identity_surface(GOVERNANCE, read(GOVERNANCE) + '\nSecurity contact: maintainer@example.org\n'))

    def test_second_handle_added_to_governance_fails(self):
        self.assertTrue(check_identity_surface(GOVERNANCE, read(GOVERNANCE) + '\nReviewer of record: @new-reviewer\n'))

    def test_email_added_to_issue_template_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml') + '\n# contact dev@example.com\n'
        self.assertTrue(check_identity_surface('bug.yml', bug))

    def test_security_mailbox_added_fails(self):
        text = read(SECURITY) + '\nSecurity mailbox: security@guildboard.example\n'
        self.assertTrue(check_identity_surface(SECURITY, text))

    def test_handle_added_to_security_fails(self):
        self.assertTrue(check_identity_surface(SECURITY, read(SECURITY) + '\nContact @alice.\n'))

    def test_handle_added_to_readme_fails(self):
        self.assertTrue(check_identity_surface(README, read(README) + '\nContact @alice.\n'))

    def test_handle_added_to_t0_governance_entry_fails(self):
        section = task_section(read(TASK_DOC))
        mutated = mutate(section, 'Limits: these checks', 'Approved by @alice. Limits: these checks')
        self.assertTrue(check_identity_surface(TASK_DOC, mutated))

    def test_team_style_handle_fails(self):
        mutated = mutate(read(GOVERNANCE), 'is @CompleteDotTech.', 'is @CompleteDotTech/core.')
        self.assertTrue(check_identity_surface(GOVERNANCE, mutated))

    def test_fullwidth_at_sign_fails(self):
        self.assertTrue(check_identity_surface(README, read(README) + '\nContact ＠alice.\n'))

    def test_fullwidth_at_sign_with_maintainer_name_fails(self):
        self.assertTrue(check_identity_surface(README, read(README) + '\nContact ＠CompleteDotTech.\n'))

    def test_underscore_prefixed_handle_fails(self):
        self.assertTrue(check_identity_surface(README, read(README) + '\nContact _@alice.\n'))

    def test_zero_width_split_maintainer_handle_fails(self):
        self.assertTrue(check_identity_surface(GOVERNANCE, read(GOVERNANCE) + '\n@Complete​DotTech\n'))

    def test_exact_maintainer_handle_with_punctuation_passes(self):
        self.assertEqual(check_identity_surface(GOVERNANCE, 'Maintainer `@CompleteDotTech`, `@CompleteDotTech.`\n'), [])

    # --- 4. duplicate headings fail (no last-one-wins) ---

    def test_duplicate_heading_fails_governance(self):
        mutated = read(GOVERNANCE) + '\n## Maintainers\n\nAnyone may approve.\n'
        errors = check_governance(mutated)
        self.assertTrue(any('duplicate heading' in e for e in errors), errors)

    def test_duplicate_heading_fails_contributing(self):
        mutated = read(CONTRIBUTING) + '\n## Definition of Done\n\nReview may be skipped.\n'
        errors = check_contributing(mutated)
        self.assertTrue(any('duplicate heading' in e for e in errors), errors)

    def test_sections_helper_reports_duplicates(self):
        self.assertEqual(duplicate_headings('# A\n\n## B\n\nx\n\n## B\n'), ['B'])
        self.assertEqual(duplicate_headings('# A\n\n## B\n'), [])

    # --- 5. escalation, owner, conduct ---

    def test_escalation_step1_removed_fails(self):
        mutated = mutate(read(GOVERNANCE),
                         'A contributor raises a scope, behavior, acceptance or sequencing question on the issue that carries the stable GB identifier.',
                         'Questions are discussed informally.')
        self.assertTrue(any('contributor raises' in e for e in check_governance(mutated)))

    def test_no_owner_until_claim_removed_fails(self):
        mutated = mutate(read(GOVERNANCE), 'An issue has no owner until a maintainer records the claim.', '')
        self.assertTrue(check_governance(mutated))

    def test_escalation_sla_fails(self):
        mutated = mutate(read(GOVERNANCE), 'No response time is committed and',
                         'Maintainers respond within 48 hours. No response time is committed and')
        self.assertTrue(check_governance(mutated))

    def test_escalation_committee_decision_fails(self):
        mutated = mutate(read(GOVERNANCE), 'and no other decision-maker is named.',
                         'and the steering committee decides.')
        self.assertTrue(check_governance(mutated))

    def test_escalation_list_removed_fails(self):
        mutated = mutate(read(GOVERNANCE), 'Escalated: scope and sequencing disputes', 'Routine matters:')
        self.assertTrue(any('Escalated' in e for e in check_governance(mutated)))

    def test_conduct_reported_publicly_in_governance_fails(self):
        mutated = mutate(read(GOVERNANCE), 'Conduct concerns are reported privately',
                         'Conduct concerns are reported publicly')
        self.assertTrue(check_governance(mutated))

    def test_private_conduct_reporting_reversed_in_coc_fails(self):
        mutated = mutate(read(CONDUCT), 'Report conduct concerns privately', 'Report conduct concerns in public')
        self.assertTrue(check_conduct(mutated))

    def test_public_posting_of_sensitive_details_allowed_fails(self):
        mutated = mutate(read(CONDUCT), 'Do not post sensitive details publicly.', 'Post details as needed.')
        self.assertTrue(check_conduct(mutated))

    # --- other clauses (unchanged coverage) ---

    def test_assignees_key_removed_check_does_not_apply_to_clean_templates(self):
        self.assertEqual(check_issue_templates(load_templates()), [])

    def test_removed_definition_of_done_heading_fails(self):
        mutated = mutate(read(CONTRIBUTING), '## Definition of Done', '## Finish notes')
        self.assertTrue(any('Definition of Done' in e for e in check_contributing(mutated)))

    def test_removed_definition_of_done_criterion_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'Deliverable exists, ', '')
        self.assertTrue(any('deliverable exists' in e for e in check_contributing(mutated)))

    def test_definition_of_done_review_made_optional_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'actual review is complete', 'actual review is optional')
        self.assertTrue(check_contributing(mutated))

    def test_removed_definition_of_ready_criterion_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'and validation is defined.', 'and validation is pending.')
        self.assertTrue(any('validation is defined' in e for e in check_contributing(mutated)))

    def test_removed_governance_section_heading_fails(self):
        mutated = mutate(read(GOVERNANCE), '## Decision escalation', '## Escalation notes')
        self.assertTrue(any('Decision escalation' in e for e in check_governance(mutated)))

    def test_removed_no_other_approvers_statement_fails(self):
        mutated = mutate(read(GOVERNANCE), 'No other contributors or approvers have been assigned.', '')
        self.assertTrue(check_governance(mutated))

    def test_second_codeowners_handle_fails(self):
        mutated = mutate(read(CODEOWNERS), '* @CompleteDotTech', '* @CompleteDotTech @second-reviewer')
        self.assertTrue(check_codeowners(mutated))

    def test_codeowners_extra_rule_with_other_owner_fails(self):
        codeowners = read(CODEOWNERS) + 'docs/ @other-owner\n'
        self.assertTrue(any('other-owner' in e or 'owners must be' in e for e in check_codeowners(codeowners)))

    def test_codeowners_without_catch_all_fails(self):
        self.assertTrue(check_codeowners('docs/ @CompleteDotTech\n'))

    def test_pr_review_checkbox_removed_fails(self):
        mutated = mutate(read(PR_TEMPLATE), '- [ ] Required functional/security review complete\n', '')
        self.assertTrue(any('review complete' in e for e in check_pr_template(mutated)))

    def test_contributing_governance_crossref_removed_fails(self):
        mutated = mutate(read(CONTRIBUTING), '[GOVERNANCE.md](GOVERNANCE.md)', 'the governance notes')
        self.assertTrue(check_contributing(mutated))

    def test_task_record_without_limits_fails(self):
        mutated = mutate(read(TASK_DOC), 'of this deliverable are not claimed', 'of this deliverable are claimed')
        self.assertTrue(check_task_record(mutated))

    def test_task_record_claiming_clause_assertion_fails(self):
        mutated = mutate(read(TASK_DOC), 'cannot prove the semantic quality of the wording',
                         'prove each clause')
        self.assertTrue(check_task_record(mutated))

    def test_task_record_original_assert_each_clause_wording_fails(self):
        mutated = mutate(read(TASK_DOC), 'They cannot prove the semantic quality of the wording.',
                         'They assert each clause.')
        self.assertTrue(check_task_record(mutated))


    # --- 6. escapes found by the independent verifier (D2-D10); each must fail ---

    def test_legacy_single_file_templates_are_scanned(self):
        for rel in ('ISSUE_TEMPLATE.md', '.github/ISSUE_TEMPLATE.md', '.github/ISSUE_TEMPLATE.yml',
                    '.github/issue_template.yaml', '.github/issue_template/task.yml',
                    'docs/ISSUE_TEMPLATE.md', 'docs/issue_template.yml'):
            with self.subTest(template=rel):
                templates = templates_under({rel: 'name: Task\nassignees: alice\n'})
                self.assertIn(rel, templates)
                self.assertTrue(check_issue_templates(templates))

    def test_assignment_keys_are_hints_in_templates(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml')
        for line in ('assign: alice', 'assigned: alice', 'assigned_to: alice', 'owner: alice',
                     '  - assign: alice', '"owner": alice', '{assigned_to: alice}'):
            with self.subTest(key=line):
                self.assertTrue(check_issue_templates({'bug.yml': bug + '\n' + line + '\n'}))

    def test_backlog_negated_visibility_fails(self):
        governance, contributing = read(GOVERNANCE), read(CONTRIBUTING)
        for sentence in ('Assigned issues are not visible in the live Project backlog.',
                         'Unassigned issues are no longer visible as unassigned.',
                         'Unassigned issues are invisible as unassigned.',
                         'Unassigned issues are not shown as unassigned.',
                         'Assigned issues cannot be seen in the live Project backlog.'):
            with self.subTest(sentence=sentence):
                mutated = mutate(governance, 'Leaving an issue unassigned is intentional.',
                                 'Leaving an issue unassigned is intentional. ' + sentence)
                self.assertTrue(check_backlog_visibility(mutated, contributing))

    def test_backlog_retention_and_deletion_rules_fail(self):
        governance, contributing = read(GOVERNANCE), read(CONTRIBUTING)
        for sentence in ('Unassigned issues are deleted after 30 days.',
                         'Unassigned issues are purged monthly.',
                         'Unassigned issues expire after 90 days.',
                         'Unassigned issues are closed after 60 days.',
                         'Unassigned issues are removed after 30 days.',
                         'Unassigned issues get auto-close after 30 days.',
                         'Stale unassigned issues are reviewed for removal.'):
            with self.subTest(sentence=sentence):
                mutated = mutate(governance, 'Leaving an issue unassigned is intentional.',
                                 'Leaving an issue unassigned is intentional. ' + sentence)
                self.assertTrue(check_backlog_visibility(mutated, contributing))

    def test_does_not_hide_is_equivalent_to_never_hides(self):
        mutated = mutate(read(GOVERNANCE), 'Assignment never hides backlog', 'Assignment does not hide backlog')
        self.assertEqual(check_backlog_visibility(mutated, read(CONTRIBUTING)), [])

    def test_response_time_phrasing_in_escalation_fails(self):
        for sentence in ('Maintainers respond within two business days.', 'Responses are given in 2 days.',
                         'Reports receive a turnaround of one week.', 'The response time of three days applies.',
                         'Maintainers respond within 48 hours.'):
            with self.subTest(sentence=sentence):
                mutated = mutate(read(GOVERNANCE), 'No response time is committed and',
                                 sentence + ' No response time is committed and')
                self.assertTrue(check_governance(mutated))

    def test_response_time_phrasing_in_conduct_and_security_fails(self):
        for sentence in ('Reports are acknowledged within three hours.', 'Replies are given in 2 weeks.',
                         'Reports have a 5-day turnaround.'):
            with self.subTest(sentence=sentence):
                self.assertTrue(check_conduct(read(CONDUCT) + '\n' + sentence + '\n'))
                self.assertTrue(check_security(read(SECURITY) + '\n' + sentence + '\n'))

    def test_public_channel_for_conduct_reports_fails(self):
        for sentence in ('Conduct reports may also be posted in public issue threads.',
                         'Report conduct concerns on the discussion board.',
                         'Reporters may comment publicly on the issue.'):
            with self.subTest(sentence=sentence):
                self.assertTrue(check_conduct(read(CONDUCT) + '\n' + sentence + '\n'))
        mutated = mutate(read(GOVERNANCE), 'Conduct concerns are reported privately through the path described there.',
                         'Conduct concerns are reported privately through the path described there. '
                         'Conduct concerns may also be raised in a public issue thread.')
        self.assertTrue(check_governance(mutated))

    def test_named_person_review_roles_without_handle_fail(self):
        cases = [
            (GOVERNANCE, read(GOVERNANCE) + '\nReviewer of record: Alice Smith\n', check_governance),
            (GOVERNANCE, read(GOVERNANCE) + '\nAlice Smith, reviewer.\n', check_governance),
            (CONTRIBUTING, read(CONTRIBUTING) + '\nApprover: Bob Jones\n', check_contributing),
            (CONDUCT, read(CONDUCT) + '\nApproved by Carol Lee.\n', check_conduct),
            (SECURITY, read(SECURITY) + '\nReviewers: Dana Kim\n', check_security),
        ]
        for name, text, check in cases:
            with self.subTest(file=name, check=check.__name__):
                self.assertTrue(check(text))

    def test_mocked_checks_rule_removal_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'Mocked platform checks are not real Discord or VPS verification.', '')
        self.assertTrue(check_contributing(mutated))
        mutated = mutate(read(PR_TEMPLATE), 'Distinguish mocks from real Discord/GoDaddy evidence.', '')
        self.assertTrue(check_pr_template(mutated))


# --- Reviewer escapes (PR520 F1-F4). Each escape is a negative case; negated and legitimate forms are positive cases.
SLA_SENTENCES = [
    'Maintainers respond within two business days.',
    'Maintainers respond within 2 business days.',
    'Maintainers respond in 48 hours.',
    'Maintainers respond in forty-eight hours.',
    'Maintainers respond in under 48 hours.',
    'Maintainers respond in under forty-eight hours.',
    'Maintainers reply within two days.',
    'Maintainers reply within 2 days.',
    'Reviews are completed within two business days.',
    'Reports are acknowledged within 72h.',
    'Reports are acknowledged within 72 hrs.',
    'Reports get a 72-hour acknowledgement.',
    'Reports get a seventy-two-hour acknowledgement.',
    'Escalations are answered by the next business day.',
    'Conduct reports are acknowledged within two days.',
    'Reports get a reply in two business days.',
    'Maintainers acknowledge claims in 1 hour.',
    'An SLA of 48 hours applies.',
    'A service-level target of 48 hours applies.',
]
GOVERNANCE_SLA_ANCHORS = [
    ('GOVERNANCE opening paragraph', 'Maintain a changelog and deprecation policy before stable release.'),
    ('Maintainers', 'CODEOWNERS is changed only to name an actual known maintainer.'),
    ('Review roles', 'Roles describe required expertise and do not create reviewers or approvals.'),
    ('Decision escalation', 'Escalation path: contributor -> issue or ADR discussion -> maintainer review.'),
    ('Contributor conduct', 'Enforcement is proportionate and documented by the maintainer.'),
    ('Issue ownership', 'An issue has no owner until a maintainer records the claim.'),
]
CONTRIBUTING_SLA_ANCHORS = [
    ('preamble', 'Decision escalation and issue ownership rules are in [GOVERNANCE.md](GOVERNANCE.md).'),
    ('Definition of Ready', 'Epics and broad features are not ready-to-code units.'),
    ('Definition of Done', 'Close only when criteria are met.'),
    ('Review', 'No paid autonomous coding-agent delegation is configured.'),
    ('Metadata', 'Stable manifest IDs survive issue renaming.'),
]
NEGATED_SLA_SENTENCES = [
    'No response time is committed.',
    'Maintainers do not promise to respond within 48 hours.',
    'The project does not commit to respond within two business days.',
    'No SLA is committed.',
    'Do not expect replies in under 48 hours.',
]
NAMED_ESCAPES = [
    'Security reviewer: Alice Smith.',
    'Second maintainer: Bob Jones',
    'Final approver is Carol Lee.',
    'REVIEWER: Alice Smith.',
    'maintainer: Alice Smith',
    'Owner: Dana Kim.',
    'Reviewer of record is Eve Stone.',
    'Alice Smith reviews the security changes.',
    'Alice Smith approves releases.',
    'Alice Smith is also a maintainer.',
    'Alice Smith is the second reviewer.',
    'Reviews are performed by Alice Smith.',
    'Approved by Carol Lee.',
    'Alice Smith, reviewer.',
    'Reviewer: Alice Smith.',
]
LEGIT_NAMED = [
    'Reviewers: The maintainer decides routing.',
    'Maintainer: @CompleteDotTech.',
    'Reviewer: @CompleteDotTech.',
    'Reviews are performed by the maintainer.',
    'The maintainer reviews changes.',
    'Owner Role values identify the expertise needed.',
]
BACKLOG_SYNONYM_ESCAPES = [
    'Unassigned issues are excluded from the default Project view.',
    'Assigned issues are filtered out of the live backlog.',
    'Unassigned issues are moved out of the Project.',
    'Unassigned issues are not listed.',
    'Unassigned backlog is cleaned up.',
]
NEGATED_RETENTION = [
    'Unassigned issues never expire and are not deleted.',
    'Assigned issues are never hidden.',
]
CHANNEL_ESCAPES = [
    'Report conduct concerns on Discord.',
    'Report conduct concerns in the Slack workspace.',
    'Report conduct concerns in GitHub Discussions.',
    'Conduct reports can also open a GitHub issue.',
]
CONDUCT_ANCHOR = 'Enforcement is proportionate and documented by the maintainer.'


class ReviewerEscapeTests(unittest.TestCase):
    def test_sla_sentences_fail_in_every_governance_section(self):
        for label, anchor in GOVERNANCE_SLA_ANCHORS:
            for sentence in SLA_SENTENCES:
                with self.subTest(section=label, sentence=sentence):
                    mutated = mutate(read(GOVERNANCE), anchor, anchor + ' ' + sentence)
                    self.assertTrue(check_governance(mutated))

    def test_sla_sentences_fail_anywhere_in_contributing(self):
        for label, anchor in CONTRIBUTING_SLA_ANCHORS:
            for sentence in SLA_SENTENCES:
                with self.subTest(section=label, sentence=sentence):
                    mutated = mutate(read(CONTRIBUTING), anchor, anchor + ' ' + sentence)
                    self.assertTrue(check_contributing(mutated))

    def test_sla_sentences_fail_in_conduct_and_security(self):
        plain = [s for s in SLA_SENTENCES if not re.search(r'\bsla\b|service[ -]level', s, re.IGNORECASE)]
        for sentence in plain + ['Maintainers respond in under 48 hours.', 'Reports are triaged by the next business day.']:
            with self.subTest(sentence=sentence):
                self.assertTrue(check_conduct(read(CONDUCT) + '\n' + sentence + '\n'))
                self.assertTrue(check_security(read(SECURITY) + '\n' + sentence + '\n'))

    def test_negated_sla_sentences_pass_everywhere(self):
        for label, anchor in GOVERNANCE_SLA_ANCHORS:
            for sentence in NEGATED_SLA_SENTENCES:
                with self.subTest(section=label, sentence=sentence):
                    mutated = mutate(read(GOVERNANCE), anchor, anchor + ' ' + sentence)
                    self.assertEqual(check_governance(mutated), [])
        for label, anchor in CONTRIBUTING_SLA_ANCHORS:
            for sentence in NEGATED_SLA_SENTENCES:
                with self.subTest(section=label, sentence=sentence):
                    mutated = mutate(read(CONTRIBUTING), anchor, anchor + ' ' + sentence)
                    self.assertEqual(check_contributing(mutated), [])

    def test_negation_must_govern_the_same_sentence_and_precede_the_phrase(self):
        anchor = 'Maintain a changelog and deprecation policy before stable release.'
        for sentence in ('Maintainers respond within 48 hours, although no response time is committed.',
                         'Maintainers respond within 48 hours. Do not promise otherwise.',
                         'Maintainers respond within 48 hours and do not promise otherwise.'):
            with self.subTest(sentence=sentence):
                self.assertTrue(check_governance(mutate(read(GOVERNANCE), anchor, anchor + ' ' + sentence)))

    def test_named_role_escapes_fail(self):
        for sentence in NAMED_ESCAPES:
            with self.subTest(sentence=sentence):
                self.assertTrue(check_governance(read(GOVERNANCE) + '\n' + sentence + '\n'))
                self.assertTrue(check_contributing(read(CONTRIBUTING) + '\n' + sentence + '\n'))

    def test_legitimate_named_sentences_pass(self):
        for sentence in LEGIT_NAMED:
            with self.subTest(sentence=sentence):
                self.assertEqual(check_governance(read(GOVERNANCE) + '\n' + sentence + '\n'), [])

    def test_backlog_synonym_escapes_fail(self):
        for sentence in BACKLOG_SYNONYM_ESCAPES:
            with self.subTest(sentence=sentence):
                mutated = mutate(read(GOVERNANCE), 'Leaving an issue unassigned is intentional.',
                                 'Leaving an issue unassigned is intentional. ' + sentence)
                self.assertTrue(check_backlog_visibility(mutated, read(CONTRIBUTING)))
        mutated = mutate(read(CONTRIBUTING), 'unassigned backlog is intentional',
                         'unassigned backlog is intentional. Unassigned issues are excluded from the Project')
        self.assertTrue(check_backlog_visibility(read(GOVERNANCE), mutated))

    def test_negated_retention_rules_pass_and_broken_negation_fails(self):
        for sentence in NEGATED_RETENTION:
            with self.subTest(sentence=sentence):
                mutated = mutate(read(GOVERNANCE), 'Leaving an issue unassigned is intentional.',
                                 'Leaving an issue unassigned is intentional. ' + sentence)
                self.assertEqual(check_backlog_visibility(mutated, read(CONTRIBUTING)), [])
        mutated = mutate(read(GOVERNANCE), 'Leaving an issue unassigned is intentional.',
                         'Leaving an issue unassigned is intentional. Unassigned issues never expire and are deleted.')
        self.assertTrue(check_backlog_visibility(mutated, read(CONTRIBUTING)))

    def test_public_channel_synonyms_fail(self):
        for sentence in CHANNEL_ESCAPES:
            with self.subTest(sentence=sentence):
                self.assertTrue(check_conduct(read(CONDUCT) + '\n' + sentence + '\n'))
                mutated = mutate(read(GOVERNANCE), CONDUCT_ANCHOR, CONDUCT_ANCHOR + ' ' + sentence)
                self.assertTrue(check_governance(mutated))

    def test_private_only_conduct_wording_passes(self):
        self.assertEqual(check_conduct(read(CONDUCT) + '\nDo not post sensitive details publicly, including on Discord or Slack.\n'), [])


if __name__ == '__main__':
    unittest.main()
