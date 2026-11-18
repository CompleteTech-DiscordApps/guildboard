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

    def test_scope_bindings_select_exact_cases_and_preserve_unmapped_clauses(self):
        report = regression.audit(regression.ROOT, self.matrix)
        clauses = {(row["feature"], row["text"]): row for row in report["requirements"]}
        expected = {
            ("GB-T9.04.01", "Run dependency, secret and static analysis checks with triaged findings"): {
                "dependency-license-lockfile": {"dependency-license-lockfile"},
                "secret-static-triage": {"secret-static-triage"},
            },
            ("GB-T9.04.01", "verify lockfile provenance and license obligations"): {
                "dependency-license-lockfile": {"dependency-license-lockfile"},
            },
            ("GB-T10.04.02", "Run external HTTPS/WSS, reconnect, large-message, idle-timeout and renewal tests against real VPS"): {
                "production-network": {"https", "wss", "reconnect-restart", "large-message",
                                       "idle-below-threshold", "idle-above-threshold", "tls-renewal"},
            },
            ("GB-T10.04.02", "prove firewall/database isolation and Discord launch"): {
                "production-network": {"firewall-isolation", "sql-asset-isolation"},
                "production-discord": {"activity-startup"},
            },
            ("GB-T12.01.02", "Exercise actual UI launch/ready/auth/navigation with controlled SDK mocks "
             "and separately real supported Discord clients"): {
                "browser-e2e": {"controlled-launch", "ready", "auth", "navigation"},
                "sdk-launch": {"actual-launch", "sdk-compatibility"},
            },
            ("GB-T12.04.01", "Run keyboard/screen-reader scenarios, load/resource budgets and real GoDaddy HTTPS/WSS/idle timeout checks"): {
                **{f"accessibility-{suffix}": {"keyboard", "screen-reader"} for suffix in
                   ("win", "mac", "chromium", "firefox", "ios", "android", "previews")},
                "bounded-load": {"bounded-load", "resource-budget"},
                "platform-network": {"https", "wss", "idle-below-threshold", "idle-above-threshold"},
            },
            ("GB-T12.04.02", "run production smoke after deployment"): {
                "deployed-build-smoke": {"verified-build", "smoke", "https-wss"},
                "deployed-client-smoke": {"verified-build", "deployed-client-journey"},
            },
        }
        self.assertEqual({key for key, row in clauses.items() if row["scopeMappingStatus"] == "mapped"},
                         set(expected))
        source_trace = regression.load(regression.ROOT, regression.TRACE)
        for identity, case_sets in expected.items():
            requirement = clauses[identity]
            links = requirement["scopeObservationLinks"]
            self.assertEqual({link["row"][0] for link in links}, set(case_sets))
            self.assertEqual(len(links), len({tuple(link["row"]) for link in links}))
            for link in links:
                with self.subTest(identity=identity, row=link["row"]):
                    self.assertEqual(set(link["cases"]), case_sets[link["row"][0]])
                    self.assertEqual(len(link["cases"]), len(case_sets[link["row"][0]]))
                    self.assertEqual(link["requirementSource"], requirement["source"])
                    index = int(link["requirementSource"].rsplit("/", 1)[1])
                    self.assertEqual((source_trace[index]["feature"], source_trace[index]["requirement"]), identity)
                    self.assertEqual(link["source"], regression.T9 if identity[0].startswith("GB-T9") else regression.T12)
                    self.assertIn(link["status"], {"pending", "blocked"})
            client_links = [link for link in links if link["row"][1].startswith("discord-")]
            if client_links:
                self.assertEqual({link["row"][1] for link in client_links}, contract.DISCORD_ROWS)
        self.assertEqual(sum(row["scopeMappingStatus"] == "unmapped" for row in clauses.values()), 298)
        for identity, requirement in clauses.items():
            if identity not in expected:
                self.assertEqual(requirement["scopeObservationLinks"], [])
                self.assertEqual(requirement["scopeEvidenceStatus"], "pending")
        # A recovery inventory or broad permissions row alone cannot represent
        # every crash/ACK/asset or session/UI clause. Keep those handoffs open.
        for feature in ("GB-T12.01.01", "GB-T12.02.01", "GB-T12.02.02", "GB-T12.03.01", "GB-T12.03.02"):
            self.assertTrue(all(row["scopeMappingStatus"] == "unmapped" for row in clauses.values()
                                if row["feature"] == feature))

    def test_mapped_clauses_reject_stale_text_feature_and_missing_source(self):
        original_load = regression.load
        original_trace = original_load(regression.ROOT, regression.TRACE)
        for identity in regression.TRACE_SCOPES:
            index = next(i for i, row in enumerate(original_trace)
                         if (row["feature"], row["requirement"]) == identity)
            for field in ("requirement", "feature"):
                trace = copy.deepcopy(original_trace)
                trace[index][field] += "-stale"
                with self.subTest(identity=identity, field=field), patch.object(regression, "load", side_effect=(
                    lambda root, name: trace if name == regression.TRACE else original_load(root, name)
                )):
                    with self.assertRaisesRegex(ValueError, "trace scope clause missing or stale"):
                        regression.audit(regression.ROOT, self.matrix)
            report = regression.audit(regression.ROOT, self.matrix)
            remaining = [row for row in report["requirements"] if (row["feature"], row["text"]) != identity]
            with self.subTest(identity=identity, field="missing"), self.assertRaisesRegex(
                    ValueError, "trace scope clause missing or stale"):
                regression.scope_observations(remaining, report["rows"], contract.DISCORD_ROWS)

    def test_scope_resolution_rejects_wrong_row_issue_source_cases_and_duplicates(self):
        report = regression.audit(regression.ROOT, self.matrix)
        for identity, targets in regression.TRACE_SCOPES.items():
            for index, target in enumerate(targets):
                name, environment, issue, source, cases = target
                for replacement, diagnostic in (
                    (("wrong-row", environment, issue, source, cases), "missing scope observation"),
                    ((name, "wrong-environment", issue, source, cases), "missing scope observation"),
                    ((name, environment, issue + 1, source, cases), "wrong scope native issue"),
                    ((name, environment, issue, "wrong-source", cases), "wrong scope observation source"),
                    ((name, environment, issue, source, ("invented-case",)), "missing canonical scope cases"),
                    ((name, environment, issue, source, ()), "empty or duplicate scope cases"),
                    ((name, environment, issue, source, (*cases, cases[0])), "empty or duplicate scope cases"),
                ):
                    changed = dict(regression.TRACE_SCOPES)
                    changed[identity] = (*targets[:index], replacement, *targets[index + 1:])
                    with self.subTest(identity=identity, row=name, diagnostic=diagnostic), patch.object(
                            regression, "TRACE_SCOPES", changed):
                        with self.assertRaisesRegex(ValueError, diagnostic):
                            regression.scope_observations(report["requirements"], report["rows"], contract.DISCORD_ROWS)
            changed = {**regression.TRACE_SCOPES, identity: (*targets, targets[0])}
            with self.subTest(identity=identity, duplicate=True), patch.object(regression, "TRACE_SCOPES", changed):
                with self.assertRaisesRegex(ValueError, "duplicate scope observation"):
                    regression.scope_observations(report["requirements"], report["rows"], contract.DISCORD_ROWS)

    def test_scope_resolution_rejects_identity_and_native_handoff_substitution(self):
        for identity in regression.TRACE_SCOPES:
            for change, diagnostic in (
                ({"gate": regression.G1}, "wrong trace scope identity"),
                ({"handoff": "GB-T0.D1"}, "wrong trace scope identity"),
                ({"workstream": "T0"}, "wrong trace scope identity"),
                ({"verification": ["GB-T0.01.01.V1"]}, "wrong scope native issue"),
            ):
                report = regression.audit(regression.ROOT, self.matrix)
                requirement = next(row for row in report["requirements"]
                                   if (row["feature"], row["text"]) == identity)
                requirement.update(change)
                with self.subTest(identity=identity, change=change), self.assertRaisesRegex(ValueError, diagnostic):
                    regression.scope_observations(report["requirements"], report["rows"], contract.DISCORD_ROWS)

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

    def test_literal_case_oracle_matches_matrix_floors_and_handoff_for_each_boundary(self):
        report = regression.audit(regression.ROOT, self.matrix)
        rows = {(row["id"], row["environment"]): row for row in report["rows"]}
        floors = regression.row_floors(regression.ROOT, contract.DISCORD_ROWS)
        for clients in (["discord-win"], sorted(contract.DISCORD_ROWS)):
            for gate in (regression.G1, regression.G2, regression.G3):
                for browser in ("local", "hosted"):
                    # This oracle is literal test data, independent of both
                    # gate_coverage and row_floors. Equality catches case loss
                    # in either helper even when the other is weakened too.
                    expected = contract.literal_gate_expectations(gate, clients, browser)
                    self.assertEqual(contract.gate_coverage(gate, clients, expected), expected)
                    for key, (issue, cases) in expected.items():
                        canonical = ("browser-e2e", "local") if key[0] == "browser-e2e" else key
                        with self.subTest(gate=gate, clients=clients, browser=browser, row=key):
                            row = rows[canonical]
                            self.assertEqual(row["issue"], issue)
                            self.assertEqual(set(row["casesByGate"][gate]), cases)
                            accepted_issue, gates, _, floor_cases = floors[canonical]
                            self.assertEqual(accepted_issue, issue)
                            self.assertIn(gate, gates)
                            # The integrated stable cases are the documented
                            # G3 overlay; all other floor sets match exactly.
                            if key != ("integrated", "hosted") or gate != regression.G3:
                                self.assertEqual(floor_cases, cases)

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
