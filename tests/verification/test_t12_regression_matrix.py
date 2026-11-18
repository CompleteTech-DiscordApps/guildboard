"""Offline checks for the #416 traceability plan."""
import copy
import json
import subprocess
import sys
import unittest

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
            for issue in row["verification"]:
                self.assertTrue(report["verificationIssues"][issue]["expectedTests"])

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
            (lambda m: m["stable"]["directPrerequisites"].remove("GB-T6.G1"), "mandatory stable"),
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
