# GB-T2.R1: role precedence and revocation research v1

Status: **proposed research; policy choices and real acceptance remain open**.
Refs [#66](https://github.com/CompleteTech-DiscordApps/guildboard/issues/66).
Observed 2026-10-26 UTC (2026-10-25 America/New_York session).
Baseline `c108b552a660e12a3b3998e1e1ad944fbd7a894d`; model version 1,
Python 3.14.3 / Windows PowerShell. No Discord API/client, SDK binary or product
authorization was executed; official documents are rolling observations.

## Scope and consumer inputs

Live issue OPEN/unassigned, no earlier claim or competing focused T2 PR; live
GraphQL native `blockedBy.totalCount=0`. Supervisor triage identifies Ready
research. Claim and isolated worktree preserve native gates and ownership.
Read [T2 scope](../workstreams/T2.md), [architecture proposal](../architecture.md),
SECURITY and CONTRIBUTING. Research does not accept runtime architecture.

Provisional inputs:

- [#481](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481), current
  head `bc28eebe41a3264045fa5d5164d38abbb99ab206`: verified current identity/read
  before receipt/digest lookup; retained historical receipt before active-lineage
  and new-write authorization. Same committed retry does not need current write
  capability or cause another mutation. Content restore preserves old receipts.
  Compared with `19d5f5a`: only T0 handoff documentation changed, not the system
  contract/fixtures. This is a proposal, not an accepted protocol.
- [#489](https://github.com/CompleteTech-DiscordApps/guildboard/pull/489),
  `630beb3bebf3f4727fc9c041e7872b038c106f3f`: atomic generation fencing is an
  assumption in its finite model; it proves neither SQL linearization nor timely
  detection of Discord role changes.
- [#491](https://github.com/CompleteTech-DiscordApps/guildboard/pull/491),
  `8a56a58b0a57cd9e467b90f8a2bb043e63a67547`: server membership and channel
  access do not prove the exact launch or current voice/Activity presence.
  SDK user/guild/channel/admin claims remain untrusted; stronger presence
  authority, OAuth binding and actual client compatibility are unresolved.

## Dated primary evidence and Discord authority distinctions

[Source observations](t2-source-observations.json) record seven successful
bounded HTTPS GETs, exact UTC dates, URLs and response SHA-256 hashes. These
identify inspected responses, not stable vendor revisions, reconstructible
archives or a verified Discord environment. No API freshness SLA was established.

| ID / current official source | Evaluated observation |
| --- | --- |
| D1 [Permissions and role hierarchy](https://docs.discord.com/developers/topics/permissions) | Role position limits certain role/member management operations; it is not general permission precedence. Base role permissions combine, then channel overwrites apply. Administrator bypasses Discord channel overwrites; Manage Guild and Manage Roles are separate permissions. Numeric permission strings require safe big-integer handling. |
| D2 [Guild/member/role resources](https://docs.discord.com/developers/resources/guild) | Member objects supply role IDs; guild roles supply definitions. Single-member lookup and listing are distinct; List Guild Members explicitly requires GUILD_MEMBERS privileged intent. |
| D3 [User member endpoint](https://docs.discord.com/developers/resources/user) | Current-user guild-member lookup requires `guilds.members.read`; `identify` resolves user identity. Guild listing does not supply full channel/board authorization. |
| D4 [Gateway and privileged intents](https://docs.discord.com/developers/events/gateway) | Member-event access and intents require appropriate configuration/approval. Missing Gateway state, disconnect/resume and HTTP restrictions must be handled, not treated as a fresh complete cache. |
| D5 [Gateway member/role events](https://docs.discord.com/developers/events/gateway-events) | Member updates include role IDs; member removal and role updates are invalidation inputs. Delivery does not establish an instantaneous change-to-application bound. |
| D6 [OAuth scopes](https://docs.discord.com/developers/topics/oauth2) | User scopes, bot installation and tokens provide different access. Scope availability or token possession does not grant Guildboard administrative authority. |
| D7 [Discord rate limits](https://docs.discord.com/developers/topics/rate-limits) | Respect per-route/global limits and Retry-After/retry_after. More frequent polling competes with API budgets and does not eliminate upstream visibility delay. |

Do not map Discord role position directly to a single Guildboard role rank.
Role management hierarchy and effective channel permissions answer different
questions. Discord `ADMINISTRATOR` is not a cross-guild or application-policy
bypass. `MANAGE_GUILD` permits Discord guild management, not automatic writing,
role mapping or moderator escalation in Guildboard. `MANAGE_ROLES` governs
Discord role changes; internal Grant the Pen need not mutate Discord roles.
These last application boundaries are recommendations, not Discord guarantees.

## Precedence alternatives and recommendation

| Alternative | Benefit / risk | Research disposition |
| --- | --- | --- |
| Highest Discord role position chooses viewer/writer/moderator/admin | Familiar ordering but confusing; role reorder changes unrelated application power and diverges from Discord permission calculation | Reject as the implicit default. Role IDs map explicitly to app capabilities, not UI names/position. |
| Highest app rank wins; admin/moderator automatically writes everywhere | Simple but merges control-plane authority with content rights and may defeat lockdown, mode and restrictions | Reject implicit bypass. Administrative actions and ordinary edits need separate decisions. |
| Any role/grant allow wins before denials | Convenient temporary access but explicit restrictions/lockdown/freshness can be bypassed | Unsafe negative control in the model; reject this ordering. |
| Explicit capability union after mandatory constraints | Multiple mapped roles compose predictably; every edit still obeys scoped visibility, restriction, mode and current authority | Preferred candidate for #67/T6 review. Viewer baseline means read capability, not an implicit deny; an explicit view-only restriction is a separate stronger fact. |
| Universal viewer-deny role beats every mapped writer role | Easy forced read-only assignment but can accidentally deny all members carrying a baseline viewer mapping | Keep explicit view-only restriction separate; do not infer denial from the label alone. |

Candidate order for **new ordinary content edits**: verified session/tenant/board,
trusted current membership and board visibility; current application generation;
explicit restrictions/view-only, emergency lockdown and T6's mode eligibility;
object/action permission; then capability union and a valid scoped temporary
grant. Unknown actions/capabilities are denied. Check all of this at the actual
commit fence, not only request arrival, UI display or WSS handshake.

Read/receipt reconciliation is a distinct branch: current identity/tenant/read
authority first, then retained receipt and digest check, then active lineage and
new-write checks **only if no committed receipt exists**. A loss of write grant
or lockdown cannot erase an authorized caller's historical commit evidence; read
loss prevents disclosure. Historical acceptance cannot replay old payload into
restored content. The model's receipt booleans stand for trusted lookup results,
not accepted client fields or a complete storage implementation.

| Candidate capability/action | Proposed constraints / decision still needed |
| --- | --- |
| Viewer | Read only if board-visible/current member/session; valid temporary grant may enable an otherwise permitted edit. Explicit view-only restriction wins. |
| Writer | Ordinary content operations only; ownership/object rules, modes, restrictions and lockdown still apply. Cannot self-grant, change mappings or unlock by writing. |
| Moderator | Request approval, scoped grant/revoke and restrictions under an explicit action matrix. Content editing requires an explicit capability/setting; do not infer it from moderation title. No self-approval or escalation to admin. |
| Administrator | Configuration/control actions enumerated separately; not automatically a content writer or lockdown bypass. Emergency unlock is a distinct authorized/audited transition, not a hidden edit exception. |
| Temporary grant | Verified recipient, same guild/board, bounded server-time expiry, explicit issuer action; never implies visibility, membership, mapping admin or unrestricted mode override. |
| Mode/presentation | T6 supplies the accepted mode predicate. Presenter/follow status alone grants no write permission. The model uses a boolean predicate and invents no product mode names or final behavior. |
| Restrictions/lockdown | Explicit edit restrictions and lockdown defeat ordinary writer/moderator/grant edit paths. Exact read restriction, retention of control actions and recovery roles require #67/T6/T9 review. |

Bootstrap options: verified guild owner/Administrator eligibility is narrower than
automatically accepting every Manage Guild user. Recommend the narrower initial
eligibility, with an explicit reviewed onboarding/recovery contract; afterwards
use enumerated mapped administration capabilities. Manage Guild delegation may
be an opt-in alternative only after owner review. Do not invent an initial admin,
self-approved escalation exception or platform-owner bypass. The precise
bootstrap and self-affecting mapping change process remains a blocking product
decision for implementation, not something the finite model authorizes.

## Least privilege and evidence acquisition

Resolve `/users/@me` with `identify` and evaluate selected-guild
`/users/@me/guilds/{guild.id}/member` with `guilds.members.read` before assuming
whole-guild listing or privileged intents are needed. Use least-privilege trusted
guild-role/channel data for effective permission calculations. Verify private
channels, member overwrites and thread access separately. Bot access proves the
bot's access, not the user's current access or Activity presence.

Member/role/channel invalidation via Gateway may require appropriate intents and
approval. Compare per-user REST refresh, Gateway-assisted bounded cache, and
strict fetch-before-sensitive-control; do not request Administrator, Manage Roles,
message content, joining guilds, voice read/write or broad member listing solely
to implement internal board grants. No such privilege was requested here. A
server-side token must not be exposed to the iframe or authorization logs.

Cache keys include guild/user and the relevant role/channel/policy dimensions.
Deletion/reordering/mapping changes invalidate affected capability evidence, not
only the user object. Role names are display data, role IDs and trusted scopes
identify mappings. API failures, 401/403/404, member removal, guild unavailability,
Gateway gaps and rejected intents need explicit outcomes. Known loss invalidates
authority; a network error cannot silently extend a previous successful TTL.

## Freshness and revocation guarantees that can be stated honestly

1. **Application revocation**: after a revocation/policy change commits at the
   shared authority fence, no later new edit may commit using the invalidated
   generation. Earlier committed edits remain accepted. The same fence must
   cover all workers, roles, grants, modes, locks, HTTP/bot/socket paths and
   prepared transactions. Broadcast timing and disconnecting a client do not
   establish this invariant. SQL/order/crash evidence is still required.
2. **Discord detection**: an external role/member/channel change occurs before
   the application necessarily learns it. Cache TTL bounds local evidence age;
   it does **not** establish the age/consistency of Discord's returned truth or
   a documented event-delivery SLA. Even fetching on every action has provider
   visibility, network and queue delays. No instantaneous external-revocation
   guarantee is possible from these observations.
3. **Bounded local stale use**: store an expiry based conservatively on request
   start/observation provenance and server time, evaluate it again at commit,
   deny after the fixed deadline and never renew it on failure. Accept no
   unspecified/infinite freshness budget. New observations need their own
   provenance; refresh response arrival alone is not proof of new truth.
4. **Invalidation/refresh race**: fence refresh publication against the generation
   captured before its request; a delayed response must not overwrite a known
   removal or later policy generation. Reconcile overlapping/out-of-order
   requests and role/channel evidence; the provider does not supply the model's
   trusted local ordering automatically. Known invalidation stops privileged
   writes while refresh/reconciliation is incomplete.

Recommended structure: operation-sensitive finite freshness budgets, strict
refresh/revalidation for onboarding/mapping/grant-control actions, bounded
Gateway-assisted cached evidence for ordinary edits, and fail-closed privileged
operations when freshness cannot be established. Bound refresh queues/cache size,
coalesce duplicate lookups, honor 429 deadlines, and cancel expired work. Final
numeric TTLs, clock/skew assumptions, API budget and latency/error targets must
be chosen from real measurements and accepted in #35/#67; no production number
is selected by this research. The model's ten ticks are arbitrary, not seconds.

If an external change occurs at `t_external`, and the application invalidates at
`t_fence`, the external detection interval is `t_fence - t_external` plus any
measurement uncertainty. Only commits after `t_fence` are covered by immediate
application fencing. A finite end-to-end upper bound additionally requires
explicit upstream consistency/delivery and clock assumptions; none is verified.
Report observed distributions and worst observed delays rather than labeling
a local timer or model trace a platform guarantee.

## Executable abuse experiment and limits

[Model](../../scripts/research/t2-policy-model.py) and
[tests](../../tests/research/t2-test-policy-model.py) use trusted abstract facts,
one hypothetical action decision and four abstract effect counters. This is
research code outside runtime packages, not a policy module or accepted API.

```sh
python tests/research/t2-test-policy-model.py -v
python scripts/research/t2-policy-model.py
python scripts/github-bootstrap/validate.py
git diff --check
```

[Deterministic report](t2-policy-model-evidence.json): **15 tests passed**;
2,048 combinations of four role bits and seven boolean policy/freshness choices.
The intentionally unsafe allow-first control admits **1,860** cases across a
hard denial; the candidate admits **zero**. This is finite coverage of this
chosen hypothetical matrix, not a risk frequency, completeness or production
security claim. Tests include valid writes, cross-tenant/board denial despite
forged client admin, viewer/grant distinctions, restriction/lockdown/mode overrides,
moderator escalation/self-approval, expiry boundaries, object/session/member
denials, stale generation, historical-receipt ordering and delayed refresh.

All modeled edit denials preserve revision/receipt/event/outbox counters exactly;
receipt/control decisions also allocate no edit. Real protected denial-audit
metadata is outside the model and may still be recorded by a future system.
Atomicity, trusted facts, time and effect counters are assumptions; no actual SQL,
socket, permission parser, grant persistence, OAuth, Discord API or GoDaddy check
ran. Do not import this research model into application code as an accepted policy.

The external-change trace deliberately accepts an edit while real membership is
removed but the cached observation is still within TTL. At expiry it denies;
once removal is observed it denies. This is the required negative control for
overclaiming external immediacy. The application-revoke trace rejects a prepared
old-generation write without effects; this assumes the fence is atomic, as #489
does. Delayed refresh publication shows why unconditional cache updates are unsafe.

Local validation: all 15 tests passed; the report matched fresh CLI stdout
byte-for-byte (SHA-256
`1826d9f1a64f7672334dce54c47cba81b55d0f771edd465d0dfe230c9db1b757`).
All seven source-response metadata entries validated. Planning validation passed:
471 items, 457 expected native relationships, 600 expected dependencies, zero
errors. Restored the validator's unrelated CRLF-only audit rewrite; final
whitespace validation passed. Research tests run explicitly; hosted workflows
are unchanged. The PR records the exact published/tested SHA and hosted status.

Review follow-up on 2026-10-26 UTC strengthens administrator self-mapping to
require the explicit `control_denied` outcome, alongside a positive control for
an administrator mapping another target. Edit counters alone cannot distinguish
allowed and denied control decisions in this model. A temporary copy outside the
checkout removes only the administrator self-target predicate: all 15 original
tests remain green, but the strengthened selected test fails with
`control_allowed != control_denied`. The unchanged candidate passes all 15 tests.
[Separate regression evidence](t2-self-mapping-regression-2026-10-26.json) records
the mutation, exact base, old/new test hashes and outcomes. Candidate source,
deterministic report bytes and original source-response observations are unchanged;
the earlier evidence is not relabeled as a new run. This validates one regression
test's sensitivity, not production policy or complete mutation coverage.

## Real acceptance and remaining decisions

Authorized config inspection still found only `.env.example` under repo/app/
package config paths. The five recognized Discord client/secret/bot variables
from #491 were absent, checked by boolean presence only. No secrets were
printed/copied, app provisioned, test guild modified or paid resource used.
Registered-app/portal/intents access, controlled two-guild users/roles/channels,
accepted policy/session/SQL contracts and an approved target remain missing.

| #66 clause | Observable research evidence | Real acceptance still required |
| --- | --- | --- |
| Role precedence and explicit abuse | Alternative/capability tables, 2,048 cases and 15 tests | #67/T6 approve role/action/mode/ownership/restriction/bootstrap matrix; implement complete allow/deny/no-side-effect suite |
| Required Discord privileges | D1–D6 and least-privilege acquisition comparison | Real token/scope/intent permissions; owner/Admin/Manage Guild, overwritten channels, private threads, deleted/reordered roles and missing bot access |
| Revocation freshness | Four-part guarantee, expiry/refresh/external-change traces | Measure change-to-observation-to-committed-fence timestamps, clock uncertainty, rate limits, Gateway gap/outage/old refresh behavior; accept numeric budgets |
| Immediate local fence | Provisional #481/#489 ordering plus old-generation no-effects trace | Barrier-controlled multi-worker SQL/HTTP/WSS/bot races, commit-before/after, expiry-in-queue, crash/retry and audit atomicity |
| Tenant/receipt/launch boundaries | Foreign-resource tests, current-read/old-receipt ordering, #491 distinction | Two-guild/object/storage/broadcast authorization and no metadata leaks; independent stronger launch/presence proof if product needs it |
| Versions/primary URLs/alternatives/uncertainty | Seven dated source hashes and model-v1 environment/report | Actual Security & Authorization/consumer review and accepted specification, not author self-certification |

#67 consumes the proposed policy specification; #35 supplies identity/evidence;
T4/T5/T8 own commit/receipt enforcement; T6 owns modes; T9 reviews privilege and
privacy; T10/T12/T13 retain mandatory GoDaddy Linux VPS, real verification and
release gates. Required current-head Copilot/independent Sol MAX, functional/
security/consumer and CODEOWNER reviews, hosted CI, merge and post-merge evidence
remain separate. No acceptance checkbox, native blocker or issue closure changed.
