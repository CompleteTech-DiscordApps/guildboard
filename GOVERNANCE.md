# Governance

The currently known repository maintainer is @CompleteDotTech. No other contributors or approvers have been assigned. Functional Owner Role values identify the expertise needed, not staffing commitments.

Propose significant architecture changes through an ADR with alternatives, contracts, security effects and consumer handoffs. Maintainer review resolves scope and sequencing disputes. New maintainers require an explicit recorded appointment; CODEOWNERS must contain only actual known maintainers. Review requirements are not waived by Project status or merged planning documents.

Versions follow semantic versioning once release artifacts exist. MVP and v1.0 gates require evidence; no deadline is committed. Maintain a changelog and deprecation policy before stable release.

## Maintainers

Maintainer: @CompleteDotTech, the only known repository maintainer. No other maintainers, contributors or approvers are assigned by this document. A new maintainer requires an explicit recorded appointment, and CODEOWNERS is changed only to name an actual known maintainer.

## Review roles

Review routing is defined in [CONTRIBUTING.md](CONTRIBUTING.md#review): auth/tenancy/revocation to security expertise, editor/protocol to realtime and canvas expertise, migrations to data expertise, and deployment to platform expertise. Roles describe required expertise and do not create reviewers or approvals. Review requirements are not waived by Project status or merged planning documents.

## Decision escalation

Escalation path: contributor -> issue or ADR discussion -> maintainer review.

1. A contributor raises a scope, behavior, acceptance or sequencing question on the issue that carries the stable GB identifier. Significant architecture changes are proposed as an ADR under `docs/adr` with alternatives, contracts, security effects and consumer handoffs.
2. An unresolved question, or a dispute about scope, sequencing or architecture, is escalated to maintainer review by @CompleteDotTech.
3. The maintainer decision is recorded in the issue, the ADR or the PR that implements it, with its rationale and the affected identifiers. An unrecorded decision is not a decision of record.

Escalated: scope and sequencing disputes, architecture and contract changes, review-role routing, changes to governance, CODEOWNERS or issue templates, and disputes about acceptance or closure. Conduct concerns use the private path in CODE_OF_CONDUCT.md, and vulnerabilities use SECURITY.md. No response time is committed and no other decision-maker is named.

## Contributor conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Conduct concerns are reported privately through the path described there. Public issues and PRs must not carry sensitive details. Enforcement is proportionate and documented by the maintainer.

## Issue ownership and backlog visibility

- Work on an issue is claimed through maintainer coordination on that issue. An issue has no owner until a maintainer records the claim.
- Assignment never hides backlog: an assigned issue stays visible in the live Project backlog, and unassigned issues stay visible as unassigned. Leaving an issue unassigned is intentional.
- Issue templates in `.github/ISSUE_TEMPLATE/` must not contain an `assignees:` key or otherwise auto-assign issues.
