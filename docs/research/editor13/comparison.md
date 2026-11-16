# Issue 13: evaluated comparison

Decision owner: assigned section owner, 2026-11-16. Source baseline `6e219f930a12a372b6cbec8e81feb542a030fb65`; prior [GB-T0.R1](../GB-T0-R1-feasibility.md) remains historical. [ADR 0004](../../adr/0004-editor-and-database-selection.md) records the delegated decision; Proposed status or an Architecture role is not a generic human hold. Native review and protected merge still apply. Issue #3 was reported closed in the assignment; no remote query was made.

## Editor interface inspection

The 0.18.1 publisher declaration `types.d.ts` lines 405–465 says `onChange(elements, appState, files)` receives an ordered scene and binary files, not a stream of individually authorized operations. `initialData` can be asynchronous; `excalidrawAPI` receives an imperative API; pointer updates include pointer/tool/button and gesture map, suitable only as untrusted ephemeral presence. `onDuplicate` may return replacement elements including deleted elements; `onPaste` can return a boolean or promise. These callbacks do not prove interception of every edit, compound atomicity, ordering or successful rollback.

`viewModeEnabled` is a boolean UI control, not a guarantee against forged requests, stale sessions or programmatic changes. The API at lines 603–635 exposes `updateScene`, reads including deleted elements, `history.clear`, `addFiles`, subscriptions and `registerAction`; many signatures are aliases to internal `App` types unavailable in the supplied excerpt. It does not establish safe history capture, echo suppression or mutation semantics. `updateFrameRendering` explicitly warns frames remain interactive in edit mode. The root declaration exports `serializeAsJSON`, restoration, blob loading and conversion helpers, but their detailed signatures and behavior are not established by this export list. Serialization is an untrusted import/export representation, not a server-authoritative operation log; bound and validate imported elements, files and references. Version and migrate durable formats explicitly.

`children`, `renderTopRightUI`, `renderEmbeddable`, `validateEmbeddable`, library and duplication callbacks offer extension points. They do not prove arbitrary new native element types or secure embeds. Prefer application-owned UI and bounded domain operations mapped to supported elements, with link/embed validation and asset limits. Test missing hooks before a fork. Reject unsupported content without side effects; do not silently discard bindings or data.

## Stack and database

React and react-dom 19.1.0 meet the exact declared Excalidraw peer ranges `^17.0.2 || ^18.2.0 || ^19.0.0`; react-dom declares React `^19.1.0`. This is a declared-range comparison, not an installed graph, build or compatibility test. TypeScript 5.9.3 and Node >=24 <25 are existing baseline repository pins/constraints, not independently exercised with these packages. Fastify 5.6.1 tagged migration and validation docs describe Node >=20, full JSON schemas and application-owned schema compilation; use trusted schemas and perform asynchronous authorization after validation. Fastify and TypeScript provide structure, not authentication, tenant isolation or revocation by default.

Publisher web inspection records MySQL 8.4.7 and MariaDB 11.8.3 release references and JSON storage differences. Raw MySQL fetch returned HTTP 403 and raw MariaDB fetch was unavailable; separate web inspection notes are summaries, not immutable page bytes or SQL execution. Both candidates require proof of transaction isolation, durable sequence/idempotency, revocation fence, crash recovery, backup/restore, migrations and private connectivity on the actual VPS. Avoid assuming MySQL binary JSON and MariaDB LONGTEXT JSON have identical replication, indexes or behavior. HTTPS/WSS proxy, persistent assets, service restart, Discord iframe mappings, CSP and supported client behavior remain untested.

## Failure states and handoff

Unknown operation/schema version or oversized payload: reject without mutation; expired session, cross-tenant request, revoked epoch or stale connection: deny and fence in-flight writes. Duplicate operation: return the existing committed result without duplicate effects; conflicting base/sequence: explicit conflict and resync from server-authoritative state. Storage/commit failure: no success acknowledgment; reconnect after uncertain response uses idempotency and durable sequence. Incompatible editor data or missing asset: reject/quarantine with a recoverable error. These are requirements for downstream implementations, not results of this static probe.

Canvas #98 must run real browser tests for every edit path, view mode, remote echo, undo/redo, deleted/bound/grouped elements, binary assets, extensions, rejection and rollback. Collaboration #132 must prove same-object conflicts, compound atomicity, convergence, epoch fencing and durable recovery. Discord #34 must test real iframe/client mappings, identity, CSP, HTTPS/WSS and reconnect. Infrastructure #324 must test actual GoDaddy Linux VPS, private database, backups, crash/restart, TLS and load. License #16/#17 must inventory actual installed graph and shipped assets; security, current patches and notices must be reviewed before adoption. Independent #14, fresh review, native CI, protected merge and post-merge acceptance are manager-owned. None has passed here.

## Evidence and reproducibility

The fixed hashes in `scripts/research/editor13/probe.py` identify supplied publisher metadata, declarations and tagged Fastify docs; Excalidraw members were extracted by the coordinator from a tarball reported verified against npm SHA-512 `sha512-6i5Gt7IDTOH//qa0Z315Ly5iVRhjWpu2whrlQFqkuwrkKUWgRsMk0P5qdE7bpyDpai7jeLeWYkyj1eVAfni1lw==`. This probe checks member bytes, not the absent tarball or extraction. It does not prove semantics from equal hashes. Source URLs and original fetch outcomes are in the private evidence receipts; links: [npm Excalidraw](https://registry.npmjs.org/@excalidraw/excalidraw/0.18.1), [Fastify v5.6.1 validation](https://github.com/fastify/fastify/blob/v5.6.1/docs/Reference/Validation-and-Serialization.md), [MySQL JSON](https://dev.mysql.com/doc/refman/8.4/en/json.html), [MariaDB JSON](https://mariadb.com/docs/server/reference/data-types/string-data-types/json). No third-party raw documents are redistributed here.

Run with a private copy of supplied evidence and an owned temporary directory:

```sh
TMPDIR=/path/to/owned/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/research/editor13 -v
TMPDIR=/path/to/owned/tmp python3 scripts/research/editor13/probe.py --evidence /path/to/editor13-primary-evidence --output /path/to/owned/result.json
```

The tests use the supplied evidence at the assigned workspace location; relocation requires matching that layout. Missing, corrupt and substituted bytes fail; an interrupted result replacement preserves the prior result. Hashes are deliberately fixed and updates require a new review, never blanket approval. Runtime, legal and security acceptance remain open.
