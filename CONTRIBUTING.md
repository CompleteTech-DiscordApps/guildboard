# Contributing

Start with the live Project and the issue's stable GB identifier. Do not infer readiness from the title. Claim bounded work with maintainer or authorized coordinator coordination; unassigned backlog is intentional and remains visible. Do not automatically assign all issues or overwrite manual Project triage. Record the owner, scope, exclusive file lease, next action and acceptance; release or hand off the claim and lease when finished or interrupted. Use a focused branch and PR referencing the issue without closing directives until acceptance evidence is available.

## Definition of Ready

Requirements and scope are bounded, acceptance is testable, architecture/security contracts exist, prerequisite native blockers are satisfied, and validation is defined. Identify the responsible owner, file scope, next action, required independent review and acceptance evidence before work starts. Epics and broad features are not ready-to-code units. Research uses primary sources with versions, dates, experiments and uncertainty. Mocked platform checks are not real Discord or VPS verification.

## Definition of Done

Deliverable exists, applicable tests pass, integration and documentation are updated, actual review is complete, relevant PR is merged and post-merge/platform checks are evidenced. Record the exact reviewed revision, validation, limitations and acceptance. Close only when criteria are met. Do not close parents with mandatory incomplete descendants. Research/specification completion never proves application functionality.

## Review

Route auth/tenancy/revocation changes to security expertise, editor/protocol changes to realtime and canvas expertise, migrations to data expertise and deployment to platform expertise. Roles describe required expertise; they do not invent contributors or approvals. Delegation requires actual owner authorization for the campaign and its applicable role, runtime, model and capacity policy; these instructions grant no standing delegation or default permissions. Preserve reviewer independence and exclusive file leases.

## Metadata

Tier identifies ownership workstream, Priority sequencing, Readiness preparation, Status execution and Dependency Status native blockers. Project fields are authoritative; priority/status labels are intentionally absent. Stable manifest IDs survive issue renaming. Do not overwrite legitimate manual triage when reconciling; audit reports drift for review.

Run `python3 scripts/github-bootstrap/validate.py` before a planning change. Include meaningful tests for implementation behavior, negative tests for every authorization boundary, and evidence limitations in the PR. For unavailable prerequisites or checks, record the exact blocker, evidence and next action; do not claim readiness or completion. If work is interrupted, preserve the current state, evidence and handoff, and release or explicitly transfer the lease through the coordinator. See SECURITY.md for private vulnerability reporting.
