"""Preview or apply exact Guildboard transfer-link substitutions to selected issues."""
import argparse
import hashlib
import json
import re
import sys

# Preview and apply both leave the checkout untouched.
sys.dont_write_bytecode = True
from api import ROOT, STATE, TRANSFERRED_REPOSITORY, TRANSFERRED_REPOSITORY_LINK, api

REPOSITORY = 'CompleteTech-DiscordApps/guildboard'
MAX_BATCH = 10
MARKER = re.compile(r'^<!-- guildboard-id:([^\s]+) -->\r?$', re.MULTILINE)
# Scan complete URL tokens first so a nested URL inside a query or path never
# becomes an independent replacement. Angle brackets delimit Markdown URLs.
URL_TOKEN = re.compile(r"""(?<![^\s<(\[{"'`])(?:[a-z][a-z0-9+.-]*:)?//[^\s<>"'`]+""", re.IGNORECASE)


def rewrite(body):
    def replace(token_match):
        token = token_match.group()
        prefix = TRANSFERRED_REPOSITORY_LINK.match(token)
        if prefix is None:
            return token
        owner_start = prefix.end() - len(TRANSFERRED_REPOSITORY)
        return token[:owner_start] + REPOSITORY + token[prefix.end():]

    return URL_TOKEN.sub(replace, body)


def selected_items(numbers):
    state = json.loads(STATE.read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'planning/guildboard-backlog.json').read_text(encoding='utf-8'))
    if state['repo'] != REPOSITORY or manifest['repository'] != REPOSITORY:
        raise ValueError('repository identity mismatch')
    selected = {}
    for item in manifest['items']:
        mapping = item.get('github', {})
        number = mapping.get('number')
        if number not in numbers:
            continue
        if (type(number) is not int or number in selected
                or not isinstance(mapping.get('id'), str) or not mapping['id']
                or not re.fullmatch(r'[A-Za-z0-9.-]+', item['id'])
                or not re.fullmatch(r'[a-f0-9]{64}', item['body_hash'])):
            raise ValueError('ambiguous or incomplete issue mapping')
        selected[number] = item
    if set(selected) != set(numbers):
        raise ValueError('an issue is not in the manifest')
    if len({item['id'] for item in selected.values()}) != len(selected):
        raise ValueError('duplicate stable IDs')
    return selected


def issue_body(issue, item, number):
    if (not isinstance(issue, dict)
            or type(issue.get('number')) is not int or issue['number'] <= 0
            or not isinstance(issue.get('node_id'), str) or not issue['node_id']
            or 'body' not in issue or (issue['body'] is not None and not isinstance(issue['body'], str))):
        raise ValueError('malformed GitHub issue response')
    if ('pull_request' in issue or issue['number'] != number
            or issue['node_id'] != item['github']['id']):
        return None
    body = issue['body']
    if body is not None and MARKER.findall(body) == [item['id']]:
        return body
    return None


def process(number, item, apply):
    endpoint = f'repos/{REPOSITORY}/issues/{number}'
    original = issue_body(api(endpoint, redact_failure=True), item, number)
    if original is None:
        return 'skipped_identity'
    updated = rewrite(original)
    if updated == original:
        return 'no_transfer_links'
    if hashlib.sha256(original.encode()).hexdigest() != item['body_hash']:
        return 'skipped_edited'
    if not apply:
        return 'would_update'
    current = issue_body(api(endpoint, redact_failure=True), item, number)
    if current != original:
        return 'skipped_changed_since_read'
    result = api(endpoint, 'PATCH', {'body': updated}, redact_failure=True)
    if issue_body(result, item, number) != updated:
        raise ValueError('write outcome was not confirmed')
    return 'updated'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issue', type=int, action='append', required=True, help='issue number (repeatable)')
    parser.add_argument('--apply', action='store_true', help='write eligible issue bodies')
    args = parser.parse_args(argv)
    if (len(args.issue) > MAX_BATCH or len(set(args.issue)) != len(args.issue)
            or any(number <= 0 for number in args.issue)):
        parser.error(f'choose one to {MAX_BATCH} distinct positive issue numbers')
    try:
        items = selected_items(args.issue)
    except (OSError, ValueError, TypeError, KeyError):
        print('Transfer link batch stopped: invalid local issue mappings.', file=sys.stderr)
        return 1
    for number in args.issue:
        item = items[number]
        try:
            outcome = process(number, item, args.apply)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            print(f'Transfer link batch stopped at issue #{number}: request or response could not be confirmed.',
                  file=sys.stderr)
            return 1
        print(json.dumps({'issue': number, 'result': outcome}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
