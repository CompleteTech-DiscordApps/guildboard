"""Offline governance policy checks (GB-T0.04.01.T1, #27).

Each clause of the #27 scope is one check over text. Repository tests run the checks on
the committed files; NegativeMutationTests feed mutated text into the same functions and
assert that they fail. Stdlib only; paths are resolved from this file; runs under python3 -I.
These checks confirm documented wording, headings and routing. They do not show that anyone
reviews, that CI runs, or that an issue is claimed or assigned in practice.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAINTAINER = '@CompleteDotTech'
GOVERNANCE = 'GOVERNANCE.md'
CONTRIBUTING = 'CONTRIBUTING.md'
CONDUCT = 'CODE_OF_CONDUCT.md'
CODEOWNERS = '.github/CODEOWNERS'
PR_TEMPLATE = '.github/pull_request_template.md'
ISSUE_TEMPLATE_DIR = '.github/ISSUE_TEMPLATE'
TASK_DOC = 'docs/workstreams/T0.md'
IDENTITY_FILES = (GOVERNANCE, CONTRIBUTING, CONDUCT, CODEOWNERS, PR_TEMPLATE)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
# An @handle is not preceded by a word character, dot, slash or @ (so emails and paths do not match).
HANDLE_RE = re.compile(r'(?<![\w.@/])@([A-Za-z0-9][A-Za-z0-9-]*)')
ASSIGNEES_KEY_RE = re.compile(r'^\s*(?:-\s*)?["\']?assignees["\']?\s*:', re.IGNORECASE | re.MULTILINE)
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*\S)\s*$')

GOVERNANCE_CLAUSES = {
    'Maintainers': [
        '@CompleteDotTech', 'the only known repository maintainer',
        'no other maintainers, contributors or approvers are assigned',
        'explicit recorded appointment', 'CODEOWNERS'],
    'Review roles': [
        'CONTRIBUTING.md', 'auth/tenancy/revocation to security expertise',
        'editor/protocol to realtime and canvas expertise', 'migrations to data expertise',
        'deployment to platform expertise', 'do not create reviewers or approvals',
        'not waived by Project status or merged planning documents'],
    'Decision escalation': [
        'contributor -> issue or ADR discussion -> maintainer review',
        'escalated to maintainer review by @CompleteDotTech',
        'is recorded in the issue, the ADR or the PR',
        'conduct concerns use the private path in CODE_OF_CONDUCT.md',
        'no response time is committed', 'no other decision-maker is named'],
    'Contributor conduct': [
        'CODE_OF_CONDUCT.md', 'reported privately', 'must not carry sensitive details',
        'documented by the maintainer'],
    'Issue ownership and backlog visibility': [
        'maintainer coordination', 'assignment never hides backlog', 'unassigned',
        'intentional', '`.github/ISSUE_TEMPLATE/`', '`assignees:`', 'auto-assign'],
}
GOVERNANCE_TOP_NEEDLES = [
    'The currently known repository maintainer is @CompleteDotTech.',
    'No other contributors or approvers have been assigned.',
]
DOR_NEEDLES = [
    'requirements and scope are bounded', 'acceptance is testable', 'contracts exist',
    'prerequisite native blockers are satisfied', 'validation is defined',
]
DOD_NEEDLES = [
    'deliverable exists', 'applicable tests pass', 'documentation are updated',
    'actual review is complete', 'relevant pr is merged', 'post-merge/platform checks are evidenced',
    'close only when criteria are met',
]
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
]
CONDUCT_NEEDLES = [
    'Report conduct concerns privately', 'contact method published on the maintainer',
    'Do not post sensitive details publicly', 'Maintainer: @CompleteDotTech',
]
TASK_NEEDLES = [
    '### GB-T0.04.01.T1 governance and contribution policy (#27)',
    '`python3 -I -m unittest discover -s tests/verification -v`',
    '`python3 scripts/github-bootstrap/validate.py`',
    '`python3 -I scripts/verification/check_licenses.py`',
    'of this deliverable are not claimed',
]


def read(rel):
    return (REPO / rel).read_text(encoding='utf-8')


def norm(text):
    return ' '.join(text.lower().split())


def sections(text):
    """Map heading text to its body, up to the next heading of any level."""
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


def missing(text, needles, label):
    haystack = norm(text)
    return [f'{label}: missing {needle!r}' for needle in needles if norm(needle) not in haystack]


def missing_section(text, heading, needles, label):
    body = sections(text).get(heading)
    if body is None:
        return [f'{label}: missing heading {heading!r}']
    return missing(body, needles, f'{label} section {heading!r}')


def check_governance(text):
    errors = missing(text, GOVERNANCE_TOP_NEEDLES, GOVERNANCE)
    for heading, needles in GOVERNANCE_CLAUSES.items():
        errors += missing_section(text, heading, needles, GOVERNANCE)
    return errors


def check_contributing(text):
    errors = missing(text, ['GOVERNANCE.md'], CONTRIBUTING)
    errors += missing_section(text, 'Definition of Ready', DOR_NEEDLES, CONTRIBUTING)
    errors += missing_section(text, 'Definition of Done', DOD_NEEDLES, CONTRIBUTING)
    errors += missing_section(text, 'Review', REVIEW_NEEDLES, CONTRIBUTING)
    return errors


def check_conduct(text):
    return missing(text, CONDUCT_NEEDLES, CONDUCT)


def check_pr_template(text):
    return missing(text, PR_NEEDLES, PR_TEMPLATE)


def check_task_record(text):
    return missing(text, TASK_NEEDLES, TASK_DOC)


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
    if not templates:
        return ['issue templates: none found']
    return [f'{name}: assignees key present'
            for name, text in sorted(templates.items()) if ASSIGNEES_KEY_RE.search(text)]


def check_identity_surface(name, text):
    errors = [f'{name}: email address present ({m.group(0)!r})' for m in EMAIL_RE.finditer(text)]
    errors += [f'{name}: handle @{h} is not {MAINTAINER}'
               for h in HANDLE_RE.findall(text) if f'@{h}' != MAINTAINER]
    return errors


def load_templates(root=REPO):
    return {p.name: p.read_text(encoding='utf-8')
            for p in sorted((root / ISSUE_TEMPLATE_DIR).glob('*.yml'))}


class RepositoryGovernanceTests(unittest.TestCase):
    def test_governance_clauses_present(self):
        text = read(GOVERNANCE)
        for heading in GOVERNANCE_CLAUSES:
            with self.subTest(clause=heading):
                self.assertEqual(missing_section(text, heading, GOVERNANCE_CLAUSES[heading], GOVERNANCE), [])
        self.assertEqual(missing(text, GOVERNANCE_TOP_NEEDLES, GOVERNANCE), [])

    def test_contributing_definition_of_ready_done_and_review(self):
        self.assertEqual(check_contributing(read(CONTRIBUTING)), [])

    def test_code_of_conduct_private_reporting(self):
        self.assertEqual(check_conduct(read(CONDUCT)), [])

    def test_codeowners_contains_only_known_maintainer(self):
        self.assertEqual(check_codeowners(read(CODEOWNERS)), [])

    def test_issue_templates_never_assign(self):
        templates = load_templates()
        self.assertTrue(templates, 'no issue templates found; check would be vacuous')
        self.assertEqual(check_issue_templates(templates), [])

    def test_pr_template_review_and_evidence_checklist(self):
        self.assertEqual(check_pr_template(read(PR_TEMPLATE)), [])

    def test_identity_surface_no_emails_only_maintainer_handles(self):
        files = {rel: read(rel) for rel in IDENTITY_FILES}
        files.update({f'{ISSUE_TEMPLATE_DIR}/{name}': text for name, text in load_templates().items()})
        for name, text in files.items():
            with self.subTest(file=name):
                self.assertEqual(check_identity_surface(name, text), [])

    def test_workstream_record_has_commands_and_limits(self):
        self.assertEqual(check_task_record(read(TASK_DOC)), [])


def mutate(text, old, new=''):
    if old not in text:
        raise AssertionError(f'mutation target not found: {old!r}')
    return text.replace(old, new, 1)


class NegativeMutationTests(unittest.TestCase):
    """Each mutation removes or adds one documented requirement; the same checks must fail."""

    def test_baseline_passes_the_same_checks(self):
        self.assertEqual(check_governance(read(GOVERNANCE)), [])
        self.assertEqual(check_contributing(read(CONTRIBUTING)), [])
        self.assertEqual(check_conduct(read(CONDUCT)), [])
        self.assertEqual(check_codeowners(read(CODEOWNERS)), [])
        self.assertEqual(check_issue_templates(load_templates()), [])
        self.assertEqual(check_pr_template(read(PR_TEMPLATE)), [])
        self.assertEqual(check_task_record(read(TASK_DOC)), [])

    def test_assignees_key_added_to_template_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml')
        errors = check_issue_templates({'bug.yml': 'assignees: [CompleteDotTech]\n' + bug})
        self.assertTrue(any('assignees key' in e for e in errors), errors)

    def test_indented_assignees_key_in_list_item_fails(self):
        feature = read(f'{ISSUE_TEMPLATE_DIR}/feature.yml')
        mutated = mutate(feature, 'labels: ["type: feature"]', 'labels: ["type: feature"]\n  - assignees: CompleteDotTech')
        self.assertTrue(check_issue_templates({'feature.yml': mutated}))

    def test_second_codeowners_handle_fails(self):
        codeowners = read(CODEOWNERS)
        mutated = mutate(codeowners, '* @CompleteDotTech', '* @CompleteDotTech @second-reviewer')
        self.assertTrue(check_codeowners(mutated))

    def test_codeowners_extra_rule_with_other_owner_fails(self):
        codeowners = read(CODEOWNERS) + 'docs/ @other-owner\n'
        self.assertTrue(any('other-owner' in e or 'owners must be' in e for e in check_codeowners(codeowners)))

    def test_codeowners_without_catch_all_fails(self):
        self.assertTrue(check_codeowners('docs/ @CompleteDotTech\n'))

    def test_removed_definition_of_done_heading_fails(self):
        mutated = mutate(read(CONTRIBUTING), '## Definition of Done', '## Finish notes')
        self.assertTrue(any('Definition of Done' in e for e in check_contributing(mutated)))

    def test_removed_definition_of_done_criterion_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'Deliverable exists, ', '')
        self.assertTrue(any('deliverable exists' in e for e in check_contributing(mutated)))

    def test_removed_definition_of_ready_criterion_fails(self):
        mutated = mutate(read(CONTRIBUTING), 'and validation is defined.', 'and validation is pending.')
        self.assertTrue(any('validation is defined' in e for e in check_contributing(mutated)))

    def test_removed_governance_section_heading_fails(self):
        mutated = mutate(read(GOVERNANCE), '## Decision escalation', '## Escalation notes')
        self.assertTrue(any('Decision escalation' in e for e in check_governance(mutated)))

    def test_removed_no_other_approvers_statement_fails(self):
        mutated = mutate(read(GOVERNANCE), 'No other contributors or approvers have been assigned.', '')
        self.assertTrue(check_governance(mutated))

    def test_assignment_may_hide_backlog_fails(self):
        mutated = mutate(read(GOVERNANCE), 'Assignment never hides backlog', 'Assignment may hide backlog')
        self.assertTrue(any('never hides backlog' in e for e in check_governance(mutated)))

    def test_email_added_to_governance_fails(self):
        text = read(GOVERNANCE) + '\nSecurity contact: maintainer@example.org\n'
        self.assertTrue(check_identity_surface(GOVERNANCE, text))

    def test_second_handle_added_to_governance_fails(self):
        text = read(GOVERNANCE) + '\nReviewer of record: @new-reviewer\n'
        self.assertTrue(check_identity_surface(GOVERNANCE, text))

    def test_email_added_to_issue_template_fails(self):
        bug = read(f'{ISSUE_TEMPLATE_DIR}/bug.yml') + '\n# contact dev@example.com\n'
        self.assertTrue(check_identity_surface('bug.yml', bug))

    def test_private_conduct_reporting_removed_fails(self):
        mutated = mutate(read(CONDUCT), 'Report conduct concerns privately', 'Report conduct concerns in public')
        self.assertTrue(any('Report conduct concerns privately' in e for e in check_conduct(mutated)))

    def test_public_posting_of_sensitive_details_allowed_fails(self):
        mutated = mutate(read(CONDUCT), 'Do not post sensitive details publicly.', 'Post details as needed.')
        self.assertTrue(check_conduct(mutated))

    def test_pr_review_checkbox_removed_fails(self):
        mutated = mutate(read(PR_TEMPLATE), '- [ ] Required functional/security review complete\n', '')
        self.assertTrue(any('review complete' in e for e in check_pr_template(mutated)))

    def test_contributing_governance_crossref_removed_fails(self):
        mutated = mutate(read(CONTRIBUTING), '[GOVERNANCE.md](GOVERNANCE.md)', 'the governance notes')
        self.assertTrue(check_contributing(mutated))

    def test_task_record_without_limits_fails(self):
        mutated = mutate(read(TASK_DOC), 'of this deliverable are not claimed', 'of this deliverable are claimed')
        self.assertTrue(check_task_record(mutated))


if __name__ == '__main__':
    unittest.main()
