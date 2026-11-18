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
to its direct verification issues and the integrated #455 evidence row. Startup
and authenticated guild context also require the supported real Discord
startup rows. Each mandatory [planning requirement](../../planning/traceability.json)
resolves its native verification owner, expected tests and handoff through the
[backlog](../../planning/guildboard-backlog.json). Stable approval includes the
Tier gates and their prerequisite closures. The [T0 criteria and measured
objectives](../requirements/GB-T0-01-01-requirements.md) supply the requirement
outcomes and operational denominators for the linked tests.

| Gate | Automated execution entry points | Manual and owned observations |
| --- | --- | --- |
| G1 MVP approval #456 | Direct verification and integrated #455 on the release candidate, covering each MVP case and the T9 security inputs. | Supported real Discord startup and authenticated guild context, exact-candidate independent security review and dispositions. |
| G2 GoDaddy approval #457 | Owned networking and proxy validation #353, isolated recovery #378, platform/load #414 and deployed-build smoke #417. | Current actual GoDaddy HTTPS/WSS, monitor signals, rollback, isolated database and asset recovery with measured RPO/RTO, and supported actual Discord proxy, reconnect and deployed-build smoke journeys. |
| G3 stable approval #472 | Inherited G1/G2 evidence, all applicable Tier verification, #393 harness, #396 controlled Activity/browser, #400 release fence, #403 isolation, #407 convergence, #410 recovery, integrated full functionality and exact-build hosted regression #417. | Supported Discord SDK and manual accessibility observations, owned GoDaddy network/load/recovery and production smoke, T9 independent security evidence, T13 handoff and reviewed artifacts. Resolve the accepted historical #471 MVP designation and verify the published tag, artifact bytes, receipt and G1 approval. |

The native issues identify the product execution and acceptance handoff. The
offline commands above exercise the matrix, planning and synthetic contract
checks. The environment registry carries the actual Discord client classes,
manual assistive technology combinations and GoDaddy measurement requirements.
Activation of any client row requires the candidate-scoped support decision,
including decisions about Firefox and preview coverage. The controlled browser
row uses the T12 local integration path. T12 permits hosted CI for that path
when its evidence records the same actual Activity/browser and controlled SDK
boundary.

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
