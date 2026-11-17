# GB-T13.S1 documentation and release contract

Contract version: `1.0.0` (candidate). Scope: [GB-T13.S1 #421][spec],
following the [GB-T13.R1 journey audit][research]. The version describes the
evidence format and is independent of the application version. Acceptance
requires Maintainer & Documentation review and review by the downstream
engineering and gate consumers before implementation.

## Guide ownership and claims

The maintainer records claims and decisions under [governance][governance].
Owners below are expertise requirements. A guide has one accountable owner
and can have multiple reviewers. Closure of a guide task requires its applicable
verification issue and the repository's [Definition of Done][contributing].

| Guide family | Accountable expertise and review | Evidence to hand off to GB-T13.D1 |
| --- | --- | --- |
| Contributor setup and architecture | Maintainer & Documentation, with setup and architecture consumers | Clean-environment steps, tool versions, authoritative configuration, accepted boundaries and exact build/test evidence |
| Discord Portal and API | Identity & Discord and transport owners, with their client and security consumers | SDK/API/protocol versions, install/launch and OAuth prerequisites, safe configuration and real client/proxy checks for supported claims |
| GoDaddy and operators | Deployment and operations owners, with data/recovery consumers | Linux VPS requirements, DNS/TLS/WSS, migrations, secrets handling, monitoring, backup/restore and rollback evidence |
| Guild administrators and moderators | Moderation and policy owners, with T2/T6 consumers | Role mapping, Grant the Pen, requests, lockdown and modes with permitted, denied and interrupted outcomes |
| End user | Editor and user experience owners, with T3/T5/T7 consumers | Canvas, durable save/history, reconnect feedback and accessible alternatives at the supported client scope |
| Community policy and release notes | Maintainer & Documentation, with affected engineering, security and release consumers | Contribution and decision paths, supported versions, changelog, known issues, migrations, notices and gate evidence |

Each guide entry identifies a stable GB issue, owned repository path, owner
expertise, audience, reviewed source revision, claim status and evidence
references. Assign each claim a stable `claimId` tied to an explicit anchor in
the guide. The pair `path`, `claimId` locates one claim at the reviewed revision.
Keep the ID across edits to the same claim and forbid reuse for another claim. Use `planned` for intended behavior and `unresolved` for a known
evidence gap, including its affected scope and next validating owner. Use
`supported` only with a passing result for the named version, scope and
environment. Mixed guides mark status per claim. On source or environment
change, revalidate affected claims or move them to `unresolved` pending review.
Owners propose changes in the issue and PR, and consumers check the behavior
and evidence before the maintainer records acceptance.

The [T0 handoff][t0] is foundation evidence. Its accepted server-authoritative
boundary governs all guides describing permissions, tenant access, save
receipts and recovery. The journey audit covers four audiences and preserves
documentary gaps. A historical source hash confirms the audited bytes.
Supported runtime behavior needs the applicable integrated or real-environment
result.

## Versioning and community decisions

Product and contract versions use SemVer. Each released public surface (API,
WS protocol, data/export formats, configuration and documented operator
interfaces) names its supported ranges and compatibility policy. An
incompatible change to a stable public surface requires a major version for
that surface, with the effect on product SemVer recorded. Backward-compatible
additions take a minor version and backward-compatible corrections a patch.
A stable deprecation requires notice in a minor release before breaking
removal in a major release. Announce replacement, affected versions, migration,
rollback or forward recovery, and any end-of-support decision. Pre-1.0 and
prerelease artifacts explicitly state which interfaces may change and include
an upgrade path or a disclosure of incompatibility. Released artifact bytes
and version identifiers are immutable. Maintain the changelog and show
compatibility, deprecations, migrations, known issues, support scope, license
notices, source revision, artifact digests and acceptance evidence in release
notes. Exact support windows and initial public interface baselines are
maintainer decisions recorded with the release.

Raise proposed scope, sequencing or acceptance decisions on the issue with
the stable GB ID. For significant architecture changes, link an ADR with
alternatives, contract impact and consumer handoffs. The actual maintainer
resolves escalations and records rationale and affected IDs in the issue,
ADR or PR. Claim ownership through the maintainer and preserve the issue's
visibility in the Project. The [Code of Conduct][conduct] and [security
policy][security] own their private reporting routes. Refer reporters there,
with a private channel requested without sensitive detail if the conduct
route lacks a published private contact. Honor existing policy for
appointments, CODEOWNERS and review routing. Publish only a redacted public
disposition when appropriate. Support, reporting-route availability and
response commitments need their own evidence.

## Release evidence schema

All records use bounded input, strict fields and reviewed references.
Reject unknown fields, duplicate JSON keys or record IDs, malformed versions
and digests, unsafe pointers and oversized values. Limit the UTF-8 JSON manifest
to 512 KiB and 128 evidence entries. Use at most 128 ASCII characters for
SemVer and 256 characters for other string fields, including generated refs.
General references use the safe relative path grammar below or the canonical
`https://github.com/CompleteTech-DiscordApps/guildboard/` base followed by
`issues/<number>`, `pull/<number>`, `actions/runs/<number>`, `commit/<revision>`
or `releases/tag/v<version>`. Numbers are positive decimal integers without
leading zeroes. Use the literal SemVer including any `+` build separator.
Credentials, escapes, queries, fragments and extra path segments are invalid. Digests are lowercase SHA-256 hex and source revisions are full
lowercase Git SHAs in the repository's current SHA-1 format. Date values
use ISO calendar dates in UTC. Keep free-text findings in reviewed,
redacted source documents referenced by the record.

| Record | Fields and invariants |
| --- | --- |
| Guide entry | `issue`, `path` (safe repository-relative path), `claimId` (lowercase letters, digits and hyphens, starting with a letter), `ownerRole`, `audience` (contributor, administrator, moderator, end-user or operator), `revision`, `claimStatus`, `evidenceIds`. For unresolved claims, require `followUpIssue` (stable GB ID). Evidence IDs resolve uniquely in the handoff. |
| Evidence entry | `id` (lowercase letters, digits and hyphens, starting with a letter), `issue`, `revision`, `date`, `environment`, `level`, `result` (pass, fail or blocked), `ref`. Issue is a canonical stable GB ID. A ref resolves to the actual redacted run, command, review or comparison, including its scope, environment and limitations. |
| Candidate manifest | `schemaVersion` (this contract version), `version` (SemVer), `gate` (GB-T13.G1, GB-T13.G2 or GB-T13.G3), `revision`, `artifactSha256`, `notesRef`, `notesSha256`, `provenanceRef`, `evidence`. `notesRef` and `provenanceRef` use safe relative bundle paths and resolve to the exact artifacts described below. G3 publication also requires `mvpPublication`, an object containing the exact published MVP candidate `identity` and canonical `releaseRef` from #471. |
| Candidate identity | `version`, `revision`, `artifactSha256`, `manifestSha256`, `notesSha256`. The publisher derives these fields from the staged bytes. An identity supplied by a caller is valid only when all fields match the derived identity. |
| Gate approval | `schemaVersion`, `gate`, `identity` (candidate identity), `decision` (`approved`), `decisionRef`, `provenanceRef`. The decision ref resolves to the authoritative maintainer decision under repository governance. Verify who made the decision, their authority for the named gate, the current applicability and outcome of the decision, and all identity fields. Gate and provenance must agree with the candidate manifest. |
| Public publication receipt | `schemaVersion`, `identity`, `gate`, `decisionRef`, `provenanceRef`, `tagRef`, `releaseRef`. Store the full candidate identity and the gate, decision and provenance references from the verified approval. `tagRef` is a fully qualified Git tag ref in this repository resolving to `identity.revision`. `releaseRef` is the canonical repository release link for that tag, resolving to the complete publication. Verify the tag target and the release bytes through authoritative readback. |
| Internal commit authorization | Bind the verified approval and applicable native prerequisite decisions to the exact candidate and committed version reservation. Store immutable proof of the decision, its authority and applicability at commit, and the verified evidence references. Redact private inputs before making any public receipt. |

The artifact digest is SHA-256 of the UTF-8 checksum index, including for a
single distributed file. For every file in the distributed payload, record
the lowercase SHA-256 of its exact bytes, two ASCII spaces, the file's
repository-relative distribution path and one LF. Use the safe path grammar
(ASCII letters, digits, underscores, hyphens and dots, with each slash-separated
component starting with a letter, digit, underscore or hyphen). Sort by path
in ascending byte order and require one entry per file with no extra entries.
Verify the index against the complete delivered payload. The index excludes
itself (`SHA256SUMS`), the manifest (`manifest.json`), the notes at
`notesRef` and the receipt (`publication-receipt.json`). These envelope paths
are distinct and reserved. Every payload and envelope file path is a leaf.
Reject a path that is an ancestor of another declared file path.
`provenanceRef` resolves to an indexed payload
file. Its exact bytes are strict UTF-8 JSON (up to 64 KiB) with fields
`schemaVersion`, `sourceRevision` (the exact manifest revision), `inputs`
(1–64 unique records by path), `recipe` (one record) and `checksumIndex`
(the literal `SHA256SUMS`, resolving to this bundle's verified index).
Input and recipe records each use `path` and `sha256`, resolving to exact
indexed payload bytes distinct from the provenance file. Inputs identify
pinned build dependencies and settings. The recipe contains the reviewed
reproducible build instructions for that source and those inputs.

After computing the artifact digest, finalize the UTF-8 notes (up to 256 KiB)
at `notesRef`. Start them with three LF-terminated lines in this order,
`Version: <version>`, `Revision: <revision>` and
`Artifact SHA-256: <artifactSha256>`, followed by a blank line and the reviewed
notes. Compare all three values to the manifest and hash the exact resolved
notes bytes. Finalize the manifest with the notes and artifact digests and
hash its exact bytes. This ordering lets approval and receipt bind all three
digests without circular hashes.

Evidence levels are `static`, `synthetic`, `integration`, `independent-review`,
`real-discord` and `real-godaddy`. Environment identifies the toolchain or
redacted test environment and platform/client versions. A date and URL
alone provide no assurance. Consumers check the linked records, verify
artifacts and approvals, ensure current native dependencies are satisfied,
and reject stale or wrong-scope evidence. A prerequisite acceptance for a
different revision needs a documented compatibility assessment and
verification of affected changes on the candidate. This preserves historical
acceptance records while grounding release claims in current evidence.

## Gate and publication handoff

| Consumer | Required evidence and resulting scope |
| --- | --- |
| [GB-T13.D1 #450][handoff] | Integrate reviewed guides, run instructions and evidence-linked limitations. Keep the native verification prerequisites and document the supported subset. Supply evidence references for G3. |
| [GB-T13.G1 #456][mvp] | Map every [MVP acceptance row][matrix] to T12 integrated evidence and native prerequisites. Include real Discord startup and authenticated guild context, simultaneous moderators, backend viewer-write denial, canvas, synchronization, save, basic lock, reconnect and fundamental security negatives. |
| [GB-T13.G2 #457][production] | Supply production and recovery evidence only. Record dated actual GoDaddy Linux VPS HTTPS/WSS and Discord networking, monitoring, rollback and smoke checks. Link isolated restore of database and assets with measured RPO/RTO, environment and unresolved findings. |
| [GB-T13.G3 #472][stable] | Require all native Tier gates, G1/G2, applicable T13 verification, MVP publication and D1. Link full integration, production acceptance, functionality including modes/moderation/import/export/accessibility/recovery, resolved independent security findings, reviewed versioned artifacts, notes and support documentation. Obtain the authoritative publication receipt designated by #471's accepted evidence independently of the candidate. Require both `mvpPublication` fields to match that designation. Recompute the historical MVP bundle identity and verify its actual G1 decision, receipt, tag target and release bytes. Missing, substituted or unverified MVP evidence leaves G3 pending. |
| [GB-T13.04.01.V1 #446][automation] | Exercise accepted and rejected dry runs that leave tags and public releases untouched. Hand the publication work items a staged versioned candidate, exact manifest and notes, checksums, build provenance, and raw dry-run evidence tied to the tested revision and environment. Record verification outcomes and approval of the automation handoff. |
| [MVP publication #471][mvp-publication] | Publish a 0.x SemVer only after matching G1 approval, accepted [release automation #446][automation], and all native prerequisites and publication criteria. Attach notes, checksums, known limitations and rollback/support guidance. The accepting owner verifies the public bytes and designates the exact candidate identity, verified receipt and canonical release URL in #471's accepted evidence. |
| [Stable publication #473][stable-publication] | Publish the first stable version as `1.0.0` after matching G3 approval, accepted [release automation #446][automation], and all native prerequisites and publication criteria. Attach reviewed artifacts, provenance, migration notes, security disposition and operator documentation. Verify checksums and actual production smoke evidence and record release and deployment receipts. |

In both publication paths, an authorized maintainer approves the exact
candidate after native prerequisites, repository checks and applicable
independent and consuming reviews pass. Apply [SECURITY.md][security] release
gate requirements, including threat model review, authorization negative
tests, dependency and license review, upload and import defenses, secret checks
and actual independent security review. Stage the
complete bytes privately and verify their identity, provenance and gate approval.
Before a new publication, record the expected prior identity, using null only
when no publication exists.

The commit point must atomically check version history, the expected prior
identity and the current applicability of the exact approval and required
prerequisite evidence, including the designated MVP receipt for G3.
Obtain the applicable decisions from each authoritative evidence source. Fence
commit against intervening changes to those decisions, including replacement,
supersession or withdrawal. Reserve the candidate
version permanently and make the complete candidate and its receipt
discoverable with a durable commit authorization. Key the version reservation by the
full released SemVer string. Any existing reservation for that version with a
different candidate identity fails, whether current or historical and
regardless of the expected prior identity. An existing reservation with the
exact identity is a read-only retry. It requires verified readback and never
advances or rolls back the current pointer, even when a newer publication is
current. For an unused version, compare against the expected prior identity
before publishing. The shared current pointer advances only to strictly
higher SemVer precedence. Build metadata distinguishes full version
reservations and has no effect on precedence. Reject an unused version of
equal or lower precedence, including recovery requests. Record recovery as
a new, higher-precedence publication, with newly verified evidence. Readers
see either the complete prior publication or the complete accepted candidate
with its receipt.

Before reporting success, read the authoritative current pointer and version
record, retrieve the published files, manifest and notes, recompute their
identity, and verify the receipt and the resolved tag and release references.
Resolve the notes and provenance paths within the observed bundle, verify the
notes declaration and the indexed provenance and build files, and require
agreement across approval, receipt, resolved source revision and recomputed
identity. Verify the stored commit authorization as evidence of the historical
decision. Subsequent changes to live authorization govern new commits.
Historical readback continues to validate against the durable proof captured
at the original commit. A null pointer is valid only with empty authoritative history.
Otherwise the pointer must resolve to a fully verified current publication
with greater precedence than every historical version. Apply that invariant
to the atomic prior-state check and reconciliation. For a historical retry or lost
acknowledgment, require the same authoritative publication and receipt checks
without changing the current pointer. A publication adapter must demonstrate
these properties in its own verification before use.

| Outcome | Publication requirement |
| --- | --- |
| `INVALID_METADATA` | Reject malformed input, mismatched staged identity, privacy violations or invalid digests. Preserve prior publication and return a safe field name or category. |
| `PREREQUISITE_UNAVAILABLE` | Keep pending with the missing issue or evidence category when a prerequisite or approval is missing, failed, stale, of insufficient level, for a different candidate, or unverifiable. Preserve prior publication. |
| `VERSION_CONFLICT` | Reject any different identity for a reserved version, before applying the prior-state comparison. Preserve all publications and the current pointer. |
| `VERSION_NOT_FORWARD` | An unused version has precedence equal to or below the verified current version. Preserve the current pointer and all reservations. |
| `ALREADY_PUBLISHED` | Return the verified receipt for the exact version and candidate identity as a read-only result, even when a different version is current. |
| `PUBLICATION_INTERRUPTED` | Interruption before commit preserves the complete prior publication. Keep staging private and retry using the same candidate identity after rechecking prerequisites and prior state. |
| `PUBLICATION_UNKNOWN` | Reconcile against authoritative readback after a possible commit. An exact, verified version record and receipt establish commit even if the publication is now historical. If the candidate version is absent, the expected prior remains current and the version can advance, retry conditionally after verification. If a different version is current and the candidate version is absent, require a new decision. Keep contradictory or unavailable readback unresolved and do not retry a possible commit blindly. |
| `PREVIOUS_PUBLICATION_CHANGED` | For an unused version, preserve the observed publication and replan with maintainer review when the expected prior state no longer matches. |

Public evidence may include revision, redacted configuration names, versions,
outcome and scope. Keep credentials, personal or tenant identifiers, board
content, private infrastructure details and private reports out of all
public fields, references and diagnostics. Validate bounded metadata and
review references for disclosure before release. Evidence access follows
existing least-privilege policy. This contract governs documentation and
release evidence. It changes neither product permission behavior nor tenant
isolation controls. The real Discord iframe/proxy/client checks and GoDaddy
Linux VPS deployment/recovery evidence belong to their gate owners.

## Verification and review

Run the [synthetic scenarios][fixtures] with
`python3 -m unittest discover -s tests/verification -p test_t13_release_contract.py -v`.
The model exercises staged byte verification, malformed identity, approval and
prerequisite checks, version conflicts, read-only retries and interrupted
publication with authoritative readback. Maintainer review assesses guide ownership, compatibility
and community routes against existing policy. D1 and gate consumers review
their evidence requirements, provenance and failure semantics. Record actual
reviewers, revision and outcomes on the PR. Repository evidence uses exact
revision and environment. These fixture results cover the contract examples
and leave real platform, operational and release verification to G1/G2/G3.

[spec]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/421
[research]: ../workstreams/T13.md#gb-t13r1-documentation-journey-research-2026-11-17
[t0]: ../workstreams/T0.md#t0-integration-and-handoff
[governance]: ../../GOVERNANCE.md
[contributing]: ../../CONTRIBUTING.md
[conduct]: ../../CODE_OF_CONDUCT.md
[security]: ../../SECURITY.md
[handoff]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/450
[mvp]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/456
[automation]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/446
[mvp-publication]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/471
[production]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/457
[stable]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/472
[stable-publication]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/473
[matrix]: ../../planning/MVP-ACCEPTANCE.md
[fixtures]: fixtures/GB-T13-S1-scenarios.json
