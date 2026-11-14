# GB-T4.R1 — proposed conflict and sequencing decision

Issue [#132](https://github.com/CompleteTech-DiscordApps/guildboard/issues/132), researched 2026-10-24 UTC. **Recommendation for review, not an accepted specification or implemented service.** #133 and the T4 release gate remain open. Parent #131, full issue acceptance and its zero-comment/no-native-blocker state were inspected.

## Recommended experiment boundary

Use a server-authoritative per-board log with per-element expected-version checks and atomic compound intents. Serialize each accepted command against current tenant/session/policy and the board revision, then commit canonical content, scoped receipt, outbox and audit together. Assign one revision per accepted compound. Reject stale affected-element intent rather than guessing a transform; unrelated unchanged elements may proceed despite an older board base revision. This is a conservative proposal, not a claim that arbitrary Excalidraw edits commute.

An editor version/versionNonce is client-controlled metadata, not a server sequence or authority token. The adapter must retain server versions separately, identify every affected/bound element, and preserve tombstones. Undo is a new bounded, currently authorized inverse intent with current preconditions; it must not replace the scene or undo another participant's accepted work. A rejected optimistic edit needs deterministic rollback and an explicit unsaved/rejected UI state. These mappings remain browser and integration experiments, not proven by the model below.

## Primary evidence and evaluated versions

- Excalidraw **0.18.1**, source `a2ec2889babf7d2295469c6d90ebe77fae57df84`: [element types](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/element/types.ts) expose element identity, versions and deletion state. [Store capture actions](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/store.ts) distinguish immediate, deferred and never-undoable updates; these are local history controls, not durable authorization/ordering. Static source was inspected; no editor code ran in this experiment.
- [Yjs document-update documentation](https://docs.yjs.dev/api/document-updates), accessed 2026-10-24, describes updates as reorderable/idempotent and provides state vectors and transaction origins. This supports CRDT as an alternative worth evaluating, not permission enforcement or a tested Excalidraw binding. No Yjs package/version was installed or benchmarked; the mutable documentation is not an evaluated binary.
- [MySQL 8.4 locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html), accessed 2026-10-24, explains why ordinary reads do not protect subsequent dependent writes. This informs a future transaction/fencing design only. No MySQL or MariaDB server, isolation mode or deployment has been tested or selected here.

Related inputs are the unmerged #477 feasibility research and local proposed architecture revision `4b69f5e981ffdc0f6d58ed623d2d89048214f5ee`. They are coordination inputs, not accepted dependencies. The separate #98 editor research reports browser startup blocked before any behavioral assertions; nothing here upgrades that result.

## Alternatives

| Candidate | Reproducible observation or review | Decision/tradeoff |
|---|---|---|
| Full-document last-write-wins | Two clients edit different elements from one initial scene; the last complete scene erases the other's change in both arrival orders | Reject for shared authoritative editing; this counterexample is not a benchmark of any existing collaboration library |
| Whole-board compare-and-set log | In all six orders of three distinct-element commands based on revision zero, only the first succeeds | Safe conservative baseline but unnecessarily rejects unrelated edits; useful fallback for operation kinds without proven element footprints |
| Per-element preconditions + serialized log | The same six schedules accept all three distinct-element changes and reach the same scalar state; same-element races accept first/reject second in both orders | Recommended next specification experiment; contention rejection is intentional and requires good recovery UX |
| Property-level merge or transforms | Not executed; can reduce conflicts but needs explicit noncommuting geometry, text, binding, deletion and undo semantics | Defer until required semantics and counterexamples are specified; do not infer transformability from JSON fields |
| CRDT-backed scene or text | Reviewed Yjs update properties only; no binding, persistence, moderation, tombstone or undo experiment | Keep as alternative for selected operation types; convergence does not itself decide which mutations are authorized or durably accepted |

An authoritative log can carry CRDT/OT payloads later if server validation and revocation boundaries remain enforceable. This recommendation does not claim CRDTs are incompatible with authorization. Neither local sorting nor WebSocket delivery order substitutes for a durable global board sequence.

## Reproducible finite-model experiment

The Python standard-library fixture in `research-fixtures/collaboration` uses three pre-existing scalar elements A/B/C. It is deliberately **not imported by application workspaces** and is not a wire codec, database adapter or service implementation. Dataclasses represent an already decoded closed domain. Calls execute sequentially as atomic transitions by construction; no thread scheduler or SQL lock is tested.

```
python3 -m unittest discover -s research-fixtures/collaboration -v
python3 scripts/github-bootstrap/validate.py
git diff --check
```

The initial 2026-10-24 run used Python 3.12.14 and passed 15 tests. Review remediation on 2026-10-25 used Python 3.14.3 on Windows: **16 tests pass**, including all **720 positional permutations** of three accepted events repeated twice (90 unique value-order sequences; duplicate positional permutations are intentionally not described as independent cases). Tests also cover:

- all six command orderings for both board-CAS and element-precondition strategies;
- same-element conflict in both orders; compound rejection after a valid first candidate leaves the original state untouched; successful compound gets one modeled revision;
- simulated unknown outcome before/after modeled commit, retry returning one receipt/revision, changed-payload collision, actor-scoped operation IDs;
- synthetic expired session, foreign guild/board, denied read/write, stale policy, and no-state-change assertions;
- revoke-before-write versus write-before-revoke serialization, and read-authorized receipt replay after write loss without another mutation;
- deletion tombstone rejecting stale/ordinary inverse resurrection;
- empty/duplicate/oversized compound and invalid scalar cases;
- replay gap buffering, duplicate delivery, conflicting pending event detection and bounded overflow returning snapshot-required.
- all 24 delivery orders of four revisions, including `(2, 3, 4, 1)`: the contiguous gap-closing event applies immediately and drains buffered successors without consuming a fourth pending slot. A fourth distinct out-of-order event still returns snapshot-required without changing replica state. The six orders delivering revision 1 last failed before the remediation and pass after it.

`model.py` and `test_model.py` hashes, Python version and exact observations are retained in [evidence](evidence/collaboration-model-2026-10-24.json). The October model cleared receipts on restore and did not cover retired-lineage receipt recovery; that coverage belongs to the separately dated November follow-up below. The modeled transition copies candidate state and commits only after validation; it is a statement of intended semantics, not proof real SQL transactions implement them.

## Protocol and integration handoff

Propose a receipt key scoped by guild, board, lineage, actor and operation ID. Digest semantic kind/payload/preconditions using an agreed strict canonical codec; exclude transport correlation ID. Verify identity and current read access before receipt disclosure; require current write authority for a new operation. Same key/different digest rejects. A retry of an already committed operation can return its receipt after write revocation only while read access remains. Do not issue a new operation ID because acknowledgment timed out.

**Cross-restore candidate:** the model now retains scoped receipts when `Board.restore` resets content and active events. After current identity/read checks and closed-domain validation, receipt lookup uses the command's lineage before rejecting old-lineage commands or checking the active revision bound. An identical committed retry returns its historical receipt even after write loss; a changed digest conflicts; an old command without a matching actor-scoped receipt gets `LINEAGE_CHANGED`. The historical revision belongs to the command's retired lineage and must never be installed as an active-lineage revision or replayed into restored content. This follows the proposed [#481 system contract at `19d5f5a35511a1edf3a8bd34773fbb4d57546b89`](https://github.com/CompleteTech-DiscordApps/guildboard/blob/19d5f5a35511a1edf3a8bd34773fbb4d57546b89/docs/specifications/GB-T0-S1-system-contract.md), sections 5–6, and #490's retention candidate. All remain provisional. The model does not implement durable receipt storage, retention quotas, client reconciliation or repeatable lineage allocation.

The receipt-retention follow-up begun on 2026-11-12 was tested at `3de06ef8c8e675b13f8fa38f79026bcc4f3dac1e` on **2026-11-13 at 02:44:45 UTC**, using Python 3.14.8 on Linux: **17 tests pass**. The appended `followup_observations` entry in the [evidence](evidence/collaboration-model-2026-10-24.json) retains the exact timestamp, source hashes, command and raw output separately from the unchanged October observations. Before remediation, two restore regressions failed against model revision `e5fbefe91e402fc361910e57e643702af245727a`: lost-ack recovery returned `LINEAGE_CHANGED`, and only the new-lineage receipt survived. The November tests cover retired-lineage receipt recovery after modeled restore, old-lineage denial without a receipt, a historical base revision above the reset revision, changed-payload conflict, current session/read/tenant checks, actor isolation, uncommitted old commands, unchanged restored content/events, and an independent same-ID new-lineage command.

Persist state, receipt and event/outbox atomically before acknowledging. Use a globally consistent lock order for board/policy/session invalidation, explicit transaction isolation, uniqueness constraints and bounded deadlock retry. A revoke that commits first fences stale intent; an already locked writer may commit before the queued revoke. This model merely enumerates those serial orders. Database faults, restarts, multiple processes and commit-time policy races require separate real tests.

Reordered delivery may buffer only within a fixed budget; gaps never advance accepted state. A contiguous event applies immediately and drains available successors; only a new out-of-order insertion consumes the three-event toy budget. On overflow, old lineage or unavailable retained events, request a validated snapshot plus strictly newer tail. Snapshot installation must be atomic after complete verification; this fixture does **not** implement snapshots, digest verification or interrupted-transfer recovery. Existing applied-revision duplicates are trusted/ignored in the toy, while conflicting pending events are detected. A production codec must validate event integrity and source before either behavior.

## Uncertainty and acceptance still open

The model intentionally omits real identity/membership verification, action/object-specific permissions, browser rendering, geometry/bindings/groups, asset references, float/canonical-JSON semantics, uint64 rollover, actual persistence/crashes, asynchronous concurrency, snapshot installation, durable receipt retention/compaction, undo transforms, backpressure byte budgets, performance and arbitrary malformed-object handling. Its scalar/compound bounds are not adopted production limits. Restore is a single transition to one second toy lineage, not repeatable production lineage allocation. Do not copy this model as a server implementation.

Before accepting #132/#133: obtain fresh realtime/security/consumer review, validate the pinned Excalidraw adapter's operation footprint and undo/rejection semantics, specify actual payload schemas and canonical digest encoding, and run database transaction/fault/recovery experiments. Discord iframe/WSS, current platform identity, actual GoDaddy Linux VPS and real load/capacity are not applicable to these finite-model observations and remain unverified elsewhere. No credentials, deployments or external security settings were touched. Required formal approval, merge and post-merge verification remain open; no issue is closed by this record.
