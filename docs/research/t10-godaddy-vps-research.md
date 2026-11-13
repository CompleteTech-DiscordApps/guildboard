# GB-T10.R1 — GoDaddy Linux VPS feasibility and bounded sizing research

Proposed research for [#324](https://github.com/CompleteTech-DiscordApps/guildboard/issues/324), observed 2026-10-26 UTC (2026-10-25 America/New_York session). Baseline `c108b552a660e12a3b3998e1e1ad944fbd7a894d`. This is a reviewable decision input, not an accepted specification, purchase, provisioned host or production certification. [#325](https://github.com/CompleteTech-DiscordApps/guildboard/issues/325) remains natively blocked on #324 until its actual Definition of Done.

## Recommendation and evidence boundary

Retain the mandatory **GoDaddy Linux VPS** target. Provisioning should eventually evaluate a self-managed, control-panel-free Linux VPS with Nginx at the public edge, Node services, a private SQL listener and private persistent asset storage. Prefer Ubuntu 24.04 LTS **if its exact image is available in the authorized account/region**; compare Debian 12 or a supported AlmaLinux image if it is not. Public product text establishes OS families, not a verified versioned image catalogue. No account, host, domain, registered Discord app or deployment credentials were supplied through this repository.

Use a 2 vCPU / 4 GB / 100 GB NVMe tier for an initial bounded staging benchmark; compare 4 vCPU / 8 GB / 200 GB for a production candidate. These are proposed starting points, not measured capacity or permission to buy. The 1 vCPU / 2 GB / 40 GB option leaves little room for SQL, application processes and backup staging; a larger tier cannot establish availability or eliminate single-host failure. Managed VPS may be evaluated for staffing needs, while retaining explicit application, backup and security ownership. Managed Node hosting remains optional and unverified; it does not replace the required VPS. Shared hosting and external application hosts are outside this comparison.

## Dated primary evidence and uncertainty

The source identifiers below correspond to `t10-sources.json`. Its fetcher records response hashes/status/date, not semantic attestation or account entitlement. Four GoDaddy pages and MySQL returned HTTP 403 to Python; the official page text was readable through the web research tool. Both observations are retained. Guessed obsolete OS/help URLs were inaccessible and were not used as evidence. Documentation is mutable and generally has no immutable release identifier.

| Primary source | Reviewed result / limit |
| --- | --- |
| [GoDaddy VPS offering](https://www.godaddy.com/hosting/vps-hosting) | Advertises 1/2/4/4 vCPU with 2/4/8/16 GB RAM and 40/100/200/200 GB NVMe standard tiers; broader range reaches 32 cores, 128 GB RAM and 1.5 TB. Lists Ubuntu, Debian, AlmaLinux, root/SSH keys, a dedicated IP, unlimited traffic, seven days of snapshot backups and manual patch ownership. These are vendor assertions, not throughput, IOPS, latency, account or application-uptime measurements. |
| [GoDaddy unsupported systems](https://www.godaddy.com/en-ph/help/unsupported-operating-systems-for-vps-hosting-41852) | States listed EOL systems cannot be newly provisioned, including Ubuntu 20.04. The retrieved current page does not enumerate exact supported Ubuntu/Debian image versions. Do not derive a current catalogue from old example outputs or older localized tables. |
| [GoDaddy SSH](https://www.godaddy.com/en-uk/help/connect-to-my-server-with-ssh-secure-shell-4943), [admin access](https://www.godaddy.com/en/help/enable-root-or-admin-access-to-my-vps-hosting-24737?inapp=true) | SSH defaults to port 22; admin/root is disabled by default and can be enabled in server settings. Entitlement and recovery access must be confirmed before any hardening change. Prefer named sudo users and keys, separate deploy/app identities and tested host-key verification. |
| [GoDaddy ports](https://www.godaddy.com/en-ph/help/common-server-ports-19608), [recovery console](https://www.godaddy.com/en/help/use-the-recovery-console-for-vps-hosting-32064) | Standard service list includes 80/443, 22 and MySQL 3306; listing a port is not proof it is reachable. Recovery documentation calls out port 2224. Obtain account-specific requirements before restricting management traffic; never apply a blanket firewall that silently breaks provider recovery. |
| [Nginx WebSocket](https://nginx.org/en/docs/http/websocket.html), [proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) | Upgrade headers need explicit forwarding; default upstream inactivity closure is 60 seconds. Explicit HTTP/1.1 remains suitable across older/newer releases. Timeout is between reads, not a total session TTL. Version-dependent defaults must not determine the product contract. |
| [Discord networking](https://docs.discord.com/developers/activities/development-guides/networking), [URL mappings](https://docs.discord.com/developers/activities/development-guides/local-development) | Activities use Discord's proxy and portal URL mappings; current networking guide supports WebSockets and excludes WebRTC. External URLs may fail CSP. The rewrite helper modifies fetch/WebSocket/XHR and is not server authorization. Trusted identity requires backend verification. |
| [Docker Ubuntu support](https://docs.docker.com/engine/install/ubuntu/), [firewall behavior](https://docs.docker.com/engine/network/packet-filtering-firewalls/) | Current install documentation includes Ubuntu 22.04/24.04/26.04/26.10. This proves Docker compatibility, not GoDaddy image availability. Published ports can bypass ufw processing; private SQL must have no public publication and external deny probes remain necessary. |
| [Node release policy](https://nodejs.org/en/about/previous-releases) | Current page identifies Node 24/22 as LTS and 26 as Current. Prefer a supported LTS after dependency/runtime checks; exact patch and image digest require release-time selection. Host Node 24.18.0 was observed, not established as the newest patch. |
| [MySQL 8.4 backup policy](https://dev.mysql.com/doc/refman/8.4/en/backup-policy.html) | Consistent transactional backups and retained binary logs support recovery, subject to table/DDL/lock conditions. They do not back up private filesystem assets or establish a measured RPO/RTO. Do not blindly copy destructive log-purge examples. |

No prices are used for the decision; billing term, renewal, tax, region and managed support scope must be confirmed on the authorized purchase screen. Public marketing does not provide a verified network Mbps cap, packet rate, IOPS budget, burst/CPU scheduling guarantee, IPv6 availability, storage expansion semantics or measured application SLA here. Retain these as explicit provider/account questions.

## Candidate topology and alternatives

| Choice | Reason to evaluate | Tradeoff / unresolved acceptance |
| --- | --- | --- |
| Compose on GoDaddy Linux VPS | Versioned images, separate networks/volumes and resource bounds make reproducible promotion practical. Recommend for initial evaluation if supported by selected OS and operator. | Pin digests and Compose/Engine versions; monitor real memory/disk; define restart/readiness/shutdown; protect socket access; verify host/provider firewall and no public SQL. Compose is not high availability. |
| systemd on the same VPS | Fewer container layers, native journald/resource controls and loopback services; useful if operator already maintains host packages. | Package/Node versions drift unless pinned; service users, sandboxing, EnvironmentFile permissions, restart limits and backup paths need a reproducible installer. No systemd unit was installed or exercised here. |
| Managed GoDaddy VPS | Potential support/patch staffing benefit without changing the mandatory target. | Determine responsibility matrix for custom Node/Nginx/SQL, incidents and restore. The generic support label is insufficient. No managed plan was provisioned or assessed. |

The proposed flow is Discord client → Discord Activity proxy → public HTTPS hostname on GoDaddy Nginx → private API/collaboration services → private SQL and private assets. A bot may make outbound Discord API/Gateway connections; it is not a trusted path around backend authorization. A single VPS concentrates failure and disk contention, so graceful denial/reconnect plus off-host recovery are mandatory before release.

Suggested route plan for specification review: Developer Portal `/` → `guildboard.example.invalid`, with `/api`, `/ws` and `/assets` preserved at that same hostname. This is a reserved placeholder, not DNS or a portal mapping. Use relative/proxied URLs from the Activity. Verify exact prefix precedence, query/path encoding and WSS rewrite with registered app/client evidence; do not duplicate a prefix through an accidental trailing-slash `proxy_pass` rewrite.

Nginx should eventually terminate valid public TLS, redirect HTTP where compatible with ACME, enforce a reviewed hostname policy and bounded request/header/connection limits, explicitly forward Upgrade/Connection and overwrite untrusted forwarding headers. `$remote_addr` behind Discord reflects a proxy peer; it is not verified end-user identity. Backend authorization must verify tenant/board/session/permissions for HTTP and socket handshakes and recheck accepted operations; Origin and forwarded IP are insufficient. An application heartbeat, frame/message bounds and reconnect/resync policy require coordinated T1/T4/T11 decisions. Do not apply blanket iframe-blocking headers such as `X-Frame-Options: DENY`; evaluate frame-ancestors/CSP against actual supported Discord clients, OAuth and asset needs.

Keep public exposure to HTTPS and the reviewed HTTP/ACME requirement, with SSH restricted to approved management sources and provider recovery requirements preserved. Bind host SQL to loopback/private interface or an un-published isolated Compose network; do not publish 3306/33060. Treat IPv4 and IPv6 separately. Private assets belong outside the web root and container writable layer; serve only through current authorization or a reviewed bounded access mechanism. `/private-assets/` in this fixture is an explicit denial, not an actual asset implementation. Store production secrets outside source/images, unreadable to unrelated users; deployment credentials must not equal application/SQL administrator credentials. No secret values were read or copied.

## Proposed sizing assumptions, not capacity claims

| Budget | Staging hypothesis | Production benchmark candidate |
| --- | --- | --- |
| Vendor tier | 2 vCPU, 4 GB RAM, 100 GB NVMe | 4 vCPU, 8 GB RAM, 200 GB NVMe |
| RAM hypothesis | OS/edge 0.75 GiB, SQL 1 GiB, API/collaboration/bot 1.25 GiB, remaining margin about 0.7 GiB if advertised RAM is decimal GB | OS/edge 1 GiB, SQL 2 GiB, application services 2 GiB, remaining margin about 2.45 GiB if decimal GB |
| Disk hypothesis | OS/images 12 GiB, SQL 8 GiB, assets 20 GiB, bounded logs 6 GiB, backup staging 8 GiB = 54 GiB; 100 decimal GB ≈93.13 GiB | OS/images 20 GiB, SQL 16 GiB, assets 60 GiB, logs 8 GiB, staging 16 GiB =120 GiB; 200 decimal GB ≈186.26 GiB |
| Synthetic workload for measurement | 20 boards, 50 simultaneous editors, 200 total sockets; each editor 2 operations/s at 512 bytes and mean fanout 10 | Same workload first, then controlled staircase; no promise that either tier sustains it |

Synthetic operation payload egress is `50 × 2 × 512 × 10 = 512,000 bytes/s`, approximately 4.096 Mbps before framing, TLS, retransmission, acknowledgements, snapshots, asset downloads or proxy overhead. A 10 MiB snapshot broadcast to 200 clients is about 2,000 MiB, so operation rate alone cannot size bandwidth. SQL indexes, retained receipts/outbox, binlogs, asset growth and backup IO must be measured on representative boards. RAM budgets are limits to try, not resident-set observations. No CPU utilization or latency result was obtained on either VPS tier.

Propose alerts before disk exceeds 70% and an action gate at 80%; queue/connection/asset size bounds must fail predictably before memory exhaustion. Proposed resize investigation triggers: sustained CPU >70%, memory >75% without useful cache explanation, growing operation queue, or failure of agreed latency/error budgets under representative load. Exact windows/objectives belong to reviewed T11/T12 specifications. Benchmark before increasing concurrency, and retain emergency disk headroom for recovery rather than treating all NVMe capacity as assets.

## Database, assets, backup and delivery compatibility

T5 [PR #490](https://github.com/CompleteTech-DiscordApps/guildboard/pull/490), observed head `5e8a9fe999e0ef6db5509ad4075e324da6c2be79` in its isolated worktree, contains provisional MySQL 8.4.11/MariaDB 11.4.13 experiments. They are useful information about SQL semantics, not an accepted runtime schema, migration or restore guarantee. Select **one** engine/version after T5 review and rerun its actual schema/driver/locking/recovery tests on the chosen OS/image. Do not infer interchangeable SQL, backup formats or upgrade paths from a MySQL-shaped URL. No database was started by this T10 probe.

Persist SQL data and assets on explicit owned durable paths/volumes, with separate environments and no anonymous container-layer persistence. Backup SQL plus asset manifests/blobs under a coordinated recovery boundary, encrypt and verify off-host copies, retain required logs and keys through a reviewed policy, and test a restore into an isolated target. Vendor snapshots are supplemental: consistency across SQL/assets, restore isolation, account failure and actual retained recovery points remain unverified. The staging space budgets above cannot hold an entire uncompressed backup of all proposed live assets/SQL; use verified streaming/incremental off-host delivery and bounded staging, or revise the budget. No off-host backup destination or credentials exist in this deliverable.

Release procedure candidate: protected CI builds a versioned artifact; operator verifies host fingerprint and target identity; serialize deploys; capture validated recovery point; use backward-compatible expand/migrate/contract steps; start candidate privately; verify readiness and read/write/authorization smoke tests; switch traffic; drain sockets with bounded reconnect/resync; retain previous artifact and migration journal. Rollback means a compatible prior application version plus health verification. Destructive schema changes require their own tested recovery plan; do not claim arbitrary automatic down-migration. Application crash recovery must be validated against SQL receipts/outbox and assets, not just `restart: unless-stopped`. No deployment workflow, firewall rule, service unit, DNS record or portal entry changed.

## Historical 2026-10-26 local experiment and results

The original idle-timeout result below was invalidated by review: the old backend
could close independently and mask a missing proxy timeout. Keep it as historical
evidence only. The corrected Linux rerun in the follow-up below supersedes that
idle claim; original non-idle observations retain their original environment scope.

Run from the repository root with Python 3.14.3 and Docker Desktop's existing Linux backend:

```powershell
python scripts/research/t10-nginx-probe.py --output docs/research/t10-nginx-evidence.json
python tests/research/t10-test-nginx-probe.py
python scripts/research/t10-capture-sources.py --output docs/research/t10-sources.json
python scripts/github-bootstrap/validate.py
```

The runner requires the exact two cached image IDs recorded in `t10-nginx-evidence.json` and refuses downloads (`--pull=never`). Observed Nginx **1.31.6**, container Python **3.12.15**, host Python **3.14.3**, host Node **24.18.0**, Docker Engine **29.8.1**, Windows 11 build **26200**. These are measured experiment versions, not approved production pins. Each owned container is nonroot, read-only, cap-drop ALL, no-new-privileges, bounded to 0.5 CPU/128 MiB/64 PIDs and 16 MiB temporary storage. Backend networking is disabled; Nginx shares only its owned network namespace. No ports, host mounts, volumes or external network access. Exact labels are checked before owned cleanup, and absence is read back.

`nginx -t` passed; **12 checks passed**: path/query retention, fixed upstream host, overwritten forged forwarded IP/protocol, private route denial, HTTP 413 for 2 KiB against the fixture's 1 KiB budget, missing Upgrade denial, actual RFC handshake accept value and text frame, idle tunnel closure, bounded idle duration, controlled backend shutdown acknowledgement and subsequent 502. The measured idle close was approximately **2.00 seconds** against a two-second fixture timeout; the report retains the exact value. Tests also deliberately remove the Upgrade header and expose the private route; both unsafe variants are detected. The 1 KiB and two-second values are synthetic stress settings, not production budgets. The toy backend is not a production WebSocket implementation; it sends one text frame and exercises inactivity, not full frame parsing, ping/pong, masking, multi-client fanout, authorization or durability.

Failure history retained: initial bridge-network creation failed because all predefined Docker address pools were subnetted. No existing network was removed or reconfigured; the design moved to `network=none` sharing. Copying into a read-only container failed, so fixtures are streamed into owned tmpfs. Initial Nginx validation detected a default temp directory under a read-only path; all temp paths were moved to the bounded tmpfs. No daemon, VM, distro, unrelated service or existing container was restarted. The final successful report verifies both containers absent.

These tests prove local HTTP/WS proxy behavior with a synthetic backend only. No TLS certificate, ACME renewal, browser/Discord iframe, public DNS, GoDaddy networking, provider firewall, VPS performance, application identity, private SQL boundary, filesystem persistence or backup restore was exercised. No host throughput benchmark or availability/RPO/RTO claim follows from them.

## Acceptance review and handoff

| Requirement | Observable local research result | Remaining acceptance |
| --- | --- | --- |
| VPS sizing/resources | Dated official tier comparison, explicit RAM/disk/traffic arithmetic and uncertainty; no claimed application limit | Authorized account/region tier and image catalogue, actual limits/IOPS/network, real representative load |
| Linux images/admin/network | Family list, EOL rejection, SSH/admin/recovery sources; local real-Nginx behavior and negatives | Exact portal image/kernel/architecture, support scope, restricted management and external v4/v6 firewall evidence |
| HTTPS/WSS/Discord | Mapping/proxy constraints and local WS 101/frame/inactivity/error evidence | Real hostname/certificate/renewal, registered app mappings, supported desktop/web/mobile clients, long-lived WSS and reconnect |
| Private SQL/assets/recovery | Explicit boundaries and T5 provisional handoff, backup/restore plan | Selected engine/runtime schema, no public DB from an external vantage, restart persistence, coherent SQL/assets isolated restore |
| Alternatives/version/date/managed Node | Compose/systemd/managed VPS compared; Node optional/unverified; sources and failures dated | Platform Engineering/security/consumer review; architecture acceptance through native roadmap |

Repo-local inspection found `.env.example` only among root `.env*` files. It is marked planning-only and contains blank credential fields; no live provisioning configuration is established. Other worktrees and machine/account credentials were not searched. T1 [PR #491](https://github.com/CompleteTech-DiscordApps/guildboard/pull/491) at `8a56a58b0a57cd9e467b90f8a2bb043e63a67547` is provisional research and explicitly lacks registered-app/client inputs; its local URL helper checks cannot supply missing Discord acceptance.

Required next inputs are an authorized GoDaddy account/region/instance target, approved hostname/DNS/TLS owner, exact allowed OS/tier, tested access/recovery path, registered Discord app/client matrix, selected SQL contract and private off-host backup target. Obtain them through the existing owner before real-environment work. Required current-head actual GitHub Copilot review, finding disposition, hosted CI, CODEOWNER/security/consumer review and branch protections remain independent gates; quota rejection is a blocker, not a review. No issue, native dependency, Project item or release gate was closed by this research.


## Corrected local Nginx rerun (2026-11-13 UTC / 2026-11-12 Eastern)

The Docker CLI exists on this Linux host but daemon access is denied, and
noninteractive sudo is unavailable. No permissions, groups or services were
changed. Instead the official Nginx **1.28.0** source archive from
`https://nginx.org/download/nginx-1.28.0.tar.gz` was built in campaign scratch
with existing GCC 16.2.1, PCRE2 and make. Archive SHA-256 is
`c6b5c6b086c0df9d3ca3ff5e084c1d0ef909e6038279c71c1c3e985f576ff76a`.
This historical version is an experiment choice, not a current recommended
production release. No package installation, public listener, TLS, shared
service change or GoDaddy access occurred.

The runner now accepts `--nginx-binary /absolute/path/to/nginx` and uses owned
foreground Nginx plus a synthetic Python backend on ephemeral loopback ports.
Temporary paths and processes are removed after each run. Existing Docker mode
and cached image requirements remain unchanged. In local mode the exact
configuration is altered only for loopback ports and owned temporary paths,
plus the explicit negative control, if selected.

On Linux 7.2.15-1-omarchy x86_64, Python **3.14.8**, code head
`7979aeec1f4e5970e20e42db62b827f9989f2ac6`, the corrected backend stays silent
for up to **10 seconds**, beyond the client's **4.5-second** deadline. The
configured two-second timeout passes; changing it to 60 seconds must fail at
the client deadline, proving that backend EOF cannot satisfy this test. Full
results and hashes are appended under `corrected_local_validation` in
[t10-nginx-evidence.json](t10-nginx-evidence.json); historical fields remain intact.

Reproduction with an explicitly provided built binary:

```sh
python3 scripts/research/t10-nginx-probe.py --nginx-binary /absolute/path/to/nginx
python3 scripts/research/t10-nginx-probe.py --nginx-binary /absolute/path/to/nginx --negative-control long-read-timeout
T10_NGINX_BINARY=/absolute/path/to/nginx python3 tests/research/t10-test-nginx-probe.py
python3 scripts/github-bootstrap/validate.py
```

The corrected positive probe passed all **12** checks and all **three** actual
Nginx negative controls were detected: 60-second timeout, stripped Upgrade,
and exposed private route. The focused suite passed **8** tests, including five
stdlib idle-oracle regressions. Planning validation passed 471 items / 457
native relationships / 600 dependencies / zero errors. Raw build/configure,
probe, control and test results are retained in campaign `2026-11-12/logs/platform`;
the handoff receipt records their absolute paths. These remain local HTTP/WS
results: real DNS/TLS/renewal, mapped Discord clients, GoDaddy firewall/capacity,
SQL persistence and coordinated restore are still unverified.


### Fresh review follow-up: setup cleanup and handshake validity

The full-head review at `947cd670322feddc799dc952e8b2b3988928818d`
identified two valid Medium findings: `4559111650` (setup errors preceded the
backend cleanup scope) and `4559111694` (the handshake oracle omitted mandatory
upgrade headers and matched `101` anywhere in the status line). Three new
regression methods produced nine assertion failures against the prior code;
the cleanup test itself shuts down leaked resources when testing that revision.

Remediation `e9b8d18cb9451804b41ca9af998fb4e93026dd0d` covers backend creation,
temporary-directory setup, Git/version metadata collection and probe execution
with cleanup. Injected directory/Git/Nginx-version failures now close the backend
socket and join its thread. The handshake requires exact HTTP/1.1 status 101,
`Upgrade: websocket` and an `upgrade` token in the case-insensitive Connection
list, while retaining the accept-hash and frame checks. Deterministic malformed
responses cover missing/wrong headers and misleading status text; a mixed-case
Connection token list remains accepted.

All **11** focused tests pass. The actual Nginx 1.28.0 baseline again passes 12
checks, and the long-timeout, stripped-upgrade and exposed-private-route controls
are detected with successful owned cleanup. Appended machine-readable evidence
and raw `t10-review2-*` logs preserve all previous results. Planning validation
and whitespace checks pass. This remains local HTTP/WS research; real
GoDaddy/Discord/TLS acceptance and fresh independent review remain open.


### Worker cleanup on unexpected probe failure

Independent review at `82e59a607f39a12d28002a05177b32524f83181b` reproduced
a P2 defect: killing only the Nginx master after an unexpected assertion left a
worker serving HTTP 502 on the probe listener. The new actual-Nginx regression
fails against that head, then explicitly terminates the leaked test worker.

Remediation `23b4af98f5f8209dd25fcc777bbb4f83248f04f5` starts the owned Nginx
master in its own session/process group. Cleanup sends TERM to that group,
waits up to five seconds, then uses group-scoped KILL when needed, including
orphan workers if the master has already exited. Backend cleanup runs even if
proxy cleanup raises. The group was created by this runner; unrelated groups
and services are never signalled.

Twelve focused tests pass, including real worker PID inspection and refusal of
connections to the old listener after injected failure. The positive baseline
again passes all twelve checks, and all three unsafe Nginx controls are detected.
Fresh machine-readable runs are appended under `worker_cleanup_followup_2026_11_13`;
`t10-review3-before.log`, `t10-review3-tests.log`, `t10-review3-runs.json` and
`t10-review3-planning.log` retain raw results. Historic evidence remains intact.
These are Linux loopback checks, not GoDaddy, Discord, TLS or production claims.
Fresh independent review remains required.


### Docker uncertain-creation and cleanup-failure follow-up

Review at `bfc8c3166ce2fbb4f48c102b6326573f4a3bc550` identified two Medium
Docker-path issues: a create timeout could leave a daemon-created container
outside the cleanup list, and a proxy cleanup error could skip the backend.
Both were reproduced with a fake Docker command boundary against the old runner.
No actual Docker daemon behavior is inferred from those fake responses.

The runner now checks for name collisions before creation and records intended
names before sending create. Cleanup checks each resource independently and
aggregates failures after attempting every intended resource. Only an explicit
missing-container response proves absence; unknown inspection errors or malformed
inspection cannot authorize removal. Label, name and immutable container ID
must match; removal uses the inspected ID to avoid a reusable-name race and is
followed by another inspection. A no-op removal fails; a removal timeout can
succeed only if the resource is independently confirmed absent. A colliding or
foreign resource is left untouched and reported.

Nineteen focused tests pass, covering create-timeout side effects, collisions,
unknown/malformed inspections, foreign labels/IDs, no-op/failed removal, failure
aggregation and continued backend cleanup. The existing actual local Nginx
baseline and all three controls pass again. Raw `t10-review4-*` logs distinguish
fake Docker regressions from actual local Nginx runs; machine-readable results
are appended under `docker_failure_followup_2026_11_13`. Docker access remains
unavailable on this host, so Docker-mode real execution remains unverified.
GoDaddy/Discord/TLS and fresh independent review gates remain open.


### Failure-path follow-up — 2026-11-13 UTC

Code revision `682b6beedff3e94c2b0a310edafb4ad6207f63dc` corrects the source collector's truncated-response
handling and the probe's failure reporting. A declared Content-Length must match
the bounded body; HTTP framing errors become failed source rows, preserving later
observations. Source hashes already recorded above remain historical observations,
not newly verified complete content. New tests use owned loopback HTTP fixtures.

Negative controls now require the expected structured failure identity; an unrelated
assertion containing `426` cannot certify the stripped-upgrade control. Probe errors
retain accumulated metadata and passed checks, and the CLI emits the failed report
with a nonzero exit. Cleanup always attempts the owned process-group KILL and reap
after a failed wait, and attempts backend cleanup independently.

On Linux / Python 3.14.8, 26 focused tests passed, including actual owned Nginx
1.28.0 controls and worker/listener cleanup. A fresh positive run passed all 12 checks.
Raw results: campaign `platform-finish-logs/t10-tests-candidate.log` and
`t10-baseline-682b6be.json`; source regressions fail against `be740d4`
(`t10-capture-before.log`). Docker uses a simulated command boundary in the new
regressions; actual Docker, public source refetch, TLS, Discord and GoDaddy
acceptance remain unverified. Fresh independent full-head review remains required.


### Elapsed-time and Docker evidence follow-up — 2026-11-13 UTC

A socket inactivity timeout does not bound a response that keeps sending bytes.
The collector now runs each public GET in an owned disposable Python subprocess,
with a 20-second elapsed-time limit per attempt and a shared 90-second collection
budget. The parent kills and reaps a timed-out child before continuing; no
uncancellable request thread survives. The time budget includes DNS, redirects
and body reading; normal process startup/cleanup adds small scheduling overhead.
Expired collection budgets produce failed rows without starting another worker.

A real loopback slow-drip fixture reaches the 0.8-second test deadline, preserves
the next healthy result, and verifies every child has exited. The prior collector
accepted the slowly delivered body after about 1.24 seconds instead. Local HTTP
fixtures, including incomplete bodies and broken chunk framing, remain synthetic
source-capture tests; public source content was not refetched.

Docker baseline failures now preserve the parsed failed check, detail and prior
passed checks. The fixture serializes generic assertion/IO failures too, with
`unexpected-probe-failure` identity that cannot certify a negative control. The
timeout assertion accepts Docker's structured detail and local mode's string.
Regression tests cover both formats, a generic IO failure after five successes,
and a failing baseline; the baseline regression fails against `0703471`.
Full-head test results and exact revision are recorded in the campaign
`receipts/platform-finish.json` and `platform-finish-logs`; actual Docker and all
previously stated external platform acceptance gates remain unverified.


### Idle-timeout phase follow-up — 2026-11-13 UTC

The idle-control failure can now originate only from reading the established
`/idle` tunnel after exact 101 status, Upgrade/Connection headers and accept-key
validation. Connection, request-write, status/header and `/ws` frame timeouts
remain unrelated failures and cannot certify the long-read-timeout control.
The idle read requests one byte so unexpected partial data is rejected rather
than mistaken for silence while waiting for a complete frame. The preceding
`/ws` check still validates the actual hello frame before the idle probe.

Four injected connection/handshake timeout cases each fail the previous
`140d7c4` behavior. Regression tests also distinguish a validated idle-read
timeout from a normal-frame timeout or malformed upgrade, and the actual local
Nginx runner rejects an injected idle connection timeout after its earlier
frame check passed. The real long-read-timeout control remains required.
Full-head results and exact SHA are in campaign `receipts/platform-finish.json`
and `platform-finish-logs/t10-phase-*`; all prior external acceptance limits
remain unchanged.


### Optimized execution and report-output follow-up — 2026-11-13 UTC

Critical handshake, idle-payload/timing, control-configuration and Docker readiness
checks now use explicit runtime failures. Python optimization cannot remove them.
Running five focused cases against `0ae7338` with `python -O` produced ten
assertion failures: invalid handshakes, invalid idle evidence and HTTP503 readiness
were accepted. The updated full suite also runs under `python -O`, including
actual local Nginx unsafe controls. No production `assert` statements remain in
the three T10 scripts, including the Docker readiness command string.

The local-binary runner requires POSIX process groups and now rejects Windows
with a structured failure before resolving the binary or creating resources.
The Windows guard is tested by platform simulation; no actual Windows local
runner verification is claimed. Docker mode retains its separate cached-Linux-
container requirements and does not use the local POSIX cleanup path. Actual
Docker execution remains unavailable in this follow-up environment.

If the requested output file cannot be written, the probe now retains the full
report on stdout and exits nonzero. Source capture similarly emits its complete
collected rows before reporting output-write failure. A directory passed as the
output path reproduced `IsADirectoryError` with empty stdout in both old CLIs;
the new regression verifies retained results and nonzero exit without public
network access. This does not certify public sources or external platforms.
Exact final-head normal/optimized test results and raw reproductions are recorded
in campaign `receipts/platform-finish.json` and `platform-finish-logs`.


### Upgrade-request validation follow-up — 2026-11-13 UTC

The synthetic backend now validates the incoming handshake before emitting 101
or a frame: GET/HTTP1.1 with Host, WebSocket Upgrade, a case-insensitive
Connection upgrade token, version13, and one valid base64 key decoding to16
bytes. Missing/malformed or duplicate singleton handshake fields are rejected;
valid header-name/value case and Connection token lists remain accepted. These
checks follow the relevant [RFC6455 section4.2.1 server-handshake requirements](https://www.rfc-editor.org/rfc/rfc6455.html#section-4.2.1),
consulted 2026-11-13. This remains a bounded synthetic fixture, not a complete
WebSocket implementation or product security boundary.

The prior `3c63842` fixture failed15 malformed-request subcases. In actual local
Nginx experiments, stripping Connection or version still allowed that old fixture
to pass all12 checks; those two unsafe controls escaped. New proxy variants strip
Connection, Sec-WebSocket-Key and Sec-WebSocket-Version in addition to Upgrade.
All four must now receive their exact expected non101 rejection, so the backend
cannot manufacture a valid-looking response when proxy forwarding is broken.
Control transformations are shared by Docker/local modes and require exactly one
matching configuration setting.

The updated suite covers direct loopback handshake positives/negatives plus
actual Nginx baseline and six unsafe variants: four stripped handshake headers,
public private-assets and excessive read timeout. Normal and optimized exact-head
results, old-fixture actual Nginx reports, raw failures and revision are in campaign
`receipts/platform-finish.json` and `platform-finish-logs/t10-request-*`. Actual
Docker, public TLS, Discord and GoDaddy acceptance remain unverified.


### Host, response negotiation and platform-test follow-up — 2026-11-13 UTC

Pinned `a5ff3e5` accepted duplicate Host fields and a Host containing a space,
sending 101 and hello. The fixture now requires one syntactically valid URI
authority: registered names (including valid escapes) and bracketed IP literals
with optional numeric ports remain supported. There is no fixed hostname
allowlist. This follows the Host rejection requirements in
[RFC 9112 section 3.2](https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2).
Direct positives cover named authorities and bracketed IPv6; malformed/duplicate
Host negatives cannot upgrade or emit a frame.

The response oracle previously accepted unsolicited extensions and subprotocols.
Because its request offers neither, it now rejects either response negotiation
header before reading a frame, following
[RFC 6455 section 4.1](https://www.rfc-editor.org/rfc/rfc6455.html#section-4.1).
Duplicate singleton response fields remain rejected, while repeated Connection
fields and valid case-insensitive token lists remain accepted. Wrong path/method/
HTTP version and malformed request keys are covered. Noncanonical base64 pad
bits are not newly prohibited: no additional requirement was established beyond
the documented base64 grammar and decoded 16-byte key.

POSIX-only local-process tests now declare their platform prerequisite; the
local-runner CLI metadata test no longer expects post-setup fields on Windows.
The portable Windows guard JSON test and simulated Docker tests remain enabled.
A Windows-capability simulation without killpg/SIGKILL ran 18 selected tests:
12 portable cases passed and six POSIX cases explicitly skipped. Actual Windows
and Docker execution remain unverified. The production local runner continues
to reject Windows before resources exist.

Before-results, independent pinned diagnostic cross-check and exact-head normal/
optimized validation are in campaign `receipts/t10-protocol-audit.json`,
`receipts/platform-finish.json` and `platform-finish-logs/t10-edge-*`. The audit
is diagnostic evidence, not approval. All real-platform acceptance and fresh
whole-head review gates remain open.


### IP-literal grammar and diagnostic preservation follow-up — 2026-11-13 UTC

The prior `e160e1b` bracket branch relied on URL parsing, which accepted invalid
IPvFuture literals such as `[v1.a b]`, `[v1.a%b]` and `[v1.[x]` as Host values.
The fixture now applies the exact IPvFuture character grammar or stdlib IPv6
validation, as specified by
[RFC 3986 section 3.2.2](https://www.rfc-editor.org/rfc/rfc3986.html#section-3.2.2).
Tests preserve bracketed IPv6/embedded IPv4, valid IPvFuture (including mixed-case
version marker and allowed punctuation), registered-name escapes and empty
optional ports. RFC 3986 zone identifiers remain outside this fixture's literal
grammar. Malformed literals cannot upgrade or emit the hello frame.

Local experiment cleanup now retains the owned stderr handle and temporary
directory until process/backend cleanup finishes, reads at most the final 64 KiB
of available stderr, then closes/deletes the artifacts. The report marks
truncation. This applies to startup/readiness failures and unexpected probe
failures as well as successful runs. A diagnostic-read error is recorded without
replacing the original experiment failure. The captured log comes only from the
owned synthetic fixture process; this tool does not collect production logs or
credentials.

Docker image preflight now runs inside the structured-report scope. Either
missing-image/inspection failure retains host/image metadata, empty owned cleanup
and bounded stdout/stderr diagnostics without creating a container. These Docker
failure paths use a simulated command boundary, not actual Docker acceptance.

Independent pinned diagnostics in `receipts/t10-host-final.json` and
`receipts/t10-evidence-final.json` established the prior failures. New regressions
use wire handshakes, an owned executable emitting a startup marker then exiting7,
and an actual local Nginx unexpected-failure marker; they verify bounded retained
evidence, original failure identity and cleanup. Exact final-head normal/optimized
results and actual Nginx controls are in campaign `receipts/platform-finish.json`
and `platform-finish-logs/t10-literal-diagnostic-*`. All external acceptance and
fresh independent whole-head review gates remain open.


### Public revision-specific evidence — 2026-11-13 UTC

The latest code validation is now reviewable in the repository:
[public receipt and source-hash manifest](evidence/t10-2026-11-13/receipt.json),
[normal suite log](evidence/t10-2026-11-13/suite-normal.log),
[optimized suite log](evidence/t10-2026-11-13/suite-optimized.log),
[baseline report](evidence/t10-2026-11-13/baseline.sanitized.json) and
[six control reports](evidence/t10-2026-11-13/controls.sanitized.json).
The [evidence index](evidence/t10-2026-11-13/README.md) links commands, Windows
capability simulation and planning output. Historical evidence fields remain
unchanged; `t10-nginx-evidence.json` now also points to this public receipt.

These results belong to exact tested code revision
`eee0ad43bcbcc4a262b352eb115d8ac11a04b59d`: 48 normal tests, 48 optimized tests,
12 baseline checks and six detected unsafe controls. The six missing raw control
reports were captured at that same code revision before publication edits.
The publication commit changes documentation/evidence only; its code, test and
configuration hashes match the receipt. No tests are claimed against the later
publication revision. Local build/temp paths use explicit placeholders; original
and published artifact hashes document that sanitization without changing test
results, tested SHAs or fixture hashes. All prior platform and approval limits
remain open.
