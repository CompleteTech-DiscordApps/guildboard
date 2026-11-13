# T8 bot installation and administration research

> Proposed research for [#260 / GB-T8.R1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/260),
> observed 2026-10-26 UTC (2026-10-25 America/New_York session).
> No architecture, API, permission matrix or deployment is accepted by this record.

Recommend evaluating guild-installed administration commands over authenticated
HTTP interactions, with a minimal bot only where the accepted membership/freshness
acquisition strategy requires it. All transports must call the same backend
policy and durable command service. Command picker visibility, a valid Discord
signature and the installer's authority each answer different questions; none
alone authorizes a Guildboard mutation. This is a candidate for #261, not a
registered application or a production implementation.

## Evidence and fixed inputs

Base: `c108b552a660e12a3b3998e1e1ad944fbd7a894d`. Live issue/PR/native-graph
inspection found #260 OPEN with zero blockers and no competing T8 PR; #261 OPEN
still depends on #260. Project ownership remains with the orchestrator. These
observations are point-in-time and do not waive specification/review gates.

| Provisional consumer | Exact inspected revision | Boundary carried forward |
| --- | --- | --- |
| [#481 system contract](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481) | `a25082ca0bca1e39610b900e4dd01db056bab4ad` | Current identity/read before scoped receipts; existing readable receipt before active-lineage/new-write checks; atomic state/receipt/outbox/audit before durable success |
| [#492 policy research](https://github.com/CompleteTech-DiscordApps/guildboard/pull/492) | `d27c71960c228fb63a1b732950c5087a71f2e282` | Explicit capabilities, no self-escalation exception; committed local fence differs from delayed external Discord observation; no automatic Administrator/Manage Guild application superuser |
| [#491 Activity research](https://github.com/CompleteTech-DiscordApps/guildboard/pull/491) | `8a56a58b0a57cd9e467b90f8a2bb043e63a67547` | Verified membership/channel access does not itself establish exact launch/current Activity presence; actual SDK/OAuth/client acceptance remains absent |

Current primary sources below were read through official web documentation and
their public responses captured in [dated metadata](t8-source-observations-2026-10-26.json).
The ten SHA-256 values identify fetched response bytes, not immutable Discord
releases or semantic certification. Capture timestamps/ETags/Last-Modified are
observations; generated Last-Modified does not prove a publication date. The
Discord reference is rolling, REST examples use API **v10**, interaction payload
`version` is **1**. No SDK/Discord library is installed by this research. Local
runtime is Node **v24.18.0**; exact OpenSSL/OS and source/test hashes are in
[execution evidence](t8-execution-2026-10-26.json).

| ID and primary source | Relevant fact |
| --- | --- |
| D1 [Application](https://docs.discord.com/developers/resources/application) | Guild installation requires the installer to have Manage Guild. Installation contexts are guild/user; application settings and per-context defaults matter. Activity-instance lookup exposes instance/location/users, but does not validate an arbitrary client claim without authoritative server use. |
| D2 [OAuth2](https://docs.discord.com/developers/topics/oauth2) | `applications.commands` installs commands; `bot` adds a bot. Command registration can use `applications.commands.update` client credentials. Extra user scopes require the user flow; bot-install redirect guild IDs are hints. |
| D3 [Application commands](https://docs.discord.com/developers/interactions/application-commands) | Installation `integration_types` and invocation `contexts` differ. Global commands support explicit guild-only settings; guild commands are guild-specific and update immediately. Default permission string `"0"` excludes ordinary members unless overwritten; Discord admins can invoke all commands. Permission editing needs a user Bearer token with `applications.commands.permissions.update`, Manage Guild and Manage Roles, ability to run the command and manage affected resources. Bot tokens cannot edit these overwrites. |
| D4 [Interaction transport/security](https://docs.discord.com/developers/interactions/overview) | HTTP and Gateway delivery are mutually exclusive for interactions. HTTP requests require Ed25519 validation of timestamp plus original body on every request; failed verification gets 401. Discord sends invalid-signature probes. Signed PING needs PONG. |
| D5 [Interaction objects/responses](https://docs.discord.com/developers/interactions/receiving-and-responding) | Guild invoker is `member`; DM invoker is `user`. `app_permissions` belongs to the app; installation owner can differ from invoker. Initial response deadline is three seconds; followup token validity is 15 minutes. Deferred acknowledgement is available. |
| D6 [Permissions](https://docs.discord.com/developers/topics/permissions) | Bitsets are strings; use BigInt. Administrator bypasses Discord channel overwrites. Manage Guild, Manage Roles and channel permissions are separate. Role hierarchy is not application policy precedence. |
| D7 [Guild/member resources](https://docs.discord.com/developers/resources/guild) | Single-member lookup differs from member enumeration; List Guild Members requires privileged GUILD_MEMBERS. Modifying Discord member roles requires Manage Roles. |
| D8 [Gateway](https://docs.discord.com/developers/events/gateway) | Intents govern event delivery; reconnect/resume can fail. Cache presence cannot be treated as perpetual current authority. |
| N1 [Node v24.18.0 crypto](https://nodejs.org/download/release/v24.18.0/docs/api/crypto.html) | Built-in key generation/import and Ed25519 sign/verify; algorithm argument must be null/undefined for Ed25519. |
| R1 [RFC 8032 §7.1](https://www.rfc-editor.org/rfc/rfc8032#section-7.1) | Independent public Ed25519 known-answer vector used locally; January 2017 informational RFC, not a Discord transport specification. |

## Installation, privileges and registration alternatives

| Candidate | Benefit | Cost / unresolved evidence |
| --- | --- | --- |
| Commands-only guild install (`applications.commands`) + HTTP | No bot token/Gateway required solely for slash ingress; smaller credential surface | Does not supply the bot membership/role/channel acquisition assumed by some provisional consumers. Accept only after T1/T2 choose a complete user-OAuth/freshness strategy. |
| Guild install (`applications.commands`, `bot`), requested bot permissions `"0"`; HTTP ingress, targeted REST | Candidate to evaluate first for a guild-owned board; avoids message-content processing and unnecessary Discord mutation | Zero is a starting least-privilege hypothesis, not proof every required lookup works. Verify exact read endpoints, channels/threads and actual bot visibility; add only demonstrated required bits. |
| Bot plus Gateway membership invalidation | Faster observation where delivered, with explicit gap recovery | Additional connection/intent/operational state; privileged GUILD_MEMBERS availability/approval and event gaps must be verified. Does not create instantaneous revocation. |
| User installation/DM administration | Convenient personal surface | Conflicts with initial guild-admin provenance assumptions. Defer unless product explicitly specifies tenant selection and authority for this surface. |

Propose no Administrator, Manage Guild, Manage Roles, Manage Channels, message
deletion, audit-log, voice Connect/Speak or Message Content/Presence privileges
for ordinary internal board administration. Grant the Pen changes Guildboard
policy, not Discord role membership. Treat View Channel as conditional on proven
channel lookup needs; Send Messages/Embed Links/Attach Files apply only if an
accepted feature needs normal channel posts/files. Do not request Read Message
History merely to receive commands. Actual interaction response and lookup
behavior under permission removals is a required live check, not established here.

For global guild-administration commands, propose explicit
`integration_types:[0]`, `contexts:[0]`; validate matching app settings rather
than relying on changing defaults. Candidate control-command default is
`default_member_permissions:"0"`; compare `"32"` (Manage Guild) only as a
reviewed discoverability choice. Either can hide commands from a mapped
Guildboard admin until appropriate Discord configuration; neither can grant
backend authority. Read/help/request commands may need separate defaults.
Keep Activity primary-entry-point command handling separate from admin slash
commands; a successful launch callback is not a policy-admin capability.

Keep command registration credentials server/operator-only, separate from
interaction verification's public key. Compare bot-token registration against
a narrowly scoped client-credentials token; do not expose either to Activity
JavaScript. First test a specifically authorized development guild, record
command IDs/schema versions and read back definitions before a reviewed global
rollout. Diff a full manifest before any bulk overwrite: it can replace unrelated
command types, including the Activity entry point. Preserve previous definitions
for rollback. No registration or portal change was performed.

Avoid automatic command-permission overwrite management initially: manual
Discord integration settings plus shared backend policy reduce scope. If the
product later requires overwrite editing, its additional user OAuth consent,
token lifecycle, resource authority and rollback become explicit specification
work. Never substitute this UI setting for application role mappings.

## Candidate administration responsibilities

Names below are responsibility labels, not registered command names or accepted
OpenAPI routes. #261 owns schemas, versioning, safe errors and Fastify composition.

| Responsibility / possible slash action | Shared service checks / result |
| --- | --- |
| Board list/select/link; permission inspection | Current scoped read; return only authorized boards/actions; channel default changes require a separate control capability. A link carries a selector, never embedded bearer authority. |
| Lock/unlock | Explicit action capability, current generation and tenant/board checks; audit reason and durable receipt. Emergency unlock needs an accepted distinct recovery policy; no hidden admin edit bypass. |
| Request / scoped grant / revoke | Distinct requester/issuer/recipient checks, grant expiry and membership; no self-approval or mapping escalation. Application revocation commits a new authority fence. |
| Role mappings / guild configuration | Explicit configuration capability, trusted role IDs, safe self-affecting transition rules. Bootstrap/recovery and owner/Manage Guild eligibility remain #67 decisions. |
| Assets/export/import/archive/restore | Use T5 shared scoped services and T2 capability matrix; avoid shell/filesystem paths or raw destructive operations exposed directly through command options. Consider limiting these to the reviewed Activity UI initially. |
| Session/context/receipt/status APIs | T1 session proof plus current scoped read; expose minimal policy generation/status and original readable receipt. No receipt/digest existence leak to former readers. |

All HTTP, WebSocket, slash, component and worker entry points should resolve an
immutable server-derived actor/tenant context and call the same action service.
Do not let a body/header/command option override guild, actor or installation.
Board IDs, channel selectors, role IDs and component `custom_id` values are still
untrusted selectors: resolve them within the authenticated guild and validate
every referenced resource. Command ID/version/type and option schema must be
allowlisted, not routed solely by a display name. Use mention suppression and
safe output encoding; ephemeral replies reduce accidental exposure but still
require current authorization. Tokens, raw bodies, board data and signatures
need not appear in routine audit logs; use safe server correlation and outcome.

## Interaction boundary, freshness and durable ordering

Candidate HTTP order: enforce TLS/proxy limits and bounded original body;
reject malformed/duplicate headers; verify Ed25519 with the configured app public
key over exact timestamp bytes plus raw body; check an accepted clock/replay
policy; only then decode/strictly validate JSON. Reject invalid signatures with
401. A parse/reserialize step changes signed bytes. Production must handle
content encodings/proxy transformations, duplicate JSON keys, streaming limits
and public-key rotation deliberately; the fixture does not implement a server.

An authentic payload supplies Discord-origin context at interaction issuance,
not eternal role authority. Check expected application, supported installation,
invocation surface, invoker and tenant; distinguish `app_permissions` from
`member.permissions`, and installation owner from actor. Resolve channel→guild
and board→guild on the server; verify current membership, mapped roles and
channel access through T1/T2's accepted evidence acquisition. A stale signed
payload or command option cannot refresh role evidence. Known revocation/gaps
must invalidate authority; an API failure must not silently prolong a lease.
There is no demonstrated bound here on Discord change→observation latency.
Once an application authority fence commits, stale prepared writes must fail at
the authoritative commit boundary; signatures do not provide that SQL fence.

Membership/channel access and slash invocation do not prove current Activity
presence. D1's server Activity-instance API is a possible stronger evidence input;
real credentials, instance binding, authorization, races/expiry and client tests
are still needed before accepting an exact-launch/current-presence claim (#35).
Do not invent a signed launch token or reclassify SDK IDs as trusted proof.

Preserve #481's proposed order: current identity/session/tenant/read → scoped
existing operation receipt and canonical digest → if absent, active lineage →
new-write capability/freshness/generation/schema/object checks → atomic state,
revision, receipt, outbox and audit commit → durable success. Same readable
receipt can settle a retry after write loss or restore; it does not replay the
old payload into the restored document. No read means no receipt/digest leak.
No silent receipt expiry is authorized. A slash adapter needs an explicit stable
operation identity/digest mapping; Discord interaction IDs and application
operation IDs are different concepts and must not be globally deduplicated.

Authenticate before PONG or deferral. Respond/defer within the platform deadline,
then perform authoritative work; deferred acknowledgement means pending, not
saved. If commit succeeds but the callback/followup fails, retry/reconcile the
same operation rather than repeat it. An unknown DB outcome is not a safe failure.
Use current read checks before any later sensitive receipt/followup disclosure.
Do not promise exactly-once delivery or discard every retry as an attack.

## Reproducible local experiment and abuse coverage

From the repo root, with Node v24.18.0 and Python 3.14.3:

```powershell
node --test tests/research/t8-test-interaction-experiment.mjs
node scripts/research/t8-interaction-experiment.mjs
python scripts/research/t8-capture-sources.py
python scripts/github-bootstrap/validate.py
git diff --check
```

The first two commands are offline and dependency-free. Source capture performs
only bounded public GETs and prints new metadata; saved original observations
are not silently updated. Test/run output and source hashes are in the execution
evidence. The tested runtime uses actual Node/OpenSSL Ed25519, including an
independent RFC public known-answer vector plus fresh ephemeral in-memory keys.
No private key is serialized/logged. Report outcomes are deterministic despite
new synthetic keys. Fixture windows **300 seconds old / 30 seconds future** and
**4096 bytes** are arbitrary proposed test values, not Discord limits/SLA or
accepted production budgets.

| Abuse / failure | Local observation | Remaining real check |
| --- | --- | --- |
| Tampered body/timestamp/signature; wrong key; JSON reserialization | Real crypto rejects; parse-only negative control accepts semantically valid tampered JSON | Framework raw-body capture, proxy bytes, key config/rotation, invalid-signature Discord probes |
| Missing/malformed/array headers; oversized/invalid UTF-8/JSON; stale/future request | Fixture denies without modeled mutation/audit/receipt changes; exact window edges checked | Raw duplicate header handling and stream limits; clocks/skew and accepted replay budget |
| Authentic DM/user install/missing member/foreign guild/channel/actor/unknown command | Hypothetical provenance allowlist denies without effects | Controlled two-guild installs, role/channel loss, mobile/desktop delivery and real command settings |
| Discord admin/app bits but no application write or stale generation | Hypothetical shared-authority gate denies | Real cross-transport policy and multi-worker transactional races |
| Same-ID retry / same-ID different bytes | One modeled effect/audit; identical retry returns receipt; changed transport body conflicts | Durable canonical operation codec, restart/restore, concurrent delivery, bounded admission and receipts |
| Readable receipt after write loss/retired lineage; no-read receipt lookup | Receipt-first candidate works; write-first negative control wrongly denies; no-read conceals receipt/digest match | SQL/outbox atomicity, no metadata leaks, actual current-read acquisition |

The 19 tests do **not** verify Discord delivery, OAuth, command configuration,
API lookup permissions, live role freshness, registered app ownership, SQL,
outbox durability, production replay protection or real user acceptance. Fixture
authority is supplied booleans; tenant IDs are fixed synthetic allowlists; maps
are unbounded/in-memory; raw transport digest is deliberately conservative and
is not #481's canonical semantic digest. No duplicate-key parser, transport
server, concurrent transaction, recovery, rate limiter or persistent replay store
is implemented. Production needs bounded admission without silent durable
receipt purging; overload must deny/backpressure safely and preserve outcome
reconciliation. The tests are research evidence, not product functionality.

## Acceptance handoff and missing inputs

Presence-only checks of recognized repo/app/package `.env*` configuration found
only `.env.example`; recognized Discord client ID/client secret/bot-token
environment variables were absent. No secret values were read/printed/copied,
app provisioned, command registered, message sent or service purchased. A
registered controlled app/test guild, authorized portal/public-key/token access,
two-guild users/channels/roles, accepted #35/#67/#261 specifications and an
approved GoDaddy Linux VPS test target remain unavailable. No hypothetical
local test is substituted for them.

| #260 acceptance area | Completed locally | Required consumer/real acceptance |
| --- | --- | --- |
| Least privilege and alternatives | D1–D8 dated facts; install/registration/options comparison | T1/T2/T8 choose evidence transport, scopes/intents/permission bits; verify install/remove/reinstall, owner/Admin/Manage Guild and actual endpoint access |
| Slash lifecycle and backend API surface | Responsibility matrix, explicit registration/rollback and common-service proposal | #261 accepted schemas/OpenAPI/WS versions, manifest/readback, command overwrites/context/deprecation behavior and Activity-entry-point coexistence |
| Verification/provenance/denial | Real local crypto plus 19 tests and negative controls | Discord signed PING/invalid probes, delayed/repeated deliveries; cross-guild and stale roles; real HTTP raw-body/proxy handling |
| Authorization/durability | Reconciled exact provisional #481/#492/#491 heads and no-side-effect model | Functional/security/consumer review; barrier-controlled SQL commit/revoke/restore races, read-before-receipt, durable retry, safe Discord failure handling |
| Evidence and gates | Dated response hashes, exact local versions and reproducible commands | Current-head Copilot/independent Sol MAX, actual Security & Authorization/Backend & Bot/consumer and CODEOWNER review; hosted CI, release and real Discord/GoDaddy acceptance remain separate |

#261 remains natively blocked on #260. No issue closure, native dependency,
Project field, accepted architecture or production package is changed here.

## Retained invocation binding follow-up (2026-11-13 UTC)

The original 19-test experiment did not advance both mutable lineage fields
before retrying an old interaction. Review finding 4559104014 exposed a modeled
second effect: transport digest validation passed, but receipt lookup recomputed
an operation key using the new lineage. The focused correction retains the
original operation key with the interaction digest. It preserves authentication,
current read and digest validation before disclosing the retained receipt.

A twentieth regression commits an old invocation, advances both lineage fields,
commits a distinct invocation in the new lineage, and only then retries the old
one. It requires the original receipt and unchanged effect/audit/receipt totals,
including after write loss; tampering, changed transport bytes and read loss
still deny without altering any map or counter. The new test fails against the
prior head and passes after correction. The original dated evidence remains
historical; this adds no SQL, concurrency, durability or real Discord claim.
