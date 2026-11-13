# Provisional research index

## T13 documentation journeys

[Documentation journey research](documentation-journeys.md) and its
[evidence manifest](documentation-journeys.json) support
[T13's documentation workstream](../workstreams/T13.md) and issue #420. They remain
provisional research, not an accepted specification, release readiness or product
acceptance. Issue acceptance, native dependencies and consumer/maintainer review
remain open; this index changes no readiness or dependency state.

The dated 2026-10-25 manual repository-gap audit covers four personas and twelve
steps. Independent review at candidate
`1e67bc267d5afa6e45e7ef1fc2d43c828b9ea262` verified 17 unique source hashes against
the evaluated Git revision; all 10 supplied tests passed on Linux with Python
3.12.3. Those checks establish bounded evidence consistency, not real-user
research, working journeys, Discord/GoDaddy behavior or production acceptance.

This later discovery index is outside that dated source inventory. The report,
manifest and all hashed source documents are preserved unchanged. In particular,
the owning T13 workstream is itself a hashed source: adding this separate entry
point avoids invalidating its recorded provenance. The auditor does not
authenticate revision-label provenance or detect newly added, unreferenced files;
manual re-evaluation remains necessary when sources or available artifacts change.

## Auditor robustness follow-up (2026-10-26 UTC)

[Separate follow-up evidence](documentation-journeys-auditor-follow-up-2026-10-26.json)
records strict version-tag validation and controlled JSON failure for a real Linux
symlink loop. All 14 focused tests pass on Linux Python 3.12.3 with zero skips,
including the unchanged escape-link test and an unrelated internal-error control.
All 17 dated source hashes, the manifest/report and T13 workstream remain byte-
preserved. Windows symlink validation remains unavailable due to the reported OS
privilege limit; no Windows symlink pass or product verification is claimed.
