# GB-T13.03.01.T1 governance documentation evidence

[Issue #438][task] covers the repository's security reporting, contribution and
community policies. [GB-T13.S1][contract] defines the governing requirements.
[Issue #421's acceptance record][contract-acceptance] identifies the accepted
specification at merge `60b3b53587c1a5a046d12c5c104c1150b89a1964`.
Native dependency readback found #421 closed and #438 open. The [maintainer's
claim][claim] records the documentation scope and preserves the outstanding
ratification and approval requirements.

## Scope and observations

| #438 clause | Published source and evidence |
| --- | --- |
| Private security reporting | The [security policy][security] directs vulnerability reports to GitHub's private reporting feature when enabled, with its documented private fallback when unavailable. The [issue chooser][chooser] points to the security policy and directs vulnerability reports away from public issues. Source review traced both paths. The governance suite checks security text for invented response commitments and contact identities. Live route availability, delivery and response remain unverified. |
| Review expectations | [Contribution review][review] routes changes to the applicable expertise and the [Definition of Done][done] requires actual review, merge and relevant verification. [Engineering guidance][agents] details exact-revision review, required native approval and protected merge. The suite checks the review wording and the [PR template's review checklist][pr-template], including rejection when the review checkbox is removed or review is made optional. |
| Code of Conduct | The [Code of Conduct][conduct] defines expected behavior, private reporting and proportionate enforcement. Its unavailable-contact path requests a private channel without sensitive detail. The suite checks private reporting and rejects variants that disclose sensitive details or allow public conduct reporting. |
| Decisions and ownership | [Decision escalation][decisions] traces a stable-ID issue or ADR through maintainer review to a recorded decision with rationale and affected identifiers. The [ownership policy][ownership] requires the maintainer to record claims and keeps assigned and unassigned work visible. The suite checks those clauses and rejects removed escalation steps and weakened backlog rules. |
| Actual known maintainers | [Governance][maintainers] and [CODEOWNERS][codeowners] agree on the sole known maintainer, `@CompleteDotTech`. A new maintainer requires an explicit recorded appointment. The suite rejects an extra CODEOWNER and unrecognized identities. Review expertise describes the work to be reviewed. Native approval and reviewer eligibility require current GitHub evidence. |
| Issue and PR templates | The [bug][bug] and [feature][feature] forms collect scope, behavior, validation and dependency context. Their acceptance fields are required and the forms leave assignment to maintainer coordination. The [PR template][pr-template] asks for the stable ID, exact evidence and relevant security and compatibility checks. Source review covered the form fields. The suite checks the lack of assignment hints and the required PR evidence and review checklist wording. |
| Welcoming contribution scope | Start with the [README][readme], [setup guide][setup] and [contribution guide][contributing]. Bounded work includes clarifying setup or architecture documentation, reporting a reproducible bug, and proposing a scoped feature with observable acceptance. Use the stable ID and live Project to check readiness and coordinate a claim. Existing public forms are for non-sensitive content. Source review traced these entry points and the suite verifies readiness, claim and backlog wording. |

## Failure scenarios

| Scenario | Exercise and outcome |
| --- | --- |
| Invalid governance configuration | The existing offline suite rejects a synthetic second CODEOWNER, auto-assignment hints in copied issue templates, optional review wording and public conduct routing. Those cases exercise configuration and policy text in fixtures. |
| Unavailable prerequisite | A documentation walkthrough followed the policy branches for a disabled security reporting feature and for conduct with no published private contact. Each path preserves privacy by following the applicable policy. A missing or unverified review, human decision or required native approval keeps acceptance pending. Native readback confirmed #439 still lists open #438 as its blocker. |
| Interrupted verification or review | A documentation walkthrough stopped before a review or validation receipt was available. At that boundary the Definition of Done remains unmet. Preserve the last confirmed evidence, read back the current issue, PR head and applicable GitHub reviews and checks, then rerun incomplete checks for the applicable revision. Record acceptance only after the required decision, approval, merge and verification are observable. |

The latter two walkthroughs assess the documented handling of these conditions.
Testing the availability, interruption or recovery of live GitHub reporting
and review workflows requires separate evidence.

## Local verification and handoff

The policy sources and test suite were inspected and tested at base
`38be950d8550aaae7179f189bdb45f8826a21154` on Linux x86_64 with
Python 3.14.8. Run the checks from the repository root.

```sh
python3 -m unittest discover -s tests/verification -p test_governance_policy.py -q
python3 scripts/github-bootstrap/validate.py
git diff --check
```

All 85 [governance tests][suite] passed with zero skips. Planning validation
passed for 471 items and the patch's whitespace check passed. Local checks
cover repository content and synthetic wording mutations. The [T0 evidence
record][t0] and [raw results][t0-raw] retain the earlier verification and its
limitations. Discord Activity iframe/proxy and GoDaddy VPS behavior are
outside the scope of this documentation change.

[PR #488][guidance-pr] merged engineering guidance. The [earlier #438
update][partial] identifies two technical COMMENT reviews of historical
candidate `ba6b23b8e7f939bea3819382e3d462b5fe5a892d`. Human governance
ratification, applicable native approval including CODEOWNER approval where
required, current-head functional and consuming review, hosted checks,
protected merge and post-merge acceptance of #438 still require their own
records. Keep unresolved requirements open.

[Issue #439][verification] owns the downstream executable acceptance scenarios,
raw results, exact tested revision and environment, and defects. Its native
dependency on #438 remains in place. Use this clause map and the linked policy
sources as inputs for #439 and the [parent capability][parent]. Any real service
claim requires dated evidence from the applicable environment.

[task]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/438
[claim]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/438#issuecomment-6965447522
[partial]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/438#issuecomment-6875871997
[contract]: ../specifications/GB-T13-S1-documentation-release-contract.md
[contract-acceptance]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/421#issuecomment-6963209428
[security]: ../../SECURITY.md
[chooser]: ../../.github/ISSUE_TEMPLATE/config.yml
[review]: ../../CONTRIBUTING.md#review
[done]: ../../CONTRIBUTING.md#definition-of-done
[agents]: ../../AGENTS.md#validation-and-review
[conduct]: ../../CODE_OF_CONDUCT.md
[decisions]: ../../GOVERNANCE.md#decision-escalation
[ownership]: ../../GOVERNANCE.md#issue-ownership-and-backlog-visibility
[maintainers]: ../../GOVERNANCE.md#maintainers
[codeowners]: ../../.github/CODEOWNERS
[bug]: ../../.github/ISSUE_TEMPLATE/bug.yml
[feature]: ../../.github/ISSUE_TEMPLATE/feature.yml
[pr-template]: ../../.github/pull_request_template.md
[readme]: ../../README.md
[setup]: ../development.md
[contributing]: ../../CONTRIBUTING.md
[suite]: ../../tests/verification/test_governance_policy.py
[t0]: GB-T0-04-01-V1-governance-acceptance.json
[t0-raw]: GB-T0-04-01-V1-raw-results.txt
[guidance-pr]: https://github.com/CompleteTech-DiscordApps/guildboard/pull/488
[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/439
[parent]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/437
