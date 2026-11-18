# Release versioning and notes

This policy applies to Guildboard product releases and independently versioned
public contracts. It implements [GB-T13.03.02.T1 #441][policy-issue] under the
[accepted T13 release contract][contract]. The [T13 workstream][workstream]
tracks the documentation and release handoffs.

## Choose the version and document compatibility

Use Semantic Versioning for the product and its public contracts. Record the
supported versions and compatibility ranges for each released public surface:
the HTTP API, WebSocket protocol, data and export formats, configuration, and
documented operator interfaces. Identify affected consumers and the versions
they can use together. The maintainer records initial public baselines,
support windows, and any end-of-support decisions with the release.

| Change to a stable public surface | Version and release-note requirement |
| --- | --- |
| Backward-compatible correction | Increment the patch version and describe the correction and any operator action. |
| Backward-compatible addition | Increment the minor version and identify the new behavior and supported consumers. |
| Deprecation | Announce it in a minor release before removal. Identify the affected versions, replacement, migration steps, recovery options and any decided end-of-support date. |
| Incompatible change, including removal | Increment the major version of the affected surface and record the corresponding product SemVer impact. Document upgrade order, compatibility during transition, and rollback or forward recovery. |

For a pre-1.0 or prerelease artifact, identify the interfaces that may change
and give an upgrade path or disclose the incompatibility. An independently
versioned surface has its own version and support range. The product release
notes explain how that surface change affects the product version and users.

Released version identifiers and artifact bytes are immutable. An exact
republication request is a verified read-only retry under the contract. A
correction or recovery that changes the published bytes requires a fresh
candidate at higher SemVer precedence with new approval. Build metadata alone
does not increase precedence.

## Maintain the changelog and prepare candidate notes

1. Record user- and operator-visible changes under [Unreleased][changelog].
   Include affected public surfaces, deprecations, upgrade actions and known
   limitations where applicable. Link decisions and evidence using reviewed,
   disclosure-safe references. Move the selected entries under the release
   version when publication is verified.
2. Explain the release scope and supported ranges in the notes. List known
   issues and their impact and workarounds. For migrations, record prerequisites,
   upgrade order, backup and verification steps, and rollback or forward recovery.
   If there is no migration, explain why. Include the applicable project and
   distributed third-party license notices, based on the actual payload and
   dependency and license review.
3. Cite the applicable acceptance, test, review and deployment evidence with
   its exact source revision, date, environment, result and scope. State
   limitations and pending checks. Actual Discord and GoDaddy claims require
   dated real-environment evidence from the relevant gate. Use the
   [security policy][security] and the contract's disclosure requirements when
   preparing public notes and references.
4. Stage the payload and compute the SHA-256 of the verified `SHA256SUMS`
   index per the contract. Write UTF-8 notes within the 256 KiB limit.
   Start with these three lines in order, each terminated by LF, followed by a
   blank line and the notes body.

   ```text
   Version: <version>
   Revision: <revision>
   Artifact SHA-256: <artifactSha256>
   ```

5. Compare the header to the manifest values. Hash the exact notes bytes
   at `notesRef` and record `notesSha256` before hashing the final manifest.
   Submit the exact candidate and its evidence for Maintainer & Documentation,
   applicable consuming and security review and the corresponding release gate.
   After a byte change, recompute the identity and obtain review and approval
   for the updated candidate.

## Verification handoff

The [synthetic candidate notes][example] demonstrate the header and note
contents with fictional payload bytes. [#445][automation] consumes the exact
contract format for local dry-run staging. [#442][verification] verifies the
policy and final notes and records raw outcomes, defects, the tested revision
and environment. The [T13 contract acceptance][acceptance] records the prior
model outcomes and their scope.

Run the existing contract scenarios and check the documentation diff from the
repository root.

```sh
python3 -m unittest discover -s tests/verification -p test_t13_release_contract.py -v
git diff --check
```

| Verification case | Expected outcome |
| --- | --- |
| Classify changes and assemble notes | Version selection follows the compatibility table. Notes cover support, migrations, known issues, licenses and evidence with explicit limits. Header fields match the signed-off candidate's manifest and the exact notes bytes hash to its recorded digest. |
| Invalid configuration or metadata | Reject malformed versions, references and digest values, header or byte mismatches, and unsafe evidence. Preserve the existing publication state and report a safe field or category. |
| Unavailable prerequisites | Missing, stale, wrong-scope or unverified evidence or approval leaves the candidate pending. Record the missing prerequisite without claiming verification. |
| Interrupted preparation or publication | Keep partial staging private. Before commit, preserve the prior publication and recheck the exact candidate, prerequisites and prior state before retry. After a possible commit, reconcile against authoritative readback before retrying. |

[policy-issue]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/441
[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/442
[automation]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/445
[acceptance]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/421#issuecomment-6963209428
[contract]: specifications/GB-T13-S1-documentation-release-contract.md
[workstream]: workstreams/T13.md
[changelog]: ../CHANGELOG.md#unreleased
[security]: ../SECURITY.md
[example]: releases/synthetic-candidate-notes.md
