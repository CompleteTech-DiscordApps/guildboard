# GB-T1.R1: Discord Activity and identity research v1

Status: **proposed research; live platform acceptance blocked**.
Refs [#34](https://github.com/CompleteTech-DiscordApps/guildboard/issues/34).
Session date: 2026-10-25 America/New_York; exact UTC observation times are recorded
in the evidence files. Baseline `66d8e778d0e3f405d02b23b6002501c56e593515`.
No application registration, credentials, live OAuth request, Developer Portal
change, client session, public tunnel or VPS deployment was performed.

## Scope, prior evidence and feasibility result

Live GraphQL confirmed #34 OPEN with native `blockedBy.totalCount=0`. The
supervisor's dated Project/native snapshot records Ready research / Backlog /
Unblocked; open PR inventory through #490 had no competing focused T1 owner.
The issue claim and publication handoff preserve those gates; research does not
authorize implementing an unresolved architecture.

Read [T1 scope](../workstreams/T1.md), [architecture proposal](../architecture.md),
SECURITY, CONTRIBUTING and draft [#477](https://github.com/CompleteTech-DiscordApps/guildboard/pull/477)
at `47964d5b697aeae70e99403c6b42dfea0ace6816`. #477 identifies SDK **2.5.0**,
its npm integrity and source commit `14264eccbf9e68d5d58c1aadbc7579e003e0dce6`;
this research independently observed npm's `latest` as **2.5.0**, verified the
same artifact and inspected T1-specific fields. This adds local URL-utility
execution, not a second package adoption/licensing decision. It does not execute
the full SDK or supersede #477's browser/platform handoff.

Draft [#481](https://github.com/CompleteTech-DiscordApps/guildboard/pull/481) at
`19d5f5a35511a1edf3a8bd34773fbb4d57546b89` remains provisional. Its server-derived
identity, verified guild/channel access, membership evidence freshness and
per-command authorization fence are preserved. No client-supplied SDK identity,
role, channel or administrator bit becomes authority. T1 must supply evidence
and a reviewed identity specification to T2/T4/T8; there is no accepted runtime
session/permission implementation here.

Recommendation: continue a pinned SDK 2.5.0 Activity integration with explicitly
mapped HTTPS/WSS and server-verified OAuth identity/membership, contingent on the
real-flow gates below. **Do not mark OAuth, authoritative launch context, client
support or GoDaddy compatibility verified from this research.** Published
interfaces are sufficient for a controlled experiment; actual app permissions,
PKCE enforcement, SDK response binding and client transport behavior remain open.

## Current primary sources and versions

[Source observations](t1-source-observations.json) contain 14 dated official
document response hashes plus the npm latest/version/tarball/integrity observation.
Discord pages are rolling documents, not pinned client versions. The first plain
urllib requests failed; named research-agent GETs succeeded, and initial failures
remain in metadata. Response hashes identify retrieved bytes, not platform
acceptance, permanent vendor content or reconstructible archived bodies.

| ID / primary source | Observed fact and implication |
| --- | --- |
| D1 [How Activities work](https://docs.discord.com/developers/activities/how-activities-work) | iframe/SDK postMessage lifecycle; entry-point command or interaction `LAUNCH_ACTIVITY` response (type 12). Wait for ready before authorization; READY does not prove server membership. |
| D2 [Networking](https://docs.discord.com/developers/activities/development-guides/networking) | Proxy/URL mappings, WebSocket support, unsupported WebRTC, untrusted client data, browser network patch side effects and iframe cookie guidance. |
| D3 [Local development and mappings](https://docs.discord.com/developers/activities/development-guides/local-development) | Platform toggles/Developer Activity Shelf; mapping targets omit scheme and point to directories; more specific prefix routes precede shorter ones. Some Discord API/CDN URLs are CSP exceptions. Temporary tunnel mappings need cleanup. |
| D4 [Mobile](https://docs.discord.com/developers/activities/development-guides/mobile) | Web/desktop enabled by default; Web/iOS/Android toggles control launchability. Safe areas and thermal behavior need mobile handling. A toggle is not a tested client support claim. |
| D5 [Production readiness](https://docs.discord.com/developers/activities/development-guides/production-readiness) | Cache busting, rate-limit handling and command backward compatibility; older clients can return INVALID_COMMAND for new commands. |
| D6 [Embedded App SDK reference](https://docs.discord.com/developers/developer-tools/embedded-app-sdk) | AuthorizeRequest includes optional state, code_challenge and S256 method; AuthorizeResponse exposes code. authorize/authenticate are listed for Web/iOS/Android. This is not an end-to-end verifier-enforcement test. |
| D7 [OAuth2](https://docs.discord.com/developers/topics/oauth2) | Server-side code grant, form-encoded token endpoint, redirect state binding and least-privilege scopes; recommends code grant with PKCE for production. Redirect-flow advice must be reconciled with SDK's code-only return. |
| D8 [User resource](https://docs.discord.com/developers/resources/user) | `identify` for current user; `guilds.members.read` for current-user member information in a selected guild. Guild listing and membership detail are distinct. |
| D9 [Guild resource](https://docs.discord.com/developers/resources/guild) | Member role IDs and guild role definitions support server policy evaluation. List Guild Members explicitly needs GUILD_MEMBERS privileged intent; avoid assuming listing is necessary to check one user. |
| D10 [Channel resource](https://docs.discord.com/developers/resources/channel) | Channel/guild association and permission overwrites are relevant server evidence; bot access to a channel does not prove a user's access or active Activity presence. |
| D11 [Permissions](https://docs.discord.com/developers/topics/permissions) | Guild roles and channel overwrites combine; permission values are strings requiring safe big-integer handling. Discord administrator does not bypass Guildboard tenant boundaries. |
| D12 [Gateway intents](https://docs.discord.com/developers/events/gateway) | Member events/listing and privileged intents have distinct access requirements. Portal/verification approval is not implied by having a bot token. |
| D13 [Rate limits](https://docs.discord.com/developers/topics/rate-limits) | Honor route/global limits and 429 Retry-After/retry_after; do not hardcode optimistic request throughput. |
| O1 [IETF OAuth security BCP](https://www.rfc-editor.org/rfc/rfc9700.html) | RFC 9700 / BCP 240, January 2025: transaction binding, code injection/CSRF defenses and PKCE requirements depend on client/flow; exact redirects and minimal token exposure. |

The npm tarball's fixed integrity is
`sha512-FNoe5PbSkoKEbqPubaBmq6tlEMOftMjR3gu55YrdrrKmBfKKM4i9P/Z+Zxl0RZdJcKviBwVcTyYMMPM/aGex/w==`.
The [artifact report](t1-sdk-evidence.json) records archive/declaration hashes,
Node/Python execution context and test output. Source tag, published artifact and
registry latest are separate observations; no reproducible-build, signature or
provenance-attestation verification is claimed. No dependency was installed into
the Guildboard application or adopted into a runtime lockfile.

## Launch, mapping and lifecycle proposal

Developer Portal needs an authorized existing app with Activities enabled, the
required platform toggles and owned URL mappings. Use an explicit root mapping
for the SPA and scoped API/assets/WSS mappings with directory targets. Keep
mapping order/configuration under review; test the actual supported prefix form
at each client, including `/.proxy` behavior shown in current examples. Do not
assume that a local URL rewrite configures the portal, bypasses CSP or proves
the public origin is secure. Mapping targets are deployment inputs, never
arbitrary user-supplied URLs. Production stays on the mandatory GoDaddy Linux VPS.

Prefer explicit mapped same-origin paths. Evaluate `patchUrlMappings` only for
dependencies whose requests cannot be routed explicitly; it changes fetch,
WebSocket and XHR globals and may affect third-party behavior. The executed URL
helper left one unrelated URL unchanged, but that observation does not generalize.
In the pinned 2.5.0 helper, an unescaped, unanchored regular expression derived
from the target host is matched against the whole URL string. Local tests show
rewrites for a lookalike hostname, a subdomain, and unrelated hosts with the
target text in the path or query. **It is not an allowlist or permission filter**.
Test these cases before any global patch adoption; CSP/proxy behavior and backend
authentication must still be tested independently.
Inventory fonts/images/workers/imports/exports and all WSS/HTTP paths, including
their direct public-origin paths, rather than assuming all traffic is protected
by proxy traversal. D3 documents exceptions to the general proxy description.

Initialize once, wait for ready, start bounded authorization, exchange on server,
then authenticate SDK as required. Close/disconnect, denied consent, unsupported
commands, malformed messages, expiry and context changes must leave the UI
unauthenticated or reconnecting without elevated permissions. SDK readiness and
visible UI controls cannot authorize backend routes/sockets. Review logging:
SDK configuration can forward console messages to the host; tokens, codes,
session handles and board content must not be logged even during debugging.

## OAuth, state and PKCE: what is known and what must be proven

The actual 2.5.0 AuthorizeInput declares `client_id`, `scope`, optional
`response_type:'code'`, `state`, `prompt:'none'`, `code_challenge`, and
`code_challenge_method:'S256'`. The response declaration contains **code only**;
it does not promise echoed state, issuer or a signed guild/channel assertion.
These are static observations, not compilation or runtime validation. Do not
invent a `response.state` check or copy an empty tutorial state as a production
CSRF defense. Generic redirect OAuth and SDK postMessage authorization are
related flows with different observable response surfaces.

Recommended experiment: the backend owns a short-lived single-use authorization
transaction and PKCE verifier, binds it to the initiating browser/session and
CSRF/origin policy, and supplies its S256 challenge to SDK authorize. Exchange
the returned code on the server with that transaction's verifier and the exact
required client/redirect parameters. Confirm actual verifier enforcement and
rejection on wrong/missing verifier, code reuse, concurrent redemption, expired
transaction, different browser/session and substituted foreign code. Determine
exact state propagation/binding from real SDK/Discord responses before accepting
the contract. A browser echo of a server nonce alone is not proof that a returned
code belongs to that nonce; provider code binding is essential.

Keep client secret, bot token and refresh tokens server-side. SDK authenticate
may require the user access token in iframe memory, as official examples show;
do not falsely promise that no token enters the client. Minimize scope/lifetime
and avoid persistent browser storage, query strings, logs and exports. Bind
Guildboard sessions to server-resolved user, verified tenant/channel access,
expiry and revocation generation. Reauthorize HTTP/WSS commands after expiry,
membership changes or lockdown, including already-connected sockets.

Cookie alternative: evaluate exact application `discordsays.com` scope with
Discord's SameSite=None/Partitioned guidance plus appropriate Secure/HttpOnly,
CSRF and explicit observed-origin controls. Generic SameSite=Lax/Strict advice
cannot simply replace iframe requirements. In-memory bearer transport avoids
ambient cookies but exposes the bearer to injected scripts. Choose only after
the actual desktop/web/mobile cookie/renewal tests. No transport is accepted here.

## Least-privilege identity and guild/channel evidence

| Need | Candidate server evidence / minimum scope | Limits and required negative cases |
| --- | --- | --- |
| User identity | User token to `/users/@me`, `identify` | Validate token and app/session binding; reject invalid/expired token and client-supplied user substitution. Email scope is unnecessary for the stated identity need. |
| Selected-guild membership/role IDs | User token to `/users/@me/guilds/{guild.id}/member`, `guilds.members.read` | Evaluate this per-user path before requesting broad listing or privileged intents. Returned role IDs need trusted current guild role definitions; member data alone is not channel access. Missing/forbidden/unavailable evidence must not preserve a privileged grant. |
| Guild selection UI | `/users/@me/guilds`, `guilds`, only if actually needed | Basic guild list is not a user's current channel overwrite result or a board permission grant. Do not request solely because a tutorial does. |
| Guild roles/channel metadata | Least-privilege installed bot REST for required role/channel data; exact access validated in controlled guild | Bot visibility is the bot's authority. Compute user's permissions using trusted member roles, guild roles and channel/member overwrites; reject foreign guild/channel IDs and revoked/missing roles. Do not request Administrator/MANAGE_ROLES to read/evaluate policy. |
| Prompt invalidation | Appropriate guild/member/role/channel events plus bounded evidence expiry | Member events may need privileged intent; evaluate need/approval. REST refresh versus cache TTL is a rate/freshness tradeoff. Local policy generation cannot detect an unobserved Discord role change; privileged writes fail closed when freshness expires. |
| Actual launch/active-channel presence | No accepted server-side proof established by this research | `guildId`, `channelId`, SDK permissions/participants and instance IDs are client claims. Membership plus channel access proves neither the exact launch nor current voice/Activity presence. Investigate verified interaction provenance or another documented server authority if the product requires that stronger property; keep it blocked otherwise. |

OAuth scopes, bot install permissions, Gateway intents and Guildboard board/grant
policy are separate authorities. Avoid email, guild join, member modification,
message content, voice read/write and privileged intents unless a reviewed
capability needs them. A user-install or DM/GDM launch may have null guild/channel
context; the pinned SDK declarations explicitly allow null. For the guild-owned
board product, propose a clear unsupported-context result with no board/session
tenant inferred from a cache/default. Do not silently fall back to another guild.

## Client support and real acceptance matrix

The source-supported Activity families are desktop/web, iOS and Android; a per-command
support table or enabled platform toggle does not establish Guildboard support.
No actual Discord, OS, browser, WebView or device versions were tested here.

| Candidate family | Versioned evidence required before claiming support |
| --- | --- |
| Discord desktop | Record OS/client release channel/build, SDK hash and mapping revision. Launch/ready, consent/code/session, WSS, sleep/reconnect, role removal and unsupported-command behavior. |
| Browser-hosted Discord | Record browser/OS/version and privacy/cookie settings for every supported browser. Verify iframe cookies/partitioning, CSP/mapped paths, denied origins and reconnect; do not infer Safari/Firefox support from a local Node test. |
| iOS | Portal enabled; record device/iOS/Discord/WebView context. OAuth/modal/storage behavior, safe areas, keyboard/touch, foreground/background renewal and bounded recovery. |
| Android | Portal enabled; record device/Android/Discord/WebView versions. Same lifecycle/storage/touch checks; thermal event availability varies (D4). |
| Older client/DM/GDM/unsupported context | INVALID_COMMAND, null guild/channel, denied scopes and missing app access produce explicit safe outcomes; no guessed tenant or permission widening. |

Do not publish minimum client versions or production client support until this
matrix has actual evidence. Test mapped HTTPS/WSS on the exact GoDaddy target,
public-origin bypass attempts, URL ordering, certificates/renewal, safe asset
caching, API failures/429 Retry-After, bounded retry/cancellation and log redaction.

## Reproducible local experiment

The [probe](../../scripts/research/t1-sdk-probe.py) verifies fixed archive integrity,
identity and selected declarations without installing package dependencies. It
executes only the reviewed hash-pinned, dependency-free `output/utils/url.mjs`
in a temporary directory via Node's test runner. It never constructs DiscordSDK,
contacts Discord, simulates OAuth or modifies browser globals. This differs from
#477's static inspection and from a mocked full SDK/browser test.

Fetch the fixed public artifact into an automatically cleaned temporary directory
and run from repo root:

```sh
python scripts/research/t1-sdk-probe.py --download --output t1-sdk-evidence-rerun.json
python scripts/github-bootstrap/validate.py
git diff --check
```

For offline use, replace `--download` with `--archive /path/to/cached/sdk.tgz`.
No tarball/vendor code is committed.
The probe rejects a mismatched/oversized artifact before module execution, checks
selected members without generic extraction, and pins the executed module's hash
`0865df06e3742aa4cf7092f95c7a1519c09ddd45126f8af9bf6afaaa3aee7038`.
Windows PowerShell/Python 3.14.3 and Node v24.18.0: all **eight actual helper tests
passed**—HTTPS/query/fragment rewrite, WSS, relative path, target parameter,
one unrelated URL unchanged, and malformed input/target/incomplete-parameter
negative cases. TAP names/results are in the historical artifact report; timings
and dates can vary on rerun. These results do not verify CSP, portal mappings, cookie behavior,
PKCE enforcement, authorization or any live client.

The expanded suite adds four characterization cases for the matching limitations
above. Run the same probe to obtain its 12-test TAP report; the committed
[t1-sdk-evidence.json](t1-sdk-evidence.json) remains the original eight-test
historical run and is not overwritten by the reproduction command.

Local evidence checks confirmed 14 successful official-document observations,
registry/artifact integrity agreement, candidate membership scope literals and
all eight Node tests. Planning validation passed: 471 items, 457 expected native
relationships, 600 expected dependencies, zero errors. The validator's unrelated
CRLF-only audit rewrite was restored; final whitespace validation passed. No
hosted workflow changed. The PR records the exact published/tested commit and
hosted planning result separately from these research observations.

## Blockers, acceptance traceability and handoff

Authorized config inspection found only `.env.example`, no actual root/app/package
`.env*` configuration files, and no nonempty recognized Discord client ID/secret
or bot-token process variables. The exact variables checked were
`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_BOT_TOKEN`,
`GUILDBOARD_DISCORD_CLIENT_ID` and `GUILDBOARD_DISCORD_CLIENT_SECRET`.
Only filenames and boolean presence were examined;
no secrets were printed/copied and no unrelated credential stores were searched.
An authorized registered test app, Developer Portal/team access, approved scopes,
controlled two-guild membership/channel roles, logged-in test clients and an
approved HTTPS/WSS mapping target were not established. Without these inputs,
live tests cannot be safely or truthfully completed. No provisioning or purchase
is performed to manufacture evidence.

| #34 scope | Observable research evidence | Still-open real acceptance |
| --- | --- | --- |
| Launch/lifecycle | D1/D3/D5, dated review and failure plan | Registered-app entry point and interaction launch; ready/close/reconnect on exact clients |
| Proxy/mappings | D2/D3, historical and expanded local pinned-helper tests | Portal/CSP/proxy cookies/HTTPS/WSS and exact GoDaddy origin/mapping behavior |
| OAuth/scopes | D6/D7/O1, actual 2.5.0 declarations and least-scope alternatives | Transaction/state/PKCE binding and error/replay/renewal tests against Discord |
| Guild/channel trust | D8–D12, nullable declarations and authority matrix | Two-guild REST/bot permission/freshness/revocation tests; stronger launch/presence proof if required |
| Desktop/browser/mobile | D4–D6 support observations and explicit versioned matrix | Actual OS/client/browser/device versions and completed positive/negative scenarios |
| Sources/versions/alternatives/uncertainty | 14 official documents, current registry observation, fixed SRI and local report | Discord Integration/security/consumer review; accepted #35 specification and downstream tests |

#35 consumes this proposed identity/platform contract; T2 defines board policy
and freshness/fencing with T4/T5/T8, T7 handles safe client states, T9 reviews
credential/tenant boundaries, and T10/T12/T13 retain real hosting/verification and
release gates. Actual current-head Copilot/independent Sol MAX, functional/security
and CODEOWNER reviews, hosted CI, merge and post-merge evidence remain separate.
No acceptance checkbox, native dependency, runtime implementation or issue closure
is changed by this research.
