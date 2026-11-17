# License and supply-chain policy (GB-T0.02.02.T1, #16)

Status: policy and an offline lockfile gate. It is not legal clearance, not independent review and not evidence that any shipped asset is licensed. A workflow step, `.github/workflows/license-policy.yml`, runs the gate on pull requests and on pushes to main that change a lockfile, the checker, the exceptions file or the workflow. That step exists, but its result is not recorded here and no native CI result is claimed. A PASS from the gate is not approval or legal clearance: the three committed canvas exceptions were decided by the coordinator on 2026-11-16 under delegated section authority, scoped to the research-only canvas fixture; they are not legal sign-off and need re-review before any product distribution. Discord, GoDaddy VPS and legal sign-off are out of scope.

Gate: `python3 scripts/verification/check_licenses.py` (stdlib only; run from the repository root). Tests: `python3 -m unittest discover -s tests/verification -v`. Exceptions and verified license overrides: `docs/evidence/license-exceptions.json`.

## Scope

The policy applies to every third-party package recorded in a lockfile the project commits, to fonts, icons and imported assets, and to notices shipped with any distribution. First-party workspace entries are excluded from license classification (see Install paths, workspaces and aliases). The gate reads `package-lock.json` and `research-fixtures/canvas/package-lock.json` by default. It does not read installed package files, so declared SPDX metadata is trusted only as far as the lockfile states it.

A new committed lockfile must be added to `DEFAULT_LOCKFILES` in `scripts/verification/check_licenses.py` and to the `paths` filters in `.github/workflows/license-policy.yml` in the same change. The workflow test fails if either trigger's `paths` filters name a lockfile that is not a default, or omit a default.

## Allowed SPDX identifiers

A third-party package is allowed only when its entire license expression resolves to these identifiers:

- `MIT`
- `Apache-2.0`
- `BSD-2-Clause`
- `BSD-3-Clause`
- `ISC`
- `0BSD`
- `BlueOak-1.0.0`
- `CC0-1.0`

`Python-2.0` is not allowlisted: no lockfile in this repository currently contains it. If it appears, it is review-required and needs a version-pinned exception with a documented reason.

## Review-required

These identifiers are not allowed without a version-pinned exception. Any SPDX identifier the policy does not name is also review-required by default.

- `MPL-2.0`
- `Python-2.0`
- `Unlicense`
- `Zlib`

## Prohibited

These licenses are never accepted and cannot be excepted or overridden. The prefix rules match the bare name and every version or variant spelling, case-insensitively, so `GPL`, `GPLv2`, `GPLv3`, `GPL-2.0-only`, `LGPLv3`, `AGPLv3`, `SSPL-1.0`, `BUSL-1.0` and `BUSL-1.1` are all prohibited.

- `GPL*`
- `LGPL*`
- `AGPL*`
- `SSPL*`
- `BUSL*`
- `CC-BY-NC*`
- `UNLICENSED`
- `UNKNOWN`
- `NOASSERTION`

Missing, empty, non-string or malformed license fields fail the gate. A missing license is treated as unknown: it is not a permissive default. A verified override (below) is the only way to supply a missing license.

## SPDX expressions

- Every identifier in an expression is classified. The expression takes the most restrictive class of its terms. This applies to `AND`, `OR` and `WITH` alike, so `MIT OR GPLv3` is prohibited.
- The gate never selects an `OR` branch on the project's behalf. A dual-licensed package such as `(MPL-2.0 OR Apache-2.0)` is therefore review-required, and an exception must name the branch relied on.
- `X WITH exception` is at least review-required, even when `X` is allowed. Only these SPDX exception identifiers are accepted after `WITH`: `Classpath-exception-2.0`, `GCC-exception-3.1` and `LLVM-exception`. Any other exception, and any `WITH` applied to a parenthesized expression, is malformed.
- Malformed expressions fail. Legacy `/` separators are not accepted.
- Identifier matching is case-insensitive.

## Exceptions

`docs/evidence/license-exceptions.json` may list a review-required package only with `name`, exact `version`, the exact lockfile `license` string and a non-empty `reason`. An exception matches one name, one version and one license string; a version change re-triggers review. The match is not bound to `integrity` or `resolved`. Duplicate exceptions are input errors.

- Missing licenses cannot be excepted; a missing license fails.
- Prohibited licenses cannot be excepted. An exception whose `license` is prohibited, or is not a well-formed SPDX expression, is an input error (exit 2), not a stale entry.
- An exception that matches no scanned package fails the run, so stale entries are removed.
- Any other identifier the policy does not name is review-required and can be excepted only by a version-pinned entry.

Exceptions are a review record, not an approval. The owner records approval in the reason or in the workstream entry.

## Verified license overrides

The `verified_license_overrides` list in `docs/evidence/license-exceptions.json` may supply the license for a lockfile entry that has no `license` field. Each entry has `name`, exact `version`, the lockfile `integrity`, `license` (an SPDX expression), `evidence` (`kind`, `source`, `file`, `sha256`, `verified_at` as `YYYY-MM-DD`) and a non-empty `reason`.

- An override applies only when name, exact version and the lockfile `integrity` all match one entry, and that entry has no `license` field (or a null one). Empty or malformed license fields are never overridden.
- The override's `license` is then classified under the normal sets above. A review-required result still needs a version-pinned exception.
- An override never applies to a prohibited license. The gate rejects such an override as invalid input (exit 2).
- A missing license without a matching override still fails. An override that matches no package, whose integrity differs from the lockfile, or whose entry already declares a license fails as `verified override not applied`.
- The gate checks the override's format only. It does not fetch the tarball or re-hash `sha256`; the evidence is recorded for review.
- Overrides record evidence, not legal sign-off. Accepting a license text as adequate is an owner decision and is not implied by an override.

## Install paths, workspaces and aliases

- A third-party entry must sit at an exact `node_modules/...` install path. Path segments `.` and `..`, absolute paths, backslashes and any other shape (for example `vendor/node_modules/x`) fail as an unexpected install path, whatever their license.
- A first-party workspace entry is skipped only when its key is `<dir>/<name>` where `<dir>/*` appears in the root entry's `workspaces` list, and it carries neither `resolved` nor `integrity`. Its own `license` field is not checked, and the workspace list is taken from the lockfile's root entry itself, not from `package.json`. No path segment named `node_modules` in any letter case is a workspace, so `apps/node_modules` is never skipped. Any other `apps/...` or `packages/...` entry that is not a nested install under a workspace (see below) is an unexpected install path.
- A `link: true` entry is skipped only when it sits at a `node_modules` path and its `resolved` target is a known workspace present in the same lockfile. Any other link fails.
- A third-party package installed under a workspace, `<dir>/<name>/node_modules/...` where `<dir>/*` is in `workspaces`, is classified by its real package name like any other third-party entry. A prefix that matches no declared workspace pattern stays an unexpected install path.
- A `workspaces` pattern that contains `node_modules` (in any letter case) or `..`, is absolute, contains a backslash or is wildcard-only (`*`, `**`) is an input error (exit 2). Only `dir/*` with a literal first segment is recognised; other shapes are not workspaces, so their entries fail as unexpected install paths.
- An npm alias is classified by the real package name in the entry's `name` field, not by the install path. Exceptions and overrides match that real name.

## Attribution and distribution obligations

Any distribution of a package (source, bundle, container image or release asset) must include the notices its license requires:

- MIT, BSD-2-Clause, BSD-3-Clause and ISC: keep the copyright line and permission/licence text in source distributions and copies. BSD binary redistributions must reproduce the notice in the accompanying documentation.
- BSD-3-Clause: do not use the copyright holder's name to endorse derived products without permission.
- Apache-2.0: keep the license text and copyright notices, mark modified files, and carry the content of any `NOTICE` file the package provides.
- BlueOak-1.0.0: retain the license text and copyright notice with redistributed copies (conservative reading; confirm against the package text when adopting).
- 0BSD and CC0-1.0: no notice obligation under the license. The project still keeps attribution in its notice bundle for traceability.
- Notice bundles for releases are owned by T13 release notes. This policy does not generate or verify them.

## Fonts, icons and imported assets

No font, icon, image, sound or other third-party asset is adopted by the #16 change. Independent verification (#17) found one existing raster image, `planning/audit/project-overview.jpg` (sha256 `19abbd313b087bb41d59b6e61c0b6a29925deb17b4320ed9d93559f3cc317b47`). Git history records it in commit `da81125` (2026-10-23, "Publish verified bootstrap report, CI evidence and Project screenshot"), and its commit message indicates that it is a screenshot of the project's GitHub Project board, published by the repository team. This rests on the commit message only, and a screenshot of a third-party UI is only partly first-party. No separate license or source URL is recorded, no code references it, and owner confirmation that it is planning documentation only and not distributed is pending. No fonts, icons or icon-library loads were found. Before any such asset is added, record in the repository:

- the asset name and version or revision;
- the source URL and the date it was retrieved;
- the SPDX identifier, or the license text path with its SHA-256;
- copyright holder and the required attribution text;
- whether the asset was modified.

An asset without a recorded license and source URL is not adoptable. Assets may use only the allowed identifiers unless a version-pinned exception applies.

## Upgrade policy

- Dependencies are pinned exactly in `package.json`. Installs use the committed lockfile.
- Every third-party registry package in a lockfile must carry an `integrity` value. The gate fails a third-party entry that has none, and reports the count (zero for both current lockfiles). Only the documented first-party workspace entries are exempt.
- Any lockfile change must rerun the gate. New or changed review-required packages need a new version-pinned exception and reason.
- Run `npm audit` on each upgrade. A zero-advisory result is a dated observation, not a security certification.
- `.github/dependabot.yml` proposes weekly npm and GitHub Actions updates. A Dependabot pull request is reviewed for license changes and new packages before merge.
- GitHub Actions use full commit SHAs, never mutable tags. Currently every `uses:` line in `.github/workflows` is SHA-pinned.
- Lifecycle scripts stay disabled for installs (`npm ci --ignore-scripts`), as recorded in `docs/development.md` and in the `npm ci` steps of `.github/workflows`.

## Input handling

- A missing exceptions file is read as no exceptions and no verified overrides. This only makes the gate stricter, and the run's `exceptions:` summary line says so (`file absent, so no exceptions or verified overrides apply`).
- A missing, unreadable, larger-than-16-MiB, malformed, duplicate-keyed, non-finite-number or deeply nested lockfile or exceptions file is an input error (exit 2) with a message, not a traceback.

## Limits

Not verified by this policy or the gate:

- The gate does not contact any registry or network service, so declared licenses are not compared with registry metadata or package tarballs.
- Transitive license texts are not read. Installed package files are not inspected.
- The two packages with no license field in the canvas research lockfile (`fuzzy` 0.1.3 and `khroma` 2.1.0) are covered by verified overrides. Their evidence came from registry tarball files checked outside this offline gate; the gate does not re-fetch or re-hash them. The overrides are evidence, not legal sign-off.
- The research fixture is not the application. Whether its dependencies ship is not decided here.
- Integrity values must be present and well-formed: one or more whitespace-separated `sha512-`, `sha384-` or `sha256-` tokens whose base64 decodes to 64, 48 or 32 bytes. A malformed value fails as `malformed integrity`. Values are checked for format, not cryptographically checked against the registry.
- The gate does not check the `resolved` download URL: an entry whose `resolved` points to a non-registry URL with a well-formed `integrity` passes.
- The CI step exists but its result is not recorded in this policy. No independent review, protected merge or post-merge check is claimed. A PASS is not owner approval of any license or exception and is not legal clearance.
- Discord, GoDaddy VPS and legal sign-off are out of scope.
