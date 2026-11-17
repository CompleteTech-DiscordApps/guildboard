# Contributing

Start with the live Project and the issue's stable GB identifier. Do not infer readiness from the title. Claim work with maintainer coordination; unassigned backlog is intentional. Use a focused branch and PR referencing the issue without closing directives until acceptance evidence is available. Decision escalation and issue ownership rules are in [GOVERNANCE.md](GOVERNANCE.md).

## Definition of Ready

Requirements and scope are bounded, acceptance is testable, architecture/security contracts exist, prerequisite native blockers are satisfied, and validation is defined. Epics and broad features are not ready-to-code units. Research uses primary sources with versions, dates, experiments and uncertainty. Mocked platform checks are not real Discord or VPS verification.

## Definition of Done

Deliverable exists, applicable tests pass, integration and documentation are updated, actual review is complete, relevant PR is merged and post-merge/platform checks are evidenced. Close only when criteria are met. Do not close parents with mandatory incomplete descendants. Research/specification completion never proves application functionality.

## Review

Route auth/tenancy/revocation changes to security expertise, editor/protocol changes to realtime and canvas expertise, migrations to data expertise and deployment to platform expertise. Roles describe required expertise; they do not invent contributors or approvals. No paid autonomous coding-agent delegation is configured.

## Metadata

Tier identifies ownership workstream, Priority sequencing, Readiness preparation, Status execution and Dependency Status native blockers. Project fields are authoritative; priority/status labels are intentionally absent. Stable manifest IDs survive issue renaming. Do not overwrite legitimate manual triage when reconciling; audit reports drift for review.

Run `python3 scripts/github-bootstrap/validate.py` before a planning change. Include meaningful tests for implementation behavior, negative tests for every authorization boundary, and evidence limitations in the PR. See SECURITY.md for private vulnerability reporting.
