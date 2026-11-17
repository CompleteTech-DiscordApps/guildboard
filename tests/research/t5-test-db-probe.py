"""Fake Docker safety regressions; no daemon or database is contacted."""
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "t5_db_probe", Path(__file__).resolve().parents[2] / "scripts/research/t5-db-probe.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeDocker:
    def __init__(self, probe, volume_owner=None, timeout_after_create=False, delayed_creation=None):
        self.probe = probe
        self.volumes = {} if volume_owner is None else {probe.volume: volume_owner}
        self.containers = {}
        self.timeout_after_create = timeout_after_create
        self.delayed_creation = delayed_creation
        self.pending_creation = None
        self.calls = []
        self.sql_calls = []
        self.failures = {}
        self.removal_noop = False

    def command(self, *args, **kwargs):
        self.calls.append(args)
        if self.failures.get(args, 0):
            self.failures[args] -= 1
            if kwargs.get("check", True):
                raise subprocess.CalledProcessError(1, args, stderr="temporary daemon failure")
            return subprocess.CompletedProcess(args, 1, "", "temporary daemon failure")
        stdout, code = "", 0
        p = self.probe
        if args[:2] == ("image", "inspect"):
            stdout = json.dumps([{"Id": "sha256:fixture", "RepoDigests": [p.image]}])
        elif args[:2] == ("volume", "create"):
            self.delay_if_requested("volume", self.volumes, p.volume)
            self.volumes.setdefault(p.volume, p.run_id)
            if self.timeout_after_create:
                raise subprocess.TimeoutExpired("docker volume create", 90)
        elif args[:2] in (("volume", "inspect"), ("container", "inspect")):
            resources = self.volumes if args[0] == "volume" else self.containers
            if args[2] not in resources:
                code = 1
            else:
                owner = resources[args[2]]
                labels = None if owner == "unlabeled" else {p.label: owner}
                value = {"Labels": labels} if args[0] == "volume" else {"Config": {"Labels": labels}}
                stdout = json.dumps([value])
        elif args[0] == "run":
            self.delay_if_requested("container", self.containers, p.name)
            self.containers[p.name] = p.run_id
        elif args[0] == "rm":
            del self.containers[args[-1]]
        elif args[:2] == ("volume", "rm"):
            if not self.removal_noop:
                del self.volumes[args[2]]
        elif args[0] == "ps":
            stdout = "\n".join(self.containers)
        elif args[:2] == ("volume", "ls"):
            stdout = "\n".join(self.volumes)
        else:
            raise AssertionError("unexpected Docker command: " + repr(args))
        if code and kwargs.get("check", True):
            raise subprocess.CalledProcessError(code, args)
        return subprocess.CompletedProcess(args, code, stdout, "")

    def delay_if_requested(self, kind, resources, name):
        if self.delayed_creation == kind:
            self.pending_creation = (resources, name)
            raise subprocess.TimeoutExpired("docker create", 90)

    def complete_pending_creation(self):
        resources, name = self.pending_creation
        resources.setdefault(name, self.probe.run_id)
        self.pending_creation = None

    def sql(self, *args, **kwargs):
        self.sql_calls.append((args, kwargs))
        return "fixture"


class OwnershipTests(unittest.TestCase):
    def make_probe(self, **kwargs):
        with patch.object(module.subprocess, "check_output", return_value="fake-context"):
            p = module.Probe("mysql", "mysql@sha256:" + "0" * 64)
        fake = FakeDocker(p, **kwargs)
        p.command, p.sql, p.ready = fake.command, fake.sql, lambda: None
        return p, fake

    def test_foreign_or_unlabeled_collision_never_launches_or_initializes(self):
        for owner in ("another-invocation", "unlabeled"):
            with self.subTest(owner=owner):
                p, fake = self.make_probe(volume_owner=owner)
                with self.assertRaisesRegex(RuntimeError, "ownership"):
                    p.start()
                self.assertFalse(any(c[0] == "run" for c in fake.calls))
                self.assertEqual(fake.sql_calls, [])
                with self.assertRaisesRegex(RuntimeError, "ownership"):
                    p.cleanup()
                self.assertEqual(fake.volumes, {p.volume: owner})
                self.assertFalse(any(c[:2] == ("volume", "rm") for c in fake.calls))

    def test_timed_out_create_still_cleans_owned_volume(self):
        p, fake = self.make_probe(timeout_after_create=True)
        with self.assertRaises(subprocess.TimeoutExpired):
            p.start()
        self.assertEqual(fake.volumes, {p.volume: p.run_id})
        p.cleanup()
        self.assertEqual(fake.volumes, {})
        self.assertTrue(p.report["cleanup"]["volume_absent"])
        self.assertFalse(any(c[0] == "run" for c in fake.calls))

    def test_creation_after_both_inventories_leaves_cleanup_unresolved(self):
        for kind in ("volume", "container"):
            with self.subTest(kind=kind):
                p, fake = self.make_probe(delayed_creation=kind)
                code, report = self.run_main(p, start=True)
                self.assertEqual(code, 1)
                self.assertEqual(report["result"], "fail")
                self.assertIn("creation unresolved", report["cleanup_error"])
                cleanup = report["cleanup"]
                self.assertEqual(cleanup["unresolved_creation"], [kind])
                observed = cleanup["observed_absence_at_final_inventory"]
                self.assertTrue(observed[kind + "_absent"])
                self.assertIsNone(cleanup[kind + "_absent"])
                self.assertFalse(any(c[0] == "rm" or c[:2] == ("volume", "rm")
                                     for c in fake.calls))
                if kind == "container":
                    self.assertEqual(fake.volumes, {p.volume: p.run_id})
                    self.assertFalse(observed["volume_absent"])
                    self.assertIsNone(cleanup["volume_absent"])

                # The daemon completes creation only after cleanup returns.
                fake.complete_pending_creation()
                p.cleanup()
                self.assertEqual(fake.volumes, {})
                self.assertEqual(fake.containers, {})
                self.assertEqual(p.report["cleanup"]["unresolved_creation"], [])
                self.assertTrue(p.report["cleanup"]["container_absent"])
                self.assertTrue(p.report["cleanup"]["volume_absent"])

    def test_timed_out_create_collision_preserves_foreign_volume(self):
        p, fake = self.make_probe(volume_owner="foreign", timeout_after_create=True)
        with self.assertRaises(subprocess.TimeoutExpired):
            p.start()
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            p.cleanup()
        self.assertEqual(fake.volumes, {p.volume: "foreign"})
        self.assertFalse(any(c[:2] == ("volume", "rm") for c in fake.calls))

    def test_owned_volume_is_verified_before_launch_and_removed_after(self):
        p, fake = self.make_probe()
        p.start()
        self.assertLess(fake.calls.index(("volume", "inspect", p.volume)),
                        next(i for i, c in enumerate(fake.calls) if c[0] == "run"))
        self.assertTrue(fake.sql_calls)
        p.cleanup()
        self.assertEqual(fake.volumes, {})
        self.assertEqual(fake.containers, {})
        self.assertTrue(p.report["cleanup"]["container_absent"])

    def test_cleanup_preserves_foreign_container(self):
        p, fake = self.make_probe()
        fake.containers[p.name] = "foreign"
        fake.volumes[p.volume] = p.run_id
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            p.cleanup()
        self.assertEqual(fake.containers, {p.name: "foreign"})
        self.assertEqual(fake.volumes, {})
        self.assertFalse(any(c[0] == "rm" for c in fake.calls))

    def run_main(self, p, *, start=False):
        if not start:
            p.start = lambda: None
        p.exercise = lambda: None
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            argv = ['probe', '--engine', 'mysql', '--image', p.image, '--output', str(output)]
            with patch.object(module, 'Probe', return_value=p), patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = module.main()
            return code, json.loads(output.read_text())

    def test_transient_inspect_failure_fails_main_and_can_retry_safely(self):
        p, fake = self.make_probe()
        p.start()
        fake.failures[("volume", "inspect", p.volume)] = 1
        code, report = self.run_main(p)
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'fail')
        self.assertFalse(report['cleanup']['volume_absent'])
        self.assertEqual(fake.volumes, {p.volume: p.run_id})
        # A retry must recheck ownership if the exact name changed meanwhile.
        fake.volumes[p.volume] = "foreign"
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            p.cleanup()
        self.assertEqual(fake.volumes[p.volume], "foreign")
        fake.volumes[p.volume] = p.run_id
        p.cleanup()
        self.assertEqual(fake.volumes, {})
        self.assertTrue(p.report['cleanup']['volume_absent'])

    def test_successful_remove_response_cannot_hide_remaining_resource(self):
        p, fake = self.make_probe()
        p.start()
        fake.removal_noop = True
        code, report = self.run_main(p)
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'fail')
        self.assertFalse(report['cleanup']['volume_absent'])
        self.assertIn(p.volume, fake.volumes)

    def test_inventory_failure_is_unknown_and_never_authorizes_deletion(self):
        p, fake = self.make_probe()
        p.start()
        fake.failures[("volume", "ls", "--format", "{{.Name}}",)] = 2
        code, report = self.run_main(p)
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'fail')
        self.assertIsNone(report['cleanup']['volume_absent'])
        self.assertIn(p.volume, fake.volumes)
        self.assertFalse(any(c[:2] == ('volume', 'rm') for c in fake.calls))

    def test_cleanup_absent_resources_is_safe(self):
        p, fake = self.make_probe()
        p.cleanup()
        self.assertTrue(p.report["cleanup"]["container_absent"])
        self.assertTrue(p.report["cleanup"]["volume_absent"])


class ConstraintFixtureTests(unittest.TestCase):
    def test_d03_varies_the_operation_and_revision_constraints_independently(self):
        with patch.object(module.subprocess, "check_output", return_value="fake-context"):
            probe = module.Probe("mysql", "mysql@sha256:" + "0" * 64)
        with patch.object(probe, "bundle", return_value="same rows"), \
                patch.object(probe, "sql", side_effect=["1\nERROR 1062", "1\nERROR 1062",
                                                       "1\nERROR 1452"]) as sql, \
                contextlib.redirect_stdout(io.StringIO()):
            probe.check_scoped_constraints()
        values = [
            "'1','board-a','lineage-a','actor-a','op-1',REPEAT('9',64),9",
            "'1','board-a','lineage-a','actor-a','op-x',REPEAT('9',64),1",
            "'2','board-a','lineage-a','actor-a','op-x',REPEAT('9',64),9",
        ]
        self.assertEqual(
            [(f"INSERT INTO receipts VALUES ({fields});", {"check": False})
             for fields in values],
            [(call.args[0], call.kwargs) for call in sql.call_args_list],
        )
        self.assertEqual(probe.report["checks"][0]["result"], "pass")


if __name__ == "__main__":
    unittest.main()
