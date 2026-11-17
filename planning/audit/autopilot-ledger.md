# Autopilot ledger

Generated 2026-11-17T15:28:37+00:00 from live GitHub state by the delegated-maintainer autopilot (Claude). Regenerate; do not hand-edit tables.

Open issues: 439 / 471. Blocked-external: 0.

## Session notes and resume instructions

- Delegated maintainer: Claude (autopilot), per owner instruction 2026-11-17 and `guildboard-finish-prompt.md`.
- `gh auth refresh -s project,read:project` requires interactive device login; **Project field updates are skipped** (owner action: grant `project` scope). Native issue state, comments and labels are the record.
- Ledger lives on branch `autopilot/ledger`; regenerate with the generator in that branch (`planning/audit/autopilot_ledger.py`).
- Phase status: Phase 0 complete (2026-11-17). Phase 1 (PR queue) in progress.

## Decision log (decisions of record are posted on the issue/PR; this is the index)



## Open PRs

| PR | Draft | Mergeable | Checks | Diff | Branch | Title |
|---|---|---|---|---|---|---|
| #521 | False | MERGEABLE | {'SUCCESS': 12} | +764/-0 | `docs/t0-integration-handoff-32` | docs(t0): integration and handoff section with enforcing tests (#32) |
| #499 | False | MERGEABLE | {'SUCCESS': 1} | +13/-0 | `chore/paseo-worktree-lifecycle-20261107` | chore(paseo): configure worktree lifecycle |
| #498 | True | MERGEABLE | {'SUCCESS': 1} | +3239/-0 | `orchestrator/t12-qe-research` | research(T12): evaluate deterministic testing and platform acceptance budgets |
| #497 | True | MERGEABLE | {'SUCCESS': 1} | +12823/-0 | `orchestrator/t10-godaddy-research` | research(T10): evaluate GoDaddy Linux VPS sizing and proxy compatibility |
| #496 | True | MERGEABLE | {'SUCCESS': 1} | +650/-1 | `orchestrator/t11-sre-research` | docs(research): propose T11 SRE objectives and measured baseline |
| #495 | True | MERGEABLE | {'SUCCESS': 1} | +1/-1 | `orchestrator/canonical-repository-config` | fix(planning): use the transferred canonical repository identity |
| #494 | True | MERGEABLE | {'SUCCESS': 1} | +1096/-0 | `orchestrator/t8-bot-research` | research(T8): evaluate least-privilege bot administration and interaction trust |
| #493 | True | MERGEABLE | {'SUCCESS': 1} | +1941/-0 | `orchestrator/t7-accessibility-research` | docs(research): evaluate T7 viewport and accessible canvas alternatives |
| #492 | True | MERGEABLE | {'SUCCESS': 1} | +735/-0 | `orchestrator/t2-policy-research` | docs(research): compare T2 policy precedence and revocation freshness |
| #490 | True | MERGEABLE | {'SUCCESS': 1} | +1404/-0 | `orchestrator/t5-durability-research` | docs(research): evaluate T5 transaction, retention and recovery strategy |
| #489 | True | MERGEABLE | {'SUCCESS': 1} | +682/-0 | `orchestrator/t9-threat-model` | docs(research): threat-model T9 boundaries and prioritize abuse acceptance |
| #488 | False | CONFLICTING | {'SUCCESS': 7} | +272/-8 | `orchestrator/review-instructions` | docs: define delegated governance and contribution ownership |
| #486 | True | MERGEABLE | {'SUCCESS': 1} | +747/-0 | `research/t13-documentation-journeys` | docs(research): audit contributor and user documentation journeys |
| #485 | True | MERGEABLE | {'SUCCESS': 1} | +600/-0 | `research/t6-mode-semantics` | docs(research): preserve presentation-mode semantics model |
| #484 | True | MERGEABLE | {'SUCCESS': 1} | +503/-0 | `research/collaboration-semantics` | docs(research): preserve collaboration semantics model |
| #482 | True | CONFLICTING | {'FAILURE': 2, 'SUCCESS': 10} | +77175/-0 | `research/license-adoption-evidence` | License inventory, bounded archive verification and fail-closed evidence gate |

## Open issues by wave (wave = longest chain of open native blockers)

| Wave | # | GB ID | Type | Release | Open blockers | Labels |
|---|---|---|---|---|---|---|
| 0 | #1 | GB-T0 | workstream | mvp |  |  |
| 0 | #32 | GB-T0.D1 | documentation | mvp |  |  |
| 0 | #33 | GB-T1 | workstream | mvp |  |  |
| 0 | #36 | GB-T1.01 | capability | mvp |  |  |
| 0 | #37 | GB-T1.01.01 | feature | mvp |  |  |
| 0 | #40 | GB-T1.01.02 | feature | mvp |  |  |
| 0 | #43 | GB-T1.02 | capability | mvp |  |  |
| 0 | #44 | GB-T1.02.01 | feature | mvp |  |  |
| 0 | #47 | GB-T1.02.02 | feature | mvp |  |  |
| 0 | #50 | GB-T1.03 | capability | mvp |  |  |
| 0 | #51 | GB-T1.03.01 | feature | mvp |  |  |
| 0 | #54 | GB-T1.03.02 | feature | mvp |  |  |
| 0 | #57 | GB-T1.04 | capability | mvp |  |  |
| 0 | #58 | GB-T1.04.01 | feature | mvp |  |  |
| 0 | #61 | GB-T1.04.02 | feature | mvp |  |  |
| 0 | #34 | GB-T1.R1 | research | mvp |  |  |
| 0 | #68 | GB-T2.01 | capability | mvp |  |  |
| 0 | #69 | GB-T2.01.01 | feature | mvp |  |  |
| 0 | #72 | GB-T2.01.02 | feature | mvp |  |  |
| 0 | #83 | GB-T2.03.01 | feature | mvp |  |  |
| 0 | #66 | GB-T2.R1 | research | mvp |  |  |
| 0 | #97 | GB-T3 | workstream | mvp |  |  |
| 0 | #100 | GB-T3.01 | capability | mvp |  |  |
| 0 | #101 | GB-T3.01.01 | feature | mvp |  |  |
| 0 | #104 | GB-T3.01.02 | feature | mvp |  |  |
| 0 | #107 | GB-T3.02 | capability | mvp |  |  |
| 0 | #108 | GB-T3.02.01 | feature | mvp |  |  |
| 0 | #111 | GB-T3.02.02 | feature | mvp |  |  |
| 0 | #114 | GB-T3.03 | capability | mvp |  |  |
| 0 | #115 | GB-T3.03.01 | feature | mvp |  |  |
| 0 | #118 | GB-T3.03.02 | feature | mvp |  |  |
| 0 | #123 | GB-T3.04 | capability | mvp |  |  |
| 0 | #124 | GB-T3.04.01 | feature | mvp |  |  |
| 0 | #127 | GB-T3.04.02 | feature | mvp |  |  |
| 0 | #98 | GB-T3.R1 | research | mvp |  |  |
| 0 | #131 | GB-T4 | workstream | mvp |  |  |
| 0 | #134 | GB-T4.01 | capability | mvp |  |  |
| 0 | #135 | GB-T4.01.01 | feature | mvp |  |  |
| 0 | #138 | GB-T4.01.02 | feature | mvp |  |  |
| 0 | #141 | GB-T4.02 | capability | mvp |  |  |
| 0 | #142 | GB-T4.02.01 | feature | mvp |  |  |
| 0 | #152 | GB-T4.02.02 | feature | mvp |  |  |
| 0 | #155 | GB-T4.03 | capability | mvp |  |  |
| 0 | #156 | GB-T4.03.01 | feature | mvp |  |  |
| 0 | #159 | GB-T4.03.02 | feature | mvp |  |  |
| 0 | #162 | GB-T4.04 | capability | mvp |  |  |
| 0 | #163 | GB-T4.04.01 | feature | mvp |  |  |
| 0 | #166 | GB-T4.04.02 | feature | mvp |  |  |
| 0 | #132 | GB-T4.R1 | research | mvp |  |  |
| 0 | #171 | GB-T5.01.01 | feature | mvp |  |  |
| 0 | #144 | GB-T5.02 | capability | mvp |  |  |
| 0 | #145 | GB-T5.02.01 | feature | mvp |  |  |
| 0 | #177 | GB-T5.02.02 | feature | mvp |  |  |
| 0 | #181 | GB-T5.03.01 | feature | mvp |  |  |
| 0 | #146 | GB-T5.R1 | research | mvp |  |  |
| 0 | #262 | GB-T8.01 | capability | mvp |  |  |
| 0 | #263 | GB-T8.01.01 | feature | mvp |  |  |
| 0 | #266 | GB-T8.01.02 | feature | mvp |  |  |
| 0 | #260 | GB-T8.R1 | research | mvp |  |  |
| 0 | #323 | GB-T10 | workstream | v1.0 |  |  |
| 0 | #326 | GB-T10.01 | capability | v1.0 |  |  |
| 0 | #327 | GB-T10.01.01 | feature | v1.0 |  |  |
| 0 | #330 | GB-T10.01.02 | feature | v1.0 |  |  |
| 0 | #333 | GB-T10.02 | capability | v1.0 |  |  |
| 0 | #334 | GB-T10.02.01 | feature | v1.0 |  |  |
| 0 | #337 | GB-T10.02.02 | feature | v1.0 |  |  |
| 0 | #340 | GB-T10.03 | capability | v1.0 |  |  |
| 0 | #341 | GB-T10.03.01 | feature | v1.0 |  |  |
| 0 | #344 | GB-T10.03.02 | feature | v1.0 |  |  |
| 0 | #347 | GB-T10.04 | capability | v1.0 |  |  |
| 0 | #348 | GB-T10.04.01 | feature | v1.0 |  |  |
| 0 | #351 | GB-T10.04.02 | feature | v1.0 |  |  |
| 0 | #324 | GB-T10.R1 | research | v1.0 |  |  |
| 0 | #355 | GB-T11 | workstream | v1.0 |  |  |
| 0 | #358 | GB-T11.01 | capability | v1.0 |  |  |
| 0 | #359 | GB-T11.01.01 | feature | v1.0 |  |  |
| 0 | #362 | GB-T11.01.02 | feature | v1.0 |  |  |
| 0 | #365 | GB-T11.02 | capability | v1.0 |  |  |
| 0 | #366 | GB-T11.02.01 | feature | v1.0 |  |  |
| 0 | #369 | GB-T11.02.02 | feature | v1.0 |  |  |
| 0 | #372 | GB-T11.03 | capability | v1.0 |  |  |
| 0 | #373 | GB-T11.03.01 | feature | v1.0 |  |  |
| 0 | #376 | GB-T11.03.02 | feature | v1.0 |  |  |
| 0 | #379 | GB-T11.04 | capability | v1.0 |  |  |
| 0 | #380 | GB-T11.04.01 | feature | v1.0 |  |  |
| 0 | #383 | GB-T11.04.02 | feature | v1.0 |  |  |
| 0 | #356 | GB-T11.R1 | research | v1.0 |  |  |
| 0 | #387 | GB-T12 | workstream | v1.0 |  |  |
| 0 | #390 | GB-T12.01 | capability | v1.0 |  |  |
| 0 | #391 | GB-T12.01.01 | feature | v1.0 |  |  |
| 0 | #394 | GB-T12.01.02 | feature | v1.0 |  |  |
| 0 | #397 | GB-T12.02 | capability | v1.0 |  |  |
| 0 | #398 | GB-T12.02.01 | feature | v1.0 |  |  |
| 0 | #401 | GB-T12.02.02 | feature | v1.0 |  |  |
| 0 | #404 | GB-T12.03 | capability | v1.0 |  |  |
| 0 | #405 | GB-T12.03.01 | feature | v1.0 |  |  |
| 0 | #408 | GB-T12.03.02 | feature | v1.0 |  |  |
| 0 | #411 | GB-T12.04 | capability | v1.0 |  |  |
| 0 | #412 | GB-T12.04.01 | feature | v1.0 |  |  |
| 0 | #415 | GB-T12.04.02 | feature | v1.0 |  |  |
| 0 | #388 | GB-T12.R1 | research | v1.0 |  |  |
| 0 | #419 | GB-T13 | workstream | v1.0 |  |  |
| 0 | #422 | GB-T13.01 | capability | v1.0 |  |  |
| 0 | #423 | GB-T13.01.01 | feature | v1.0 |  |  |
| 0 | #426 | GB-T13.01.02 | feature | v1.0 |  |  |
| 0 | #429 | GB-T13.02 | capability | v1.0 |  |  |
| 0 | #430 | GB-T13.02.01 | feature | v1.0 |  |  |
| 0 | #433 | GB-T13.02.02 | feature | v1.0 |  |  |
| 0 | #436 | GB-T13.03 | capability | v1.0 |  |  |
| 0 | #437 | GB-T13.03.01 | feature | v1.0 |  |  |
| 0 | #440 | GB-T13.03.02 | feature | v1.0 |  |  |
| 0 | #443 | GB-T13.04 | capability | v1.0 |  |  |
| 0 | #444 | GB-T13.04.01 | feature | v1.0 |  |  |
| 0 | #420 | GB-T13.R1 | research | v1.0 |  |  |
| 0 | #65 | GB-T2 | workstream | v1.0 |  |  |
| 0 | #75 | GB-T2.02 | capability | v1.0 |  |  |
| 0 | #76 | GB-T2.02.01 | feature | v1.0 |  |  |
| 0 | #79 | GB-T2.02.02 | feature | v1.0 |  |  |
| 0 | #82 | GB-T2.03 | capability | v1.0 |  |  |
| 0 | #86 | GB-T2.03.02 | feature | v1.0 |  |  |
| 0 | #89 | GB-T2.04 | capability | v1.0 |  |  |
| 0 | #90 | GB-T2.04.01 | feature | v1.0 |  |  |
| 0 | #93 | GB-T2.04.02 | feature | v1.0 |  |  |
| 0 | #143 | GB-T5 | workstream | v1.0 |  |  |
| 0 | #170 | GB-T5.01 | capability | v1.0 |  |  |
| 0 | #174 | GB-T5.01.02 | feature | v1.0 |  |  |
| 0 | #180 | GB-T5.03 | capability | v1.0 |  |  |
| 0 | #184 | GB-T5.03.02 | feature | v1.0 |  |  |
| 0 | #187 | GB-T5.04 | capability | v1.0 |  |  |
| 0 | #188 | GB-T5.04.01 | feature | v1.0 |  |  |
| 0 | #191 | GB-T5.04.02 | feature | v1.0 |  |  |
| 0 | #195 | GB-T6 | workstream | v1.0 |  |  |
| 0 | #198 | GB-T6.01 | capability | v1.0 |  |  |
| 0 | #199 | GB-T6.01.01 | feature | v1.0 |  |  |
| 0 | #202 | GB-T6.01.02 | feature | v1.0 |  |  |
| 0 | #205 | GB-T6.02 | capability | v1.0 |  |  |
| 0 | #206 | GB-T6.02.01 | feature | v1.0 |  |  |
| 0 | #209 | GB-T6.02.02 | feature | v1.0 |  |  |
| 0 | #212 | GB-T6.03 | capability | v1.0 |  |  |
| 0 | #213 | GB-T6.03.01 | feature | v1.0 |  |  |
| 0 | #216 | GB-T6.03.02 | feature | v1.0 |  |  |
| 0 | #219 | GB-T6.04 | capability | v1.0 |  |  |
| 0 | #220 | GB-T6.04.01 | feature | v1.0 |  |  |
| 0 | #223 | GB-T6.04.02 | feature | v1.0 |  |  |
| 0 | #196 | GB-T6.R1 | research | v1.0 |  |  |
| 0 | #227 | GB-T7 | workstream | v1.0 |  |  |
| 0 | #230 | GB-T7.01 | capability | v1.0 |  |  |
| 0 | #231 | GB-T7.01.01 | feature | v1.0 |  |  |
| 0 | #234 | GB-T7.01.02 | feature | v1.0 |  |  |
| 0 | #237 | GB-T7.02 | capability | v1.0 |  |  |
| 0 | #238 | GB-T7.02.01 | feature | v1.0 |  |  |
| 0 | #241 | GB-T7.02.02 | feature | v1.0 |  |  |
| 0 | #244 | GB-T7.03 | capability | v1.0 |  |  |
| 0 | #245 | GB-T7.03.01 | feature | v1.0 |  |  |
| 0 | #248 | GB-T7.03.02 | feature | v1.0 |  |  |
| 0 | #251 | GB-T7.04 | capability | v1.0 |  |  |
| 0 | #252 | GB-T7.04.01 | feature | v1.0 |  |  |
| 0 | #255 | GB-T7.04.02 | feature | v1.0 |  |  |
| 0 | #228 | GB-T7.R1 | research | v1.0 |  |  |
| 0 | #259 | GB-T8 | workstream | v1.0 |  |  |
| 0 | #269 | GB-T8.02 | capability | v1.0 |  |  |
| 0 | #270 | GB-T8.02.01 | feature | v1.0 |  |  |
| 0 | #273 | GB-T8.02.02 | feature | v1.0 |  |  |
| 0 | #276 | GB-T8.03 | capability | v1.0 |  |  |
| 0 | #277 | GB-T8.03.01 | feature | v1.0 |  |  |
| 0 | #280 | GB-T8.03.02 | feature | v1.0 |  |  |
| 0 | #283 | GB-T8.04 | capability | v1.0 |  |  |
| 0 | #284 | GB-T8.04.01 | feature | v1.0 |  |  |
| 0 | #287 | GB-T8.04.02 | feature | v1.0 |  |  |
| 0 | #291 | GB-T9 | workstream | v1.0 |  |  |
| 0 | #294 | GB-T9.01 | capability | v1.0 |  |  |
| 0 | #295 | GB-T9.01.01 | feature | v1.0 |  |  |
| 0 | #298 | GB-T9.01.02 | feature | v1.0 |  |  |
| 0 | #301 | GB-T9.02 | capability | v1.0 |  |  |
| 0 | #302 | GB-T9.02.01 | feature | v1.0 |  |  |
| 0 | #305 | GB-T9.02.02 | feature | v1.0 |  |  |
| 0 | #308 | GB-T9.03 | capability | v1.0 |  |  |
| 0 | #309 | GB-T9.03.01 | feature | v1.0 |  |  |
| 0 | #312 | GB-T9.03.02 | feature | v1.0 |  |  |
| 0 | #315 | GB-T9.04 | capability | v1.0 |  |  |
| 0 | #316 | GB-T9.04.01 | feature | v1.0 |  |  |
| 0 | #319 | GB-T9.04.02 | feature | v1.0 |  |  |
| 0 | #292 | GB-T9.R1 | research | v1.0 |  |  |
| 0 | #447 | GB-T13.04.02 | feature | post-v1.0 |  |  |
| 1 | #458 | GB-T0.G1 | test | mvp | #32 |  |
| 1 | #35 | GB-T1.S1 | specification | mvp | #34 |  |
| 1 | #67 | GB-T2.S1 | specification | mvp | #66 |  |
| 1 | #99 | GB-T3.S1 | specification | mvp | #98 |  |
| 1 | #147 | GB-T5.S1 | specification | mvp | #146 |  |
| 1 | #261 | GB-T8.S1 | specification | mvp | #260 |  |
| 1 | #325 | GB-T10.S1 | specification | v1.0 | #324 |  |
| 1 | #357 | GB-T11.S1 | specification | v1.0 | #356 |  |
| 1 | #389 | GB-T12.S1 | specification | v1.0 | #388 |  |
| 1 | #421 | GB-T13.S1 | specification | v1.0 | #420 |  |
| 1 | #197 | GB-T6.S1 | specification | v1.0 | #196 |  |
| 1 | #229 | GB-T7.S1 | specification | v1.0 | #228 |  |
| 1 | #293 | GB-T9.S1 | specification | v1.0 | #292 |  |
| 2 | #38 | GB-T1.01.01.T1 | task | mvp | #35 |  |
| 2 | #41 | GB-T1.01.02.T1 | task | mvp | #35 |  |
| 2 | #45 | GB-T1.02.01.T1 | task | mvp | #35 |  |
| 2 | #48 | GB-T1.02.02.T1 | task | mvp | #35 |  |
| 2 | #52 | GB-T1.03.01.T1 | task | mvp | #35 |  |
| 2 | #59 | GB-T1.04.01.T1 | task | mvp | #35 |  |
| 2 | #62 | GB-T1.04.02.T1 | task | mvp | #35 |  |
| 2 | #445 | GB-T13.04.01.T1 | task | mvp | #421 |  |
| 2 | #70 | GB-T2.01.01.T1 | task | mvp | #67 |  |
| 2 | #84 | GB-T2.03.01.T1 | task | mvp | #67 |  |
| 2 | #102 | GB-T3.01.01.T1 | task | mvp | #99 |  |
| 2 | #105 | GB-T3.01.02.T1 | task | mvp | #99 |  |
| 2 | #109 | GB-T3.02.01.T1 | task | mvp | #99 |  |
| 2 | #112 | GB-T3.02.02.T1 | task | mvp | #99 |  |
| 2 | #116 | GB-T3.03.01.T1 | task | mvp | #99 |  |
| 2 | #119 | GB-T3.03.02.T1 | task | mvp | #99 |  |
| 2 | #125 | GB-T3.04.01.T1 | task | mvp | #99 |  |
| 2 | #128 | GB-T3.04.02.T1 | task | mvp | #99 |  |
| 2 | #133 | GB-T4.S1 | specification | mvp | #99 #132 |  |
| 2 | #172 | GB-T5.01.01.T1 | task | mvp | #147 |  |
| 2 | #148 | GB-T5.02.01.T1 | task | mvp | #147 |  |
| 2 | #264 | GB-T8.01.01.T1 | task | mvp | #261 |  |
| 2 | #267 | GB-T8.01.02.T1 | task | mvp | #261 |  |
| 2 | #328 | GB-T10.01.01.T1 | task | v1.0 | #325 |  |
| 2 | #331 | GB-T10.01.02.T1 | task | v1.0 | #325 |  |
| 2 | #335 | GB-T10.02.01.T1 | task | v1.0 | #325 |  |
| 2 | #342 | GB-T10.03.01.T1 | task | v1.0 | #325 |  |
| 2 | #345 | GB-T10.03.02.T1 | task | v1.0 | #325 |  |
| 2 | #349 | GB-T10.04.01.T1 | task | v1.0 | #325 |  |
| 2 | #360 | GB-T11.01.01.T1 | task | v1.0 | #357 |  |
| 2 | #363 | GB-T11.01.02.T1 | task | v1.0 | #357 |  |
| 2 | #367 | GB-T11.02.01.T1 | task | v1.0 | #357 |  |
| 2 | #370 | GB-T11.02.02.T1 | task | v1.0 | #357 |  |
| 2 | #374 | GB-T11.03.01.T1 | task | v1.0 | #357 |  |
| 2 | #381 | GB-T11.04.01.T1 | task | v1.0 | #357 |  |
| 2 | #384 | GB-T11.04.02.T1 | task | v1.0 | #357 |  |
| 2 | #392 | GB-T12.01.01.T1 | task | v1.0 | #389 |  |
| 2 | #395 | GB-T12.01.02.T1 | task | v1.0 | #389 |  |
| 2 | #399 | GB-T12.02.01.T1 | task | v1.0 | #389 |  |
| 2 | #402 | GB-T12.02.02.T1 | task | v1.0 | #389 |  |
| 2 | #413 | GB-T12.04.01.T1 | task | v1.0 | #389 |  |
| 2 | #416 | GB-T12.04.02.T1 | task | v1.0 | #389 |  |
| 2 | #424 | GB-T13.01.01.T1 | documentation | v1.0 | #421 |  |
| 2 | #427 | GB-T13.01.02.T1 | documentation | v1.0 | #421 |  |
| 2 | #431 | GB-T13.02.01.T1 | documentation | v1.0 | #421 |  |
| 2 | #434 | GB-T13.02.02.T1 | documentation | v1.0 | #421 |  |
| 2 | #438 | GB-T13.03.01.T1 | documentation | v1.0 | #421 |  |
| 2 | #441 | GB-T13.03.02.T1 | documentation | v1.0 | #421 |  |
| 2 | #87 | GB-T2.03.02.T1 | task | v1.0 | #67 |  |
| 2 | #91 | GB-T2.04.01.T1 | task | v1.0 | #67 |  |
| 2 | #94 | GB-T2.04.02.T1 | task | v1.0 | #67 |  |
| 2 | #175 | GB-T5.01.02.T1 | task | v1.0 | #147 |  |
| 2 | #189 | GB-T5.04.01.T1 | task | v1.0 | #147 |  |
| 2 | #192 | GB-T5.04.02.T1 | task | v1.0 | #147 |  |
| 2 | #200 | GB-T6.01.01.T1 | task | v1.0 | #197 |  |
| 2 | #207 | GB-T6.02.01.T1 | task | v1.0 | #197 |  |
| 2 | #210 | GB-T6.02.02.T1 | task | v1.0 | #197 |  |
| 2 | #214 | GB-T6.03.01.T1 | task | v1.0 | #197 |  |
| 2 | #217 | GB-T6.03.02.T1 | task | v1.0 | #197 |  |
| 2 | #221 | GB-T6.04.01.T1 | task | v1.0 | #197 |  |
| 2 | #224 | GB-T6.04.02.T1 | task | v1.0 | #197 |  |
| 2 | #232 | GB-T7.01.01.T1 | task | v1.0 | #229 |  |
| 2 | #235 | GB-T7.01.02.T1 | task | v1.0 | #229 |  |
| 2 | #239 | GB-T7.02.01.T1 | task | v1.0 | #229 |  |
| 2 | #242 | GB-T7.02.02.T1 | task | v1.0 | #229 |  |
| 2 | #246 | GB-T7.03.01.T1 | task | v1.0 | #229 |  |
| 2 | #249 | GB-T7.03.02.T1 | task | v1.0 | #229 |  |
| 2 | #253 | GB-T7.04.01.T1 | task | v1.0 | #229 |  |
| 2 | #256 | GB-T7.04.02.T1 | task | v1.0 | #229 |  |
| 2 | #271 | GB-T8.02.01.T1 | task | v1.0 | #261 |  |
| 2 | #274 | GB-T8.02.02.T1 | task | v1.0 | #261 |  |
| 2 | #278 | GB-T8.03.01.T1 | task | v1.0 | #261 |  |
| 2 | #281 | GB-T8.03.02.T1 | task | v1.0 | #261 |  |
| 2 | #285 | GB-T8.04.01.T1 | task | v1.0 | #261 |  |
| 2 | #288 | GB-T8.04.02.T1 | task | v1.0 | #261 |  |
| 2 | #296 | GB-T9.01.01.T1 | task | v1.0 | #293 |  |
| 2 | #299 | GB-T9.01.02.T1 | task | v1.0 | #293 |  |
| 2 | #303 | GB-T9.02.01.T1 | task | v1.0 | #293 |  |
| 2 | #306 | GB-T9.02.02.T1 | task | v1.0 | #293 |  |
| 2 | #310 | GB-T9.03.01.T1 | task | v1.0 | #293 |  |
| 2 | #313 | GB-T9.03.02.T1 | task | v1.0 | #293 |  |
| 2 | #317 | GB-T9.04.01.T1 | task | v1.0 | #293 |  |
| 2 | #448 | GB-T13.04.02.T1 | task | post-v1.0 | #421 |  |
| 3 | #39 | GB-T1.01.01.V1 | test | mvp | #38 |  |
| 3 | #42 | GB-T1.01.02.V1 | test | mvp | #41 |  |
| 3 | #46 | GB-T1.02.01.V1 | test | mvp | #45 |  |
| 3 | #49 | GB-T1.02.02.V1 | test | mvp | #48 |  |
| 3 | #53 | GB-T1.03.01.V1 | test | mvp | #52 |  |
| 3 | #60 | GB-T1.04.01.V1 | test | mvp | #59 |  |
| 3 | #63 | GB-T1.04.02.V1 | test | mvp | #62 |  |
| 3 | #446 | GB-T13.04.01.V1 | test | mvp | #445 |  |
| 3 | #71 | GB-T2.01.01.V1 | test | mvp | #70 |  |
| 3 | #85 | GB-T2.03.01.V1 | test | mvp | #84 |  |
| 3 | #103 | GB-T3.01.01.V1 | test | mvp | #102 |  |
| 3 | #106 | GB-T3.01.02.V1 | test | mvp | #105 |  |
| 3 | #110 | GB-T3.02.01.V1 | test | mvp | #109 |  |
| 3 | #113 | GB-T3.02.02.V1 | test | mvp | #112 |  |
| 3 | #117 | GB-T3.03.01.V1 | test | mvp | #116 |  |
| 3 | #121 | GB-T3.03.02.V1 | test | mvp | #119 |  |
| 3 | #126 | GB-T3.04.01.V1 | test | mvp | #125 |  |
| 3 | #129 | GB-T3.04.02.V1 | test | mvp | #128 |  |
| 3 | #139 | GB-T4.01.02.T1 | task | mvp | #133 |  |
| 3 | #153 | GB-T4.02.02.T1 | task | mvp | #133 |  |
| 3 | #157 | GB-T4.03.01.T1 | task | mvp | #133 |  |
| 3 | #160 | GB-T4.03.02.T1 | task | mvp | #133 |  |
| 3 | #164 | GB-T4.04.01.T1 | task | mvp | #133 |  |
| 3 | #167 | GB-T4.04.02.T1 | task | mvp | #133 |  |
| 3 | #173 | GB-T5.01.01.V1 | test | mvp | #172 |  |
| 3 | #149 | GB-T5.02.01.V1 | test | mvp | #148 |  |
| 3 | #265 | GB-T8.01.01.V1 | test | mvp | #264 |  |
| 3 | #329 | GB-T10.01.01.V1 | test | v1.0 | #328 |  |
| 3 | #332 | GB-T10.01.02.V1 | test | v1.0 | #331 |  |
| 3 | #336 | GB-T10.02.01.V1 | test | v1.0 | #335 |  |
| 3 | #343 | GB-T10.03.01.V1 | test | v1.0 | #342 |  |
| 3 | #346 | GB-T10.03.02.V1 | test | v1.0 | #345 |  |
| 3 | #350 | GB-T10.04.01.V1 | test | v1.0 | #349 |  |
| 3 | #361 | GB-T11.01.01.V1 | test | v1.0 | #360 |  |
| 3 | #364 | GB-T11.01.02.V1 | test | v1.0 | #363 |  |
| 3 | #368 | GB-T11.02.01.V1 | test | v1.0 | #367 |  |
| 3 | #371 | GB-T11.02.02.V1 | test | v1.0 | #370 |  |
| 3 | #375 | GB-T11.03.01.V1 | test | v1.0 | #374 |  |
| 3 | #382 | GB-T11.04.01.V1 | test | v1.0 | #381 |  |
| 3 | #385 | GB-T11.04.02.V1 | test | v1.0 | #384 |  |
| 3 | #393 | GB-T12.01.01.V1 | test | v1.0 | #392 |  |
| 3 | #396 | GB-T12.01.02.V1 | test | v1.0 | #395 |  |
| 3 | #400 | GB-T12.02.01.V1 | test | v1.0 | #399 |  |
| 3 | #403 | GB-T12.02.02.V1 | test | v1.0 | #402 |  |
| 3 | #414 | GB-T12.04.01.V1 | test | v1.0 | #413 |  |
| 3 | #425 | GB-T13.01.01.V1 | test | v1.0 | #424 |  |
| 3 | #428 | GB-T13.01.02.V1 | test | v1.0 | #427 |  |
| 3 | #432 | GB-T13.02.01.V1 | test | v1.0 | #431 |  |
| 3 | #435 | GB-T13.02.02.V1 | test | v1.0 | #434 |  |
| 3 | #439 | GB-T13.03.01.V1 | test | v1.0 | #438 |  |
| 3 | #442 | GB-T13.03.02.V1 | test | v1.0 | #441 |  |
| 3 | #88 | GB-T2.03.02.V1 | test | v1.0 | #87 |  |
| 3 | #92 | GB-T2.04.01.V1 | test | v1.0 | #91 |  |
| 3 | #95 | GB-T2.04.02.V1 | test | v1.0 | #94 |  |
| 3 | #176 | GB-T5.01.02.V1 | test | v1.0 | #175 |  |
| 3 | #190 | GB-T5.04.01.V1 | test | v1.0 | #189 |  |
| 3 | #193 | GB-T5.04.02.V1 | test | v1.0 | #192 |  |
| 3 | #201 | GB-T6.01.01.V1 | test | v1.0 | #200 |  |
| 3 | #208 | GB-T6.02.01.V1 | test | v1.0 | #207 |  |
| 3 | #211 | GB-T6.02.02.V1 | test | v1.0 | #210 |  |
| 3 | #215 | GB-T6.03.01.V1 | test | v1.0 | #214 |  |
| 3 | #218 | GB-T6.03.02.V1 | test | v1.0 | #217 |  |
| 3 | #222 | GB-T6.04.01.V1 | test | v1.0 | #221 |  |
| 3 | #225 | GB-T6.04.02.V1 | test | v1.0 | #224 |  |
| 3 | #233 | GB-T7.01.01.V1 | test | v1.0 | #232 |  |
| 3 | #236 | GB-T7.01.02.V1 | test | v1.0 | #235 |  |
| 3 | #240 | GB-T7.02.01.V1 | test | v1.0 | #239 |  |
| 3 | #243 | GB-T7.02.02.V1 | test | v1.0 | #242 |  |
| 3 | #247 | GB-T7.03.01.V1 | test | v1.0 | #246 |  |
| 3 | #250 | GB-T7.03.02.V1 | test | v1.0 | #249 |  |
| 3 | #254 | GB-T7.04.01.V1 | test | v1.0 | #253 |  |
| 3 | #257 | GB-T7.04.02.V1 | test | v1.0 | #256 |  |
| 3 | #279 | GB-T8.03.01.V1 | test | v1.0 | #278 |  |
| 3 | #282 | GB-T8.03.02.V1 | test | v1.0 | #281 |  |
| 3 | #286 | GB-T8.04.01.V1 | test | v1.0 | #285 |  |
| 3 | #289 | GB-T8.04.02.V1 | test | v1.0 | #288 |  |
| 3 | #297 | GB-T9.01.01.V1 | test | v1.0 | #296 |  |
| 3 | #300 | GB-T9.01.02.V1 | test | v1.0 | #299 |  |
| 3 | #304 | GB-T9.02.01.V1 | test | v1.0 | #303 |  |
| 3 | #307 | GB-T9.02.02.V1 | test | v1.0 | #306 |  |
| 3 | #311 | GB-T9.03.01.V1 | test | v1.0 | #310 |  |
| 3 | #314 | GB-T9.03.02.V1 | test | v1.0 | #313 |  |
| 3 | #318 | GB-T9.04.01.V1 | test | v1.0 | #317 |  |
| 3 | #449 | GB-T13.04.02.V1 | test | post-v1.0 | #448 |  |
| 4 | #55 | GB-T1.03.02.T1 | task | mvp | #53 #46 #35 |  |
| 4 | #130 | GB-T3.D1 | documentation | mvp | #129 #126 #121 #117 #113 #110 #106 #103 #99 |  |
| 4 | #150 | GB-T4.02.01.T1 | task | mvp | #149 #106 #133 |  |
| 4 | #158 | GB-T4.03.01.V1 | test | mvp | #157 |  |
| 4 | #161 | GB-T4.03.02.V1 | test | mvp | #160 |  |
| 4 | #165 | GB-T4.04.01.V1 | test | mvp | #164 |  |
| 4 | #178 | GB-T5.02.02.T1 | task | mvp | #149 #147 |  |
| 4 | #338 | GB-T10.02.02.T1 | task | v1.0 | #336 #325 |  |
| 4 | #377 | GB-T11.03.02.T1 | task | v1.0 | #375 #357 |  |
| 4 | #450 | GB-T13.D1 | documentation | v1.0 | #446 #442 #439 #435 #432 #428 #425 #421 |  |
| 4 | #258 | GB-T7.D1 | documentation | v1.0 | #257 #254 #250 #247 #243 #240 #236 #233 #229 |  |
| 4 | #275 | GB-T8.02.02.V1 | test | v1.0 | #193 #190 #274 |  |
| 4 | #320 | GB-T9.04.02.T1 | task | v1.0 | #307 #304 #300 #297 #293 |  |
| 5 | #56 | GB-T1.03.02.V1 | test | mvp | #55 |  |
| 5 | #461 | GB-T3.G1 | test | mvp | #130 #129 #126 #121 #117 #113 #110 #106 #103 |  |
| 5 | #179 | GB-T5.02.02.V1 | test | mvp | #178 |  |
| 5 | #339 | GB-T10.02.02.V1 | test | v1.0 | #338 |  |
| 5 | #465 | GB-T7.G1 | test | v1.0 | #258 #257 #254 #250 #247 #243 #240 #236 #233 |  |
| 5 | #321 | GB-T9.04.02.V1 | test | v1.0 | #403 #400 #320 |  |
| 6 | #64 | GB-T1.D1 | documentation | mvp | #63 #60 #56 #53 #49 #46 #42 #39 #35 |  |
| 6 | #73 | GB-T2.01.02.T1 | task | mvp | #56 #67 |  |
| 6 | #151 | GB-T4.02.01.V1 | test | mvp | #179 #150 |  |
| 6 | #182 | GB-T5.03.01.T1 | task | mvp | #179 #147 |  |
| 6 | #352 | GB-T10.04.02.T1 | task | v1.0 | #346 #339 #336 #325 |  |
| 6 | #322 | GB-T9.D1 | documentation | v1.0 | #321 #318 #314 #311 #307 #304 #300 #297 #293 |  |
| 7 | #459 | GB-T1.G1 | test | mvp | #64 #63 #60 #56 #53 #49 #46 #42 #39 |  |
| 7 | #74 | GB-T2.01.02.V1 | test | mvp | #73 |  |
| 7 | #154 | GB-T4.02.02.V1 | test | mvp | #151 #153 |  |
| 7 | #183 | GB-T5.03.01.V1 | test | mvp | #182 |  |
| 7 | #467 | GB-T9.G1 | test | v1.0 | #322 #321 #318 #314 #311 #307 #304 #300 #297 |  |
| 8 | #136 | GB-T4.01.01.T1 | task | mvp | #49 #74 #133 |  |
| 8 | #140 | GB-T4.01.02.V1 | test | mvp | #183 #139 |  |
| 8 | #268 | GB-T8.01.02.V1 | test | mvp | #74 #49 #267 |  |
| 8 | #77 | GB-T2.02.01.T1 | task | v1.0 | #74 #67 |  |
| 8 | #185 | GB-T5.03.02.T1 | task | v1.0 | #179 #183 #147 |  |
| 9 | #137 | GB-T4.01.01.V1 | test | mvp | #136 |  |
| 9 | #168 | GB-T4.04.02.V1 | test | mvp | #140 #154 #151 #167 |  |
| 9 | #453 | GB-T8.02.01.T2 | task | mvp | #179 #173 #268 #261 |  |
| 9 | #406 | GB-T12.03.01.T1 | task | v1.0 | #140 #154 #389 |  |
| 9 | #78 | GB-T2.02.01.V1 | test | v1.0 | #77 |  |
| 9 | #186 | GB-T5.03.02.V1 | test | v1.0 | #185 |  |
| 9 | #272 | GB-T8.02.01.V1 | test | v1.0 | #173 #268 #271 |  |
| 10 | #169 | GB-T4.D1 | documentation | mvp | #168 #165 #161 #158 #154 #151 #140 #137 #133 |  |
| 10 | #454 | GB-T8.02.01.V2 | test | mvp | #453 |  |
| 10 | #353 | GB-T10.04.02.V1 | test | v1.0 | #39 #137 #352 |  |
| 10 | #378 | GB-T11.03.02.V1 | test | v1.0 | #190 #186 #377 |  |
| 10 | #407 | GB-T12.03.01.V1 | test | v1.0 | #406 |  |
| 10 | #80 | GB-T2.02.02.T1 | task | v1.0 | #78 #67 |  |
| 10 | #194 | GB-T5.D1 | documentation | v1.0 | #193 #190 #186 #183 #179 #149 #176 #173 #147 |  |
| 11 | #455 | GB-T12.MVP1 | test | mvp | #46 #161 #113 #454 #179 #154 #151 #140 #137 #129 #85 #74 #49 #39 |  |
| 11 | #462 | GB-T4.G1 | test | mvp | #169 #168 #165 #161 #158 #154 #151 #140 #137 |  |
| 11 | #354 | GB-T10.D1 | documentation | v1.0 | #353 #350 #346 #343 #339 #336 #332 #329 #325 |  |
| 11 | #386 | GB-T11.D1 | documentation | v1.0 | #385 #382 #378 #375 #371 #368 #364 #361 #357 |  |
| 11 | #409 | GB-T12.03.02.T1 | task | v1.0 | #378 #186 #389 |  |
| 11 | #81 | GB-T2.02.02.V1 | test | v1.0 | #137 #80 |  |
| 11 | #463 | GB-T5.G1 | test | v1.0 | #194 #193 #190 #186 #183 #179 #149 #176 #173 |  |
| 11 | #290 | GB-T8.D1 | documentation | v1.0 | #454 #289 #286 #282 #279 #275 #272 #268 #265 #261 |  |
| 12 | #456 | GB-T13.G1 | test | mvp | #454 #455 #179 #154 #140 #137 #129 #103 #85 #74 #56 #46 #39 #268 #265 |  |
| 12 | #468 | GB-T10.G1 | test | v1.0 | #354 #353 #350 #346 #343 #339 #336 #332 #329 |  |
| 12 | #469 | GB-T11.G1 | test | v1.0 | #386 #385 #382 #378 #375 #371 #368 #364 #361 |  |
| 12 | #410 | GB-T12.03.02.V1 | test | v1.0 | #409 |  |
| 12 | #96 | GB-T2.D1 | documentation | v1.0 | #95 #92 #88 #85 #81 #78 #74 #71 #67 |  |
| 12 | #203 | GB-T6.01.02.T1 | task | v1.0 | #81 #197 |  |
| 12 | #466 | GB-T8.G1 | test | v1.0 | #290 #454 #289 #286 #282 #279 #275 #272 #268 #265 |  |
| 13 | #471 | GB-T13.04.01.O1 | operations | mvp | #446 #456 |  |
| 13 | #417 | GB-T12.04.02.V1 | test | v1.0 | #257 #410 #407 #353 #416 |  |
| 13 | #460 | GB-T2.G1 | test | v1.0 | #96 #95 #92 #88 #85 #81 #78 #74 #71 |  |
| 13 | #204 | GB-T6.01.02.V1 | test | v1.0 | #203 |  |
| 14 | #418 | GB-T12.D1 | documentation | v1.0 | #455 #417 #414 #410 #407 #403 #400 #396 #393 #389 |  |
| 14 | #457 | GB-T13.G2 | test | v1.0 | #417 #414 #378 #353 |  |
| 14 | #226 | GB-T6.D1 | documentation | v1.0 | #225 #222 #218 #215 #211 #208 #204 #201 #197 |  |
| 15 | #470 | GB-T12.G1 | test | v1.0 | #418 #455 #417 #414 #410 #407 #403 #400 #396 #393 |  |
| 15 | #464 | GB-T6.G1 | test | v1.0 | #226 #225 #222 #218 #215 #211 #208 #204 #201 |  |
| 16 | #472 | GB-T13.G3 | test | v1.0 | #450 #471 #442 #439 #435 #432 #428 #425 #457 #456 #470 #469 #468 #467 #466 #465 #464 #463 #462 #461 #460 #459 #458 |  |
| 17 | #473 | GB-T13.04.01.O2 | operations | v1.0 | #446 #472 |  |

## Closed issues

#2 GB-T0.R1, #3 GB-T0.S1, #4 GB-T0.01, #5 GB-T0.01.01, #6 GB-T0.01.01.T1, #7 GB-T0.01.01.V1, #8 GB-T0.01.02, #9 GB-T0.01.02.T1, #10 GB-T0.01.02.V1, #11 GB-T0.02, #12 GB-T0.02.01, #13 GB-T0.02.01.T1, #14 GB-T0.02.01.V1, #15 GB-T0.02.02, #16 GB-T0.02.02.T1, #17 GB-T0.02.02.V1, #18 GB-T0.03, #19 GB-T0.03.01, #20 GB-T0.03.01.T1, #21 GB-T0.03.01.V1, #22 GB-T0.03.02, #23 GB-T0.03.02.T1, #24 GB-T0.03.02.V1, #25 GB-T0.04, #26 GB-T0.04.01, #27 GB-T0.04.01.T1, #28 GB-T0.04.01.V1, #29 GB-T0.04.02, #30 GB-T0.04.02.T1, #31 GB-T0.04.02.V1, #451 GB-T0.03.02.T1.S1, #452 GB-T0.03.02.T1.S2
