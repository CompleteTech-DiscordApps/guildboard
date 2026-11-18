"""Offline checks for the #416 traceability plan."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_t12_verification_evidence_contract as contract

from scripts.verification import t12_regression_matrix as regression


class RegressionMatrixTest(unittest.TestCase):
    def setUp(self):
        self.matrix = regression.load(regression.ROOT, regression.MATRIX)

    def test_report_resolves_canonical_requirements_and_handoffs(self):
        report = regression.audit(regression.ROOT, self.matrix)
        rows = report["requirements"]
        self.assertEqual({row["case"] for row in report["mvp"]}, contract.MVP_BEHAVIORS)
        self.assertEqual(sum(row["gate"] == regression.G3 for row in rows), 187)
        self.assertEqual(sum(row["gate"] == regression.G1 for row in rows), 118)
        self.assertNotIn("Post-v1.0", {row["gate"] for row in rows})
        self.assertIn("GB-T8.02.01.V2", report["verificationIssues"])
        mvp = {row["case"]: row["observationRows"] for row in report["mvp"]}
        self.assertEqual(mvp["moderator-role"], [["integrated", "hosted"]])
        self.assertIn(["discord-startup", "discord-win"], mvp["activity-startup"])
        for row in rows:
            self.assertEqual(row["scopeEvidenceStatus"], "pending")
            self.assertEqual(row["handoffIssue"]["id"], row["handoff"])
            self.assertIn("/issues/", row["handoffIssue"]["url"])
            for issue in row["verification"]:
                self.assertTrue(report["verificationIssues"][issue]["expectedTests"])

        startup = next(row for row in report["mvp"] if row["case"] == "activity-startup")
        self.assertEqual({entry["method"] for entry in startup["observations"]}, {"automated", "owned-platform"})
        self.assertTrue(all(entry["cases"] == ["activity-startup"] for entry in startup["observations"]))
        accessibility = report["stableFunctionality"]["accessibility"]
        manual_rows = [entry for entry in accessibility if entry["method"] == "manual"]
        self.assertEqual({entry["row"][1] for entry in manual_rows}, contract.DISCORD_ROWS)
        self.assertTrue(all(entry["cases"] == ["accessible-task-coverage"] for entry in manual_rows))
        self.assertTrue(all(entry["source"] == regression.T12 for entry in manual_rows))
        self.assertTrue(all(entry["environmentSource"].startswith(regression.PLATFORMS) for entry in manual_rows))
        acceptance = next(row for row in rows if row["text"] == "run production smoke after deployment")
        self.assertEqual(acceptance["handoffIssue"]["url"].rsplit("/", 1)[1], "418")
        self.assertIn("GB-T12.04.02.V1", {item["id"] for item in
                                       report["handoffs"]["GB-T12.D1"]["prerequisites"]})
        deployed = acceptance["scopeObservationLinks"]
        self.assertEqual({entry["row"][0] for entry in deployed}, {"deployed-build-smoke", "deployed-client-smoke"})
        self.assertIn("regression", {entry["row"][0] for entry in acceptance["issueLevelObservationLinks"]})
        browser = next(row for row in rows if row["text"].startswith("Exercise actual UI launch/ready/auth/navigation"))
        self.assertEqual({entry["row"][0] for entry in browser["scopeObservationLinks"]},
                         {"browser-e2e", "sdk-launch"})
        self.assertTrue(all(entry["issue"].endswith("/417") and entry["status"] == "blocked"
                            for entry in deployed))

    def test_rows_match_accepted_t12_gate_and_behavior_floors(self):
        report = regression.audit(regression.ROOT, self.matrix)
        self.assertEqual(set(report["platformEnvironments"]), contract.EXTERNAL)
        rows = {(row["id"], row["environment"]): row for row in report["rows"]}
        for gate in regression.GATES:
            gate_rows = {key: row for key, row in rows.items() if gate in row["gates"]}
            self.assertEqual(set(report["gates"][gate]["prerequisites"]),
                             contract.native_gate_dependencies(gate))
            for key, (issue, cases) in contract.gate_coverage(gate, contract.DISCORD_ROWS).items():
                with self.subTest(gate=gate, row=key):
                    self.assertEqual(gate_rows[key]["issue"], issue)
                    self.assertEqual(gate_rows[key]["class"], contract.CLASS_BY_ROW[key[1]])
                    self.assertLessEqual(cases, set(gate_rows[key]["casesByGate"][gate]))
            if gate != regression.G2:
                self.assertLessEqual(contract.SECURITY_KEYS, gate_rows.keys())

    def test_rejects_missing_or_substituted_evidence(self):
        for attack, diagnostic in (
            (lambda m: m["mvp"].pop("activity-startup"), "mandatory MVP"),
            (lambda m: m["stable"]["integratedCases"].remove("modes"), "mandatory stable"),
            (lambda m: m["rows"].pop(), "missing required evidence rows"),
            (lambda m: m["rows"][0].update(environment="local"), "unknown environment"),
            (lambda m: m["rows"][0].update(gates=[regression.G2]), "wrong native issue or release gate"),
            (lambda m: m["rows"][0].update(issue=417), "wrong native issue or release gate"),
            (lambda m: m["rows"][0].update(status="pass"), "unsupported status"),
            (lambda m: m["rows"][0].update(candidateSha="1" * 40), "unexpected row field"),
            (lambda m: m["productionSmoke"].update(state="closed"), "#417 production smoke"),
        ):
            matrix = copy.deepcopy(self.matrix)
            attack(matrix)
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(ValueError, diagnostic):
                regression.audit(regression.ROOT, matrix)

    def test_each_row_rejects_case_loss_case_invention_source_swap_and_freeform_claims(self):
        for index, original in enumerate(self.matrix["rows"]):
            unrelated_source = regression.T9 if original["source"] == regression.T12 else regression.T12
            for change, diagnostic in (
                ({"cases": original["cases"][1:]}, "canonical observation cases"),
                ({"cases": ["other-case", *original["cases"][1:]]}, "canonical observation cases"),
                ({"cases": [*original["cases"], "other-case"]}, "canonical observation cases"),
                ({"source": unrelated_source}, "canonical observation source"),
                ({"limitation": "All acceptance checks passed."}, "planned status or limitation"),
            ):
                matrix = copy.deepcopy(self.matrix)
                matrix["rows"][index].update(change)
                with self.subTest(row=original["id"], environment=original["environment"], change=change):
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        regression.audit(regression.ROOT, matrix)

    def test_browser_and_regression_have_explicit_accepted_observations(self):
        report = regression.audit(regression.ROOT, self.matrix)
        rows = {(row["id"], row["environment"]): row for row in report["rows"]}
        self.assertEqual(set(rows["browser-e2e", "local"]["cases"]), {
            "controlled-launch", "ready", "auth", "cancel", "navigation", "policy-feedback",
            "reconnect", "drafts", "accessible-controls",
        })
        self.assertLessEqual(contract.MVP_BEHAVIORS | {"modes", "moderation", "import-export", "recovery",
                                                       "accessibility", "verified-build"},
                             set(rows["regression", "hosted"]["cases"]))
        self.assertLessEqual({"verified-build", "https-wss", "smoke"},
                             set(rows["deployed-build-smoke", "vps-network"]["cases"]))
        for client in contract.DISCORD_ROWS:
            self.assertLessEqual({"verified-build", "deployed-client-journey", "activity-startup",
                                  "authenticated-guild", "mapped-proxy", "reconnect"},
                                 set(rows["deployed-client-smoke", client]["cases"]))

    def test_each_native_gate_rejects_omission_or_duplicate(self):
        for gate in regression.GATES:
            for replacement in ([], [*self.matrix["nativePrerequisites"][gate],
                                     self.matrix["nativePrerequisites"][gate][0]]):
                matrix = copy.deepcopy(self.matrix)
                matrix["nativePrerequisites"][gate] = replacement
                with self.subTest(gate=gate, replacement=replacement):
                    with self.assertRaisesRegex(ValueError, "native release prerequisite list"):
                        regression.audit(regression.ROOT, matrix)

    def test_rejects_ambiguous_source_registries(self):
        original_load = regression.load
        for path, collection, diagnostic in (
            (regression.BACKLOG, "items", "duplicate registry identity"),
            (regression.HANDOFF, "handoffMatrix", "duplicate registry identity"),
            (regression.PLATFORMS, "external_rows", "duplicate registry identity"),
            (regression.TRACE, None, "duplicate registry identity"),
        ):
            data = original_load(regression.ROOT, path)
            rows = data[collection] if collection else data
            rows.insert(0, copy.deepcopy(rows[0]))
            with self.subTest(path=path), patch.object(regression, "load", side_effect=(
                lambda root, name: data if name == path else original_load(root, name)
            )):
                with self.assertRaisesRegex(ValueError, diagnostic):
                    regression.audit(regression.ROOT, self.matrix)

        for field in ("number", "id"):
            registry = original_load(regression.ROOT, regression.BACKLOG)
            first, second = registry["items"][:2]
            second["github"][field] = first["github"][field]
            with self.subTest(field=field), patch.object(regression, "load", side_effect=(
                lambda root, name: registry if name == regression.BACKLOG else original_load(root, name)
            )):
                with self.assertRaisesRegex(ValueError, "duplicate registry identity"):
                    regression.audit(regression.ROOT, self.matrix)

    def test_mvp_source_rejects_duplicate_behavior_omission_and_verification(self):
        original = (regression.ROOT / regression.MVP).read_text(encoding="utf-8")
        line = next(line for line in original.splitlines() if line.startswith("| Discord Activity startup |"))
        duplicate_link = line.split("|")[3].strip()
        native = {row["id"]: row["github"]["number"] for row in
                  regression.load(regression.ROOT, regression.BACKLOG)["items"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / regression.MVP
            path.parent.mkdir()
            for replacement, diagnostic in (
                (f"{line}\n{line}", "duplicate behavior"),
                ("", "mandatory behavior set changed"),
                (line.replace(duplicate_link, f"{duplicate_link}, {duplicate_link}"), "duplicate verification"),
            ):
                path.write_text(original.replace(line, replacement), encoding="utf-8")
                with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(ValueError, diagnostic):
                    regression.mvp_requirements(root, native)

    def test_production_smoke_report_stays_blocked(self):
        smoke = next(row for row in self.matrix["rows"] if row["id"] == "production-smoke")
        smoke["class"] = "hosted_ci"
        with self.assertRaisesRegex(ValueError, "wrong evidence class"):
            regression.audit(regression.ROOT, self.matrix)
        smoke.update({"class": "real_godaddy", "status": "pending"})
        with self.assertRaisesRegex(ValueError, "owned environment prerequisites unavailable"):
            regression.audit(regression.ROOT, self.matrix)

        result = subprocess.run(
            [sys.executable, "scripts/verification/t12_regression_matrix.py", "--report"],
            cwd=regression.ROOT, capture_output=True, text=True, check=True,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["productionSmoke"], {
            "issue": 417, "state": "open", "status": "blocked", "limitation": regression.SMOKE,
        })
        self.assertEqual({gate["status"] for gate in report["gates"].values()}, {"pending"})


if __name__ == "__main__":
    unittest.main()
