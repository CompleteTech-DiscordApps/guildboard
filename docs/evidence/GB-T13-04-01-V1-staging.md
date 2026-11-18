# GB-T13.04.01.V1 private staging verification

[Issue #446][verification] verifies the [private release automation][automation]
delivered for [#445][implementation]. The source revision was
`f84a5f911c01dc9a02d7707bde19435a8157b0da`. The dry-run CLI evaluated
authority on 2026-11-18 UTC. The environment was Linux x86-64 with Node
24.22.3, npm 11.19.1, Python 3.14.8 and Git 2.56.0.

## Build, staged identities and provenance

The following commands ran from clean checkouts of that revision with a
pre-populated npm cache.

```sh
npm ci --offline --ignore-scripts
npm run build
python3 -B scripts/release/stage_candidate.py stage \
  --source "$PWD" --output "$private_root" \
  --metadata "$fixture_metadata" --notes-body "$fixture_notes"
(cd "$private_root/$version" && sha256sum --strict --check SHA256SUMS)
python3 -B scripts/release/stage_candidate.py dry-run \
  --output "$private_root" --version "$version" \
  --authority "$synthetic_snapshot" --authority-sha256 "$synthetic_pin"
python3 -B -m unittest discover -s tests/release -v
python3 -B -m unittest discover -s tests/verification -p test_t13_release_contract.py -v
git diff --check
```

Both private candidates had 44 build inputs, 30 compiled outputs, 37 indexed
entries and 40 files in total. Their common artifact SHA-256 was
`daba8c445ab55c352430a030681d8e784d886d5de511d93c244cebd0181d6094`.
The earlier [#543 merge][staging-merge] run had 28 outputs and 35 indexed
entries. The two additional entries at this revision were independently
verified against the completed build inventory.

| Added output | SHA-256 |
| --- | --- |
| `apps/api/dist/resource-admission.d.ts` | `ebb6a391172e9ac6cfeac6c5b9d7c0e47b6254f18bfa40041b721ab44ee99f72` |
| `apps/api/dist/resource-admission.js` | `fceb6b4654271429c3fe243e896c359fa743f249ec6231b810e2feea043501fc` |

| Version and gate | Manifest SHA-256 | Notes SHA-256 |
| --- | --- | --- |
| `0.1.0-rc.1`, GB-T13.G1 | `cbe7044d64c87c69b15bc94bfa53a60f2996c2e79be52329d286e5dc9ba18e60` | `c3fae0e7218c7b9b580d3a03bd05b291183a979a7725990236b14677e020f540` |
| `1.0.0`, GB-T13.G3 | `4ceabb7b25021e8d1314bdf4227a07ae807014c88314633aee15f33ce70a65e2` | `5b8c8c3eeeb4745644613d548c046e240b7074c92a9f4619d5c137a6c488c5cc` |

Independent checks compared every indexed file against its SHA-256, every
build input against its committed Git bytes, and every compiled output against
the engineering build manifest. The indexed provenance named the tested
revision and bound the completed build manifest, lockfile, package settings,
TypeScript configuration, build entry point and recipe by digest. The notes
header matched the version, source revision and artifact digest. Both
candidate trees and files were owner-only. A second locked install and build
in a fresh worktree reproduced both complete candidate trees byte for byte,
including the checksum index, provenance, manifests and notes. The same-root
exact retry also returned the original identity.

## Gate and failure scenarios

All gate authority, approval references, platform evidence and the historical
MVP designation were synthetic fixtures. The fields named `real-discord`
and `real-godaddy` exercised the bounded acceptance checks using synthetic
data. Each accepted dry run returned the same candidate identity as staging
and the exact synthetic snapshot digest.

| Scenario | Observed result |
| --- | --- |
| G1 and G3 with matching, current synthetic authority | Exit 0, `DRY_RUN_ACCEPTED` for each gate |
| G1 and G3 with absent, rejected, expired, mispinned or wrong-identity authority, or mismatched evidence | Exit 3, `PREREQUISITE_UNAVAILABLE` with the applicable reason |
| G1 without platform evidence, G3 without historical MVP designation | Staging succeeded. Dry runs returned exit 3 with `evidence` and `mvp-publication`, respectively |
| Stable version supplied for G1 | Exit 2, `INVALID_METADATA` with category `gate` |
| Different notes for an existing version | Exit 2, `VERSION_CONFLICT`. The original candidate bytes were preserved |
| Compiled payload modified in a disposable staged copy | Exit 2, `INVALID_METADATA` with category `checksum` |
| Child process terminated immediately before the staging rename | Injected exit 72. The final version directory was absent and the 40 private files remained in a mode-0700 temporary directory. Retry produced the original identity |
| Staging root sync failed immediately after promotion | Exit 2, `INPUT_UNAVAILABLE`. The complete candidate remained in place. Exact retry returned the original identity and preserved the promoted directory inode |

Dry runs and version-conflict checks preserved the original candidate trees.
The focused staging and contract suites passed all 15 and 16 tests,
respectively. An initial harness invocation before the first build had
completed returned `INVALID_METADATA` with category `build-manifest`.
Sequencing staging after the completed build resolved it.

## Handoff

The restricted campaign inventory `446-private-stage` retains the two
candidate bundles, manifests, draft notes, checksum and provenance files,
locked build logs, focused test logs, per-command arguments and exit codes,
raw CLI output, synthetic snapshots and recorded interruption state. The
verification output contains fixture data and is intended for automation
review. The actual Discord and GoDaddy gates, historical MVP publication,
tagging and public release operations were outside this exercise.

The [T13 contract][contract] requires a recorded decision approving the
automation handoff. The maintainer can approve it on #446 against this
revision and the retained evidence after repository review. Real G1 and G3
authorization and public readback belong to the subsequent native gate and
publication issues.

[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/446
[implementation]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/445
[staging-merge]: https://github.com/CompleteTech-DiscordApps/guildboard/pull/543
[automation]: ../release-automation.md
[contract]: ../specifications/GB-T13-S1-documentation-release-contract.md#gate-and-publication-handoff
