# GB-T13.R1: Documentation journey evidence

Status: provisional repository research for issue #420; not accepted specification,
release readiness, application usability, or completed real-user research.

Evaluated 2026-10-25 against repository commit
`da811252acc975a0e5a1b087ab653b523443f3fa` (package version `0.0.0`).
The experiment requires Python 3.11+; no application dependencies or Discord/VPS
access are required. Other local research branches are not merged evidence.

## Question and method

Can a contributor, guild administrator, moderator, or end-user complete their
expected journey using the documentation and artifacts actually in this revision?
Inspect three concrete steps per persona. Record the supporting source files,
SHA-256 hashes, limitation, and next validation in
[documentation-journeys.json](documentation-journeys.json). “Documented” means the
narrow step has documentation, not that the product works. “Partial” means some
supporting instructions exist but essential evidence is missing. “Blocked” means
the intended action cannot currently be completed with this repository's artifacts.

The executable experiment checks that all four personas have evidence-backed
steps and that evidence bytes have not drifted. It does not classify prose,
automatically detect product claims, authenticate source provenance, verify remote
links, or certify the manually assigned findings. Reviewers must re-read changed
sources; do not merely refresh hashes to make the check green.

## Findings

- Contributor: actual project state is clearly documented. Planning-validation
  instructions exist; runtime setup remains unavailable. Contribution gates are
  documented, but independent reviewer availability is not established.
- Administrator: installation and GoDaddy deployment/recovery cannot be completed.
  Security reporting guidance exists, but availability of private reporting and
  the fallback contact must be verified. No response SLA is promised.
- Moderator: Grant the Pen, revocation, lockdown and presentation remain requirements.
  There is no operating manual validated against a working UI or server.
- End-user: there is no joinable application, tested save-state feedback, or tested
  accessible alternative. Scaffolding does not substantiate usability claims.

The current inventory contains 12 steps: one documented, three partial, eight
blocked. These counts are a manual repository-gap inventory, not a score for UX,
accessibility or security. No person or client was observed in this experiment.
The gap is primarily absent implemented/validated journeys, not broken links.

## Alternatives and recommendation

1. Write full manuals now from intended behavior. This is fast but risks publishing
   invented UI, scopes, commands, save semantics and installation instructions.
2. Wait until release before writing anything. This avoids speculation but discovers
   missing operational/support contracts too late.
3. Maintain evidence-linked provisional journeys now, then replace each limitation
   with exact tested instructions as its owning implementation is accepted.

Recommend option 3. Keep the README's unavailable-product warning until actual
release evidence changes it. Maintain separate contributor, administrator, moderator
and participant guides rather than one permission-ambiguous manual. Do not turn
this research into a prerequisite that blocks unrelated ready implementation.

## Required handoffs and unresolved questions

- T1/T8: actual installation flow, client matrix, scopes and API/WS versions.
- T2/T6: authoritative permissions, expiry/revocation and mode behavior that manuals
  must describe, including denied and interrupted paths.
- T3/T5/T7: canvas limitations, durable save/recovery semantics, keyboard and
  screen-reader alternatives, tested with participants rather than static checks.
- T10/T11: GoDaddy Linux VPS deployment, rollback, restore and support ownership.
  Managed Node hosting is not an assumed substitute.
- T13 specification: documentation ownership/versioning, actual release support
  policy, independently available review, and a verified private reporting route.

These are handoffs, not assignments, deadlines or new approvals. Existing issue
metadata must be rechecked live before changing readiness or closure. No remote
state was changed by this experiment. Final #420 acceptance still requires review
of this recommendation and any additional real-journey validation the maintainer
requires; product implementation issues remain open.

## Reproduce

From the repository root:

```sh
python3 scripts/research/audit_documentation_journeys.py
python3 -m unittest discover -s tests/research -p 'test_documentation_journeys.py' -v
python3 scripts/github-bootstrap/validate.py
```

Observed locally: audit evidence valid with `product_verified: false`; ten tests
passed; planning validation passed with 471 manifest items. The malformed manifest,
missing evidence, source drift, duplicate persona, traversal and escaping-symlink
negative cases passed. Python/runtime versions and test results are environmental
evidence, not clean-machine setup proof or production deployment evidence.

## Primary repository sources

All source contents were inspected locally at the evaluated commit; these immutable
URLs identify their provenance, not a claim of live URL/network verification:

- [README](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/README.md)
- [Development setup](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/docs/development.md)
- [Contribution gates](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/CONTRIBUTING.md)
- [Security policy](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/SECURITY.md)
- [GoDaddy scaffold](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/infra/godaddy/README.md)
- [T13 scope](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/docs/workstreams/T13.md)
- [Canonical local backlog](https://github.com/CompleteTech-DiscordApps/guildboard/blob/da811252acc975a0e5a1b087ab653b523443f3fa/planning/guildboard-backlog.json)

The companion manifest lists the remaining evidence files and exact hashes.
