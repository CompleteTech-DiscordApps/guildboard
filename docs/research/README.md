# Provisional research index

## T13 documentation journeys

[Documentation journey research](documentation-journeys.md) and its
[evidence manifest](documentation-journeys.json) support
[T13's documentation workstream](../workstreams/T13.md) and provide provisional
research inputs. [Issue #420](https://github.com/CompleteTech-DiscordApps/guildboard/issues/420)
records review and acceptance of the research. The downstream specification,
product and release gates track their own evidence and native dependencies.

The dated 2026-10-25 manual repository-gap audit covers four personas and twelve
steps. Independent review at candidate
`1e67bc267d5afa6e45e7ef1fc2d43c828b9ea262` verified 17 unique source hashes against
the evaluated Git revision; all 10 supplied tests passed on Linux with Python
3.12.3. Those checks establish bounded evidence consistency, not real-user
research, working journeys, Discord/GoDaddy behavior or production acceptance.

The October index was added outside the dated source inventory. The report,
manifest and all hashed source documents were unchanged at that revision,
including the T13 workstream. Reproduce those 17 hashes from the pinned Git tree.
The current checkout has later source edits, including the T13 workstream. The
auditor checks only the bytes and shape of referenced evidence. Authenticate the
revision and re-evaluate later sources when applying the historical findings.

## Auditor robustness follow-up (2026-10-26 UTC)

[Separate follow-up evidence](documentation-journeys-auditor-follow-up-2026-10-26.json)
records strict version-tag validation and controlled JSON failure for a real Linux
symlink loop. All 14 focused tests passed on Linux Python 3.12.3 with zero skips,
including the unchanged escape-link test and an unrelated internal-error control.
The October follow-up preserved all 17 source hashes, the report, the manifest
and the then-current T13 workstream. Windows symlink validation was unavailable
with the privileges in that environment.

## Current reproduction

The October record and follow-up above describe their original revisions.
For current-base findings and the Git archive command that verifies the unchanged
historical manifest, see the [T13 research handoff](../workstreams/T13.md#gb-t13r1-documentation-journey-research-2026-11-17).
The auditor's default root is the current checkout, where the historical hashes
expose drift. The focused unit suite uses deterministic synthetic source bytes
so ordinary test discovery needs no Git history.
