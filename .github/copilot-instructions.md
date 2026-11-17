# Guildboard review guidance

Apply `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, accepted ADRs and the live
issue's scope, GB ID and native blockers. Inspect integration. Give located,
reproducible findings with impact; distinguish evidence from assumptions.
Do not invent defects or unperformed checks. Explain non-applicable areas.

Review affected boundaries:

- Discord OAuth, sessions and roles: verify code exchange, least-privilege scopes,
  origin/redirect and replay/CSRF defenses, expiry and verified guild/channel
  provenance. Never trust client roles/admin flags or expose tokens/secrets.
- Backend authority: deny by default on reads, writes, commands, exports, assets
  and WebSocket messages. Check current membership, role, mode, object policy,
  restrictions and grants. UI read-only state and a handshake are insufficient.
  Revocation/role removal/lockdown must fence active sockets and in-flight writes;
  grant TTL uses server time. Test allow/deny, stale/replayed claims and no side
  effects. Prevent self-approval, privilege escalation and unsafe moderation.
- Multi-guild isolation: tenant/board-scope every query/join, cache, room, broadcast,
  operation ID, asset and audit lookup. Test cross-guild/board/object access,
  leakage and concurrent users.
- Collaboration: versioned bounded messages, authenticated WSS, server sequencing,
  monotonic board revisions, scoped idempotency, explicit base revisions,
  deterministic element conflicts, compound atomicity and revision-aware undo.
  Reject naive full-document last-write-wins. Test duplicate/reordered/dropped
  frames, simultaneous edits, mode/presenter/revocation races and reconnect;
  compare canonical hashes and durable history for convergence.
- Persistence: atomically commit operation/state/receipt before ACK; test lost
  ACK retries, concurrent duplicates, crash/restart and transaction rollback.
  Review tenant constraints, MySQL/MariaDB locking, consistent snapshot cuts,
  lineage and bounded replay. Migrations need compatibility and interruption/
  recovery checks. Backup acceptance requires isolated restore with assets/logs
  and measured RPO/RTO.
- Abuse/privacy: validate upload/import content, bytes, dimensions and element
  counts; prevent XSS, SQL injection, path traversal and SSRF. Authorize private
  assets and moderation/audit access. Bound rates, queues, connections, storage
  and work; test slow consumers/exhaustion and cleanup. Keep presence ephemeral.
- Config/platform: follow `planning/configuration-contract.md`; no secrets in
  diagnostics or successful-config logs. Verify fail-before-bind startup. Target
  GoDaddy Linux VPS, Nginx HTTPS/WSS, private DB and persistent assets; inspect
  Discord proxy/DNS/origins, TLS renewal, health, shutdown and rollback.
- UI/architecture: keyboard/focus, screen readers, contrast, touch, reduced motion,
  responsive Discord views, save/error/permission feedback and canvas alternatives.
  Preserve accepted service/adapter contracts; significant changes need an ADR.

Require meaningful negative, failure, concurrency and regression tests.
Planning changes run `python3 scripts/github-bootstrap/validate.py`.
Record commands, environment, exact SHA, results and limits. Local/model/mock
checks do not prove real Discord, GoDaddy, recovery or production acceptance.

When an owner-authorized campaign requires Copilot review, obtain adequate
GitHub Copilot code review of the eligible changes at the full PR head SHA,
including relevant integration. Before requesting or re-requesting review,
inspect current requests and reviews. Use the supported code-review flow for
`copilot-pull-request-reviewer[bot]`. A coding-agent assignment or mention
does not count as code review.

Use the strongest available effort allowed by the campaign and confirmed to
fit the included usage without additional charges. If that cannot be
confirmed, leave review pending. Record the actual reviewer, reviewed SHA,
reported effort and linked evidence. Report available controls and coverage
accurately. Pending, stale or inadequate review does not pass.
See [GitHub's review effort and billing guidance](https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/code-review).

Identify changed paths that [GitHub Copilot excludes from review](https://docs.github.com/en/copilot/reference/review-excluded-files).
Record each excluded path and the reason. When the campaign allows it, a
qualified independent reviewer covers those paths and their affected
integration at the same full PR head SHA. This complements the required
Copilot review of eligible paths. If GitHub excludes every changed path,
record that scope and obtain authorized independent coverage of every
path and affected integration. Keep the gate pending for any uncovered path. Honor any explicit Copilot-only STOP for both complementary review
and fallback.

On confirmed Copilot quota, access or service failure, record the evidence
and reason. An inadequate completed review remains pending unless such a
failure is confirmed. If the campaign explicitly authorizes fallback in that
situation, a qualified independent reviewer may review the full PR at its
current full head SHA, including relevant integration. Keep the gate pending
if the authorized fallback is unavailable or incomplete.

Independent reviewers must be fresh and qualified under the campaign's
role, runtime and model policy. They must have no implementation role,
make no writes and perform no delegation. Record reviewer identity,
model/effort, full reviewed SHA, scope, findings, checks and limitations
in a durable receipt. The technical gate requires current-head coverage
of the complete delta through Copilot for eligible paths and complementary
review for excluded paths, or an explicitly authorized complete fallback. Required functional
and security expertise, CODEOWNER approval and all other native approvals
still apply. This guidance authorizes no additional spend or delegation.

Maintain a findings ledger covering every inline and summary finding from applicable
reviews, its disposition, remediation SHA and verification evidence, including
reasons for non-applicable findings. Remediate valid actionable findings and
obtain qualified review again after any pushed head change, including code fixes;
earlier reviews do not cover the new SHA. Read back the live full PR head,
matching review evidence, findings dispositions and current checks before merge.
Required native approvals, prerequisite gates and passing CI remain separate.
Never bypass branch protection, use an administrator override, weaken tests or
relabel blockers to manufacture readiness. Merge only with explicit authority.

Reference issues without closing directives until their full Definition of Done;
never claim deployment or completed capabilities from scaffolds or documents.
