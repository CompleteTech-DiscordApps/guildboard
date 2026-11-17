# License and supply-chain policy (GB-T0.02.02.T1, #16)

Status: policy and an offline lockfile gate. It is not legal clearance, not independent review, not native CI and not evidence that any shipped asset is licensed. Discord, GoDaddy VPS and legal sign-off are out of scope.

Gate: `python3 scripts/verification/check_licenses.py` (stdlib only; run from the repository root). Tests: `python3 -m unittest discover -s tests/verification -v`. Exceptions and verified license overrides: `docs/evidence/license-exceptions.json`.

## Scope

The policy applies to every package recorded in a lockfile the project commits, to fonts, icons and imported assets, and to notices shipped with any distribution. The current gate reads `package-lock.json` and `research-fixtures/canvas/package-lock.json`. It does not read installed package files, so declared SPDX metadata is trusted only as far as the lockfile states it.

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

- `LGPL-2.0-only`
- `LGPL-2.0-or-later`
- `LGPL-2.1-only`
- `LGPL-2.1-or-later`
- `LGPL-3.0-only`
- `LGPL-3.0-or-later`
- `MPL-2.0`
- `Python-2.0`
- `Unlicense`
- `Zlib`

## Prohibited

These licenses are never accepted and cannot be excepted:

- `GPL-*` (all GPL versions and variants)
- `AGPL-*`
- `SSPL-*`
- `CC-BY-NC*`
- `BUSL-1.1`
- `UNLICENSED`
- `UNKNOWN`
- `NOASSERTION`

Missing, empty, non-string or malformed license fields fail the gate. A missing license is treated as unknown: it is not a permissive default. A verified override (below) is the only way to supply a missing license.

## SPDX expressions

- Every identifier in an expression is classified. The expression takes the most restrictive class of its terms. This applies to `AND`, `OR` and `WITH` alike.
- The gate never selects an `OR` branch on the project's behalf. A dual-licensed package such as `(MPL-2.0 OR Apache-2.0)` is therefore review-required, and an exception must name the branch relied on.
- `X WITH exception` is at least review-required, even when `X` is allowed.
- Malformed expressions fail. Legacy `/` separators are not accepted.
- Identifier matching is case-insensitive. Unknown identifiers default to review-required.

## Exceptions

`docs/evidence/license-exceptions.json` may list a review-required package only with `name`, exact `version`, the exact lockfile `license` string and a non-empty `reason`. An exception matches one name, one version and one license string; a version change re-triggers review. Prohibited, missing and unknown licenses cannot be excepted. An exception that matches no scanned package fails the run, so stale entries are removed.

Exceptions are a review record, not an approval. The owner records approval in the reason or in the workstream entry.

## Verified license overrides

The `verified_license_overrides` list in `docs/evidence/license-exceptions.json` may supply the license for a lockfile entry that has no `license` field. Each entry has `name`, exact `version`, the lockfile `integrity`, `license` (an SPDX expression), `evidence` (`kind`, `source`, `file`, `sha256`, `verified_at` as `YYYY-MM-DD`) and a non-empty `reason`.

- An override applies only when name, exact version and the lockfile `integrity` all match one entry, and that entry has no `license` field (or a null one). Empty or malformed license fields are never overridden.
- The override's `license` is then classified under the normal sets above. A review-required result still needs a version-pinned exception.
- An override never applies to a prohibited license. The gate rejects such an override as invalid input (exit 2).
- A missing license without a matching override still fails. An override that matches no package, whose integrity differs from the lockfile, or whose entry already declares a license fails as `verified override not applied`.
- The gate checks the override's format only. It does not fetch the tarball or re-hash `sha256`; the evidence is recorded for review.
- Overrides record evidence, not legal sign-off. Accepting a license text as adequate is an owner decision and is not implied by an override.

## Attribution and distribution obligations

Any distribution of a package (source, bundle, container image or release asset) must include the notices its license requires:

- MIT, BSD-2-Clause, BSD-3-Clause and ISC: keep the copyright line and permission/licence text in source distributions and copies. BSD binary redistributions must reproduce the notice in the accompanying documentation.
- BSD-3-Clause: do not use the copyright holder's name to endorse derived products without permission.
- Apache-2.0: keep the license text and copyright notices, mark modified files, and carry the content of any `NOTICE` file the package provides.
- BlueOak-1.0.0: retain the license text and copyright notice with redistributed copies (conservative reading; confirm against the package text when adopting).
- 0BSD and CC0-1.0: no notice obligation under the license. The project still keeps attribution in its notice bundle for traceability.
- Notice bundles for releases are owned by T13 release notes. This policy does not generate or verify them.

## Fonts, icons and imported assets

No font, icon, image, sound or other third-party asset is adopted by this change. Before any such asset is added, record in the repository:

- the asset name and version or revision;
- the source URL and the date it was retrieved;
- the SPDX identifier, or the license text path with its SHA-256;
- copyright holder and the required attribution text;
- whether the asset was modified.

An asset without a recorded license and source URL is not adoptable. Assets may use only the allowed identifiers unless a version-pinned exception applies.

## Upgrade policy

- Dependencies are pinned exactly in `package.json`. Installs use the committed lockfile.
- Every registry package in a lockfile must carry an `integrity` value. The gate reports the count of packages without one (zero for both current lockfiles).
- Any lockfile change must rerun the gate. New or changed review-required packages need a new version-pinned exception and reason.
- Run `npm audit` on each upgrade. A zero-advisory result is a dated observation, not a security certification.
- `.github/dependabot.yml` proposes weekly npm and GitHub Actions updates. A Dependabot pull request is reviewed for license changes and new packages before merge.
- GitHub Actions use full commit SHAs, never mutable tags. Currently every `uses:` line in `.github/workflows` is SHA-pinned.
- Lifecycle scripts stay disabled for installs (`npm ci --ignore-scripts`), as already recorded in `docs/tooling-dependencies.md`.

## Limits

Not verified by this policy or the gate:

- The gate does not contact any registry or network service, so declared licenses are not compared with registry metadata or package tarballs.
- Transitive license texts are not read. Installed package files are not inspected.
- The two packages with no license field in the canvas research lockfile (`fuzzy` 0.1.3 and `khroma` 2.1.0) are covered by verified overrides. Their evidence came from registry tarball files checked outside this offline gate; the gate does not re-fetch or re-hash them. The overrides are evidence, not legal sign-off.
- The research fixture is not the application. Whether its dependencies ship is not decided here.
- Integrity values are counted, not cryptographically checked against the registry.
- No independent review, native CI, protected merge or post-merge check is claimed.
- Discord, GoDaddy VPS and legal sign-off are out of scope.
