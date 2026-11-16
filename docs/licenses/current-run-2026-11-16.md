# Current candidate evidence — 2026-11-16

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
