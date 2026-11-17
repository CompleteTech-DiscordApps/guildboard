"""Restricted-token repository audit. No Project scope needed; no GitHub writes."""
import datetime
import json
import re

from api import ROOT, api, gql, save


DISPOSITION_STATES = {
    'resolved_incident': {'closed'},
    'campaign_tracking': {'open', 'closed'},
}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate disposition configuration key {key!r}')
        result[key] = value
    return result


def load_dispositions(path, repository):
    data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    if (
        not isinstance(data, dict)
        or data.keys() != {'repository', 'issues'}
        or data['repository'] != repository
        or not isinstance(data['issues'], list)
    ):
        raise ValueError('Expected disposition configuration for the manifest repository')
    dispositions = {}
    for entry in data['issues']:
        if not isinstance(entry, dict) or entry.keys() != {'issue', 'kind', 'reason'}:
            raise ValueError('Each disposition requires an issue number, kind and reason')
        number, kind, reason = entry['issue'], entry['kind'], entry['reason']
        if type(number) is not int or number < 1 or number in dispositions:
            raise ValueError('Disposition issue numbers must be positive and unique')
        if not isinstance(kind, str) or kind not in DISPOSITION_STATES:
            raise ValueError(f'Unknown disposition kind for issue #{number}')
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f'Missing disposition reason for issue #{number}')
        dispositions[number] = entry
    return dispositions


def audit_repository(manifest, dispositions):
    repo = manifest['repository']
    rows = []
    page = 1
    while True:
        batch = api(f'repos/{repo}/issues?state=all&per_page=100&page={page}')
        rows.extend(issue for issue in batch if 'pull_request' not in issue)
        if len(batch) < 100:
            break
        page += 1

    by_id = {item['id']: item for item in manifest['items']}
    actual = {}
    findings = []
    reviewed = []
    seen_dispositions = set()
    for issue in rows:
        body = issue.get('body') or ''
        marker = re.search(r'<!-- guildboard-id:([^ ]+) -->', body)
        number = issue['number']
        disposition = dispositions.get(number)
        if disposition:
            seen_dispositions.add(number)
            if re.search(r'<!--\s*guildboard-id\b', body, re.IGNORECASE):
                findings.append({'issue': number, 'kind': 'disposition_has_roadmap_marker'})
            elif issue['state'] not in DISPOSITION_STATES[disposition['kind']]:
                findings.append({
                    'issue': number, 'kind': 'disposition_state_mismatch', 'state': issue['state'],
                })
            else:
                reviewed.append({**disposition, 'state': issue['state']})
                continue
        if not marker:
            if not disposition:
                findings.append({
                    'issue': number,
                    'kind': 'needs_triage',
                    'reason': 'Issue has no canonical stable ID or reviewed disposition.',
                })
            continue
        stable_id = marker[1]
        if stable_id in actual:
            findings.append({'issue': number, 'kind': 'duplicate_stable_id', 'id': stable_id})
        actual[stable_id] = issue
        if stable_id not in by_id:
            findings.append({'issue': number, 'kind': 'untracked_id', 'id': stable_id})
            continue
        item = by_id[stable_id]
        verification_section = (
            'Review and Verification' if item['work_type'] == 'Epic' else 'Validation and Evidence'
        )
        for section in ('Acceptance Criteria', verification_section):
            if '## ' + section not in body:
                findings.append({'issue': number, 'kind': 'missing_section', 'section': section})
        labels = {label['name'] for label in issue['labels']}
        for label in item['labels']:
            if label not in labels:
                findings.append({'issue': number, 'kind': 'missing_label', 'label': label})
        if not issue['milestone']:
            findings.append({'issue': number, 'kind': 'missing_milestone'})

    for number in sorted(dispositions.keys() - seen_dispositions):
        findings.append({'issue': number, 'kind': 'disposition_issue_missing'})

    node_ids = [issue['node_id'] for issue in actual.values()]
    native = {}
    for offset in range(0, len(node_ids), 30):
        nodes = gql(
            'query($ids:[ID!]!){nodes(ids:$ids){... on Issue{id number state parent{id} '
            'blockedBy(first:100){nodes{id state}} subIssues(first:100){nodes{number state}}}}}',
            ids=node_ids[offset:offset + 30],
        )['nodes']
        native.update({node['id']: node for node in nodes if node})

    for stable_id, item in by_id.items():
        issue = actual.get(stable_id)
        if issue is None:
            findings.append({'id': stable_id, 'kind': 'missing_issue'})
            continue
        node = native[issue['node_id']]
        if item['parent_id']:
            parent = actual.get(item['parent_id'])
            if not parent or not node['parent'] or node['parent']['id'] != parent['node_id']:
                findings.append({'id': stable_id, 'kind': 'parent_mismatch'})
        blockers = node['blockedBy']['nodes']
        blocker_ids = {blocker['id'] for blocker in blockers}
        for dependency in item['dependencies']:
            if dependency not in actual or actual[dependency]['node_id'] not in blocker_ids:
                findings.append({
                    'id': stable_id, 'kind': 'missing_native_dependency', 'dependency': dependency,
                })
        if issue['state'] == 'closed':
            if any(child['state'] != 'CLOSED' for child in node['subIssues']['nodes']):
                findings.append({'id': stable_id, 'kind': 'premature_parent_closure'})
            if '.G' in stable_id and any(blocker['state'] != 'CLOSED' for blocker in blockers):
                findings.append({'id': stable_id, 'kind': 'premature_release_gate'})
    return len(rows), findings, sorted(reviewed, key=lambda entry: entry['issue'])


def main():
    manifest = json.loads((ROOT / 'planning/guildboard-backlog.json').read_text())
    try:
        dispositions = load_dispositions(
            ROOT / 'planning/repository-issue-dispositions.json', manifest['repository']
        )
    except (OSError, ValueError) as error:
        issues, reviewed = 0, []
        findings = [{'kind': 'invalid_disposition_configuration', 'reason': str(error)}]
    else:
        issues, findings, reviewed = audit_repository(manifest, dispositions)

    report = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': ('Repository labels, milestones, issue bodies, native parents/blockers, '
                  'enrollment expected by native workflow. Actual Project fields require full audit.py.'),
        'issues': issues,
        'reviewed_dispositions': reviewed,
        'findings': findings,
        'result': 'needs_attention' if findings else 'pass',
    }
    save(ROOT / 'planning/audit/repository-integrity.json', report)
    print(json.dumps(report, indent=2))
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
