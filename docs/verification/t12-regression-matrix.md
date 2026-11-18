# T12 regression and acceptance matrix

[GB-T12.04.02.T1 #416](https://github.com/CompleteTech-DiscordApps/guildboard/issues/416)
tracks the coverage plan. [GB-T12.04.02.V1 #417](https://github.com/CompleteTech-DiscordApps/guildboard/issues/417)
remains open for independent integrated regression and production smoke.
**Production smoke requires an approved deployed candidate at the GoDaddy target.**

The [matrix](t12-regression-matrix.json) describes expected observations.
Run these offline commands from the repository root.

```sh
python3 scripts/verification/t12_regression_matrix.py
python3 scripts/verification/t12_regression_matrix.py --report
python3 -m unittest discover -s tests/verification -p 'test_t12*.py' -v
python3 scripts/github-bootstrap/validate.py
```

The report links each of the twelve [MVP behaviors](../../planning/MVP-ACCEPTANCE.md)
to its direct verification issues and scoped observations. Each behavior has
a hosted integrated observation under #455. Startup and authenticated guild
context also have owned observations for each supported Discord client. The
stable functionality view links modes, moderation, import/export and recovery
to hosted integration and regression. Accessibility includes hosted regression
and manual keyboard and assistive technology observations on supported clients.
Every observation links the native verification issue, required cases, contract
and, where applicable, the exact environment registry entry.

Each [planning requirement](../../planning/traceability.json) carries its
workstream and feature, verification issue IDs and documentation handoff.
The [backlog](../../planning/guildboard-backlog.json) supplies the linked native
issues, expected tests and documentation artifacts. An issue-level observation
link identifies the group of rows owned by that verification issue. Scoped
links identify exact row/environment/native-issue/contract identities and only
the case subsets relevant to the complete clause. `requirementSource` on each
scoped link resolves to that clause's current traceability JSON entry; observation
`source` and `environmentSource` retain their separate contract and environment
provenance. A missing or renamed mapped clause, mismatched verification owner,
wrong row/source, or absent canonical case fails the offline audit.

The report currently has **seven explicitly mapped clauses and 298 unmapped
clauses**. `scopeMappingStatus` describes this coverage plan; it never supplies
execution credit. All `scopeEvidenceStatus` values remain `pending`, and all
observation rows remain `pending` or `blocked`. An issue-level link or documentation
handoff alone leaves `scopeObservationLinks` empty. Broad or partially represented
requirements remain unmapped rather than borrowing every case of a related row.
For example, harness setup cases do not enumerate all shared-contract/auth/policy/
storage/bot API coverage, and recovery inventories alone do not enumerate every
crash/ACK/tenant/asset outcome. Those requirements need further reviewed coverage
and qualifying receipts.

| Traceability clause | Specific planned observations | Accepted source and limit |
| --- | --- | --- |
| T9 dependency/secret/static checks with triage | #318 hosted `dependency-license-lockfile` and `secret-static-triage` cases. | T9 security inputs; no completed scan or triage is claimed. |
| T9 lockfile provenance/license obligations | #318 hosted `dependency-license-lockfile` only. | T9 provenance/license input; unrelated secret/static cases are excluded. |
| T10 external HTTPS/WSS/reconnect/large-message/idle/renewal tests | #353 GoDaddy network: `https`, `wss`, `reconnect-restart`, `large-message`, both idle thresholds and `tls-renewal`. | T12 operational crosswalk and environment registry; real VPS execution is blocked. |
| T10 firewall/database isolation and Discord launch | #353 GoDaddy `firewall-isolation`/`sql-asset-isolation`; separate `activity-startup` on each registered Discord row. | T12 production networking crosswalk; platform evidence remains blocked. |
| T12 controlled UI launch/ready/auth/navigation and separate real supported clients | #396 browser: `controlled-launch`, `ready`, `auth`, `navigation`; each actual SDK row: `actual-launch`, `sdk-compatibility`. | T12 browser/SDK crosswalk; cancellation, drafts and other browser cases remain in the broader issue-level link. |
| T12 keyboard/screen-reader, load/resource and GoDaddy HTTPS/WSS/idle checks | #414 each client: `keyboard`, `screen-reader`; VPS load: `bounded-load`, `resource-budget`; VPS network: `https`, `wss`, both idle thresholds. | T12 client/AT and platform crosswalk; client support decisions and actual platform receipts remain unavailable. |
| T12 production smoke after deployment | #417 GoDaddy: `verified-build`, `smoke`, `https-wss`; each Discord row: `verified-build`, `deployed-client-journey`. | T12 regression/smoke crosswalk; an approved deployed candidate is required. |

Client expansion retains all seven registered client environments as planned rows.
It does not activate Firefox or preview support or establish compatibility. The
candidate-scoped support decision and independent receipts still control active
coverage. The focused tests pin exact clause identities, relevant case subsets and
client expansion, so silently widening a scope link to an entire observation row
fails regression checks even when all those cases are valid for the owning issue.
They also reject stale/missing clauses, duplicate targets, case loss/invention and
native issue, gate, handoff or source substitution. The [T0 criteria and measured
objectives](../requirements/GB-T0-01-01-requirements.md) supply the requirement
outcomes and operational denominators for the linked tests.

| Gate | Automated execution entry points | Manual and owned observations |
| --- | --- | --- |
| G1 MVP approval #456 | Direct verification and integrated #455 on the release candidate, covering each MVP case and the T9 security inputs. | Supported real Discord startup and authenticated guild context, exact-candidate independent security review and dispositions. |
| G2 GoDaddy approval #457 | Owned networking and proxy validation #353, isolated recovery #378, platform/load #414 and deployed-build smoke #417. | Current actual GoDaddy HTTPS/WSS, monitor signals, rollback, isolated database and asset recovery with measured RPO/RTO, and supported actual Discord proxy, reconnect and deployed-build smoke journeys. |
| G3 stable approval #472 | Inherited G1/G2 evidence, all applicable Tier verification, #393 harness, #396 controlled Activity/browser, #400 release fence, #403 isolation, #407 convergence, #410 recovery, integrated full functionality and exact-build hosted regression #417. | Supported Discord SDK and manual accessibility observations, owned GoDaddy network/load/recovery and production smoke, T9 independent security evidence, T13 handoff and reviewed artifacts. Resolve the accepted historical #471 MVP designation and verify the published tag, artifact bytes, receipt and G1 approval. |

The report links every direct prerequisite for G1, G2 and G3 individually.
The [T12 integration handoff #418](https://github.com/CompleteTech-DiscordApps/guildboard/issues/418)
and [workstream gate #470](https://github.com/CompleteTech-DiscordApps/guildboard/issues/470)
consume the native verification issues, including #417 and #455. The
[stable approval #472](https://github.com/CompleteTech-DiscordApps/guildboard/issues/472)
consumes #470, G1, G2 and the remaining native prerequisites, including the
[historical MVP publication #471](https://github.com/CompleteTech-DiscordApps/guildboard/issues/471).

The offline commands exercise the matrix, planning and synthetic contract
checks. The linked native issues specify runtime execution and acceptance.
The [environment registry](../research/t12-validation-matrix.json) records
Discord client classes, manual assistive technology combinations and GoDaddy
measurement requirements. Activation of any client row requires a
candidate-scoped support decision, including decisions about Firefox and
preview coverage. In the [controlled browser observation #396](https://github.com/CompleteTech-DiscordApps/guildboard/issues/396),
exercise launch, ready, authentication, cancellation, navigation, policy
feedback, reconnect, draft handling and accessible controls on the built
Activity. This plan selects local integration. T12 also permits hosted CI for
the same actual Activity/browser and controlled SDK boundary.

For #417, the hosted regression covers the verified build's MVP behaviors and
stable functionality. After an approved deployment, the GoDaddy smoke row
checks the deployed build and HTTPS/WSS. The separate real Discord rows observe
startup, authenticated guild context, the mapped proxy path and reconnect on
the supported clients. Each deployed row remains blocked.

For each candidate, QE records the exact native verification issue, candidate
SHA, case outcomes, environment/build IDs, method, verifier, scope, artifact
digest and redacted trace receipt. Preserve failed and interrupted attempts,
cleanup, limitations and findings. Rerun affected observations when the
candidate, environment, policy, fixtures or prerequisites change. Qualify
receipts and resolve native approvals through the accepted [T12 verification
contract](../specifications/GB-T12-S1-verification-evidence-contract.md),
[T9 security contract](../specifications/GB-T9-S1-security-privacy-contract.md)
and [T13 release contract](../specifications/GB-T13-S1-documentation-release-contract.md).
The coverage plan accepts pending and blocked rows. G1, G2 and G3 are pending.


## Synthetic handoff coverage correction (2026-11-18)

Related [#588](https://github.com/CompleteTech-DiscordApps/guildboard/issues/588)
repairs the offline handoff model's weaker case floor against the already
committed matrix. G2 and G3 retain backup recovery objectives, all three
capacity/restart/reconnect objectives, HTTPS/WSS deployed smoke and all supported
client journey observations. G3 also retains every controlled browser journey
case and exact-build regression coverage for the twelve MVP behaviors, stable
functionality and accessibility. No accepted matrix case or existing test is
removed.

The new literal oracle enumerates required cases independently of
`gate_coverage()`, `row_floors()` and the implementation's shared MVP constant.
Cross-file equality checks bind that oracle to the committed matrix and both
floor helpers. Synthetic positive controls cover G1, G2 with all seven registered
clients, and G3 with all seven clients under both permitted controlled-browser
environments. Each of 618 mandatory case iterations removes that case, observes
its failure while other cases are outstanding, substitutes an unrelated passing
case, and observes an unrelated failure. Both matrix qualification and the full
T13 handoff are checked. Every altered fixture retains otherwise eligible
candidate, scope, artifact digest, result observer, cleanup observer, registry
and authority bindings; the findings inventory is rebuilt for its exact receipt
bytes. Synthetic support grants for Firefox and previews authorize only these
model fixtures. They establish no actual supported-client decision.

Validation uses Python 3.12.14 on Linux from base
`270f1dc822d12a8b57888573e3de427cd0314357`; the PR validation receipt records the
full resulting head. Run the combined checks from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/verification python3 -B -m unittest test_t12_verification_evidence_contract test_t12_regression_matrix test_t9_security_privacy_contract test_t13_release_contract -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/verification python3 -B -O -m unittest test_t12_verification_evidence_contract test_t12_regression_matrix test_t9_security_privacy_contract test_t13_release_contract -v
python3 -B scripts/verification/t12_regression_matrix.py --report
python3 -B scripts/github-bootstrap/validate.py
git diff --check
```

The literal consistency regression also detects the original base helper when
that helper is injected in memory: one expected assertion failure and no errors.
That negative control does not change repository files. All observations here
are model/fixture checks. There is no actual browser/SDK, SQL, Discord, manual
assistive technology, GoDaddy, deployed smoke, performance, restore or release
approval evidence. #416 and #417 remain open; G1/G2/G3 remain pending and
production smoke remains blocked. Fresh independent functional and defensive
review at the full head, required hosted CI, protected merge and applicable
post-merge verification remain required before the bounded issue may close.

## Synthetic availability-row follow-up (2026-11-18)

Independent review found one further existing row omission, tracked by
[#594](https://github.com/CompleteTech-DiscordApps/guildboard/issues/594).
The G3 handoff now requires the committed `availability/vps-network` row for
[#364](https://github.com/CompleteTech-DiscordApps/guildboard/issues/364), with
`complete-utc-month`, `counts-incidents-gaps` and
`representative-end-to-end-read-and-write`. G1 and G2 requirements are unchanged.

The independent literal expectations include the same three cases. The existing
complete-control, omission, substitution and required/unrelated failure checks
exercise each availability case through matrix qualification and the full T13
handoff under both controlled-browser environments. A separate whole-row test
accounts for every committed matrix row for each gate, client subset and browser
boundary. It names the six separately qualified T9 security rows explicitly;
the only other separately qualified row is G3's historical MVP publication,
whose bytes, receipt and G1 approval T13 verifies. Neither path is a waiver.

Before the helper correction, the new whole-row test failed in all four G3
client/browser combinations, identifying exactly the missing availability row.
The command exited 1 with four subtest assertion failures and no errors. This
negative control is retained separately from successful validation. Replay the
combined normal/optimized suites and report commands above; the PR records the
exact resulting head, results and independent reviews. The base for this
follow-up is `8861c8eb796299b52d1cfb16741d84e10a2df5f4`.

All receipts here remain synthetic. Requiring a case name does not observe or
measure a month: actual qualified monitoring, complete UTC-month records,
incident/gap accounting, representative end-to-end reads/writes and independent
environment-specific results are still missing. #364, #416 and #417 remain open,
all release gates remain pending, and no deployment or production approval is
established. Historical validation receipts above are preserved.
