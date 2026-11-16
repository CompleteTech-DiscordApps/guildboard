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

## Xiaolai evidence and font review follow-through, 2026-11-16

The preceding `3000d42fe6ef0c1a958d3e9a1cc6f5bd44f85ff3` native push run 43930104540 and PR run 43930114365 each passed 40 tests and 100 real-cache archive/notice bindings. The final assessment remained unknown with seven diagnostics and exited 1. These are prior-revision results, not successor execution.

Its functional font review rejected one documentation sentence: the upstream root MIT notice accompanies the copied index sources as a separate file, rather than appearing inside them. This successor corrects that sentence without modifying any notice. Its provenance review verified all 11 binary identities and source bindings but remained inconclusive on base-tree equivalence; fresh review must inspect actual Git-derived base and diff evidence. Both original verdicts remain retained.

[The separate Xiaolai record](xiaolai-source-terms.json) retains the complete source header, actual LXGW 2020 copyright and OFL declaration, and generic full OFL terms without borrowing Excalifont attribution. Root reran the worker verifier: all 209 raw binary length/SHA-256/Git blob identities matched all 209 source imports and original inventory paths, totaling 12,667,492 bytes. The initial worker check counted one non-font TypeScript import; it was corrected to count WOFF2 imports, then generation and complete recalculation passed.

No font parser was used. Version and modification statements are source metadata and claims; actual transformations, per-binary grants, reserved names and product shipping/export remain unresolved. No font binary is added to product source. Npm code, tests, inventory and seven unknown diagnostics are unchanged. Fresh exact-successor review remains required; no legal, whole-issue, distribution, release or merge acceptance is claimed.

## Actual embedded font metadata after 5b0db5a, 2026-11-16

The preceding 5b0db5a native push 43931757909 and PR 43931773019 passed 40 tests and 100 archive/notice bindings, then failed the final assessment on seven unknown diagnostics. Two fresh independent reviews approved its bounded semantics and supplied Git-object/source-byte identity sections; those approvals do not transfer to this successor.

Root acquired and checked the remaining 14 font sources (343,356 bytes), then independently verified their five available index sources and ten font imports. The worker assignment was ended after broad enumeration and a child-process invocation contrary to its instructions; those actions were excluded from acceptance. Exact deliverable hashes and root checks are retained separately. The index-only record does not establish absence of embedded declarations.

Root used installed FreeType 2.13.2 to inspect the actual SFNT name tables in all 234 identity-verified WOFF2 files: 234 successes, zero failures, 133 distinct records. Face index 0 was read; no glyph rendering or font-program execution was requested. The extractor bounds file size, names, per-name and total name bytes, CPU and process address space, and releases face/library handles. Full raw name bytes and exact text are retained with hashes; unsupported encodings remain raw. The extractor source is retained as a non-executable provenance copy with its original workspace-relative layout, not as a product command or CI gate.

Cascadia’s embedded license text mixes restrictive Microsoft language with OFL-based permissions and conditions. Liberation references a separate agreement; no generic OFL identifier is assigned from its name or URL. Assistant and Lilita include explicit reserved-name statements. These fields materially refine the earlier index-only evidence. Ownership, authoritative applicable grants where unclear, source/transformation history and actual shipping/export remain open. New synthesis and independent review are required. No font binaries are adopted into product source, and the npm inventory, code and tests are unchanged.

## Embedded-terms synthesis after fbfb1dd, 2026-11-16

The synthesis covers nine families, all 234 files, all 133 raw record entities and 1,761 per-file references. Its worker independently verified every raw font identity against the three receipts and original inventory, plus raw record hashes/decoding and mappings. Root verified all 244 input, font, script and result manifest entries before integration. An initial typo in the worker verifier’s pinned commit constant failed; the corrected constant matched all inputs and the full verification passed. Actual font parsing remains the separate root FreeType run, not the synthesis worker’s execution.

The preceding fbfb1dd inspection remains inconclusive: it passed 301 manifest hashes, 234 font byte identities, 133 retained name-record decodes and 1,761 references, but independently rerunning the parser and establishing Git-tree completeness were outside that reviewer’s scope. The manager submitted a separate exact-library runtime profile for trusted qualification; no engineering turn is claimed before qualification and actual execution. Original verdicts remain immutable.

Root’s section decision records exact embedded declarations without granting adoption. Virgil’s copyright reservation and OFL permission are not by themselves contradictory; source authority and provenance are separate questions. Cascadia’s product-bound restrictions and broader OFL-based permission need specific reconciliation against authoritative release evidence; Liberation’s referenced agreement is still missing. Assistant and Lilita reserved-name statements remain explicit. Fresh changed-head review, independent parser evidence and actual source/usage follow-through remain required. The npm seven-diagnostic assessment and all release holds remain unchanged.


The direct locked Acorn 8.19.0 AUTHORS supplement is retained from gitHead
`0e0ece7cc7202624d4aca531be4b515b0114b5d0`, bound to the matching source
package manifest and LICENSE. The original unresolved direct gap is retained
in its history. The names are contributor attribution, not proof of legal
ownership; the full MIT notice remains unchanged. The Prettier AUTHORS gap
remains unresolved because the historical @babel/parser reference is not
established by this source. Distribution scope and overall clearance remain
unknown. This revision requires fresh independent review and native CI.

Root verification after the worker result: all 45 fixture-backed tests passed with zero skips, including the 100-archive cache (11,636,214 bytes, four nested contexts). The assignment's broad-enumeration restriction prevented the worker from invoking fixture setup; the coordinator ran it in the root environment instead. Eight worker counterexamples exercised text/hash/path/gitHead, association, missing-source, lock-version and inappropriate Prettier-gap resolution, including recalculated-catalog cases. The source archive itself was prior evidence in the worker source review; root's fixture suite executed its actual-cache archive cases.

The integrated inventory has 100 components, 246 sections and 67 retained notices, with unchanged original/intermediate section records. It is 2,075,913 bytes under the unchanged 2 MiB cap. Exact direct Acorn source identity and original-gap history are required independently of the catalog digest. The explicit catalog revision is 1692ab4ed92bc66117851dd29f28974dc4465b7b56b8006d9b9ea847f97a8974. Six diagnostics remain: Prettier classification, terms 5/6/180, the bundled AUTHORS gap and distribution scope. The final assessment stays unknown and exits 1. Fresh exact-head functional/security review and actual native CI remain required. No distribution or issue acceptance is claimed.

## Actions root-source observations after f7728ea, 2026-11-16

The f7728ea revision received bounded independent static functional, security and actual font-parser reviews. The independent security completion executed 45 fixture tests without skips, 100 archive identities and 100 notice bindings, exact direct Acorn source/archive comparisons and seven adversarial checks. The actual independent FreeType comparison matched all 234 fonts, 1,761 ordered records and 133 entities. Earlier inconclusive verdicts remain historical; successful checks do not clear the six substantive assessment unknowns. Native push 43936855397 and PR 43936861895 each passed 45 tests and 100 bindings, then exited 1 on those six unknowns.

The separate Actions catalog covers all eight declared workflow reference groups at this source revision: seven observed exact commits and 17 uses locations. The worker and coordinator each recomputed all 21 retained source lengths, SHA-256 and Git blob identities. The coordinator compared all full catalog notice/action/package texts to the retained bytes and all declared workflow lines to the unchanged source. Seven complete root MIT notices and 14 action/package manifests are retained. Mutable `v4` resolutions have dated observations only; package versions and workflow comments are distinct. No action or package code was executed.

The root notices apply conditionally to covered material and do not license bundled third-party content automatically. Exact bundled/transitive sources and notices, fetched tools, runtime/runner terms, execution identities and shipping/archive/use facts remain unresolved. Actions observations are separate from the npm inventory and do not reduce its six diagnostics. Fresh bounded review of this documentation/data candidate is required before delivery integration; prior f7728ea approvals do not transfer.

### Actions generated-cache source observations

The retained source slice covers all 279 cache memberships across seven action revisions: checkout 84, setup-node 143, setup-python 46 and upload-artifact 6. All 207 unique raw objects retain exact YAML, byte lengths, SHA-256 and Git blob associations; seven API tree responses and the acquisition receipt remain separate source observations. The 85 distinct raw scalar bodies have individual inspection findings and 290 source-fragment bindings. Full texts include MIT, ISC, BSD, Blue Oak and Apache variants, separate AUTHORS and Microsoft notices, and short references that supply no complete grant. One generated protoc Apache text has apparent omissions; missing holders, applicable NOTICE sources, raw YAML semantics and authoritative release applicability remain explicit gaps.

The two HTTP client cache declarations of `other` remain unchanged. Exact registry archives for releases 3.0.2 and 4.0.1 were checked against retained SHA-512/SHA-1 metadata, parsed under raw archive bounds without execution, and independently verified to contain the same 1,119-byte LICENSE texts as their cache blocks. Their package declarations are MIT; signature and attestation references were not verified. This is source evidence, not proof those packages are included in a particular executed or shipped Actions bundle.

The review history preserves the original checkout and second text-shard inconclusive verdicts. Individual source-text findings are distinct from action-revision membership verification and final candidate review. Empty-homepage parsing errors in two review artifacts were corrected only in separate coordinator copies from exact raw lines; immutable original results and their verdicts remain retained. No approval transfers to a changed candidate. No npm diagnostic, source-authority gap, bundle-completeness gap, distribution requirement or execution hold is cleared by this data retention. The six npm assessment diagnostics remain unknown and the assessment exits 1.

A separate focused reviewer completed the second shard’s supplied mapping: 62 bindings cover 60 raw objects and 81 distinct receipt memberships across seven API tree observations (86 binding-to-membership references include repeats). The original inconclusive review is unchanged. All 85 text bodies and 290 source-fragment associations are retained; final candidate acceptance requires fresh reviews, and no source interpretation or mapping result supplies runtime or shipping clearance.
