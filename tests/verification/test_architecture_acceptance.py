import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('verifier', ROOT / 'scripts/verification/verify_architecture.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in v.BASELINE:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
    def tearDown(self):
        self.tmp.cleanup()
    def test_baseline(self):
        self.assertIn('PASS', v.verify(self.root))
    def test_architecture_reversals_and_omissions(self):
        p = self.root / 'docs/architecture.md'
        original = p.read_text()
        mutations = [
            ('B --> C', 'B --> DB'),
            ('atomic state + revision + receipt + outbox + audit commit', 'ACK before commit'),
            ('Revocation ordered first suppresses subsequent queued releases', 'Revocation permits subsequent queued releases'),
            ('never replay the operation into the restored document', 'replay the operation into the restored document'),
            ('Public clients cannot directly reach SQL or assets', 'Public assets are allowed'),
            ('external ingress, proxy-to-service hop and private data plane', 'external ingress'),
            ('C --> S[(Private assets: quarantine and finalized objects)]', ''),
            ('D-->>C: durable commit\n    C->>C: serialized protected release check\n    C-->>A: ACK only if release authorized', 'C-->>A: ACK only if release authorized\n    D-->>C: durable commit'),
            ('[ADR 0002](adr/0002-server-authority-and-interactions.md)', '[ADR 0002](missing.md)'),
        ]
        for old, new in mutations:
            with self.subTest(old=old):
                self.assertIn(old, original)
                p.write_text(original.replace(old, new, 1))
                with self.assertRaises(v.VerificationError): v.verify(self.root)
    def test_fixture_nested_malformed_and_scenario_reversal(self):
        p = self.root / 'docs/specifications/fixtures/GB-T0-01-02-interactions.json'
        original = json.loads(p.read_text())
        for change in ('malformed', 'reversal', 'missing_reference'):
            obj = json.loads(json.dumps(original))
            if change == 'malformed': obj['scenarios'][0]['contract_scenarios'] = {'bad': [None]}
            elif change == 'reversal': obj['scenarios'][0]['expected'] = 'ACK before commit'
            else: obj['scenarios'][0]['contract_scenarios'] = []
            p.write_text(json.dumps(obj))
            with self.subTest(change=change), self.assertRaises(v.VerificationError): v.verify(self.root)
    def test_missing_prerequisite_and_invalid_config(self):
        (self.root / next(iter(v.BASELINE))).unlink()
        with self.assertRaises(v.VerificationError): v.verify(self.root)
        with self.assertRaises(v.VerificationError): v.verify(None)
        self.assertEqual(v.main(['--root', str(self.root / 'missing')]), 1)
    def test_oversized_regular_file_and_growth_after_fstat(self):
        p = self.root / next(iter(v.BASELINE))
        p.write_bytes(b'x' * (v.SIZE_LIMIT + 1))
        with self.assertRaisesRegex(v.VerificationError, 'input exceeds size limit'):
            v.verify(self.root)
        # A small reported size must not authorize an unrestricted read.
        actual_fstat = v.os.fstat
        def small_size(fd):
            result = actual_fstat(fd)
            values = list(result)
            values[6] = 1
            return os.stat_result(values)
        with mock.patch.object(v.os, 'fstat', side_effect=small_size):
            with self.assertRaisesRegex(v.VerificationError, 'input exceeds size limit'):
                v.verify(self.root)

    def test_directory_and_symlink_rejected(self):
        p = self.root / next(iter(v.BASELINE))
        p.unlink()
        p.mkdir()
        with self.assertRaises(v.VerificationError): v.verify(self.root)
        p.rmdir()
        try:
            p.symlink_to(ROOT / next(iter(v.BASELINE)))
        except (OSError, NotImplementedError) as exc:
            self.skipTest('symlinks unavailable: ' + str(exc))
        with self.assertRaises(v.VerificationError): v.verify(self.root)

    @unittest.skipUnless(hasattr(os, 'mkfifo') and hasattr(os, 'O_NONBLOCK'), 'POSIX FIFO required')
    def test_fifo_without_writer_is_rejected(self):
        p = self.root / next(iter(v.BASELINE))
        p.unlink()
        os.mkfifo(p)
        # Assert the open itself is nonblocking; no writer or subprocess needed.
        real_open = os.open
        def checked_open(path, flags, *args, **kwargs):
            self.assertTrue(flags & os.O_NONBLOCK)
            return real_open(path, flags, *args, **kwargs)
        with mock.patch.object(v.os, 'open', side_effect=checked_open):
            with self.assertRaisesRegex(v.VerificationError, 'not a regular file'):
                v.verify(self.root)

    def test_missing_safe_open_flags_fails_closed(self):
        with mock.patch.object(v.os, 'O_NOFOLLOW', create=True):
            del v.os.O_NOFOLLOW
            with self.assertRaisesRegex(v.VerificationError, 'unsupported'):
                v.verify(self.root)

    def test_interruption_is_not_success(self):
        def stop(): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): v.verify(self.root, stop)
        old = v.verify
        try:
            v.verify = lambda root: (_ for _ in ()).throw(KeyboardInterrupt())
            self.assertEqual(v.main(['--root', str(self.root)]), 130)
        finally: v.verify = old

class ControlsProjection(unittest.TestCase):
    seed_build_output = False

    def setUp(self):
        spec = importlib.util.spec_from_file_location('controls_acceptance', ROOT / 'scripts/verification/verify_architecture_controls.py')
        self.h = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.h)
        spec = importlib.util.spec_from_file_location('controls_gate', ROOT / 'scripts/architecture-controls/check.py')
        self.h.g = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.h.g)
        self.tmp = tempfile.TemporaryDirectory()
        self.tree = Path(self.tmp.name) / 'tree'
        self.original_source = self.h.snapshot(ROOT)
        self.source = Path(self.tmp.name) / 'source'
        self.h.copy_projection(ROOT, self.source)
        if self.seed_build_output:
            output = self.source / 'apps/api/dist'
            output.mkdir(exist_ok=True)
            (output / 'fixture-build-output.js').write_text('// synthetic build output\n')
        # Qualify only the owned test fixture before injecting invalid entries.
        # Include copied build outputs rather than filtering protected names.
        # This synthetic witness never changes the checkout's accepted baseline.
        witness = self.source / 'docs/architecture-controls/baseline.json'
        data = json.loads(witness.read_text())
        names = set(data['boundaries'])
        for folder in ('apps', 'packages', 'database', 'infra/godaddy'):
            names.update(str(p.relative_to(self.source))
                         for p in (self.source / folder).rglob('*') if p.is_file())
        data['boundaries'] = {
            name: hashlib.sha256((self.source / name).read_bytes()).hexdigest()
            for name in sorted(names)
        }
        witness.write_text(json.dumps(data, indent=2) + '\n')
        self.h.copy_projection(self.source, self.tree)
    def tearDown(self):
        try:
            self.assertEqual(self.original_source, self.h.snapshot(ROOT))
        finally:
            self.tmp.cleanup()
    def test_protected_generated_names_preserved_and_rejected_by_gate(self):
        self.h.g.check(self.source, self.tree)
        original = self.h.snapshot(self.tree)
        for name in ('dist', 'node_modules', '.git', '__pycache__'):
            p = self.tree / 'apps/api' / name
            existed = p.exists()
            p.mkdir(exist_ok=True)
            hidden = p / 'hidden'
            self.assertFalse(hidden.exists())
            try:
                hidden.write_text('unrecorded')
                with self.assertRaises(self.h.g.Invalid): self.h.g.check(self.source, self.tree)
                out = Path(self.tmp.name) / ('copy-' + name)
                self.h.copy_projection(self.tree, out)
                self.assertEqual((out / 'apps/api' / name / 'hidden').read_text(), 'unrecorded')
                with self.assertRaises(self.h.g.Invalid): self.h.g.check(self.source, out)
            finally:
                hidden.unlink(missing_ok=True)
                if not existed:
                    p.rmdir()
            self.assertEqual(original, self.h.snapshot(self.tree))
            self.h.g.check(self.source, self.tree)
        before = self.h.snapshot(self.tree)
        for name in ('.git', 'node_modules', 'dist'):
            p = self.tree / name; p.mkdir(); (p / 'junk').write_text('outside roots')
        self.assertEqual(before, self.h.snapshot(self.tree))

    def test_global_limits_and_race_fail_closed(self):
        p = self.tree / 'apps/api'
        for i in range(4): (p / ('empty'+str(i))).mkdir()
        with mock.patch.object(self.h, 'MAX_DIRS', 3):
            with self.assertRaises(ValueError): self.h.projection(self.tree)
        with mock.patch.object(self.h, 'MAX_ENTRIES', 3):
            with self.assertRaises(ValueError): self.h.projection(self.tree)
        deep = p
        for i in range(6):
            deep = deep / ('depth'+str(i)); deep.mkdir()
        with mock.patch.object(self.h, 'MAX_DEPTH', 5):
            with self.assertRaises(ValueError): self.h.projection(self.tree)
        with mock.patch.object(self.h, 'MAX_CONTENT', 1):
            with self.assertRaises(ValueError): self.h.projection(self.tree)
        real_read = self.h.g.read
        def add(root, name):
            data = real_read(root, name)
            (p / 'raced').touch()
            return data
        out = Path(self.tmp.name) / 'race-output'
        with mock.patch.object(self.h.g, 'read', side_effect=add):
            with self.assertRaises(ValueError): self.h.copy_projection(self.tree, out)
        self.assertFalse(out.exists())

    def test_enumeration_addition_and_replacement(self):
        real_listdir = self.h.os.listdir
        for action in ('add', 'replace'):
            target = self.tree / 'apps/api'
            identity = os.stat(target).st_ino
            fired = [False]
            def race(fd):
                names = real_listdir(fd)
                if not fired[0] and os.fstat(fd).st_ino == identity:
                    fired[0] = True
                    if action == 'add': (target / 'late').touch()
                    else:
                        target.rename(target.parent / 'api-old')
                        target.mkdir()
                return names
            out = Path(self.tmp.name) / ('enum-' + action)
            with mock.patch.object(self.h.os, 'listdir', side_effect=race):
                with self.assertRaises((ValueError, OSError, self.h.g.Invalid)):
                    self.h.copy_projection(self.tree, out)
            self.assertTrue(fired[0]); self.assertFalse(out.exists())
            if action == 'add': (target / 'late').unlink()
            else:
                target.rmdir(); (target.parent / 'api-old').rename(target)

    def test_catalog_traversal_rejected_before_fixture_write(self):
        path = self.tree / 'docs/architecture-controls/traceability.json'
        obj = json.loads(path.read_text())
        next(iter(obj['interfaces'].values()))['evidence'].append('../escape')
        path.write_text(json.dumps(obj))
        out = Path(self.tmp.name) / 'bad-catalog'
        with self.assertRaises((ValueError, OSError, self.h.g.Invalid)):
            self.h.copy_projection(self.tree, out)
        self.assertFalse(out.exists())

    def test_unsafe_entries_rejected_without_source_writes(self):
        before = self.h.snapshot(self.tree)
        for kind in ('symlink', 'fifo'):
            p = self.tree / ('apps/api/dist' if kind == 'symlink' else 'apps/api/node_modules')
            saved = Path(self.tmp.name) / ('saved-' + kind)
            existed = p.exists()
            if existed:
                p.rename(saved)
            try:
                if kind == 'symlink': p.symlink_to('README.md')
                else: os.mkfifo(p)
                with self.assertRaises((ValueError, OSError, self.h.g.Invalid)):
                    self.h.copy_projection(self.tree, Path(self.tmp.name) / ('out-' + kind))
                self.assertFalse((Path(self.tmp.name) / ('out-' + kind)).exists())
            finally:
                p.unlink(missing_ok=True)
                if existed:
                    saved.rename(p)
            self.assertEqual(before, self.h.snapshot(self.tree))
    def test_write_failure_cleans_staging(self):
        out = Path(self.tmp.name) / 'write-failure'
        with mock.patch.object(Path, 'write_bytes', side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError): self.h.copy_projection(self.tree, out)
        self.assertFalse(out.exists())
        self.assertFalse(list(Path(self.tmp.name).glob('.projection-*')))

    def test_revision_validation(self):
        self.assertEqual(self.h.revision('a' * 40), 'a' * 40)
        for value in ('abc', 'A' * 40, 'g' * 40, 'a' * 41):
            with self.assertRaises(self.h.argparse.ArgumentTypeError): self.h.revision(value)


class BuiltControlsProjection(ControlsProjection):
    """Run the same controls with pre-existing projected build output."""
    seed_build_output = True


if __name__ == '__main__': unittest.main()
