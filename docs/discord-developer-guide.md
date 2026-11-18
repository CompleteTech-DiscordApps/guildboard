# Discord developer guide

<a id="discord-runtime-evidence"></a>
This setup guide records the planned Guildboard integration for
[GB-T13.01.02.T1 (#427)](https://github.com/CompleteTech-DiscordApps/guildboard/issues/427).
Public Discord guidance was checked on 2026-11-17 America/New_York.
The repository provides architecture and configuration foundations. It has no
implemented Discord launch, bot installation or published Guildboard HTTP/WSS
contract to exercise. Use the local checks below for reproducible evidence
while the [T1 identity](workstreams/T1.md), [T8 transports](workstreams/T8.md)
and [T10 deployment](workstreams/T10.md) workstreams resolve the runtime setup.

## Claim status and handoff

Accountable expertise: Identity & Discord and transport owners; client and
security consumers review the affected scope. Audience: contributors. The
[claim register](evidence/GB-T13-01-02-T1-guide-claims.json) pins each explicit
anchor to exact guide bytes under the [T13 contract](specifications/GB-T13-S1-documentation-release-contract.md#guide-ownership-and-claims).

| Claim anchor | Status | Next validating owner and scope |
| --- | --- | --- |
| [discord-runtime-evidence](#discord-runtime-evidence) | unresolved | GB-T13.01.02.V1 [#428](https://github.com/CompleteTech-DiscordApps/guildboard/issues/428): real install, launch, clients and proxy evidence with T1/T8/T10 owners. |
| [discord-registration-mappings](#discord-registration-mappings) | planned | T1/T10: reviewed application, redirect and mapping decisions. |
| [discord-scopes-installation](#discord-scopes-installation) | planned | T1/T8: least-privilege scopes, installation and verified interactions. |
| [discord-sdk-lifecycle](#discord-sdk-lifecycle) | planned | T1: runtime adoption, lifecycle and credential/session handling. |
| [discord-http-wss-contract](#discord-http-wss-contract) | planned | T1/T8: published schemas, interface versions and compatibility. |
| [discord-verification-handoff](#discord-verification-handoff) | unresolved | GB-T13.01.02.V1 #428: every positive/failure scenario and affected scope before D1/G3 handoff. |

The dated source review, SDK archive/helper experiment and configuration
checks below retain their original scope. Local helper execution and pure
parser tests do not verify integrated Guildboard services, Discord clients
or GoDaddy ingress. This handoff adds no new runtime or platform result.

<a id="discord-registration-mappings"></a>
## Application registration and mapping decisions

1. For an authorized test environment, create a team-owned development
   application in the Developer Portal and record its owner, installation
   contexts and intended launch surfaces. Use a separate production
   application and credentials. Guild installation is the candidate for
   guild-owned boards and moderation. User installation and DM/group DM
   launch support require separate product decisions. Record the application
   ID as a decimal string for the SDK and the server's `DISCORD_CLIENT_ID`.
   If using HTTP interactions, obtain the application's public verification
   key from General Information. [Discord Activity setup][activity] ·
   [Discord bot setup][bot]
2. Under OAuth2 → Redirects, use the entry required by the reviewed OAuth
   flow. Discord's SDK-only tutorial requires a Portal entry and uses a
   placeholder because the SDK handles the return to the iframe. If a
   separate browser redirect flow is approved, register the exact trusted
   callback for that environment. The Guildboard redirect, transaction
   binding and applicable PKCE behavior remain T1 decisions.
   [Discord Activity setup][activity] · [Discord OAuth2][oauth]
3. Under Activities → URL Mappings, map the Activity root and only the
   required API or WSS prefixes. Targets are hosts or directories with no
   scheme. Place more specific prefixes before their parent. Then enable
   the Activity and confirm the intended entry point and platform settings
   before testing a launch. [Discord mapping guide][local] ·
   [Discord Activity setup][activity]

For a mapping review, the following placeholders show how the UI, HTTPS
requests and WSS upgrades can share one public ingress. The examples reserve
no Guildboard routes. Confirm the actual prefixes, forwarded path and
credentials on the approved target.

| Portal prefix in evaluation order | Illustrative target | What the verifier checks |
| --- | --- | --- |
| `/api` | `gateway.example.test/api` | An iframe-relative HTTPS request reaches only the intended backend handler. |
| `/ws` | `gateway.example.test/ws` | A WSS upgrade on the Activity proxy origin reaches the intended socket handler. |
| `/` | `activity.example.test` | The iframe loads the Activity shell and scoped static assets. |

Prefer iframe-relative HTTP requests. Use the mapped Activity origin for WSS.
The pinned URL helper can rewrite lookalike hosts and URLs containing a
target in the path or query. Check parsed origins against an explicit
allowlist before attaching credentials. Verify CSP, exact origin,
forwarded-header trust, cookie attributes and client
acceptance, redirects, proxy cache behavior, upgrade handling and idle timeouts.
Use GoDaddy Linux VPS with Nginx HTTPS/WSS as the production target. SQL and
persistent board assets stay private behind the server. Preserve the accepted
read-authorization boundary for every protected asset delivery. [Discord
networking][network] · [Architecture](architecture.md#interaction-architecture-gb-t00102t1)

<a id="discord-scopes-installation"></a>
## Scopes and bot installation

| Permission layer | Candidate and decision |
| --- | --- |
| Activity user OAuth | Use `identify` for the current user's identity. Consider `guilds.members.read` only if T1 selects the current-user membership endpoint for the target guild. Request `guilds` only for a demonstrated need to list the user's guilds. A guild listing is insufficient for role, channel access or launch provenance. Omit unrelated scopes such as `email`, `connections` and `guilds.join`. [Discord OAuth2][oauth] |
| Guild installation | Use `applications.commands` for commands. Add `bot` when a reviewed bot-user operation requires it. Discord includes `applications.commands` with `bot`. Keep the Guild Install permission bitfield at zero until an approved operation needs a specific permission. `ADMINISTRATOR` and broad role/message management are outside the planned default. [Discord bot setup][bot] · [Discord command authorization][commands] |
| Gateway intents and command defaults | Review the event and field requirements separately from install permissions. Leave privileged intents off until a specific event or field requires one and any required approval is established. Set command visibility/default permissions for the approved guild contexts. Guildboard still checks the actor, tenant and current policy on every action. [Discord Gateway][gateway] · [Discord commands][commands] |

After the install manifest has an app, target guild, contexts, approved scopes
and permission bits, use the Portal's Installation settings and Discord
Provided Link for the controlled guild installation. A member with
`MANAGE_GUILD` authorizes Guild Install. Review the prompt before accepting
and read back the installed permissions, contexts and command list. Exercise
guild-scoped registration for development slash commands before any global
rollout. The Activity's primary entry-point command has separate global
registration rules. T1/T8 still own the approved command set and whether
interaction delivery uses Gateway or an HTTP endpoint. [Discord bot setup][bot] ·
[Discord commands][commands]

If HTTP delivery is chosen, configure the Portal's Interactions Endpoint URL
only after the endpoint verifies the Ed25519 signature over the timestamp and
unaltered body and handles signed PING/PONG. Reject invalid signatures with
HTTP 401 and apply the reviewed freshness/replay rules before dispatch.
Verified interaction provenance is one input to Guildboard's policy check.
The bot uses the same tenant-scoped command service as the Activity.
[Discord interactions][interactions] ·
[Server authority](specifications/GB-T0-S1-system-contract.md#3-identity-and-authorization-invariant)

<a id="discord-sdk-lifecycle"></a>
## Embedded App SDK lifecycle and credentials

The checked research pin is `@discord/embedded-app-sdk` **2.5.0**. The
[archive and helper receipt](research/t1-sdk-evidence.json) records its integrity
and selected declarations. The [dated source assessment](research/t1-current-source-assessment-2026-11-16.json)
records the npm observation and unresolved provider/client checks. This is a
research pin. Runtime adoption and supported client versions remain open.

1. Instantiate the SDK with the public application ID in the Activity iframe.
   Await `ready()` before calling `commands.authorize`. Handle timeout, SDK
   command errors, closure and unsupported context without issuing a
   Guildboard session. [Discord SDK reference][sdk]
2. Request the reviewed scopes, send the authorization code to the
   Guildboard backend for one-time exchange, and verify user and
   guild/channel evidence on the server. Bind the exchange to the reviewed
   transaction and apply exact redirect, state, replay and applicable PKCE
   controls. The SDK request accepts optional state and an S256 challenge,
   while its documented response exposes only the code. Verify actual
   transaction binding and verifier enforcement before relying on them.
   Client guild/channel/instance values are context hints. [Discord SDK
   reference][sdk] · [Discord OAuth2][oauth] ·
   [T1 research](research/t1-discord-feasibility.md)
3. If the reviewed flow calls `commands.authenticate`, provide the user access
   token to the iframe only for that SDK step, keep it in memory and avoid
   persistent browser storage. Establish the separate Guildboard session from
   verified server-side evidence. For expiry, sleep, reconnect, logout or a
   context switch, stop protected work until session and scope are revalidated.
   End stale subscriptions and clean up timers and sockets when the Activity
   closes. Deny access when required provenance or freshness is unavailable.
   [Discord SDK reference][sdk] · [T1 identity](workstreams/T1.md)

Keep the OAuth client secret, bot token, Discord refresh token, session
signing secret and database credentials in trusted server-side secret storage.
Keep codes, tokens, cookies and board contents out of URLs, logs, telemetry,
source, images and review artifacts. Rotate exposed credentials and follow
the [private reporting policy](../SECURITY.md). The
[five-key configuration parser](../packages/config/README.md) validates the
public ID as a decimal string and returns names-only failure diagnostics.
Service startup wiring and Discord credential configuration still need their
runtime contracts. Never log a successful parser result.

<a id="discord-http-wss-contract"></a>
## Planned OpenAPI and WebSocket contract

Discord's [API version table][rest] lists REST **v10** as available. Pin
`/api/v10` when designing Guildboard calls to applicable Discord REST
resources. Discord OAuth token exchange follows the provider's documented
form-encoded grant. Discord REST v10 and SDK 2.5.0 are upstream versions.
The [accepted system design](workstreams/T0.md#deliverable-disposition)
describes Guildboard logical envelope
`version: 1`. The OpenAPI dialect, HTTP route/version prefix, authentication
binding, WS path and subprotocol, executable schemas and supported
compatibility window remain T1/T8 implementation decisions. There is no
published Guildboard OpenAPI artifact or supported WSS wire version.
[Discord OAuth2][oauth] · [System contract §4](specifications/GB-T0-S1-system-contract.md#4-versioned-command-receipt-and-error-shapes)

| Planned surface | What T8 must specify and verify |
| --- | --- |
| HTTP/OpenAPI | Generate the description from strict shared schemas for session/auth, scoped board and guild operations, moderation, imports/exports and assets. Publish the version and compatibility rules, request and response schemas, input limits and safe request-correlated errors. Reject malformed or unsupported versions before side effects. |
| WSS | Validate origin and session at upgrade, authorize scoped joins and each action, and recheck read authority at delivery. Define versioned join/recovery, durable command/receipt/event and ephemeral presence messages, encoded bounds, queue limits and reconnect behavior. Preserve server revisions, idempotency, lineage and commit-before-ACK. |
| Errors | Use bounded, safe rejections with a request ID. The logical design maps unauthenticated requests to 401, unknown and foreign resources to the same 404, throttling to 429 and unavailable dependencies to 503. WSS uses the same logical error codes. A lost ACK requires reconciliation under current read authorization. Rejection and transport failure must never expose a token, raw input or another tenant's data. |

[System contract §§3–6](specifications/GB-T0-S1-system-contract.md#3-identity-and-authorization-invariant) ·
[T8 scope](workstreams/T8.md#api-compatibility)

<a id="discord-verification-handoff"></a>
## Evidence and independent verification

From the repository root, with the project's Node 24 toolchain and Python
available, reproduce the bounded checks using the reviewed public SDK archive.
The probe verifies the pin before running the isolated URL helper. It exercises
synthetic paths and WSS URLs with no Discord account or service. For an offline
run, replace `--download` with `--archive /path/to/cached/sdk.tgz`.

```sh
python3 scripts/research/t1-sdk-probe.py --download --output /tmp/guildboard-sdk-evidence.json
npm ci --ignore-scripts
npm run test:config
python3 scripts/github-bootstrap/validate.py
git diff --check
```

| Scenario | Available evidence and remaining work |
| --- | --- |
| Registration and least-privilege installation | Review the owner, redirect, scopes, contexts, minimal permission bits and installer against the official sources above. Independently verify the Portal settings, actual grant and a missing-permission denial in a controlled guild. Record unsupported contexts and verify that a second guild's identifiers never grant access. |
| SDK pin and mappings | The historical receipt records eight actual helper tests. The expanded suite includes four additional characterization cases. Verify real iframe launch, prefix order, HTTPS/WSS, CSP, cookies, reconnect and desktop/browser and each claimed iOS/Android client version on the approved mapping target. [Pinned experiment](research/t1-discord-feasibility.md#reproducible-local-experiment) |
| Invalid configuration and leaked values | The config tests exercise malformed and missing fields and names-only diagnostics. Verify runtime exit before bind on invalid config and redaction on all service, proxy and client logging paths once wiring exists. [Configuration acceptance](evidence/GB-T0-03-02-V1-config-acceptance.json) |
| Missing or unavailable prerequisites | Withhold test-app or guild access, membership evidence or proxy reachability in applicable cases. Verify explicit blocked or denied outcomes, no privilege widening, and no unauthorized durable or broadcast effects. Retain the missing prerequisite and the reproduction conditions. |
| Interruption and contract parity | Interrupt authorization, installation or a WSS command before completion. Confirm no partial session or unauthorized effect, reconcile the actual installation state before retrying, and check that a lost ACK never duplicates a committed operation. Compare published OpenAPI and WSS schemas to the running services, including unsupported versions, revocation during an open socket, and cross-guild lookups. |

[Independent verification #428](https://github.com/CompleteTech-DiscordApps/guildboard/issues/428)
must execute the positive and failure scenarios and independently check every
documented scope clause, including invalid configuration, unavailable
prerequisites and interrupted execution. Retain executable scenarios, exact
tested revision and environment, client and interface versions, raw results
with secrets removed, failures and defects. Record commands, applicability and
limitations in [T13](workstreams/T13.md). Live verification requires an
authorized test application and account, controlled guilds and roles, approved
HTTPS/WSS ingress, implemented versioned services and the claimed client builds.
Any Discord or GoDaddy integration pass requires dated evidence from the real
environment. Fixtures provide local evidence only. #428 supplies its
verification record to [guide integration #450](https://github.com/CompleteTech-DiscordApps/guildboard/issues/450)
and [stable release gate #472](https://github.com/CompleteTech-DiscordApps/guildboard/issues/472).

[activity]: https://docs.discord.com/developers/activities/building-an-activity
[bot]: https://docs.discord.com/developers/quick-start/getting-started
[oauth]: https://docs.discord.com/developers/topics/oauth2
[local]: https://docs.discord.com/developers/activities/development-guides/local-development
[network]: https://docs.discord.com/developers/activities/development-guides/networking
[commands]: https://docs.discord.com/developers/interactions/application-commands
[gateway]: https://docs.discord.com/developers/events/gateway
[interactions]: https://docs.discord.com/developers/interactions/overview
[sdk]: https://docs.discord.com/developers/developer-tools/embedded-app-sdk
[rest]: https://docs.discord.com/developers/reference#api-versioning
