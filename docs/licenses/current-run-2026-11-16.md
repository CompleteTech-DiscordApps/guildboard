# Current candidate evidence — 2026-11-16

## Successor integration to published dad1918, 2026-11-16

This record describes the integration after `dad191837d5ef5f377acdf5f2c4c22c8beaf09ea`; its exact revision is the enclosing Git commit. Sections 119 and 236 now have bounded known-term interpretations with all original and intermediate unresolved decisions retained. The full CC0 text and two upstream wcwidth comments add three content-addressed notices. The inventory has 100 components, 246 original sections and 66 notices, occupies 2,073,254 bytes below the unchanged 2 MiB cap, and binds catalog `849aa106bbf49ab635613cac7735262e081b830eb002ba8159d6892dc1eccab0`. No original decision was removed to fit the cap.

Root executed the following sequentially with an absolute private TMPDIR and the 100-archive fixture/receipt:

- `python3 -B -m unittest discover -s tests/licenses -v`: 40 tests passed, including five new supplemental binding/history regressions. The initial 40-test invocation had one unsupported-scope structural assertion failure without its diagnostic. An isolated reproduction was valid; assertions now include diagnostics, and the full 40-test rerun passed. The initial log remains retained; its cause is unestablished, and fresh independent verification is required.
- `check_archives.verify_archives(root, artifacts)`: the actual live-fetched cache verified 100 components and 100 component notice bindings; this differs from 66 unique retained notices.
- `check.assess(root)`: structure valid, clearance unknown, seven diagnostics. Ordinals 5, 6 and 180 remain unresolved alongside Prettier classification, two AUTHORS gaps and distribution scope. The CLI remains a failing gate with exit 1.

Both supplemental npm archives were also verified using bounded gzip and raw header scanning before selected manifest metadata was parsed. Available lomemo MIT/CC0 terms do not establish distribution inclusion or unknown separate vendor terms. Wcwidth ancestry and 142 matching ranges support the identified historical grant but do not establish behavioral equivalence or complete source provenance.

Native license-policy runs [43924798509](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43924798509) and [43924809671](https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/43924809671) concern the preceding published dad1918 revision (the PR run checked a synthetic merge). Each passed 35 tests and 100 archive bindings and then failed the assessment with nine unknown diagnostics. They are prior evidence for this successor. Fresh exact-revision review, publication and native CI remain required. Issue #16 and #17, distribution scope, asset/action rights and release holds remain open.

## Earlier 82ac8b record, retained verbatim

Private draft PR #482 candidate `82ac8b2593864e885194d665d38da17b509ad3d4` is unpublished and has no issue acceptance or inherited approval. Main #507 merged engineering graph as `8f75`; actual repository head is `2dcb`. #3 is closed; #17 remains open on #16. The following are supplied prior evidence, not tests executed for this documentation update: 35 root tests passed; a live fetch of 100 archives used an unchanged fetch file; current archive verification matched 100 components and 100 notice bindings. The assessment reports 100 components (four nested), 246 sections, 63 retained notices, five unresolved ordinals 5, 6, 119, 180 and 236, 99 interpreted components with Prettier unresolved, two AUTHORS gaps, unknown scope and nine diagnostics with exit 1. The initial 31-test run had a stale expected notice count failure and the corrected 35-test run passed; the original failure remains historical evidence. Grant 217 retains the exact 1,103-byte README notice without an added LF; the 190 history remains retained.

The current interfaces and workflow are documented in [policy](POLICY.md). Native CI has not yet run. The workflow's fixture-backed test and archive identity gates precede an unwrapped assessment that is expected to fail while unknowns remain. A pass of the former is not license clearance. Manager follow-through includes actual CI, fresh independent review, publication and the remaining five terms, two AUTHORS gaps and scope evidence. No legal, distribution or whole-issue clearance follows.

## Historical report retained

The commands, results and three-package decision below describe the original revision and are not current commands or current approval.

# Historical three-package local evidence — 2026-11-16

Source candidate `3ac0830b6a506f59ae1ab96491aa147ec8702a1d`, base `6e219f930a12a372b6cbec8e81feb542a030fb65`; local changes are unpublished, unapproved, and not an issue acceptance. Work copy and commands run from the architecture-adoption directory, Python 3, `TMPDIR=$PWD/scratch PYTHONDONTWRITEBYTECODE=1`. Supplied read-only archive source: `license16-artifacts`; installed notice source: `engineering20-final-candidate/node_modules`; fetch provenance: `license16-artifact-fetch-receipt.json`. No local network, npm, Node, or package code was run.

```
python3 -m unittest discover -s scratch/license16-completion/tests/licenses -v
Ran 15 tests in 0.053s
OK
python3 scratch/license16-completion/scripts/licenses/check.py --root scratch/license16-completion --node-modules engineering20-final-candidate/node_modules --artifacts license16-artifacts
CHECKED: 3 reviewed npm records and notice bytes; distribution remains blocked pending artifact review
python3 scratch/license16-completion/scripts/licenses/check_archives.py scratch/license16-completion engineering20-final-candidate/node_modules license16-artifacts
MATCHED @types/node 1 notice(s)
MATCHED typescript 2 notice(s)
MATCHED undici-types 1 notice(s)
```

All three commands exited 0. Archive SHA-256: `node-24.19.2.tgz` e01cc90bdafb14295f15a8dfbcddd37834250e9dfab4763ff686fb751915d9ce; `typescript-5.9.3.tgz` 10e108c9cf7d5f2879053dff18515fb405abf2ccef63eaaf017d9c571687a1d3; `undici-types-7.24.6.tgz` 2abf595a86b87dd22951218848ec4ad89c018db0e656716dc04b8b2f9290a0f4. Source URLs and SHA-512 are recorded per component in `inventory.json` and verified again by the checker. Manifest and lock SHA-256s are in inventory. Historical blocked evidence is retained separately; the inventory's historical unresolved statement is not an automatic approval marker.

Owned decision: #16 section owner chose to review only this exact three-package graph, require fresh lock-matched bytes and all listed installed notices, and block changed or nested graphs pending separate review. Rationale: version and packaging changes invalidate this bounded evidence. Validation is the commands above; follow-through: manager commissions #507 graph inventory and checker update before distribution, and runs fresh independent #17 acceptance/review and native CI for the actual head. Actual artifact-specific packaging review, action/asset rights, protected merge and post-merge verification remain open.

## Font source supplement after 8f265000, 2026-11-16

The [font source catalog](font-source-terms.json) adds bounded evidence for ComicShanns and Excalifont without changing the npm catalog or checker. Root independently verified two complete index identities and 11 font binary Git blob/SHA-256/length identities against the original 234-path inventory and exact source imports. Four complete metadata notice blocks and six source/receipt files are retained; the upstream root MIT notice accompanies the copied index sources. No font binaries are adopted into product source.

The source grant observations are MIT and OFL-1.1, respectively; actual per-binary applicability remains unresolved. ComicShanns lists five copyright holders in its generated copyright field and two in its full license field; both texts remain intact. Index version labels are metadata, with no independent internal font-table decoding or transformation provenance. Shipping/export, modification, reserved-name and other-family evidence remain open. These are documented review gaps, not generic role approvals.

The preceding published `8f265000d49d8ef59ce5378c05d315355c48968f` completed two native 40-test and 100-archive checks; each final assessment failed closed with seven diagnostics. Its independent security review and separate section 119/236 semantic reviews approved their bounded sections. The functional review retained an inconclusive verdict and an initial directory-change error alongside a passing isolated reproduction and 40-test rerun; later section reviews do not rewrite that verdict. This font supplement needs fresh exact-revision review and CI. No issue, distribution, legal or release acceptance is claimed.
