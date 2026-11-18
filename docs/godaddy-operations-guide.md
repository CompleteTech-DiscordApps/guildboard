# GoDaddy deployment and troubleshooting guide

**Status: planned procedure.** The mandatory production target is a GoDaddy
Linux VPS with Nginx HTTPS/WSS, private SQL and persistent private assets.
The [repository foundation](../README.md#foundation-status) has a workspace
build and pure configuration parser. Activity, API and bot entry points,
production Nginx and service definitions, migration tooling and deployable
Guildboard artifacts still require implementation and verification. Record
documentation work in [#431](https://github.com/CompleteTech-DiscordApps/guildboard/issues/431)
and execute the acceptance procedure under
[#432](https://github.com/CompleteTech-DiscordApps/guildboard/issues/432).
See the [T10 infrastructure](workstreams/T10.md), [T11 operations](workstreams/T11.md),
[system contract](specifications/GB-T0-S1-system-contract.md) and
[T13 release contract](specifications/GB-T13-S1-documentation-release-contract.md).

The provider references below were checked read-only on 2026-11-17.
They describe published behavior. Account availability, compatibility, capacity,
networking, recovery and release approval require their own evidence.
All operator commands in this guide are illustrative and unexecuted. Fill in
environment-specific values in the restricted change record and run checks
only under approved staging or production authority.

## Preflight and stage ownership

| Responsible role | Required inputs before deployment |
| --- | --- |
| Hosting owner and platform operator | Confirm the actual GoDaddy account's Linux image, support lifecycle, management model, resource and storage limits, IP assignment, ingress policy, console rescue and backup options. Record OS and supported package versions for Node, Nginx and the selected database plus patch ownership. Use the repository's Node 24 engine constraint when checking candidates. Size CPU, memory, disk, inodes, I/O, and bandwidth against measured staging concurrency, asset growth, backup and restore headroom. [GoDaddy VPS documentation](https://www.godaddy.com/hosting/vps-hosting) |
| Platform operator | Verify the SSH host key through a trusted channel. Confirm key-based access, a named administrator with scoped elevation, a second authorized session and console recovery before tightening SSH or firewall rules. Restrict SSH to approved administrative access. Permit public HTTPS and HTTP as needed for redirect or ACME. Check provider and host firewall rules for both address families. [GoDaddy SSH guidance](https://www.godaddy.com/help/connect-to-my-server-with-ssh-secure-shell-4943) |
| DNS and Discord application owners | Confirm authoritative DNS rights and the approved hostname, certificate challenge path, Developer Portal application rights and staging guild/client access. Record the intended DNS and Activity mappings and their previous values in the restricted change record. |
| Release and database operators | Bring the immutable artifact digest and source SHA, supported service supervisor configuration, compatibility matrix, migration plan, verified rollback artifact, separate staging credentials/data, and a demonstrated recovery path. Assign release decision, backup custodian, incident response and security escalation ownership. |

Missing rights, unsupported versions, unavailable monitoring or backup
verification, and insufficient measured headroom block rollout. Keep staging
separate from production by hostname, Discord application and credentials, SQL
and asset storage. Prove the full sequence on staging before requesting a
production change window. The [infrastructure scaffold](../infra/godaddy/README.md)
leaves service supervisor selection to T10.

## DNS, HTTPS and Activity WSS

1. Publish the approved A record at the authoritative DNS provider. Publish an
   AAAA record only when the IPv6 ingress, TLS, and firewall path are verified.
   Compare authoritative answers, independent recursive answers and expected
   addresses; allow for cached TTLs before cutover. Manage the records in GoDaddy
   when GoDaddy hosts the authoritative zone. Save the prior record values and
   TTLs. [GoDaddy DNS guidance](https://www.godaddy.com/help/manage-dns-records-680)
2. Obtain a trusted certificate for the origin hostname and serve the full
   chain via Nginx. HTTP-01 requires reachable port 80 and the challenge route.
   DNS-01 requires publishing the challenge TXT record at the authoritative
   `_acme-challenge.<domain>` destination. Publish it directly or use CNAME or
   NS delegation. Use narrowly scoped credentials for automation. Redirect
   other approved HTTP traffic to HTTPS.
   Schedule renewal and external expiry alerts; after renewal validate the config
   and reload Nginx, then verify the externally served certificate and chain.
   Exercise renewal in staging and check the actual reload hook separately.
   [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/)
   [Certbot renewal guide](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)
3. Bind upstream application services privately. Confirm Nginx routing for the
   Activity, API and socket paths in the candidate contract. On the socket
   upstream use HTTP/1.1 and explicitly forward the Upgrade and Connection
   headers. Set bounded handshake, read, and idle windows and align heartbeat
   intervals with measured behavior through Nginx and Discord. Limit request
   bodies and connection pressure at ingress and enforce authenticated rate,
   frame and queue budgets in the application. Trust forwarded metadata only
   through the configured ingress boundary. [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html)
4. Use approved Discord Activity URL Mappings for the app, API and WSS paths.
   Validate the Activity's proxy hostname, iframe content security policy,
   origin allowlists and session behavior in supported Discord clients.
   Verify upgrade, authenticated room join, idle survival, forced disconnect
   and reconnect through the mapped proxy as well as directly at the GoDaddy
   origin with an approved test client. Require continuing authorization on
   socket activity, including revocation while a connection is open. An HTTP
   101 alone establishes transport upgrade only. [Discord Activity networking](https://docs.discord.com/developers/activities/development-guides/networking)

Illustrative diagnostics for an approved environment. Replace
`guildboard.example` with the authorized host before use. The DNS and TLS
checks run from an external verifier. Listener and Nginx checks run on the VPS.

```sh
dig guildboard.example A
dig guildboard.example AAAA
openssl s_client -connect guildboard.example:443 -servername guildboard.example \
  -verify_hostname guildboard.example -verify_return_error -brief </dev/null
sudo ss -lntp
sudo nginx -t
```

Repeat TLS checks over each published address family, corroborate local
listener scope with authorized external reachability checks, and verify
HTTP redirect behavior and mapped WSS separately.

## Private SQL, assets and secrets

- Use a local socket, loopback or a restricted private database interface.
  Verify SQL and service ports are inaccessible from public ingress over IPv4
  and IPv6. Grant runtime identities only required database privileges. Use a
  separate, temporary migration role for DDL and separate backup and recovery
  access. ADR 0004 selects MySQL/InnoDB for the first experiment. Review the
  exact engine and tool versions before selecting backup or migration
  procedures. [Database experiment decision](adr/0004-editor-and-database-selection.md)
- Place SQL and asset data on persistent private storage outside the release
  artifact and container writable layer. Check mounts, ownership and space
  before startup and readiness. Fail closed if a required volume is missing,
  so startup cannot create empty replacement data on the root disk. Keep
  assets behind server-side tenant authorization. Verify state and asset
  retrieval across restarts and deploys.
- Inject secrets through the selected supervisor's protected secret files
  or approved runtime environment. Use separate service identities and
  access per environment. Keep secrets outside Git, images and deploy logs.
  Follow the [configuration contract](../planning/configuration-contract.md)
  and preserve names-only `CONFIG_INVALID` diagnostics. Verify a future service
  entry point exits before binding on invalid configuration. Coordinate
  rotation with database and Discord owners, plan session invalidation where
  applicable, and remove old credentials after authorized validation. Follow
  [private security reporting](../SECURITY.md) for suspected exposure.

## Staged release and migrations

1. Verify artifact identity and compatibility with the running build, protocol,
   SQL migration state and asset layout. Hold a single release lock and gate
   ingress on readiness. Define liveness separately so a dependency outage
   does not trigger a restart loop. Record the previous artifact and config
   identities, migration position, and matching recovery point before rollout.
2. Rehearse against isolated representative data. Use an additive schema
   change when old and new releases must overlap, then run bounded,
   resumable backfills and verify data and migration ledger invariants.
   Defer destructive schema cleanup to a later approved stage after the
   rollback window. Verify behavior when migration is interrupted at each
   durable step. Inspect partial DDL effects using the selected engine's
   semantics before retrying. Never assume every DDL change is transactional.
3. Take and verify the coordinated backup. Quiesce or fence writes whenever
   the approved migration or recovery plan requires a consistent cut. Apply
   the reviewed migration under a single authorized runner and check the
   resulting schema, row and asset invariants before starting the candidate.
   A failed step keeps the release gated until the operator reconciles the
   ledger, schema and data against the reviewed recovery plan.
4. Start the versioned services with scoped users and resource limits. Admit
   traffic only after readiness and authorized external smoke pass. Drain
   old traffic with bounded shutdown and preserve committed receipts across
   reconnects. Check private state, valid and denied role actions, and
   application, proxy and migration telemetry before broadening traffic.
   Stop rollout if a smoke check, error budget or integrity check fails.

## Backups, recovery and rollback

- Capture a consistent SQL recovery point together with required log ranges,
  matching private assets and their hashes, and the deployment and schema
  identifiers. Align the asset manifest with the SQL recovery boundary and
  retain any keys needed for decryption under separate access control.
  Encrypt and retain copies outside the VPS failure domain. Track recovery
  point age, upload integrity and retention under the approved policy.
  Provider snapshots can supplement the coordinated backups.
- Restore into an isolated clean environment with no production write access.
  Verify backup digests and key access, restore the base and replay approved
  logs to the selected cut, restore matching assets, and check migrations,
  revisions, durable receipts, tenant authorization and asset hashes. For
  the recovery point measurement, use fault time minus the original durable
  commit time of the latest corroborated pre-fault canary that matches the
  exact restored scope, lineage and cut. Keep the measurement unknown if
  qualifying evidence is unavailable. Compare independent acknowledgment
  and recovery inventories for losses. Measure recovery duration separately
  from declaration through verified service, and compare with approved
  objectives. [Accepted T11 backup and restore requirements](specifications/GB-T11-S1-sre-operations-contract.md#independent-backup-and-restore-acceptance)
- If rollback is required, stop promotion, gate affected writes and retain
  evidence. Use the previous verified artifact and config only if they are
  compatible with the live schema, assets and protocol. With an incompatible
  or partially applied migration, keep writes fenced and follow the reviewed
  forward repair or isolated restore and cutover plan. Recovery decisions must
  account for acknowledged writes after the selected recovery point. Recheck
  readiness, TLS/WSS/reconnect, authorization and data integrity before
  reopening traffic, and record the selected procedure and outcome.

## Monitoring and failure handling

Assign owners, alert thresholds and response windows using measured staging
baselines and approved objectives. Monitor external HTTPS and certificate
expiry, Discord WSS upgrade and reconnect failures, authorization denials and
traffic saturation, readiness and restarts, SQL health and migration progress,
disk and inode capacity, asset availability, and backup freshness and restore
success. Exercise alert delivery and acknowledgment. Keep structured logs and
metrics free of credentials, session tokens, URLs containing secrets,
unnecessary board content and unnecessary user identifiers.

| Symptom | Check and response |
| --- | --- |
| Invalid config, missing access, missing volume or unavailable dependency | Stop before binding, admitting traffic or migrating. Record names-only config failures or the missing prerequisite and responsible owner. Correct and rerun preflight. |
| Wrong DNS answer, invalid chain or failed renewal | Compare authoritative and recursive A/AAAA answers, reachability, SNI, challenge configuration and reload status. Hold cutover until external validation passes. Preserve certificate validation throughout troubleshooting. |
| Activity fails to load, socket upgrade fails or idle clients disconnect | Check mapping paths, iframe/origin policy, proxy headers and upstream readiness. Compare timed direct and Discord-path observations to locate the failing hop. Check heartbeat, timeout and drain behavior before changing limits. |
| Migration interrupted, disk pressure or SQL/asset mismatch | Stop promotion and fence writes when integrity is uncertain. Compare durable schema, migration ledger, disk and asset state with the verified recovery point. Choose approved repair or recovery only after identifying committed effects. |
| Backup too old, corrupt or unrestorable | Hold promotion, alert the backup owner and reconcile recovery point, key access, logs and assets. Demonstrate a new isolated restore before relying on the backup. |
| Unauthorized room access, unexpected writes or suspected disclosure | Contain the affected path, preserve restricted evidence and use the private security route. Check for durable and broadcast side effects and tenant scope before resuming. [Security policy](../SECURITY.md) |

## Verification handoff

All scenarios below are pending under
[#432](https://github.com/CompleteTech-DiscordApps/guildboard/issues/432).
Use controlled fixtures and test guilds with explicit authorization. Actual
GoDaddy VPS and Discord client access, compatible artifacts, test roles,
baseline measurements and operational change rights are prerequisites for
real-environment results.

| Verifier | Observable acceptance |
| --- | --- |
| Hosting and DNS operators, with an external verifier | Confirm supported GoDaddy Linux host and measured capacity, intended DNS, chain and renewal rehearsal, private listener reachability boundaries and approved state mounts. Record a blocked run when access or a required prerequisite is absent. |
| Release and database operators | Exercise valid and invalid config, migration interruption and resume or recovery, readiness, failed promotion and compatible or incompatible rollback. Verify no premature traffic or silent state loss. Include restart and mount failure scenarios. |
| Discord application owner and guild test participants | Verify mapped Activity and authenticated WSS on supported clients. An authorized writer produces one durable edit across disconnect/retry; a viewer or wrong-guild participant produces no unauthorized state or broadcast. Exercise moderator or administrator revocation against a connected writer and verify denial without side effects. |
| Backup operator and on-call verifier | Recover a matched SQL and asset cut in isolation, compare receipts and asset hashes, measure RPO/RTO, and record alert and acknowledgment evidence for failure paths. |

Attach the UTC date/time, full source SHA and artifact digest, environment and
versions, test role, exact commands or client actions, expected and actual
results, restricted raw evidence location, sanitized output and defect links
to each scenario record. Record blocked prerequisites and owner. Identify local
fixtures, staged real-platform runs and production verification by their actual
environment. Use the evidence for the [parent capability](https://github.com/CompleteTech-DiscordApps/guildboard/issues/430)
and [production recovery gate](https://github.com/CompleteTech-DiscordApps/guildboard/issues/457).
