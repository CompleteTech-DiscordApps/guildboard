# Provisional license and supply-chain evidence

Observed 2026-10-24 UTC. Input to architecture [#3](https://github.com/CompleteTech-DiscordApps/guildboard/issues/3) and license implementation [#16](https://github.com/CompleteTech-DiscordApps/guildboard/issues/16)/verification [#17](https://github.com/CompleteTech-DiscordApps/guildboard/issues/17).

**Not an accepted policy, dependency adoption, legal clearance or completed issue.** #16 is natively blocked by #3; #17 is blocked by #16. This report does not change those gates. Architecture and distribution-specific review must decide the implementation. No legal terms were accepted, packages installed, services deployed or platform tests performed.

## Separate the three inventories

### Merged foundation

Examined main `da811252acc975a0e5a1b087ab653b523443f3fa`. Its eight package manifests (root, three apps, four packages) have no dependencies/devDependencies; there is no npm lockfile. This is **not** evidence of a license-cleared future application. Python roadmap tools and SHA-pinned GitHub Actions are build/maintenance inputs, not browser dependencies. Third-party Actions' complete bundled inventories were not audited here.

Guildboard's own `LICENSE` contains MIT terms and contributor attribution. The only tracked file matching font/image suffixes `.woff`, `.woff2`, `.ttf`, `.otf`, `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp` is `planning/audit/project-overview.jpg`. It is planning evidence, not a shipped app asset. This suffix scan does not establish its rights, capture all embedded/binary assets, or clear future user uploads.

### Unmerged configuration tooling

PR [#478](https://github.com/CompleteTech-DiscordApps/guildboard/pull/478), head `b1bdf8c87c0d4ff9b3ed1ccf0d3ca9cde3c3bfce`, and stacked [#479](https://github.com/CompleteTech-DiscordApps/guildboard/pull/479), head `e789f4b585dc380adfd5d017e55ab6a9cbbb9951`, introduce the same three external lockfile packages:

| Package | Exact version | Relationship | Declared SPDX | Inspected artifact evidence |
| --- | --- | --- | --- | --- |
| `@types/node` | 24.19.2 | Direct dev dependency | MIT | License names Microsoft Corporation |
| `typescript` | 5.9.3 | Direct dev dependency | Apache-2.0 | LICENSE.txt **and ThirdPartyNoticeText.txt** present |
| `undici-types` | 7.24.6 | Transitive dev dependency of `@types/node` | MIT | License names Matteo Collina and Undici contributors |

The exact npm tarballs matched each lockfile SHA-512. Notice member paths and SHA-256 hashes are in [the evidence ledger](evidence/proposed-tooling-licenses-2026-10-24.json). Package code was not executed. These are tooling dependencies, not dependencies already on main. TypeScript's third-party notice file means a package-level SPDX field alone is not the complete notice inventory. No production bundle was available to determine which files will be redistributed. Preserve applicable notices when distributing tooling or copied/generated material rather than assuming “dev dependency” means no obligations.

### Candidate editor and SDK, not adopted dependencies

Existing [PR #477](https://github.com/CompleteTech-DiscordApps/guildboard/pull/477), head `47964d5b697aeae70e99403c6b42dfea0ace6816`, separately inspects Excalidraw 0.18.1 and Discord Embedded App SDK 2.5.0. Its source/publisher artifact findings are not repeated here as freshly executed tests. It explicitly leaves bundled fonts, transitive dependencies and distribution clearance open.

Additional primary-source inspection of Excalidraw commit `a2ec2889babf7d2295469c6d90ebe77fae57df84` found **234 WOFF2 source files across nine families**. [Inventory](evidence/license-source-inventory-2026-10-24.json) retains every source path/Git blob ID, not a claim that those exact bytes will all ship in Guildboard. The recursive source tree was complete, not truncated.

| Family | Source WOFF2 count | License evidence at this exact source revision | Remaining gap |
| --- | ---: | --- | --- |
| Assistant | 4 | No per-font license established in this pass | Recover corresponding upstream version/notices and map to actual shipped bytes |
| Cascadia | 1 | Import declaration alone does not establish license | Same |
| ComicShanns | 4 | [Index metadata](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/fonts/ComicShanns/index.ts) identifies MIT and font version 1.3.0; multiple attribution lines | Preserve complete attribution; verify exported subsets/metadata |
| Excalifont | 7 | [Index metadata](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/fonts/Excalifont/index.ts) identifies OFL 1.1, version 1.000 and Excalidraw copyright | Confirm complete notice and reserved-name/modification requirements for distributed fonts |
| Liberation | 1 | Import declaration alone does not establish license | Resolve exact source/version and notices |
| Lilita | 2 | Import declaration alone does not establish license | Same |
| Nunito | 5 | Import declaration alone does not establish license | Same |
| Virgil | 1 | Import declaration alone does not establish license | Same |
| Xiaolai | 209 | [Index metadata](https://github.com/excalidraw/excalidraw/blob/a2ec2889babf7d2295469c6d90ebe77fae57df84/packages/excalidraw/fonts/Xiaolai/index.ts) identifies OFL 1.1, version 3.11 and LXGW copyright; records glyph/spacing modifications | Recover full original notice/RFN declaration and validate modified subset provenance |

Excalidraw's Emoji and Helvetica index files use its local-font protocol, not WOFF2 imports. This is not permission to redistribute OS font files. Export-generated embedding must be checked separately. Inline SVG icons, embedded data and imported user assets also require explicit inventory; the WOFF2 source list does not clear them.

## Obligations to carry into the proposed policy

These are engineering review inputs, not a blanket compatibility opinion:

- **MIT:** retain the relevant copyright and permission notices when distributing covered copies/substantial portions. Guildboard's own MIT notice cannot replace other authors' notices. [SPDX MIT text](https://spdx.org/licenses/MIT.html).
- **Apache-2.0:** preserve the license, applicable attribution and NOTICE material, and mark modified files as required. Review patent/trademark provisions and the actual distributed material. Do not relabel third-party code MIT. [Apache's official text](https://www.apache.org/licenses/LICENSE-2.0).
- **OFL-1.1:** fonts retain OFL; preserve copyright/license, check reserved names for modified versions, and do not sell font software by itself. The license distinguishes font software from documents produced with it; verify whether each export embeds font software. [Official OFL 1.1 text](https://openfontlicense.org/open-font-license-official-text/).
- **Unknown, custom or conflicting evidence:** hold adoption/distribution for targeted review. Do not substitute guessed SPDX identifiers or assume a missing LICENSE file means permissive terms. Preserve a precise unresolved record rather than silently marking it approved.

## Proposed implementation and verification handoff (not adopted)

After #3 is accepted, #16 should define a machine-readable per-component record: exact version/source/hash, direct/transitive/build/runtime category, shipped paths, SPDX expression or unresolved status, complete notice source/hash, modification history, distribution modes, reviewer/evidence link and decision. Capture OS/container packages, fonts, icons, embedded assets and generated output as well as npm packages. User uploads must stay distinct from Guildboard-owned content; an upload is not a grant to relicense it MIT.

For upgrades, regenerate the resolved graph, diff added/removed components and notices, inspect lifecycle scripts and provenance, revalidate packaging and retain the previous approved inventory for rollback. Keep exact lockfiles and reviewed SHA-pinned Actions; updates still require independent review. npm documents that `npm ci` requires a matching lockfile; GitHub recommends full-length commit pins and least-privilege workflow credentials. These controls aid reproducibility, not legal or malware clearance. [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/) · [GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use).

#17 should verify these scenarios against a future implementation and actual distribution:

1. Positive: complete approved fixture produces a deterministic inventory and a distribution containing required notices.
2. Negative: missing/unknown license, conflicting metadata, missing attribution, omitted transitive/font/embedded file, changed artifact hash or unreviewed upgrade fails closed.
3. Unavailable prerequisites: absent lockfile, inaccessible upstream evidence or unavailable review produces incomplete/blocked status, never a clearance pass.
4. Interrupted run: partial evidence cannot replace an accepted manifest or generate a success marker; recover using validated immutable inputs.
5. Packaging: inspect actual browser bundles, font downloads, downloadable exports, source archives and server/container artifacts separately. Verify notice accessibility and verify that development tooling was or was not redistributed rather than inferring from dependency type.

No executable policy gate or packaging test exists in this report. Fresh architecture/security review, native dependencies, PR merge and post-merge validation remain required. Discord and GoDaddy runtime verification are not applicable to these static observations and have not been claimed.

## Recheck the repository observations

From the repository clone, use `git show REV:path` for each exact revision above; `git ls-tree -r --name-only REV` enumerates tracked paths. Read all eight main package manifests and the proposed branch package-lock.json. The source font ledger was obtained from GitHub's recursive tree endpoint for the exact Excalidraw commit and the linked index files. Tarball sources and verified notice hashes are retained in the tooling ledger. This report contains a dated manual review, not an automated ongoing audit.
