#!/usr/bin/env python3
"""Bounded offline checks of requirements definitions; never tests the product."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = 'docs/requirements/GB-T0-01-01-requirements.md'
FIX = 'docs/requirements/fixtures/GB-T0-01-01-use-cases.json'
REQUIRED = {f'R{i:02}' for i in range(1, 9)}
# Semantic anchors are intentionally shorter than the prose and can evolve with it.
ANCHORS = {
 'R01': ('moderator', 'durabl', 'acknowledg'),
 'R02': ('viewer', 'no write', 'mutation'),
 'R03': ('guild', 'server', 'not-found'),
 'R04': ('revoc', 'fail closed', 'protected', 'side effects'),
 'R05': ('receipt', 'lineage', 'reconnect', 'interrupted'),
 'R06': ('configuration', 'unavailable', 'interrupt', 'secrets'),
 'R07': ('mvp', 'v1.0', '#455', '#456', '#457', '#472'),
 'R08': ('availability', 'capacity', 'latency', 'recovery'),
}
OBJECTIVES = {
 'Capacity and durable ACK latency': ('10 active boards', '20 connected', '5 simultaneous', '5,000', '5 bounded operations/second', '30 minutes', '250 attempts/second', 'p95 <=250 ms', 'p99 <=1 s', 'errors and timeouts'),
 'Reconnect': ('200 reconnect attempts', '<=5 s', 'all complete'),
 'Process restart': ('every acknowledged operation', 'zero lost', 'unverifiable'),
 'Backup recovery': ('<=24 h', '<=4 h', 'each planned restore', 'at least one'),
 'Availability': ('one-minute', 'all scheduled minutes', '99.5%', 'missing'),
}

class VerificationError(Exception):
    pass

def check(root=ROOT, config=None, interrupt=None):
    """Return only a complete result; interruptions and missing input raise."""
    if config is not None and (not isinstance(config, dict) or config != {'version': 1}):
        raise VerificationError('invalid verification configuration')
    root = Path(root)
    try:
        doc = (root / DOC).read_text(encoding='utf-8')
        fixture = json.loads((root / FIX).read_text(encoding='utf-8'))
        # These are mandatory inputs, independently of whether the document links them.
        contract = (root / 'docs/specifications/GB-T0-S1-system-contract.md').read_text(encoding='utf-8')
        matrix = (root / 'planning/MVP-ACCEPTANCE.md').read_text(encoding='utf-8')
        milestones = (root / 'planning/MILESTONES.md').read_text(encoding='utf-8')
    except (OSError, UnicodeError, ValueError) as exc:
        raise VerificationError('required input unavailable or invalid') from exc
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    require(all(x in contract.lower() for x in ('identity and authorization', 'idempotency', 'recovery', 'proposed objectives')), 'system contract scope missing')
    require(all(x in matrix.lower() for x in ('activity startup', 'guild context', 'moderator role', 'read-only viewers', 'backend-enforced permissions', 'synchronization', 'locking', 'reconnection', 'security negatives', '/455', '/456')), 'MVP matrix scope missing')
    require(all(x in milestones for x in ('/456', '/457', '/472', 'Security and backup restore')), 'milestone gates missing')
    sections = dict(re.findall(r'^- \*\*(R\d\d) [^*]+\*\*:\s*(.*)$', doc, re.M))
    require(set(sections) == REQUIRED, 'requirement IDs missing, unknown or duplicated')
    ids = re.findall(r'^- \*\*(R\d\d) [^*]+\*\*:', doc, re.M)
    require(len(ids) == len(set(ids)), 'duplicate requirement ID')
    for rid, words in ANCHORS.items():
        value = sections.get(rid, '').lower()
        require(all(w in value for w in words), rid + ' mandatory scope missing')
    require(isinstance(fixture, dict), 'fixture must be object')
    if not isinstance(fixture, dict):
        raise VerificationError('fixture must be object')
    require(fixture.get('version') == 1 and fixture.get('status') == 'declarative-not-executed', 'fixture version or evidence label invalid')
    require(fixture.get('requirements_document') == '../GB-T0-01-01-requirements.md', 'fixture document link invalid')
    cases = fixture.get('cases')
    if not isinstance(cases, list):
        raise VerificationError('case list unavailable')
    seen, covered = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append('invalid case'); continue
        cid = case.get('id')
        if not isinstance(cid, str) or cid in seen:
            errors.append('invalid or duplicate case ID')
        else:
            seen.add(cid)
        reqs = case.get('requirements')
        if not isinstance(reqs, list) or not reqs or any(not isinstance(x, str) or x not in REQUIRED for x in reqs):
            errors.append('unknown or missing case requirement')
        else:
            covered.update(reqs)
        for field in ('actor', 'preconditions', 'action', 'expected'):
            require(isinstance(case.get(field), str) and bool(case[field].strip()), 'case field missing: ' + field)
    require(seen == {f'UC{i:02}' for i in range(1, 21)}, 'mandatory case IDs missing or unknown')
    require(covered == REQUIRED, 'requirement coverage incomplete')
    expected_trace = ['R01 R03', 'R01', 'R02', 'R02 R04', 'R03 R04', 'R04', 'R04', 'R04', 'R04 R05', 'R05', 'R05', 'R05', 'R05', 'R06', 'R04 R06', 'R05 R06', 'R07', 'R08', 'R04', 'R05']
    for index, expected in enumerate(expected_trace, 1):
        matches = [c for c in cases if isinstance(c, dict) and c.get('id') == f'UC{index:02}']
        require(len(matches) == 1 and set(matches[0].get('requirements', [])) == set(expected.split()), f'UC{index:02} traceability mismatch')
    # Critical examples must retain both their actor and boundary outcome.
    by_id = {c.get('id'): c for c in cases if isinstance(c, dict) and isinstance(c.get('id'), str)}
    for cid, terms in {'UC01': ('moderator', 'durable'), 'UC03': ('viewer', 'no write'), 'UC04': ('viewer', 'deny', 'mutation'), 'UC05': ('guild', 'not_found'), 'UC08': ('session', 'suppress'), 'UC17': ('mvp', 'v1.0')}.items():
        content = ' '.join(str(v) for v in by_id.get(cid, {}).values()).lower()
        require(all(t in content for t in terms), cid + ' actor or boundary missing')
    for name, words in OBJECTIVES.items():
        match = re.search(r'^\| ' + re.escape(name) + r' \| (.*?) \|$', doc, re.M)
        value = match.group(1).lower() if match else ''
        require(all(w.lower() in value for w in words), name + ' operational definition missing')
    require(10 * 5 * 5 == 250 and 10 * 20 == 200, 'workload arithmetic invalid')
    for target in re.findall(r'\]\(([^)]+)\)', doc):
        if not re.match(r'^(?:https?://|#)', target):
            path = target.split('#', 1)[0]
            require((root / DOC).parent.joinpath(path).is_file(), 'relative link target missing')
    require('not executed product tests' in doc and 'No release is asserted' in doc and 'No fixture' in doc, 'evidence limitations missing')
    if interrupt is not None:
        interrupt()  # No result is returned if execution is interrupted.
    return {'status': 'fail' if errors else 'pass', 'kind': 'offline-definition-check', 'checks_complete': True, 'errors': sorted(set(errors)), 'case_count': len(cases), 'product_runtime': 'not tested'}

def main():
    try:
        result = check()
    except (VerificationError, KeyboardInterrupt):
        print(json.dumps({'status': 'incomplete', 'checks_complete': False, 'kind': 'offline-definition-check'}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'pass' else 1

if __name__ == '__main__':
    sys.exit(main())
