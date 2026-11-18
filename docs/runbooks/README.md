# Guildboard operations runbook

[GB-T11.04.01.T1 (#381)](https://github.com/CompleteTech-DiscordApps/guildboard/issues/381)
documents planned operator procedures for the mandatory GoDaddy Linux VPS
with Nginx HTTPS/WSS, private SQL and persistent private assets. SRE owns the
runbook with T10 deployment, T4/T5 persistence, T9 security and T12 verification
review. Use the [GoDaddy operations guide][godaddy] for platform procedures
and the [T11 operations contract][sre] for recovery and incident decisions.
Independent rehearsal and environment evidence remain open under
[GB-T11.04.01.V1 (#382)](https://github.com/CompleteTech-DiscordApps/guildboard/issues/382).

## Deploy, roll back and patch

1. Before a change, confirm the approved environment, window, operator and
   decision owner. Record the source SHA, artifact digest, configuration
   reference, compatibility and migration plan, previous release, verified
   recovery point, and abort and recovery criteria. Verify access, required
   mounts, backup and measured headroom. Hold for missing approval, access,
   recovery evidence or prerequisites. Report invalid configuration by
   variable name only. [Preflight and stage ownership][preflight]
2. Prove the sequence in authorized staging. Hold the release lock, gate
   ingress, and perform migrations with a single authorized runner. On
   interruption, check the migration ledger and actual durable effects before
   retry. Verify readiness, HTTPS and mapped WSS/reconnect, authorized and
   denied actions, and state and receipt integrity before promoting. Drain
   old traffic with bounded shutdown and reconcile uncertain commits using
   their original operation identities. [Staged release and migrations][release]
3. On failed promotion, stop rollout and fence affected writes while integrity
   is uncertain. Return to the previous verified artifact and configuration
   only with compatible schema, protocol and assets. Otherwise keep writes
   fenced and use the reviewed forward repair or isolated restore plan.
   Account for acknowledged writes since the recovery point before approving
   cutover. Repeat readiness, network, authorization and integrity checks
   before reopening traffic. [Backups, recovery and rollback][backup]
4. For OS, Nginx, database and runtime patches, review support and compatibility,
   including restart or reboot requirements. Verify console recovery, the
   recovery point and the patch-specific rollback or repair path. Rehearse in
   staging, drain affected services before restart, then check mounts, SQL,
   external HTTPS/WSS, readiness, receipts and alerts before restoring traffic.
   Record versions, checks and the decision in the change record.
   [Preflight and stage ownership][preflight]

## TLS and credential rotation

- Check renewal scheduling and expiry alerts. Investigate failed renewal by
  checking authoritative DNS, challenge reachability and reload status. After
  authorized renewal, validate Nginx configuration before reload, then verify
  the externally served hostname, chain and validity across published address
  families and check the mapped WSS path. Hold cutover on a failed check.
  [DNS, HTTPS and Activity WSS][tls]
- Inventory affected consumers by role and configuration reference. With the
  responsible database, Discord or platform owner, authorize the scope and
  sequence, including any required session invalidation. Use the approved
  protected runtime injection path, verify least-privilege access and
  dependent service readiness, then retire the superseded access and verify
  its rejection. For suspected exposure, escalate to T9 for containment and
  revocation. Keep credential material out of logs, evidence and messages.
  [Private SQL, assets and secrets][secrets] · [Security policy][security]

## Resource and disk pressure

Use owner-approved alert and admission criteria based on measured staging
capacity. Check CPU, memory, queues, disk bytes, inodes, mounts, database and
backup health. Stop promotion and reduce admission using approved controls.
Fence affected writes when durable commits or integrity are uncertain.
Preserve accepted state, retained receipts across lineages, required replay
logs, pinned assets and audit evidence. Reclaim only approved expendable
material or add capacity. Pressure never authorizes receipt expiry or physical
purge. Verify durable receipt reconciliation, SQL/asset integrity and stable
headroom before lifting restrictions. [Monitoring and failure handling][monitoring]
· [Persistence and recovery contract][persistence]

## Back up and restore in isolation

1. Verify the coordinated encrypted SQL cut, required replay range, matching
   asset manifest and hashes, accessible recovery keys, and an off-host copy.
   Record the verified generation and recovery point independently of job
   completion. An interrupted attempt stays incomplete until revalidated.
   [Independent backup and restore acceptance][recovery]
2. Before opening artifacts or writing, verify target identity, read/write
   isolation, scoped recovery access and absence of production routing. Verify
   a synthetic target marker and unchanged independent guard markers in the
   authorized rehearsal environment. Record zero destination writes if
   preflight denies the restore. Verify artifacts, restore the matched cut and
   quarantine any interrupted output before retrying from a verified cut.
   [Independent backup and restore acceptance][recovery]
3. Independently authenticate the applied deletion cut against the exact
   recovered generation, SQL/log cut, assets, exports and scoped references.
   Verify the restored projection reflects that cut. If unproven, reconcile
   from an independently established earlier cut or keep the target isolated.
   Apply authoritative, contiguous deletion markers through a serialized
   exposure fence or reconcile again at an equivalent fence. Reapply current
   revocations and verify that deleted or revoked content, assets, exports and
   references remain inaccessible, including reads from a previously authorized
   session. Exercise negative cross-guild and cross-board reads and writes and
   verify denial leaves no durable or delivery effect. Verify audit continuity against
   protected independent anchors through the accepted head, including the
   active tail. Missing, stale or gapped evidence, an unapplied deletion,
   or an unverified audit head keeps the target isolated. [T5 disaster recovery][disaster] · [T9 deletion policy][deletion]
   · [T9 audit integrity][audit]
4. Before authorized cutover, verify hashes, tenant boundaries, current
   authority, lineage and receipt coverage, and fence the prior serving
   generation. Establish fresh disaster-recovery lineages and preserve
   unknown historical outcomes when receipt coverage is incomplete. Compare independent pre-fault acknowledgment and recovery
   inventories, escalate known loss at or before the cut or outside the
   approved post-cut boundary, and record missing coverage. Measure the
   recovery point from the original verified pre-fault canary commit to
   fault time and recovery time from declaration through verified service.
   Compare each result with its separately approved objective. Keep the target
   isolated when required coverage or timing is unknown, an objective is
   breached, or the drill verdict is failed or undetermined. Record the
   evidence gap and the independent decision before retry.
   [Independent backup and restore acceptance][recovery]

## Outage triage and handoff

1. The designated SRE on-call or incident commander records declaration time,
   impact and affected scope, and assigns responders. Compare external HTTPS
   and the Discord WSS path, then check DNS/TLS, Nginx, service readiness,
   SQL/assets and host resources to isolate the failing boundary. Escalate
   suspected data loss, disclosure or compromised credentials immediately.
   Contain affected paths and preserve restricted evidence.
   [Monitoring and failure handling][monitoring] · [Security policy][security]
2. T10 owns edge, host and rollout actions. T4/T5 own durable state,
   acknowledgment and recovery analysis. T9 owns security containment,
   evidence custody and private reporting. T12 QE checks the evidence.
   The incident commander records the decision and hands off the UTC timeline,
   current impact, actions, write/traffic gates, recovery or loss status,
   restricted evidence references, next decision and owner. Obtain
   acknowledgment from the receiving role or escalate to the designated
   alternate under the approved rota. [Incident roles and handoffs][roles]
3. The communications owner drafts a redacted update with confirmed impact,
   current mitigation and next update time. Obtain explicit approval for
   the audience, channel and content before any real communication. Use the
   private security route for suspected security incidents under the applicable
   authority. At closure verify recovery, record the known loss boundary or
   open uncertainty, and assign follow-up owners. [Incident roles and handoffs][roles]
   · [Security policy][security]

For suspected credential compromise and other security incidents, use the
[security incident decisions and post-release care](security-incident-and-post-release-care.md)
supplement for approved containment, evidence custody and disclosure decisions.

## Synthetic tabletop evidence plan

Use paper or local synthetic fixtures and simulate approvals, notifications and
acknowledgment. Assign a facilitator, decision roles and an observer. Mark a
case passed when the observer records the expected decision and evidence,
failed when an observed decision or safeguard diverges, and blocked when
required inputs or observations are missing.

| Scenario | Pass evidence |
| --- | --- |
| Release succeeds, then inject invalid configuration, a missing prerequisite or an interrupted migration | Promotion follows readiness and smoke checks in the positive case. Negative cases stay gated, show names-only diagnostics for invalid configuration, and reconcile durable migration state before retry. Compatible rollback and incompatible forward recovery have distinct decisions. |
| Patch requires restart and a TLS renewal reload fails | The patch response records the approved recovery path, drain and post-restart checks. The TLS response holds cutover pending valid external TLS and WSS checks. |
| Disk/inodes and queues saturate during an uncertain commit | The decision limits admission or fences writes as appropriate, preserves durable receipts and recovery evidence, and reconciles the original operation before reopening. |
| Isolated restore succeeds, then inject unsafe destination, interruption, gapped deletion markers, unanchored audit tail or loss of an acknowledged write | The positive case identifies the exact recovered cut and all exposure proofs. Unsafe destination gives zero writes. Partial output is quarantined, missing proofs prevent exposure, and known loss at or before the cut or outside the approved post-cut boundary is escalated. |
| Discord-path outage and suspected credential exposure overlap an on-call change | The timeline identifies the failing path and immediate security escalation. The alternate acknowledges handoff when the primary is unavailable. The simulated communications decision requires approval and verifies that the update is redacted. |

For each case record UTC time, full source SHA, artifact identity if
applicable, environment and fixture/version, roles, inputs and simulated
actions, expected and observed decisions, verdict, restricted evidence
reference, cleanup or untouched status, defects and follow-up owner. Use T12
for evidence qualification and T13 for the release handoff. Record tabletop
results as synthetic. [#382](https://github.com/CompleteTech-DiscordApps/guildboard/issues/382)
tracks independent rehearsal on the applicable authorized environments and
production acceptance requires its own gate evidence.
[T12 evidence contract][verification] · [T13 release gate handoff][handoff]

[godaddy]: ../godaddy-operations-guide.md
[preflight]: ../godaddy-operations-guide.md#preflight-and-stage-ownership
[release]: ../godaddy-operations-guide.md#staged-release-and-migrations
[backup]: ../godaddy-operations-guide.md#backups-recovery-and-rollback
[tls]: ../godaddy-operations-guide.md#dns-https-and-activity-wss
[secrets]: ../godaddy-operations-guide.md#private-sql-assets-and-secrets
[monitoring]: ../godaddy-operations-guide.md#monitoring-and-failure-handling
[sre]: ../specifications/GB-T11-S1-sre-operations-contract.md
[recovery]: ../specifications/GB-T11-S1-sre-operations-contract.md#independent-backup-and-restore-acceptance
[roles]: ../specifications/GB-T11-S1-sre-operations-contract.md#incident-roles-and-handoffs
[persistence]: ../specifications/GB-T5-S1-persistence-recovery-contract.md#4-snapshot-cut-immutable-assets-and-bounds
[disaster]: ../specifications/GB-T5-S1-persistence-recovery-contract.md#5-distinct-recovery-boundaries
[deletion]: ../specifications/GB-T9-S1-security-privacy-contract.md#deletion-and-recovery-policy
[audit]: ../specifications/GB-T9-S1-security-privacy-contract.md#audit-integrity-and-incident-evidence
[security]: ../../SECURITY.md
[verification]: ../specifications/GB-T12-S1-verification-evidence-contract.md#closed-evidence-envelope
[handoff]: ../specifications/GB-T13-S1-documentation-release-contract.md#gate-and-publication-handoff
