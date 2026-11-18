# Post-release maintenance intake

This guide is the prospective intake procedure for
[GB-T13.04.02.T1 #448][implementation], under [GB-T13.04.02 #447][parent].
The repository currently has no supported application release, approved
collection or measured post-release results for this procedure. Begin collecting
only for an authorized release and an approved evidence source. The mandatory
deployment target is GoDaddy Linux VPS with Nginx HTTPS/WSS, a private MySQL or
MariaDB data plane and persistent assets. [T13 release contract][t13-contract] ·
[ADR 0001][vps-direction]

## Collect and protect the evidence

1. A maintainer designates an intake owner and review date. Before collection,
   record the supported release version, full source SHA and artifact-index
   SHA-256, supported surface, coarse environment class, and the decision that
   verifies release scope. Record each source's purpose, approved measures and
   window, access roles, retention and deletion, and any approved disclosure
   rules. If authorization or the release record is unavailable, leave intake
   pending. Use synthetic examples for procedure review. [Security and privacy
   contract][privacy-contract] · [Release versioning policy][versioning]
2. Collect narrow aggregates using approved existing support, operational or
   accessibility review sources. For example, use launch failures per eligible
   launch attempt, reconnect failures per eligible reconnect attempt, or a
   count of accessibility barriers found on a defined set of tasks. Record
   the time window in UTC, signal category, measure and units, numerator and
   denominator where applicable, baseline measured with the same definition,
   coverage and known gaps. Distinguish retries from separate incidents, and
   distinguish missing data from zero observed failures. Use the evidence to
   describe impact on the workflow rather than to infer individual behavior.
3. Keep authorized source evidence restricted to designated reviewers under
   the approved policy. Record a restricted reference and access owner in the
   private decision record. Keep board or message content, guild/channel/user
   identifiers or hashes, session IDs, tokens, IP addresses, private hostnames,
   screenshots, raw logs and free-text exports out of intake summaries. Suppress
   or combine small cohorts under the approved disclosure rule, including when
   differences between summaries could expose a small cohort. If no disclosure
   rule applies or redaction is uncertain, retain the decision privately and
   withhold the summary. Route suspected vulnerabilities or tenant exposure
   through the [private security reporting policy][security].
4. Use one record per problem and release identity. Match repeated submissions
   to the existing record and update its observation window and evidence
   references without double-counting prior observations. If intake is
   interrupted, resume from the last complete record and reconcile the key and
   evidence before a decision is recorded. Incomplete records stay pending.
   If the release identity changes, open a new record or explicitly document
   why a comparison across identities is valid.

## Decide what enters the maintenance backlog

For each candidate, record the intake key, release identity and environment
class, affected workflow and expected behavior, aggregate observation and
baseline, impact and workaround, confidence and coverage limits, dependencies,
estimated effort, proposed owner role, measurable acceptance criteria, and
review date. An enhancement can cite dated evidence of an unmet workflow
rather than a failure rate. Keep unmeasured ideas provisional and give them an
evidence question and revisit trigger.

| Evidence at triage | Disposition |
| --- | --- |
| Suspected privacy, security or tenant isolation issue | Escalate privately under the security policy. Public intake carries no incident details. |
| Unmet existing release, GoDaddy, security or recovery requirement | Route to the existing mandatory work item and its owner with a safe evidence reference. Preserve its status and acceptance criteria. |
| Measured issue or evidenced nonessential enhancement with bounded scope, owner role and acceptance criteria | Propose an independently prioritized maintenance item. Link existing work for duplicates. |
| Missing prerequisite, weak coverage, unknown impact or inconsistent data | Record the gap and revisit trigger. Keep the item provisional. |
| Hosting hypothesis | Track as optional research with a specific measured problem, expected operational benefit and an evidence plan. |

The maintainer and affected workstream reviewer order optional items separately
from release work. Compare user harm and workflow blockage first, then frequency
or breadth, strength and recency of evidence, and available workarounds. Use
effort, dependencies and operational risk to resolve ties or schedule a smaller
investigation. Record the rationale, reviewer, decision date and next check.
Escalate a mandatory defect through its existing gate. An optional backlog
decision carries no release or hosting approval. [Governance][governance] ·
[T13 release contract][t13-contract]

## Optional managed Node hosting research

Public documentation consulted on 2026-11-17 US/Eastern. These are provisional
observations about provider features. The comparison uses the repository's
Node 24 requirement and accepted storage and trust boundaries. [Workspace
runtime constraint][node-runtime] · [Architecture][architecture]

| Area | Render | Railway |
| --- | --- | --- |
| Node and public ingress | Node versions can be pinned. Web services terminate TLS and support WebSocket upgrades on the public HTTP port. Instance replacement closes connections. [Node version][render-node] · [Web services][render-web] · [WebSockets][render-ws] | Railpack supports explicit Node version selection. The public edge documents TLS and WebSockets over HTTP/1.1. [Railpack Node][railway-node] · [Edge specs and limits][railway-edge] |
| Private SQL and durable assets | Private services provide a nonpublic path. The persistent-disk documentation describes custom MySQL on a disk. Data outside the mount is ephemeral, and disk attachment interrupts redeploys. [Private services][render-private] · [Persistent disks][render-disks] | Private networking is scoped to a project environment. Railway documents a MySQL service, optional backup and recovery features, and persistent volumes. An attached volume prevents overlapping deploys of the service. [Private networking][railway-private] · [MySQL][railway-mysql] · [Volumes][railway-volumes] · [Healthchecks][railway-health] |
| Migrations and rollback | Eligible paid services can run a pre-deploy command in a separate instance without the service disk. Rollback can reuse a retained build artifact, and disk data persists across code rollbacks. [Deploys][render-deploy] · [Rollbacks][render-rollback] | Pre-deploy commands run without attached volumes. A deploy-time health check gates activation when configured. Rollback uses a previous image and variables while the deploy is retained. [Pre-deploy][railway-predeploy] · [Healthchecks][railway-health] · [Rollback][railway-rollback] |

A future evaluation would need a measured need to justify the work and a scope
approved under repository governance. Refresh sources and compare the same
workload and operating requirements against the mandatory VPS baseline. Confirm
plan and region availability, runtime pinning, support responsibilities and
cost drivers for compute, egress, storage and recovery. Require evidence for
trusted HTTPS/WSS ingress and actual Discord iframe/proxy/client behavior,
connection draining and reconnect, private SQL and scoped asset access, secrets
rotation, and tenant isolation. Test backward-compatible migrations, interrupted
deploys, and code rollback with persisted data. Restore SQL and assets together
into an isolated environment and measure achieved data loss and recovery time.
A provider capability or code rollback alone establishes none of those
outcomes. The documented comparison leaves platform compatibility, costs and
operational fit open. [GoDaddy deployment guidance][godaddy]

## Verification handoff

Give [GB-T13.04.02.V1 #449][verification] the reviewed intake guide and, when
authorized, the candidate-scoped aggregate evidence, restricted evidence
references, decision records and dated research sources. The verifier records
the exact tested revision and environment, commands or scenario steps,
sanitized outputs, observed outcomes, defects and unresolved prerequisites.
Retain permitted raw verification results under the applicable access and
retention rules. Report synthetic, desk research and real-environment evidence
with their respective scope.

| Scenario for #449 | Expected result |
| --- | --- |
| Synthetic supported-release record with a safe aggregate and separate enhancement | Link evidence and a measurable acceptance criterion for the measured need. Record the enhancement independently with its evidence or revisit trigger. |
| Missing release approval or source policy, invalid identity or measure, or a summary that risks exposing a small cohort | Leave the record pending or withhold the summary. Produce only a safe status or field category. |
| Interrupted submission or duplicate evidence | Reconcile the record and retain one complete disposition without double-counting. |
| Managed hosting research and an unmet mandatory VPS requirement are submitted together | Keep the research provisional and route the VPS requirement to its existing gate. |
| Source becomes unavailable or there is only synthetic transport or recovery evidence | Mark the affected finding stale or unverified, and identify the missing evidence. |

The [T13 workstream][workstream] is the integration index. Actual post-release
collection, independent prioritization decisions, product and platform
verification, and release approvals require their own linked evidence.

[implementation]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/448
[parent]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/447
[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/449
[t13-contract]: specifications/GB-T13-S1-documentation-release-contract.md
[vps-direction]: adr/0001-editor-activity-vps-direction.md
[privacy-contract]: specifications/GB-T9-S1-security-privacy-contract.md
[versioning]: release-versioning.md
[security]: ../SECURITY.md
[governance]: ../GOVERNANCE.md
[node-runtime]: ../package.json
[architecture]: architecture.md
[godaddy]: ../infra/godaddy/README.md
[workstream]: workstreams/T13.md
[render-node]: https://render.com/docs/node-version
[render-web]: https://render.com/docs/web-services
[render-ws]: https://render.com/docs/websocket
[render-private]: https://render.com/docs/private-services
[render-disks]: https://render.com/docs/disks
[render-deploy]: https://render.com/docs/deploys
[render-rollback]: https://render.com/docs/rollbacks
[railway-node]: https://railpack.com/languages/node
[railway-edge]: https://docs.railway.com/networking/public-networking/specs-and-limits
[railway-private]: https://docs.railway.com/networking/private-networking
[railway-mysql]: https://docs.railway.com/databases/mysql
[railway-volumes]: https://docs.railway.com/volumes
[railway-health]: https://docs.railway.com/deployments/healthchecks
[railway-predeploy]: https://docs.railway.com/deployments/pre-deploy-command
[railway-rollback]: https://railway.com/guides/roll-back-bad-deploy
