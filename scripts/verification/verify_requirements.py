#!/usr/bin/env python3
"""Bounded offline checks of requirements definitions; never tests the product."""
import json
import hashlib
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

# Reviewed issue #6 definition oracle, revision ae7aa92a76ff18522e643821df6840bf3bbabc4d.
# Whitespace-normalized exact text, not natural-language interpretation or runtime evidence.
# Any accepted definition change requires a fresh independent review before updating.
DOC_DIGEST = 'af0c5fae340ebfc1b03ca36d55f0fb95e0bf6af23bc835329cc1c21adbc268b9'
CASE_DIGESTS = {'UC01': {'actor': 'cfde2ca5188afb7bdd0691c7bef887baba78b709aadde8e8c535329d5751e6fe', 'preconditions': '4c8672331cf35c5d1456e60d11ecefdffd3399f76ecb036feabd88f790db1e9c', 'action': '4bf3332b35da6efddcf4b5228ab05c2bdbaaa8ba379fc7bacf56faf0efa4252e', 'expected': '3f1564e79e661ee9cd20556e26791c49bc00c12b682ad7a4fc16ff1d590656b5'}, 'UC02': {'actor': 'b5ae7f7397ca0bd6532f8ab8bcbe4804283719569649ddbbad47e18078844d6e', 'preconditions': '70bebb2eb96739a904faabb8517b1f65ba6efd62ccec73400c207093d81467a5', 'action': 'ba1cd21a83b79e8a7781ec0d04c5b190237c32bb0cdbc61e389c94a03fe96e9e', 'expected': '7d69c63ae78c5509c0a36b5e2b048ec8332a6f9e607b8ff0b036f3ee1347fe11'}, 'UC03': {'actor': 'd35ca5051b82ffc326a3b0b6574a9a3161dee16b9478a199ee39cd803ce5b799', 'preconditions': '91c33b0f52eaa0d9366c7a5b1711e593d08ee05c9f9c6406429e0b3617fb35b1', 'action': '4ea97d64d97fef78e2827129fff91734f2ece77075f361a83ebf884fa3046fe2', 'expected': '0f784e512863e40fd2c5ff2944086b0719ca039e572135baaf8e98f831f1908c'}, 'UC04': {'actor': 'd35ca5051b82ffc326a3b0b6574a9a3161dee16b9478a199ee39cd803ce5b799', 'preconditions': 'c7b61f5464c4f245f02b25242a9663fa89794be15c028aa87c8e435b1fae95fe', 'action': 'd805b0f27419c248a7ac86bc8bca2973fd0628ff036e46cc579c256eb5f44b5f', 'expected': 'b688304af95859b8144257712438679525b2d539ef4e4017a869090b40934832'}, 'UC05': {'actor': '2ca7c9b66676393b9682802a1b3a0b5f78881707eb80ef37384bb6caf8f7f15d', 'preconditions': '662129a5f8c64b4e75f2d2c2b26c45a53d92ab70e7416a7afe35218cb69b688f', 'action': '712a4282b5492dde0207b16e0a0852bd74cebb483685ca5ee469ed23b45af2f7', 'expected': '551989ea57db307d39369914f410da7fba8cbe20081f448ef30a3db2b38f5f4f'}, 'UC06': {'actor': 'fa7fd1ba76b8b63a8a93a9b7bc0c3343a21ac414be3d6a3327db0cd7becac5e0', 'preconditions': '8159095301c52140b32e9ba8cc43d07a6a5c287fd281061a5d342c6b9e6e0d35', 'action': '9a629830df859f91eb8041632f4603456b4aac54cb03f7a8fdae9f8a5b357e63', 'expected': '220a8dc9d7f91a0e5ab484987dfeb9cdee93c40cc9307d2b66fb44c64ef499ae'}, 'UC07': {'actor': '822ce3ede5f3ad3b5ac9b7bc497b26c02e0911de6c96c0591158e52da229772e', 'preconditions': '6f3deb4d25707df9c567deaff25caccd19946f6efaf6fbf40b49f2fbe9af73fc', 'action': '5f3ca901e0e1bb101471f72db2302c3e4a274428d04432d3531601c2570ee400', 'expected': 'f50779f00b737abb1d9de4c614087e2f0e052f11d7e4e64a2b0b6e95fcba0d34'}, 'UC08': {'actor': '5b4d3a2b811c5a633ae5682e4a9ee387ee72ce45007e15c865c57486ec1df30e', 'preconditions': 'd6f1b72845591b356e582d35d229a05ccc1b83fc0b2c4cc503e01ad5b6c4025c', 'action': '9ad0a8f5fb639e86f771856fa7662ec57a30a32f0d6c5b6164d8b1365cbe1ddd', 'expected': '26357f996c2a28e33b1e9d75de1165e92babeefe3f56765cc7ea525c3bce95ac'}, 'UC09': {'actor': '725d47c23d8232c3bdb71c489b7e10c13efb14b20cf439fa0dc5c4fb62d1c180', 'preconditions': 'f18740b1a12e9e04d6f06f9b00567a480b5e2a77e95c92ff4fafef5d944c8abb', 'action': '4e4eea6c156ba125dfcfb53d87f4078a87a39b706ce4e66845cc45f652765e1d', 'expected': 'a4886988bcc85940d06a8b64d06225c875a8e0a801cbc655c468b14e05aec7bf'}, 'UC10': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': '91ffe571c9841ec7b7784fd7abe4550f7d659eb31370c0d0ed90c8ec9bf11bd0', 'action': 'bd81b9c62ed8b38a5d09a8bf84fd21fb862e668685cbde61fdd8268687b0f5f3', 'expected': '24f5842136a8a372fad9b4966932d47df92aca421f95ed6e4b88a89d12389724'}, 'UC11': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': '37656134b95f4eba40447669dc21a9df4498e787ad836cc7659672d5fb8259dd', 'action': '5fa3625acbbae435821871fc67079e770fd3132efd32db6b6bfddb1857160093', 'expected': '0ee2b743764e1537c10130a49bc0ac8ddc822869240910a01bf2ec57474b7c2a'}, 'UC12': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': 'b16ffb36dbf80a402ebae863244ca792c520449117660d3574d18855016e7138', 'action': 'd6a933c0e5d9901437de156f9300e13b9e35b93abf26ff21636e4ae12ccac7e6', 'expected': '6356361c8283879b6f997e620d63ea273970776fc6a799813252e9d4903f76fb'}, 'UC13': {'actor': 'ab49fc8748981a2030933e28166a171ac70a08be2c41fa7efb7fed7fe7d04a14', 'preconditions': '8821c244c448c1603e4971fdc00f3fe1d1407074060046be9194895c5076466c', 'action': 'e16cbbc292799049393846a25c664fdee3100cc885b8f48613564341512eea7d', 'expected': 'a114bc9eab1b827510ba2c83af78bfb87d7773703699f8c77da3690ed425df8a'}, 'UC14': {'actor': '06e55b633481f7bb072957eabcf110c972e86691c3cfedabe088024bffe42f23', 'preconditions': 'ef5ec1625b7b8f138b44f9d631d63bc9fb8a38d4970d5ad1e3dfedcd02f402f8', 'action': 'b6416c68df38b1d33328d83fe4b2e5f8c473d20bba5e574a71f83857e56bd7dd', 'expected': '6b97d7d75b506692b471bd02e33f92f0563bf11c129f5499b6df7e62e1b2ba0c'}, 'UC15': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': 'eacd182153873944f4f4b82baf47c15254855d05ea82b5b38688e1face41142c', 'action': 'e630d69a3c181b90ea2ff3c80625a82afc2aea4147f3e30d56295a03b45d6bdf', 'expected': 'ce7cc092e25c3653c283baac20b4532fc1dc56b3de8689e27238cf54f2dc85da'}, 'UC16': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': '908b3c947a5d77166422f9a1be3467df64426bc9aed3463b0884b81a899e9572', 'action': '573dde76d9b3173f35f51f7076cea175747493162cc77a5aaaefae8c7333261c', 'expected': 'f16fbc325ff1fdfe9418491ff45b7932843acd129787e958824b20a6951e9118'}, 'UC17': {'actor': '59a5f46759e65156728a19f53135da79cbdae75fc739929b34076e795636fc56', 'preconditions': 'ce59d2e91d206b471d206084918dd5c51606c916d8ee7ed38783df02e9a6e336', 'action': '761cbe1bd55de4eb2843cfdb2680c2ccb639f5121c44ffaa94d3e477c888d3d2', 'expected': '1f4e741234dec72021df5102f613fe35b9504d1f0a1f58b0d78854b2ee6dd3f5'}, 'UC18': {'actor': 'de75aaabb6c692b7bfb14f9a92c12e9def5b628ea5ecb10513f2072d3ca5df4d', 'preconditions': 'e2533ad889f964d06a81bfb9d1e4050095cac7c24d5d91dcf4e8c78dd1d1807c', 'action': 'a31c089030c1155369b411444a4c8651f3d18764af3f80be313435fca1344244', 'expected': '921d9d99b5689230584932dcd1535ce7ba3ed326b18c05209a88197a12aa27cd'}, 'UC19': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': 'c01c322f1d22d1532ae97c68a4121db546cb2f57f80b9e8418d1a82f59cb2281', 'action': '9c94f2649acc1415aa056760828f62e56dba63cb6e853e5e9d3720d32d2d9d9b', 'expected': '29c34aea781ad4cb624fdb4cab086531384cf483f3d1e9b922f7aa8423d51a15'}, 'UC20': {'actor': 'b93006774cbdd4b299389a03ac3d88c3a76b460d538795bc12718011a909fba5', 'preconditions': 'af6457e81b118280dd08b4e626df25089f5d02ea507c7896742b5ed1bae4b2ee', 'action': '0422c923529ff3c1e3bd6bf471349c162c71a51331f0e4760d88aad2626b7cc0', 'expected': 'd49608a6a73ed59b7d1fb26e1276b26d4d57fc2fe4331e16f80ec73a104118f1'}}

def normalized_digest(value):
    return hashlib.sha256(" ".join(value.split()).encode("utf-8")).hexdigest()

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
    if normalized_digest(doc) != DOC_DIGEST:
        errors.append('accepted requirements document differs from reviewed baseline; fresh review required')
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
            value = case.get(field)
            require(isinstance(value, str) and bool(value.strip()), 'case field missing: ' + field)
            if isinstance(value, str) and isinstance(cid, str):
                require(normalized_digest(value) == CASE_DIGESTS.get(cid, {}).get(field), str(cid) + ' ' + field + ' differs from reviewed baseline')
    require(seen == {f'UC{i:02}' for i in range(1, 21)}, 'mandatory case IDs missing or unknown')
    require(covered == REQUIRED, 'requirement coverage incomplete')
    expected_trace = ['R01 R03', 'R01', 'R02', 'R02 R04', 'R03 R04', 'R04', 'R04', 'R04', 'R04 R05', 'R05', 'R05', 'R05', 'R05', 'R06', 'R04 R06', 'R05 R06', 'R07', 'R08', 'R04', 'R05']
    for index, expected in enumerate(expected_trace, 1):
        matches = [c for c in cases if isinstance(c, dict) and c.get('id') == f'UC{index:02}']
        reqs = matches[0].get('requirements') if len(matches) == 1 else None
        require(isinstance(reqs, list) and all(isinstance(x, str) for x in reqs) and len(reqs) == len(expected.split()) and set(reqs) == set(expected.split()), f'UC{index:02} traceability mismatch')
    # Critical examples must retain both their actor and boundary outcome.
    by_id = {c.get('id'): c for c in cases if isinstance(c, dict) and isinstance(c.get('id'), str)}
    for cid, terms in {'UC01': ('moderator', 'durable'), 'UC03': ('viewer', 'no write'), 'UC04': ('viewer', 'deny', 'mutation'), 'UC05': ('guild', 'not_found'), 'UC08': ('session', 'suppress'), 'UC17': ('mvp', 'v1.0')}.items():
        content = ' '.join(str(v) for v in by_id.get(cid, {}).values()).lower()
        require(all(t in content for t in terms), cid + ' actor or boundary missing')
    for name, words in OBJECTIVES.items():
        match = re.search(r'^\| ' + re.escape(name) + r' \| (.*?) \|$', doc, re.M)
        value = match.group(1).lower() if match else ''
        require(all(w.lower() in value for w in words), name + ' operational definition missing')
    # The pinned entire operational section includes comparators, denominators,
    # workload arithmetic and failure rules; no independent measurement is claimed.
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
