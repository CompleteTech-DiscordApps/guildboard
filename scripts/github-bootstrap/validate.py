"""Offline roadmap validation with deterministic, fail-closed JSON diagnostics."""

import argparse
import collections
import json
import os
import secrets
from pathlib import Path

from api import ROOT

REQUIRED_FIELDS = (
    'Tier', 'Work Type', 'Priority', 'Readiness', 'Status', 'Dependency Status',
    'Release Target', 'Risk', 'Effort', 'Owner Role', 'Research Confidence',
    'Verification Status',
)
CRITICAL_PATH_NOTE = (
    'Longest unweighted dependency chain, not a duration forecast. '
    'Parallel branches and role availability also constrain release.'
)


def graph_paths(graph, label, errors):
    """Return prerequisite-first paths without recursion; reject back edges."""
    state, paths = {}, {}
    cyclic = False
    for start in graph:
        if state.get(start) == 2:
            continue
        state[start] = 1
        active = [start]
        stack = [(start, iter(graph[start]))]
        while stack:
            node, edges = stack[-1]
            child = next(edges, None)
            if child is None:
                candidates = [paths[d] for d in graph[node] if d in paths]
                paths[node] = (max(candidates, key=len) if candidates else []) + [node]
                state[node] = 2
                stack.pop()
                active.pop()
            elif state.get(child) == 1:
                cyclic = True
                errors.append(label + ' cycle: ' + ' -> '.join(active[active.index(child):] + [child]))
            elif state.get(child) != 2:
                state[child] = 1
                active.append(child)
                stack.append((child, iter(graph[child])))
    return None if cyclic else paths


def validate_manifest(manifest, schema):
    """Validate data only. Never call GitHub or mutate input objects."""
    errors = []
    report = {
        'result': 'fail', 'item_count': 0, 'native_relationships_expected': 0,
        'dependencies_expected': 0, 'mvp_prerequisite_closure': 0,
        'max_depth': None, 'errors': errors, 'longest_prerequisite_chain': [],
        'critical_path_note': CRITICAL_PATH_NOTE,
    }

    def check(ok, message):
        if not ok:
            errors.append(message)

    if not isinstance(manifest, dict) or not isinstance(manifest.get('items'), list):
        errors.append('manifest: items must be an array')
        return report
    items = manifest['items']
    report['item_count'] = len(items)
    if not isinstance(schema, dict):
        errors.append('schema: expected an object')
        return report
    for key in REQUIRED_FIELDS:
        values = schema.get(key)
        check(isinstance(values, list) and bool(values)
              and all(isinstance(v, str) and v for v in values),
              'schema: missing/invalid ' + key)
    if errors:
        return report

    by = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f'item[{index}]: expected an object')
            continue
        identity = item.get('id')
        if not isinstance(identity, str) or not identity.strip():
            errors.append(f'item[{index}]: missing/invalid stable ID')
            continue
        if identity in by:
            errors.append('duplicate stable ID: ' + identity)
            continue
        by[identity] = item

    parents, dependencies = {}, {}
    invalid_hierarchy = invalid_dependencies = False
    for identity, item in by.items():
        fields = item.get('fields')
        if not isinstance(fields, dict):
            fields = {}
        for key in REQUIRED_FIELDS:
            check(fields.get(key) in schema[key], identity + ': missing/invalid ' + key)
        for key in ('acceptance_criteria', 'expected_tests'):
            values = item.get(key)
            check(isinstance(values, list) and bool(values)
                  and all(isinstance(v, str) and v.strip() for v in values),
                  identity + ': missing/invalid ' + key)
        check(isinstance(item.get('milestone'), str) and bool(item['milestone'].strip()),
              identity + ': missing/invalid milestone')
        check(isinstance(item.get('workstream'), str) and bool(item['workstream']),
              identity + ': missing/invalid workstream')
        check(item.get('work_type') in schema['Work Type'], identity + ': missing/invalid work_type')
        check(item.get('work_type') == fields.get('Work Type'), identity + ': contradictory work_type')

        parent = item.get('parent_id')
        parents[identity] = []
        if 'parent_id' not in item or (parent is not None and not isinstance(parent, str)):
            errors.append(identity + ': missing/invalid parent_id')
            invalid_hierarchy = True
        elif parent is not None:
            report['native_relationships_expected'] += 1
            if parent not in by:
                errors.append(identity + ': nonexistent parent ' + parent)
                invalid_hierarchy = True
            else:
                parents[identity] = [parent]
                check(by[parent].get('workstream') == item.get('workstream'),
                      identity + ': unexpected cross-tier parent')
        else:
            check(item.get('work_type') == 'Epic', identity + ': orphan')

        deps = item.get('dependencies')
        dependencies[identity] = []
        if not isinstance(deps, list):
            errors.append(identity + ': dependencies must be an array')
            invalid_dependencies = True
        else:
            report['dependencies_expected'] += len(deps)
            seen = set()
            for dep in deps:
                if not isinstance(dep, str) or dep not in by or dep == identity:
                    errors.append(identity + ': invalid dependency ' + repr(dep))
                    invalid_dependencies = True
                elif dep in seen:
                    errors.append(identity + ': duplicate dependency ' + dep)
                    invalid_dependencies = True
                else:
                    seen.add(dep)
                    dependencies[identity].append(dep)
            if deps:
                check(fields.get('Dependency Status') == 'Blocked',
                      identity + ': contradictory dependency classification')
                check(fields.get('Readiness') != 'Ready',
                      identity + ': incorrectly ready with unresolved blockers')
        if item.get('work_type') in ('Epic', 'Capability', 'Feature'):
            check(fields.get('Readiness') != 'Ready', identity + ': broad parent marked ready')
        labels = item.get('labels')
        if not isinstance(labels, list):
            errors.append(identity + ': labels must be an array')
        else:
            for label in labels:
                check(isinstance(label, str) and bool(label), identity + ': invalid label')
                if isinstance(label, str):
                    check(not label.startswith(('priority:', 'status:')),
                          identity + ': redundant priority/status label')

    children = collections.Counter(parent for edges in parents.values() for parent in edges)
    for identity, count in children.items():
        check(count <= 100, identity + ': exceeds sub-issue fanout')
    hierarchy_paths = graph_paths(parents, 'hierarchy', errors)
    if hierarchy_paths is not None and not invalid_hierarchy:
        report['max_depth'] = max((len(path) for path in hierarchy_paths.values()), default=0)
        check(report['max_depth'] <= 8, 'hierarchy too deep')
    prerequisite_paths = graph_paths(dependencies, 'blocking', errors)
    if prerequisite_paths is not None and not invalid_dependencies:
        report['longest_prerequisite_chain'] = max(prerequisite_paths.values(), key=len, default=[])
    check(sum(x.get('work_type') == 'Epic' for x in by.values()) == 14, 'expected 14 workstreams')
    for tier in range(14):
        check(any(x.get('workstream') == f'T{tier}' and x.get('work_type') == 'Test'
                  for x in by.values()), f'T{tier}: missing verification')

    closure = set()
    if 'GB-T13.G1' not in by:
        errors.append('missing MVP approval gate GB-T13.G1')
    else:
        pending = ['GB-T13.G1']
        while pending:
            identity = pending.pop()
            if identity in closure:
                continue
            closure.add(identity)
            pending.extend(dependencies[identity])
        for identity in sorted(closure):
            milestone = by[identity].get('milestone')
            check(isinstance(milestone, str) and milestone.startswith(('M0', 'M1', 'M2')),
                  identity + ': MVP approval depends on a later release phase')
    report['mvp_prerequisite_closure'] = len(closure)
    report['result'] = 'fail' if errors else 'pass'
    return report


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def save_report(path, report, directory_fd=None):
    """Stage and replace relative to a pinned directory descriptor."""
    own_fd = directory_fd is None
    if own_fd:
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    temporary = None
    try:
        while True:
            candidate = '.roadmap-' + secrets.token_hex(16) + '.tmp'
            try:
                fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600, dir_fd=directory_fd)
                temporary = candidate
                break
            except FileExistsError:
                continue
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, ensure_ascii=True) + '\n')
        os.replace(temporary, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        if own_fd:
            os.close(directory_fd)



def paths_alias(first, second):
    """Recognize lexical, symlink and hardlink aliases of an input file."""
    if first.resolve() == second.resolve():
        return True
    try:
        return first.samefile(second)
    except FileNotFoundError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'planning/guildboard-backlog.json')
    parser.add_argument('--schema', type=Path, default=ROOT / 'planning/project-schema.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'planning/audit/local-validation.json')
    args = parser.parse_args(argv)
    directory_fd = None
    try:
        directory_fd = os.open(args.report.parent, os.O_RDONLY | os.O_DIRECTORY)
        # Linux procfs resolves through the held directory, even if its original
        # pathname is subsequently retargeted. Fail closed if unavailable.
        anchored_parent = Path('/proc/self/fd') / str(directory_fd)
        if not anchored_parent.is_dir():
            raise OSError('cannot inspect pinned report directory (procfs unavailable)')
        anchored_report = anchored_parent / args.report.name
        if any(paths_alias(anchored_report, source) for source in (args.manifest, args.schema)):
            raise ValueError('report must not alias the manifest or schema; inputs preserved')
    except (OSError, ValueError, RuntimeError) as exc:
        if directory_fd is not None:
            os.close(directory_fd)
        print(json.dumps({'result': 'fail', 'errors': ['report path: ' + str(exc),
              'cannot write validation report: unsafe or unavailable destination']}, indent=2))
        return 1
    try:
        try:
            manifest = json.loads(args.manifest.read_text(), object_pairs_hook=unique_object)
            schema = json.loads(args.schema.read_text(), object_pairs_hook=unique_object)
            report = validate_manifest(manifest, schema)
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            report = {'result': 'fail', 'errors': ['input: ' + str(exc)]}
        try:
            save_report(args.report, report, directory_fd)
        except (OSError, UnicodeError, ValueError) as exc:
            report['result'] = 'fail'
            report['errors'].append('cannot write validation report: ' + str(exc))
    finally:
        os.close(directory_fd)
    print(json.dumps(report, indent=2))
    return int(report['result'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
