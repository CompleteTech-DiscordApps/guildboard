# Private release candidate staging

[GB-T13.04.01.T1 (#445)] and [GB-T13.S1] define the local staging
and gate dry-run interface. [GB-T13.04.01.V1 (#446)] owns the acceptance
handoff. Use Linux, Python 3.11+, Git, Node 24 and npm. Work from a checked-out
Git revision with the [engineering build] completed. The current build
produces engineering artifacts for the monorepo.

## Stage the candidate

Run the build and complete staging before running another build in the same
checkout. Use an owner-only output directory outside the checkout, and
retain the metadata and reviewed, redacted UTF-8 notes body separately.

```sh
npm ci --ignore-scripts
npm run build
candidate_root=$(mktemp -d)
python3 scripts/release/stage_candidate.py stage \
  --source "$PWD" --output "$candidate_root" \
  --metadata /path/to/candidate-input.json --notes-body /path/to/notes-body.md
```

The candidate input is a JSON object with `schemaVersion` (`1.0.0`),
`version`, `gate`, and `evidence`. Use a 0.x SemVer with `GB-T13.G1` for
MVP or `1.0.0` with `GB-T13.G3` for the first stable release.
`evidence` contains the strict GB-T13.S1 evidence records. An empty list can
produce a draft with its gate still pending. A G3 input may carry the contract's
`mvpPublication` designation. G3 gate acceptance requires that designation.
Supply the reviewed notes body beginning after the blank line that follows the
GB-T13.S1 header. Staging generates the header using the exact staged version,
source revision and artifact SHA-256. The changelog and notes workflow can
provide that body before candidate review.

Staging checks the complete recorded engineering input and output inventories,
the build versions and file digests, and the input bytes in Git. It packages the
compiled outputs, completed engineering build manifest, pinned settings, build
entry point, recipe and indexed provenance. It sorts the checksum index by
distribution path and derives the exact artifact, manifest and notes digests.
The engineering build manifest supplies the full input inventory. The provenance
links the indexed build manifest, lockfile, configuration, build entry point
and recipe to the pinned source revision. Run the recipe again at that revision
to reproduce the output hashes. Repeat staging with the same inputs to reproduce
the complete candidate.

The result is a JSON report and a complete directory named by the full SemVer.
Files and directories are synced and the directory is promoted with a same-root
rename. An exact retry returns the same identity. Different bytes for an existing
version return `VERSION_CONFLICT`. An interrupted process may leave an
unpublished owner-only `.stage-*` directory. It can be removed after the
process has exited. Retry with the same inputs to produce or read back the
complete version directory. The staged files are private to the account running
the command.

## Dry-run the gate

Obtain the current snapshot and its expected SHA-256 through the maintainer's
trusted handoff, separately from the staged candidate and its proponents.
Resolve the approval and prerequisite references under repository governance.
For G3, the authority must verify the independently designated #471 MVP
publication, including the historical receipt, identity, G1 decision, tag
target and release bytes before supplying the snapshot. Use each current pin
only while its decisions remain applicable.

```sh
python3 scripts/release/stage_candidate.py dry-run \
  --output "$candidate_root" --version 0.1.0-rc.1 \
  --authority /path/to/current-authority.json \
  --authority-sha256 "$trusted_authority_sha256"
```

The bounded snapshot has the following required fields.

| Field | Value |
| --- | --- |
| `schemaVersion` | `1.0.0` |
| `validFrom`, `validUntil` | Inclusive start and exclusive end dates in UTC as `YYYY-MM-DD` |
| `approval` | The exact GB-T13.S1 gate approval record with `decision` set to `approved` |
| `prerequisites` | An object containing the matching `gate` and exact candidate `identity`, the authoritative `decisionRef`, `decision` set to `accepted`, the exact manifest `evidence` array, and the verified `mvpPublication` for G3 or null for G1 |

The dry-run recalculates the candidate identity and checks the snapshot digest,
validity window, scope and exact evidence against that identity. It requires
passing evidence with real Discord evidence for G1 (`GB-T12.MVP1`) or GoDaddy
evidence for G3 (`GB-T13.G2`) at the candidate revision. The snapshot issuer
checks coverage of all applicable prerequisites and any compatibility assessments
needed for other rows. Local dry-runs are read-only. A digest authenticates the
snapshot only when its expected value came from the trusted handoff. Reusing a
previous pin can miss supersession within the date window. The publication
operator must independently revalidate current authority at its own commit point.

The command returns JSON on standard output. Exit status 0 means
`STAGED` or `DRY_RUN_ACCEPTED`. Status 3 means
`PREREQUISITE_UNAVAILABLE`, including absent, denied, stale or mismatched
authority. Status 2 covers invalid inputs, an unavailable local filesystem
input or a staging conflict. Reports include the exact identity when
available, and dry-run reports include the UTC evaluation date. Accepted
reports name the pinned snapshot digest.

## Verification handoff

```sh
python3 -m unittest discover -s tests/release -v
python3 -m unittest discover -s tests/verification -p test_t13_release_contract.py -v
git diff --check
```

Retain the staged bundle, exact candidate identity and dry-run output for
#446 with the tested revision, command, Python, Git, Node and npm versions,
environment and any defects. The focused tests exercise real local filesystem
and Git behavior with synthetic authority and platform evidence, including
missing or denied approvals, stale authority, G1/G3 evidence and abrupt
interruption. Actual Discord, GoDaddy, acceptance, release and deployment
evidence belong to their respective gates and publication operations.

[GB-T13.04.01.T1 (#445)]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/445
[GB-T13.04.01.V1 (#446)]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/446
[GB-T13.S1]: specifications/GB-T13-S1-documentation-release-contract.md
[engineering build]: development.md
