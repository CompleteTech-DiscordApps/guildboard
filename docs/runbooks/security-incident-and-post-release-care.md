# Security incident decisions and post-release care

[GB-T11.04.02.T1 (#384)][issue] supplements the [operations runbook][runbook]
for suspected credential compromise, disclosure or cross-tenant access. Use the
[accepted incident roles][roles] and the [private reporting policy][security].
SRE records the decision and tracks the handoff. T9 owns containment and
evidence with the responsible system owner. Use the approved rota and alternate
when a responder is unavailable. Escalate suspected compromise immediately
even when the affected scope or evidence coverage remains uncertain.

## Contain and verify

1. Record the UTC declaration time, affected environment and release identity
   if known, narrowest evidenced service or tenant scope, suspected impact,
   decision owner and outstanding questions. Uncertain scope stays explicit.
   Hold affected admission or writes through already authorized controls when
   current authority or commit integrity cannot be established.
2. Before revocation or rotation, verify the action and target against the
   affected scope and record T9's decision with the responsible system owner's
   authorization. Reference the approved configuration and affected consumers
   by role. For invalid configuration record field names only and hold the
   requested action. If authority or a prerequisite is unavailable, continue
   authorized containment and escalate the gap. Commit mandatory audit
   metadata atomically with the authoritative transition. When the required
   audit path is unavailable or atomic acceptance is unproven, hold the
   transition and continue separately authorized safeguards.
   For routine rotation, verify
   replacement access and dependent service readiness before retiring
   superseded access, following the [rotation procedure][rotation]. For
   suspected compromise, T9 and the responsible system owner may approve
   urgent revocation and isolation before replacement access is ready. Keep
   affected admission or writes fenced until replacement access and dependent
   services are verified where required, the containment checks below pass,
   and SRE approves recovery.
3. Verify that superseded authority is rejected, including any affected open
   session, reconnect, and queued protected delivery on applicable surfaces.
   Exercise denial across the affected tenant boundary and confirm no new
   durable or delivery effect caused by the denied action. Reconcile an
   operation already committed before revocation using its original identity.
   Verify affected paths remain isolated until the new authority, unaffected
   scope and applicable durable state are established. [T9 commit and release][fence]
4. If containment, revocation or verification is interrupted, retain the
   current fence and leave the affected action incomplete. Before retry, use
   authorized records to reconcile the actual revocation and isolation state,
   independent effects and unresolved scoped operations. Verify the same
   decision scope and authority before continuing. Keep the boundary held
   until required evidence is complete and SRE approves recovery.

## Preserve and route

- Use only the separately authorized evidence destination and scoped custody
  approved for this incident. Before collecting or transferring, confirm the
  purpose, exact source and window, custodian, recipient access, retention or
  approved hold, and destination. Withhold the operation when authorization,
  access, integrity verification or the destination is unavailable.
- Preserve the minimum material needed under the approved policy. Record the
  source reference, time window, collection and transfer times, responsible
  custodians, approved hold or expiry reference, and integrity verification
  at collection and transfer inside the restricted record. Keep credential
  material out of incident artifacts and messages. Keep sensitive raw
  diagnostics in the authorized store and use redacted or opaque references
  for handoffs. Record access decisions under the existing audit rules.
  If preservation is interrupted or integrity is uncertain, keep partial
  evidence restricted, record the gap and verify it before use or transfer.
  [T9 audit integrity and incident evidence][audit]
- With approved audience, channel and content, use GitHub's private vulnerability
  reporting feature when enabled. If confirmed unavailable, verify the
  maintainer contact method on the actual profile named in SECURITY.md
  before sharing details. When the private route is unknown or unverified,
  retain the report privately and escalate through the approved rota.
  Public summaries require their own authorization and redaction. Record
  acknowledgment or the outstanding handoff and alternate. [Security policy][security]
- Record verified recovery, the known loss boundary or an explicit unresolved
  loss item, and the redacted evidence reference for the parent and release
  gate. The runbook's isolated restore and cutover checks apply whenever
  recovery uses a restore. [Isolated restore][restore] · [Release gate handoff][release]

## Maintain after release

Use the authorized release identity, designated owners, and existing review
calendar. Record the checked revision, time, scoped evidence reference, result,
gaps, owner and next review in the maintenance record.

| Check | Decision and evidence |
| --- | --- |
| Dependency updates | Review the proposed version and advisories, committed lockfile, package integrity, licenses and applicable regressions under the existing upgrade gate. Retain the dated audit and review evidence for the candidate. If any required check or advisory disposition is incomplete, hold the update and assign the next action. [Upgrade policy][upgrades] |
| Backup health | Verify the expected job against the approved finish deadline and maximum recovery-point age. Require an independently verified fresh recovery point and verified intact chain bound to the expected job, deployment and profile. Investigate interrupted or missing jobs, unavailable chain proof or a stale point. Immediately escalate confirmed integrity failures, unsafe restore targets or known acknowledged loss outside the trial boundary under T11. [T11 candidate alert rules][alerts] · [Isolated restore][restore] |
| Post-incident improvements | Record each gap or corrective action once against a restricted incident reference. Assign an accountable owner, measurable completion criterion, evidence reference and review date. Link existing work when it already covers the action. At the next review keep unresolved items open, update the next decision, and close an item only after the recorded criterion has verified evidence. Use the existing mandatory gate for release blockers and the maintenance intake for eligible nonessential improvements. [Maintenance intake][maintenance] |

## Synthetic acceptance

Run `python3 -m unittest discover -s tests/verification -p test_t11_security_incident_decisions.py -v`.
The pure decision examples cover approved scoped revocation and isolation,
urgent revocation before replacement readiness with recovery held,
invalid configuration, unavailable authorization and audit, interrupted action
and reconciliation, no unauthorized evidence transfer, safe private route
selection, and held maintenance checks and follow-ups. The fixture values
represent observations supplied by a tabletop facilitator. Exercise the
observable outcomes in the [operations tabletop][tabletop] evidence format
with separate responder and verifier roles before using the workflow.

Independent SRE and security review, maintainer approval of the actual rota,
authorities, custody and notification paths, and a dated independent authorized
rehearsal remain acceptance inputs. Obtain exact-revision evidence where the
rehearsal requires registered Discord session behavior or applicable GoDaddy
containment, backup and recovery behavior. The offline tests have no host or
Discord integration, credentials, evidence collection or message sending.

[issue]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/384
[runbook]: README.md
[roles]: ../specifications/GB-T11-S1-sre-operations-contract.md#incident-roles-and-handoffs
[security]: ../../SECURITY.md
[rotation]: README.md#tls-and-credential-rotation
[fence]: ../specifications/GB-T9-S1-security-privacy-contract.md#commit-lookup-and-read-release
[audit]: ../specifications/GB-T9-S1-security-privacy-contract.md#audit-integrity-and-incident-evidence
[restore]: README.md#back-up-and-restore-in-isolation
[release]: ../specifications/GB-T13-S1-documentation-release-contract.md#gate-and-publication-handoff
[upgrades]: ../license-supply-chain-policy.md#upgrade-policy
[alerts]: ../specifications/GB-T11-S1-sre-operations-contract.md#indicators-and-alert-evaluation
[maintenance]: ../maintenance-intake.md
[tabletop]: README.md#synthetic-tabletop-evidence-plan
