# OAuth and session control design review

GB-T9.01.01.T1 ([#296](https://github.com/CompleteTech-DiscordApps/guildboard/issues/296)) ·
Reviewed repository baseline `0d912bc41d829ad716c51ac136b78e9f7f5ff0c7` · Evidence level: offline design review and structural checks.

The accepted [T0 system contract](../specifications/GB-T0-S1-system-contract.md)
and [T9 security and privacy contract](../specifications/GB-T9-S1-security-privacy-contract.md)
set the control requirements. The observable Activity and auth entry points
are scaffold exports. The API entry point exports audit and deletion helpers.
The shared contracts entry point exports a version constant. OAuth exchange,
session authority, HTTP/WSS ingress enforcement and protected release
therefore remain implementation work at this baseline. The walkthrough uses
tracked source and synthetic evidence.
[Activity](../../apps/activity/src/index.ts) · [Auth](../../packages/auth/src/index.ts) ·
[API](../../apps/api/src/index.ts) · [Shared contracts](../../packages/contracts/src/index.ts)

## Control review

| Control | Contract and observable evidence | Required before activation |
| --- | --- | --- |
| Server-side code exchange and replay | T9 B4 requires a short-lived, single-use authorization transaction bound to its initiating context and approved redirect. T1's pinned SDK research reports a code-only response declaration and optional state and PKCE inputs. Provider binding remains unverified. The T9 `auth_transaction` fixture declares one valid redemption and missing, expired, rebound and duplicate outcomes. [T1 research](../research/t1-discord-feasibility.md#oauth-state-and-pkce-what-is-known-and-what-must-be-proven) · [T9 scenarios](../specifications/fixtures/GB-T9-S1-scenarios.json) | T1 must record supported code binding and exact redirects where applicable, trusted launch and membership evidence, minimum scopes, transaction lifetime and failure handling. Acceptance must establish that only one contender can create a session, including across workers and ambiguous exchange outcomes. An expired, unbound, invalid or repeated attempt grants no authority. |
| Session fixation, renewal and termination | T0 §3 defines the internal server session tuple with user, session and generation, verified guild/channel access, expiry and membership evidence version. Request selectors confer no authority. T9 B4 requires renewal by rotation and authority recheck, and revocation must invalidate current authority. T9 `membership`, `commit_order` and `release_order` describe related denial and ordering properties. [T0 contract](../specifications/GB-T0-S1-system-contract.md#3-identity-and-authorization-invariant) · [T9 scenarios](../specifications/fixtures/GB-T9-S1-scenarios.json) | Issue fresh server-controlled session authority at authentication and renewal. A pre-auth handle or superseded generation grants no access. Define expiry, logout, membership invalidation and unavailable evidence behavior. T8 must apply current authority through HTTP and WSS, including reconnect and already-connected clients, and preserve T0 write and release ordering. |
| Origin and CSRF | T9 B2 requires exact accepted browser origins and redirects and session-bound CSRF protection where credentials are ambient. The T9 `ingress` fixture distinguishes origin from authentication and classifies untrusted forwarding. T1's SDK URL helper tests characterize rewriting only. [T9 scenarios](../specifications/fixtures/GB-T9-S1-scenarios.json) · [SDK helper tests](../../tests/research/t1-sdk-url.test.mjs) | If the chosen transport carries ambient credentials, require session-bound CSRF protection on applicable requests and verify the chosen cookie and iframe behavior. If it uses explicit credentials, verify the actual HTTP/WSS credential paths, any ambient fallback, browser origin enforcement and exposure of browser-held credentials. Both designs need exact allowlists, trusted proxy handling and fresh session checks. URL rewriting conveys no ingress authority. |
| Token exposure, secret handling and rotation | T9's data classification limits access to authorization transactions, credentials and sessions and excludes raw tokens from board, audit, evidence, export and general backup data. `parseConfig` enforces the structural `SESSION_SECRET` check and names-only invalid diagnostics. Its success result holds credential material. Ignore rules cover local environment files and permit the example template. The closed audit parser covers one record surface. [Configuration contract](../../planning/configuration-contract.md) · [Config parser](../../packages/config/src/index.ts) · [Ignore rules](../../.gitignore) · [Audit parser](../../apps/api/src/audit-evidence.ts) | Keep secrets out of source and images and provider/client secrets, bot tokens and refresh tokens on the server. If SDK authentication requires a user access token, approve its minimum scope and lifetime and constrain it to the required SDK use in memory. Exclude credentials, codes and session handles from diagnostic and telemetry payloads, application URLs, browser persistence, and exports. Define separate rotation and retirement procedures for provider credentials and session secret material, including multi-worker cutover, expiry, revocation and failed rollover. Successful config diagnostics and audit schema checks provide no runtime redaction or key lifecycle evidence. |

## Synthetic acceptance inputs for #297

The [T9 scenario manifest](../specifications/fixtures/GB-T9-S1-scenarios.json)
is declarative. These expected observations translate it into checks for
a future offline harness with a fake provider, inert references, synthetic
sentinels, controlled ordering and a deterministic clock.

- **Exchange and session issuance** · For a valid bound transaction and fresh
  verified user and tenant evidence, observe one issued generation. For
  malformed, expired, repeated, differently bound or concurrent attempts,
  assert the expected safe denial and no extra session. Unavailable
  authoritative evidence grants no access. Include failure before issuance
  and an interrupted response after issuance.
- **Rotation and termination** · Confirm a new generation becomes authoritative
  after successful login or renewal. Check that pre-auth and superseded
  authority, expiry, logout and revocation produce no new protected reads,
  writes, joins or delivery. Use synthetic queued output to verify both orderings
  of termination against commit and release. An accepted commit ordered first
  stays durable, and termination ordered first suppresses later protected
  output, including ACKs for previously accepted writes.
- **Ingress and scope** · Check allowed origin plus valid authority, disallowed
  origin, missing session, untrusted forwarding and requested cross-guild
  scope using abstract fixture classifications. For an ambient transport, add
  valid and missing or mismatched session-bound CSRF evidence. For explicit
  credentials, verify the chosen upgrade and reconnect design and any ambient
  fallback. Denials must issue no authority or room join, emit no protected
  output and create no accepted board mutation, revision, receipt or outbox
  record. Foreign and unknown resources have the same public result.
- **Credentials and rotation** · Inspect only harness-generated outputs and
  synthetic build/export fixtures for inert sentinels. Check names-only
  configuration failures and credential omission from application URLs,
  logs, telemetry, client bundles, exports and audit/evidence records.
  Verify approved rotation and retirement behavior across simulated workers,
  including an unavailable credential update and a rollback attempt. Retired
  authority stays invalid.

## Handoff and evidence

- **T1 identity and session policy** · [#35](https://github.com/CompleteTech-DiscordApps/guildboard/issues/35)
  owns the reviewed binding mechanism, Discord scopes and provenance, session
  and transaction bounds, renewal and termination, membership freshness and
  outage handling. The [T1 research](../workstreams/T1.md#2026-11-16--research-context-update)
  records the open platform questions.
- **T8 transport and T10 ingress** · [#261](https://github.com/CompleteTech-DiscordApps/guildboard/issues/261)
  owns the reviewed API/WSS contract and middleware. Document the selected session
  transport, exact origins and redirects, CSRF applicability, trusted proxy
  hops, credential handling and T0-compatible errors and write/release fences.
  T10 must provide evidence for the actual Discord proxy and GoDaddy ingress.
  [T8](../workstreams/T8.md) · [T10](../workstreams/T10.md)
- **T9 verification** · [#297](https://github.com/CompleteTech-DiscordApps/guildboard/issues/297)
  still needs implemented adapters, positive and negative acceptance, raw
  results tied to the exact revision and environment, and actual independent
  security review. Authorized platform verification must separately establish
  supported Discord client behavior and the actual GoDaddy HTTPS/WSS and proxy
  boundaries. This review leaves product implementation and verification open.

Offline checks at the baseline used Python 3.14.8 on Linux x86_64.

| Command | Result and evidence |
| --- | --- |
| `python3 -B scripts/github-bootstrap/validate.py` | Passed. Roadmap integrity across 471 planning items. |
| `python3 -B -m unittest discover -s tests/verification -p 'test_t9_security_privacy_contract.py'` | Passed. 14 structural tests of the T9 contract and declarative fixtures. |
| `python3 -B scripts/verification/verify_architecture.py` | Passed. Seven accepted architecture artifact digests matched. |
