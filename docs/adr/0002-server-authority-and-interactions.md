# ADR 0002: Server authority and interaction boundaries

Status: **proposed**, pending fresh independent architecture, security and consumer review and delegated coordinator acceptance. Issue: [GB-T0.01.02.T1 #9](https://github.com/CompleteTech-DiscordApps/guildboard/issues/9). Proposed status does not itself impose a human-only decision gate; configured repository protections and actual required review still apply.

## Context and evidence

[ADR 0001](0001-editor-activity-vps-direction.md) accepts a controlled server-authoritative Activity experiment on the GoDaddy VPS path. The accepted [GB-T0.S1 system contract](../specifications/GB-T0-S1-system-contract.md), whose acceptance history is in [T0](../workstreams/T0.md), supplies the detailed boundary, receipt, authorization and release semantics. [Requirements](../requirements/GB-T0-01-01-requirements.md), use cases and the [MVP matrix](../../planning/MVP-ACCEPTANCE.md) require tenant isolation, viewer denial, durable acknowledged saves and recovery. These are design requirements, not evidence of a working service.

## Decision and alternatives

Select server-derived session and tenant authority, one shared command service for Activity/API and verified bot intents, private SQL and assets, atomic durable state/receipt/outbox and serialized protected response release. The [architecture interaction view](../architecture.md#interaction-architecture-gb-t00102t1) explains flows and handoffs. The canonical contract retains control of exact shapes, ordering and defaults.

| Alternative | Assessment |
| --- | --- |
| Server-authoritative bounded intent | Selected: supports per-command tenant and policy fences, durable receipts and controlled recovery. Requires verified identity freshness, durable transactions and release fencing. |
| Browser authority or full-scene last-write-wins | Rejected: client assertions cannot enforce tenant/revocation boundaries and scene replacement can erase concurrent accepted edits; contradicts ADR 0001. |
| CRDT or OT as authority | Not selected as an architecture substitute: convergence alone does not supply current authorization, atomic receipts or read revocation. A future reviewed implementation may use a compatible algorithm behind the same authority and contract. |
| In-memory authority or acknowledgments | Rejected: process loss cannot establish durable acceptance or resolve lost ACKs. |
| Public database or direct public assets | Rejected: bypasses scoped policy and release-time read revocation, including queued chunks. |

## Consequences and validation

All transports use the shared command boundary; read-only historical receipt return is distinct from new write authority. Committed writes survive denied ACK release; restore preserves receipts without replaying old operations. These choices require T1/T2 identity and policy evidence, T4/T5 atomicity and recovery, T7 honest client states, T8 transport integration and T9 independent security review. [Declarative interaction scenarios](../specifications/fixtures/GB-T0-01-02-interactions.json) identify review obligations, not executed product behavior. T10–T13 must verify real platform, operations and release gates; no runtime or production claim follows from this ADR.
