# GB-T0.R1 — Editor, Activity and VPS feasibility

Research issue: [#2](https://github.com/CompleteDotTech/guildboard/issues/2). Evaluated 2026-10-24 UTC.
Status: recommendation submitted for review; this is not an accepted architecture ADR or production certification.

## Recommendation and evidence boundary

Proceed with a **controlled Excalidraw integration experiment inside a Discord Activity**, with a server-authoritative API/collaboration service on the mandatory **GoDaddy Linux VPS**. The published interfaces and vendor documentation support this direction. Runtime feasibility remains conditional on the experiments below. Do not install these candidate packages into the application or approve distribution on this research record alone.

The reproducible experiment inspects immutable publisher artifacts. It executes no package code and verifies no browser behavior, permission rule, collaboration algorithm, deployment, or capacity target. No Discord application, credentials, domain, TLS endpoint or VPS was provisioned. No runtime security or performance test passed as part of this issue.

## Evaluated artifacts

[Pins](feasibility-pins.json) record exact versions, npm tarball SHA-512 integrity, upstream source commits, license hashes and declaration-file SHA-256 hashes. [Observed output](evidence/feasibility-2026-10-24.json) binds the experiment to that pins file.

| Candidate | Published version | Source tag resolved to commit | Static result |
| --- | --- | --- | --- |
| `@excalidraw/excalidraw` | 0.18.1 | `a2ec2889babf7d2295469c6d90ebe77fae57df84` (`v0.18.1`) | Tarball matches npm integrity; React component, scene callbacks, read-only prop and imperative scene interface declarations present |
| `@discord/embedded-app-sdk` | 2.5.0 | `14264eccbf9e68d5d58c1aadbc7579e003e0dce6` (`v2.5.0`) | Tarball matches npm integrity; SDK lifecycle, authorization, authentication and URL remapping declarations present |

These are evaluated candidates, not a promise that they are the newest versions or a runtime dependency lock. The npm artifact and tag commit are independently identified; no claim of a reproducible build from that source is made. Refresh research when versions change. The local probe environment is recorded in its output; the host's Node installation does not establish an approved production runtime.

## Licensing and distribution

Both packages declare MIT in their pinned `package.json`. The pinned [Excalidraw source license](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/LICENSE) permits use and redistribution subject to retaining the notice; the [Discord source license](https://github.com/discord/embedded-app-sdk/blob/14264eccbf9e68d5d58c1aadbc7579e003e0dce6/LICENSE.md) has the corresponding MIT terms. The SDK archive includes its source-matching license. No license-named file was found in the inspected Excalidraw archive; keep its pinned source notice in any eventual distribution.

The Excalidraw archive also ships fonts, including Assistant, Cascadia, ComicShanns and Excalifont assets. A package-level MIT declaration **does not clear each bundled asset or transitive dependency**. [License policy implementation #16](https://github.com/CompleteDotTech/guildboard/issues/16) and [verification #17](https://github.com/CompleteDotTech/guildboard/issues/17) must inventory the installed graph and shipped files, identify font/icon licenses and required notices, and test distribution packaging. Imported user assets need a separate policy. Guildboard's MIT intent remains conditional on that audit; this issue grants no legal approval.

## Controlled editing and collaboration

The pinned Excalidraw declarations expose `onChange`, `onPointerUpdate`, `viewModeEnabled`, `updateScene`, scene reads and file insertion. Its root exports serialization/import helpers and `CaptureUpdateAction`. Current [props documentation](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props/) describes the component controls; the [imperative API documentation](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props/excalidraw-api) describes scene updates and history handling. These documents are mutable and must be checked against the pinned declarations before using a specific signature.

Recommended ownership:

- Activity adapter translates a local scene change into a bounded proposed operation. Keep selection, viewport and presence separate from durable board content.
- Server validates identity, guild/board access, current permission epoch, operation schema, object ownership and resource limits before accepting any mutation. A UI prop is a usability control, never an authorization boundary.
- Server sequences and durably acknowledges accepted operations. Clients consume accepted operations with idempotency and reconnect recovery; they do not overwrite authoritative boards with arbitrary full-scene snapshots.
- Adapter applies accepted remote scenes without causing an echo loop or polluting local undo history. Define rejection/rollback and compound-operation behavior before implementation.

These are proposed constraints for [system specification #3](https://github.com/CompleteDotTech/guildboard/issues/3), not a finished protocol. [Canvas research #98](https://github.com/CompleteDotTech/guildboard/issues/98) must test the pinned editor in a browser: remote update echo suppression, rejected edits, undo/redo after remote edits, deleted elements, bindings/grouping, binary assets, read-only pointer/keyboard paths, touch/stylus, and extensions such as sticky notes. [Collaboration research #132](https://github.com/CompleteDotTech/guildboard/issues/132) owns operation granularity, same-object conflicts, compound atomicity and convergence. Do not assume the scene callback is an ordered, durable operation log.

The editor is browser-side; the [integration guide](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/integration) describes client-only mounting and container sizing. This favors a React SPA adapter. Rendering, memory use and mobile performance remain unmeasured.

## Discord Activity constraints

[Activity architecture](https://docs.discord.com/developers/activities/how-activities-work) places the SPA in an iframe and describes SDK readiness followed by authorization/authentication. The client-supplied guild, channel and identity context must not become trusted permission evidence. [Networking guidance](https://docs.discord.com/developers/activities/development-guides/networking) describes the proxy, mapped URLs, WebSocket support, unsupported WebRTC, browser API patches and cookie constraints. Do not copy the illustrative OAuth state value into a production flow.

Plan same-origin mapped API, asset and WSS paths. Inventory editor fonts, libraries, images and worker requests; test CSP failures rather than assuming CDN access. Prefer explicit mapped paths. Evaluate `patchUrlMappings` only where necessary because it modifies browser networking globals. Session design must address OAuth state binding, server-side code exchange, expiration, revocation and cross-site iframe behavior. The cookie requirements in the vendor guide need browser verification and do not replace CSRF controls.

[Discord research #34](https://github.com/CompleteDotTech/guildboard/issues/34) must record actual client/SDK versions and test startup, scopes, server-verified identity, mapping/CSP, HTTPS/WSS, reconnect, permission refresh and supported desktop/web/mobile clients. Static declarations do not prove these paths work or that the chosen role APIs/scopes are available for every guild context. Role authority and platform permissions remain unresolved until that evidence exists.

## GoDaddy Linux VPS feasibility

[GoDaddy's VPS access guide](https://www.godaddy.com/help/enable-root-or-admin-access-to-my-vps-hosting-24737) documents enabling administrative access to install/configure software. This supports evaluating a self-managed Linux service stack, not a particular plan, image or uptime guarantee. No account entitlement, region, image, sizing, price, firewall or network limit was verified.

Proposed topology: public Nginx TLS endpoint → loopback/private Node API and WebSocket service → private MySQL/MariaDB and persistent assets. Use a supported Linux image and supported Node LTS, least-privilege service users, versioned migrations, backup/restore and health-gated rollback. [Nginx's WebSocket guide](https://nginx.org/en/docs/http/websocket.html) documents upgrade header forwarding and idle timeout behavior. Confirm the installed Nginx version, explicit HTTP/1.1 upstream behavior, connection headers and heartbeat/timeout configuration on the selected image; the guide can evolve independently of a VPS package.

[Infrastructure research #324](https://github.com/CompleteDotTech/guildboard/issues/324) must record a real GoDaddy plan/image, root/SSH policy, Node/Nginx/database versions, DNS/TLS, Discord URL mappings, WSS upgrade/reconnect/idle behavior, renewals, disk durability, restore and rollback evidence. Size only after a declared workload and measured load test. Managed Node hosting can be separately researched but cannot replace the required VPS deployment. No purchase or deployment is authorized by this document.

## Alternatives and decision triggers

| Alternative | Evaluation | Revisit when |
| --- | --- | --- |
| Excalidraw adapter with server-owned mutations | Preferred experiment: existing editor surface with explicit trust boundary; diff/undo/conflict behavior still needs proof | Pinned-version browser experiments pass and licensing audit clears shipped assets |
| Maintained Excalidraw fork | Can add missing hooks; creates upgrade, security and license-maintenance obligations | A required invariant cannot be implemented through supported public hooks |
| Custom canvas engine | Maximum control; substantial editing, accessibility and collaboration cost | Adapter and narrowly scoped extensions fail documented requirements |
| Reuse full-scene last-write-wins collaboration | Reject: would discard required per-operation authorization, durable sequencing and conflict semantics | Not an acceptable production fallback |
| GoDaddy managed Node hosting | Optional research only; persistent process/WSS/storage/administrative guarantees unverified | Never substitutes for the mandatory Linux VPS acceptance path |

## Reproduce and review

From the repository root, using Python 3.12 or later:

```sh
python3 -m unittest discover -s tests/research -v
python3 scripts/research/probe_feasibility.py --cache /tmp/guildboard-feasibility --output /tmp/guildboard-feasibility-result.json
python3 scripts/research/probe_feasibility.py --cache /tmp/guildboard-feasibility --offline
```

The first probe fetches pinned public tarballs/licenses with bounded reads; subsequent offline runs use the cache and check the same bytes. Expanded tar bytes are bounded before parsing, including PAX metadata hidden from member iteration. No install scripts execute. Tests reject corrupt bytes, identity substitution, missing/changed declarations, duplicate members, symlinked selected files and metadata expansion beyond the byte budget. Exit zero means these static checks passed; it is not a software adoption or runtime acceptance result. Compare `pins_sha256` before using old output after a pin change.

The [platform source ledger](evidence/platform-sources-2026-10-24.json) records dated raw fetches and byte hashes where available, including HTTP failures. Sources with denied raw requests were successfully inspected through the web tool. Hashes detect drift; they are not immutable documentation revisions or archived page contents. Source links are primary publisher pages. Refresh them before implementation and record any changed constraints.

Acceptance coverage: licensing → pinned manifests/source notices plus explicit distribution-audit handoff; editor hooks → hashed declarations plus browser experiment handoff; Discord iframe/proxy → vendor guidance plus real-client handoff; VPS → vendor access/proxy guidance plus real-infrastructure handoff. Alternatives and uncertainties are recorded above. This focused research can support the next specification after review; all runtime and distribution gates remain open in their linked issues.
