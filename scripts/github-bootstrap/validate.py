"""Offline roadmap validation with deterministic, fail-closed JSON diagnostics."""

import argparse
import collections
import json
import os
import secrets
import stat
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


class WindowsDirectory:
    """Directory-relative Windows operations; never reconstruct a destination path."""

    def __init__(self, path):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.nt = ctypes.WinDLL('ntdll')
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                            wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                            ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        self.nt.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
                                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                          wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
                                          wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
        self.nt.NtCreateFile.restype = ctypes.c_long
        self.nt.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                                   ctypes.c_void_p, wintypes.ULONG,
                                                   ctypes.c_int]
        self.nt.NtSetInformationFile.restype = ctypes.c_long
        self.nt.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        self.nt.RtlNtStatusToDosError.restype = wintypes.ULONG
        self.handle = self.kernel.CreateFileW(str(path), 0x001000a2, 7, None, 3,
                                               0x02000000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        self.kernel.CloseHandle(self.handle)

    def open_relative(self, name, access, disposition, insensitive=False):
        c, w = self.ctypes, self.wintypes
        if not name or name in ('.', '..') or any(ch in name for ch in '/\\:'):
            raise OSError('invalid report filename')
        encoded = name.encode('utf-16-le')
        if len(encoded) > 65534:
            raise OSError('report filename is too long')
        class UnicodeString(c.Structure):
            _fields_ = [('Length', w.USHORT), ('MaximumLength', w.USHORT),
                        ('Buffer', c.c_void_p)]
        class ObjectAttributes(c.Structure):
            _fields_ = [('Length', w.ULONG), ('RootDirectory', w.HANDLE),
                        ('ObjectName', c.POINTER(UnicodeString)), ('Attributes', w.ULONG),
                        ('SecurityDescriptor', c.c_void_p), ('SecurityQualityOfService', c.c_void_p)]
        class IoStatus(c.Structure):
            _fields_ = [('Status', c.c_void_p), ('Information', c.c_size_t)]
        buffer = c.create_string_buffer(encoded + b'\0\0')
        name_string = UnicodeString(len(encoded), len(encoded), c.addressof(buffer))
        attrs = ObjectAttributes(c.sizeof(ObjectAttributes), self.handle,
                                 c.pointer(name_string), 0x40 if insensitive else 0, None, None)
        ios = IoStatus()
        handle = w.HANDLE()
        status = self.nt.NtCreateFile(c.byref(handle), access | 0x100000,
                                      c.byref(attrs), c.byref(ios), None, 0x80, 7,
                                      disposition, 0x60, None, 0)
        if status < 0:
            code = self.nt.RtlNtStatusToDosError(status)
            raise c.WinError(code)
        return handle.value

    def identity(self, handle):
        c, w = self.ctypes, self.wintypes
        class FileInformation(c.Structure):
            _fields_ = [('attributes', w.DWORD), ('creation', w.FILETIME),
                        ('access', w.FILETIME), ('write', w.FILETIME),
                        ('volume', w.DWORD), ('size_high', w.DWORD),
                        ('size_low', w.DWORD), ('links', w.DWORD),
                        ('index_high', w.DWORD), ('index_low', w.DWORD)]
        info = FileInformation()
        if not self.kernel.GetFileInformationByHandle(handle, c.byref(info)):
            raise c.WinError(c.get_last_error())
        index = (info.index_high << 32) | info.index_low
        if not index:
            raise OSError('cannot establish file identity')
        return info.volume, index

    def source_identity(self, path):
        c = self.ctypes
        handle = self.kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0x02000000, None)
        if handle == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        try:
            return self.identity(handle)
        finally:
            self.kernel.CloseHandle(handle)

    def target_identity(self, name):
        def lookup(insensitive):
            try:
                handle = self.open_relative(name, 0x80, 1, insensitive)
            except OSError as exc:
                if exc.winerror in (2, 3):
                    return None
                raise
            try:
                return self.identity(handle)
            finally:
                self.kernel.CloseHandle(handle)

        exact, folded = lookup(False), lookup(True)
        if exact and folded and exact != folded:
            raise OSError('ambiguous case-sensitive report destination')
        return exact or folded

    def publish(self, name, report):
        import msvcrt
        c, w = self.ctypes, self.wintypes
        while True:
            temporary = '.roadmap-' + secrets.token_hex(16) + '.tmp'
            try:
                handle = self.open_relative(temporary, 0x00010002, 2)
                break
            except OSError as exc:
                if exc.winerror not in (80, 183):
                    raise OSError(f'cannot create report stage: {exc}') from exc
        fd = None
        published = False
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            payload = (json.dumps(report, indent=2, ensure_ascii=True) + '\n').encode('utf-8')
            while payload:
                count = os.write(fd, payload)
                if not count:
                    raise OSError('short report write')
                payload = payload[count:]
            encoded = name.encode('utf-16-le')
            class RenameInfo(c.Structure):
                _fields_ = [('ReplaceIfExists', c.c_ubyte), ('RootDirectory', w.HANDLE),
                            ('FileNameLength', w.DWORD), ('FileName', w.WCHAR * 1)]
            size = RenameInfo.FileName.offset + len(encoded)
            buffer = c.create_string_buffer(max(size, c.sizeof(RenameInfo)))
            info = RenameInfo.from_buffer(buffer)
            info.ReplaceIfExists = True
            info.RootDirectory = self.handle
            info.FileNameLength = len(encoded)
            c.memmove(c.addressof(buffer) + RenameInfo.FileName.offset, encoded, len(encoded))
            class IoStatus(c.Structure):
                _fields_ = [('Status', c.c_void_p), ('Information', c.c_size_t)]
            ios = IoStatus()
            # FileRenameInformation (10) preserves RootDirectory. The Win32
            # FileRenameInfo wrapper returned ERROR_INVALID_PARAMETER on the
            # hosted Windows runner for this same directory-relative request.
            status = self.nt.NtSetInformationFile(handle, c.byref(ios), buffer,
                                                   max(size, c.sizeof(RenameInfo)), 10)
            if status < 0:
                error = c.WinError(self.nt.RtlNtStatusToDosError(status))
                raise OSError(f'cannot rename report stage: {error}') from error
            published = True
        finally:
            if not published:
                delete = w.BOOL(True)
                self.kernel.SetFileInformationByHandle(handle, 4, c.byref(delete), c.sizeof(delete))
            if fd is None:
                self.kernel.CloseHandle(handle)
            else:
                os.close(fd)


def open_report_directory(path):
    """Pin a POSIX directory without resolving its pathname again."""
    if os.name == 'nt':
        return WindowsDirectory(path)
    if os.name != 'posix' or not all(fn in os.supports_dir_fd for fn in
                                      (os.open, os.stat, os.rename, os.unlink)):
        raise OSError('pinned report directory operations are unavailable')
    flags = getattr(os, 'O_PATH', os.O_RDONLY) | getattr(os, 'O_DIRECTORY', 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise NotADirectoryError(str(path))
        return fd
    except BaseException:
        os.close(fd)
        raise


def save_report(path, report, directory_fd=None):
    """Stage and replace relative to a pinned directory descriptor."""
    own_fd = directory_fd is None
    if own_fd:
        directory_fd = open_report_directory(path.parent)
    if isinstance(directory_fd, WindowsDirectory):
        try:
            directory_fd.publish(path.name, report)
        finally:
            if own_fd:
                directory_fd.close()
        return
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



def report_aliases_input(directory_fd, report_name, sources):
    """Compare existing input identities to the destination in the pinned directory.

    Missing inputs are rejected: without their identities we cannot establish that
    a dangling destination link or a case-insensitive name does not alias them.
    """
    if isinstance(directory_fd, WindowsDirectory):
        source_ids = [directory_fd.source_identity(source) for source in sources]
        target = directory_fd.target_identity(report_name)
        return target is not None and target in source_ids
    source_stats = [os.stat(source) for source in sources]
    try:
        target = os.stat(report_name, dir_fd=directory_fd)
    except FileNotFoundError:
        return False
    return any(os.path.samestat(target, source) for source in source_stats)


def close_report_directory(directory):
    if isinstance(directory, WindowsDirectory):
        directory.close()
    else:
        os.close(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'planning/guildboard-backlog.json')
    parser.add_argument('--schema', type=Path, default=ROOT / 'planning/project-schema.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'planning/audit/local-validation.json')
    args = parser.parse_args(argv)
    directory_fd = None
    try:
        directory_fd = open_report_directory(args.report.parent)
        if report_aliases_input(directory_fd, args.report.name, (args.manifest, args.schema)):
            raise ValueError('report must not alias the manifest or schema; inputs preserved')
    except (OSError, ValueError, RuntimeError) as exc:
        if directory_fd is not None:
            close_report_directory(directory_fd)
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
        close_report_directory(directory_fd)
    print(json.dumps(report, indent=2))
    return int(report['result'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
