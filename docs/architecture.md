# Architecture boundaries and initial constraints

The owner accepted the controlled experiment and VPS direction in [ADR 0001](adr/0001-editor-activity-vps-direction.md). The system specification and downstream research and verification gates remain open; this is not a certified running architecture.

| Boundary | Responsibility | Trust rule |
| --- | --- | --- |
| Activity frontend | Discord SDK lifecycle, React shell, Excalidraw adapter | Client role and guild claims are untrusted |
| API | OAuth exchange, sessions, tenant-scoped routes | Resolve identity and policy on server |
| Bot | Guild installation and authorized slash commands | Verify interaction and guild context |
| Collaboration | Authorized operation processing, presence, recovery | Server sequences accepted intent; no full-document last-write-wins |
| MySQL/MariaDB | Board metadata, policy, operations, snapshots, audit | Commit operation and receipt atomically before acknowledgment |
| Asset store | Opaque, scoped validated uploads | No user-controlled filesystem paths |
| GoDaddy VPS | Nginx HTTPS/WSS, private services, durable volumes | Real external networking tests required |

Policy must be evaluated against current role/grant/mode generation for every mutation, including already-connected clients. A grant revoke must fence in-flight writes. Tenant keys must scope every lookup, cache entry, room, operation ID and asset reference.

Concurrency decisions must explicitly cover same-object edits, undo intent, compound operations, idempotency, durable revisions and snapshot boundaries. Feature implementations wait for reviewed contracts rather than choosing incompatible synchronization strategies independently.

No specific capacity, latency, RPO/RTO or availability claim is established. Research will define objectives; verification will measure achieved results. No production hostname, credentials or VPS instance has been provisioned by this bootstrap.
