# GB-T13.04.01.V1 retained staging replay

This new [#446][verification] run verifies private engineering candidate
staging at source `57ad491cc1df755061187a10f52df4586862416c`. Actual execution
was **2026-11-18 05:06:23–05:11:56 UTC**. It does not recover the unavailable
historical `446-private-stage` inventory in the [earlier receipt][historical].
The archive's 2026-11-17 filename preserves the campaign label, not run time.

## Retained evidence and provenance

The [private retained archive][archive] requires authenticated access by the
authorized account; it is not a public artifact. The archive and its embedded
`staging-replay/receipt.json` were rehashed for this documentation handoff.

| Retained object | SHA-256 |
| --- | --- |
| `guildboard-staging-evidence-2026-11-17.zip` | `fcd817339787a8529379bef041d275c380bacacff18e37f5a5532c1a8dfaf1da` |
| `staging-replay/receipt.json` | `b4e849c966185b737079d41b35e3030781685140876d7ebc85c1e54b8332cce5` |

The retained receipt records Linux 6.18.57 x86_64, Node 24.22.3, npm 11.9.0,
Python 3.12.14 and Git 2.52.0. Independent verification worker OpenAI
`gpt-6.1-sol`, effort `high`, used the documented black-box CLI and
contract-derived fixtures without reading implementation code or diffs.
The archive retains 1,351 indexed files and 203 command records, raw outputs,
input and authority fixtures, candidate inventories, checks and harness notes.
Raw inventories and local absolute paths remain in restricted evidence.

Two initially clean detached checkouts performed offline locked installs and
actual local builds. Each build manifest bound 48 committed-source inputs
and 38 compiled outputs. Four primary private candidates (G1 and G3 from each
build) had 48 files each. Complete candidate directories matched byte for
byte across both builds, including manifests, checksum indexes, provenance
and draft notes. Each primary candidate passed strict checksum verification.
These are local build/filesystem integration results; gate conditions remain
synthetic. The common artifact-index SHA-256 was
`6096bf6eeb54563b091276ccbdb3b61c892c41afc4b3ae34aabf9abf66c4b2c4`.

| Candidate version and synthetic gate | Manifest SHA-256 | Notes SHA-256 |
| --- | --- | --- |
| `0.1.0-rc.1`, GB-T13.G1 | `ad28ad63e94132e433d583d9645cb489f5bbb6bd67df5df8a3297d1eb7610ccd` | `86cd290bfd84e076b4351739fc3a87dc37372c5d0cb0c2a5f191eb3fea6b63e5` |
| `1.0.0`, GB-T13.G3 | `d44df2d3f37390893390b50d26f7f077e9d62c7fe4e2da46f7dad08e174a5dc9` | `5eadc864f5dacf88d26b77abd307d825801e2abba6364d7b14687a5a60b44cde` |

## Outcomes and retained failures

Two matching synthetic G1/G3 dry runs accepted. Denied, stale, malformed,
mismatched, missing or insufficient authority/evidence cases refused; the
independent review replay executed 33 such gate rejection cases. Invalid
metadata, unavailable input, checksum corruption and reserved-version
conflict were rejected. Generic external fault injection terminated a process
before promotion (exit 86, no complete candidate) and failed root fsync after
promotion (exit 2, complete candidate retained). Exact retries reproduced
the original complete bytes. Dry runs preserved candidate contents.

The existing staging suite passed 15 tests and the synthetic contract model
suite passed 16, with zero skips, both normally and in corrected Python API
offline-guard runs. The guard probe failed before connecting. This guard is
not kernel network isolation and does not prove arbitrary native subprocess
network denial. Generic rename/fsync injection does not prove physical
power-loss durability.

The original evidence preserves ten unexpected harness exits: one offline
wrapper import setup error and nine missing required output-root attempts.
An additional missing-cwd attempt never invoked the CLI. The earlier
aggregate failed check also remains recorded. Corrected executions have
separate command records; failed attempts were not relabeled as passes.
The receipt records 193 expected exits out of 203 original command records
and no observed implementation defect in valid completed cases.

## Independent review and remaining handoff

The public [independent review receipt][review] records **APPROVE** by a fresh
OpenAI `gpt-6-astra` reviewer at reasoning effort `xhigh`, completed
**2026-11-18 05:19:50 UTC**, against the source revision above. The reviewer
had no implementation or original-evidence role, made no tracked/GitHub
writes and did not delegate. The reviewer independently checked all 1,351
indexed file hashes and inventory, all 203 stdout/stderr bindings, both
builds' source/output hashes and complete candidate directories. A fresh
offline install/build reproduced the retained full build manifest and both
48-file candidates byte for byte. The independent replay ran 73 commands
with expected exit codes, including the two accepted and 33 rejected gate
cases, focused suites and interruption/retry checks. No blocking defect was
found within that bounded scope.

APPROVE covers actual local builds, private staging, checksum/provenance
integrity and synthetic gate logic. It establishes no actual Discord or
GoDaddy result, authentic approval/currentness, historical MVP publication,
public tag/release, deployment, kernel isolation or physical power-loss
result. The historical MVP and platform records are fictitious fixtures.
No real credentials, external API, publication or deployment were used.
No observed secret/PII exposure was found in the retained-byte review;
pattern checks do not constitute security certification.

This receipt records evidence for the [accepted T13 handoff][contract]. It
does not close #446 or approve a real gate. Maintainer automation-handoff
acceptance, native prerequisites and real platform/publication decisions
remain with their respective issues. Future candidate changes require
assessment of compatibility and affected checks against exact source bytes.

[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/446
[historical]: GB-T13-04-01-V1-staging.md#handoff
[contract]: ../specifications/GB-T13-S1-documentation-release-contract.md#gate-and-publication-handoff
[review]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/446#issuecomment-6969905116
[archive]: https://chatgpt.com/library?file_id=libfile_fde3_f-a815314b45a081919e2bdda57840be11_1471bf43ad308191941acbf25b257a9a&account_id=personal
