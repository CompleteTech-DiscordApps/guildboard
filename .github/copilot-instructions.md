# Guildboard mandatory review guidance

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

Before merge, seek actual GitHub Copilot code review of the current full PR head
SHA first, covering the complete PR delta and relevant integration. Inspect
existing pending requests and completed reviews before requesting or re-requesting
the actual reviewer `copilot-pull-request-reviewer[bot]` through the supported
Copilot code-review flow; a coding-agent assignment or mention is not a review.
Use the strongest review effort actually available through that flow. Record
the actual reviewer, reviewed SHA, available/reported effort and linked evidence;
do not invent model/effort controls, relabel Lite or limited review as Balanced,
or claim unperformed checks. Pending, stale or inadequate review does not pass.

On confirmed Copilot quota, access or service failure, or an inadequate completed
review, record the evidence and reason. A fresh, independent `gpt-6.1-sol`
reviewer at `max` reasoning effort may then review the full PR at its current
head SHA, including relevant integration. It must have no implementation role,
make no writes and perform no delegation. Record reviewer identity, model/effort,
full reviewed SHA, scope, findings, checks and limitations in a durable receipt.
If that qualified fallback is unavailable or incomplete, keep the technical gate
pending. This policy authorizes no purchases or otherwise unassigned delegation.

Either a qualified current-head Copilot review or that qualified independent
review satisfies the technical review gate. Neither route constitutes a native
GitHub approval or replaces required functional/security expertise or CODEOWNER
approval. Requests, quota failures, author self-review and fabricated clean
reports are not completed reviews.

Maintain a findings ledger covering every inline and summary finding from both
routes, its disposition, remediation SHA and verification evidence, including
reasons for non-applicable findings. Remediate valid actionable findings and
obtain qualified review again after any pushed head change, including code fixes;
earlier reviews do not cover the new SHA. Read back the live full PR head,
matching review evidence, findings dispositions and current checks before merge.
Required native approvals, prerequisite gates and passing CI remain separate.
Never bypass branch protection, use an administrator override, weaken tests or
relabel blockers to manufacture readiness. Merge only with explicit authority.

Reference issues without closing directives until their full Definition of Done;
never claim deployment or completed capabilities from scaffolds or documents.
