# Guildboard engineering and review instructions

These instructions apply throughout this repository. Follow `CONTRIBUTING.md`,
`GOVERNANCE.md`, `SECURITY.md`, the live issue and Project, and accepted contracts.
This file adds implementation and review checks; it does not waive their gates,
appoint maintainers or reviewers, itself authorize delegation, or change issue
readiness. Follow the actual owner authorization and runtime/model policy for
each campaign; no standing delegation or default permissions are implied.

## Scope, ownership and architecture

- Use the canonical repository, `CompleteTech-DiscordApps/guildboard`. Inspect the
  live issue, stable GB ID, native blockers and open PRs before claiming work.
  Coordinate ownership with the maintainer and existing owner; preserve unrelated
  work and use a focused branch or isolated worktree. Do not create duplicate work.
- Read `docs/architecture.md`, the applicable `docs/workstreams/T*.md` and accepted
  ADRs. The scaffold and proposed contracts do not establish a working product.
  Do not implement unresolved runtime architecture across native research or
  specification blockers. The bounded configuration contract in
  `planning/configuration-contract.md` is an explicitly documented exception.
- Preserve the Activity/API/bot, shared contract, canvas adapter, collaboration,
  database and infrastructure boundaries. Version protocol/schema changes and
  document consumer compatibility, ownership and handoffs. Significant design
  changes require an ADR with alternatives, failure behavior and security effects.
  Avoid independently invented, incompatible synchronization or policy systems.

## Agent ownership and capacity

- In a user-authorized agent campaign, each immediate-parent directory containing
  changed files has exactly one logical directory orchestrator. Directory
  orchestrators are direct children of the lead. Nested filesystem directories
  add no delegation levels. The lead
  may also serve as the root directory orchestrator; do not create competing owners.
  One agent may hold several logical directory roles when capacity requires it.
- After the maintainer records the issue claim, lease each changed file
  exclusively to one file worker. File workers and
  reviewers are direct children of the responsible directory orchestrator. Record
  the exact path, owner, base SHA, branch/worktree and handoff receipt. File workers
  modify only their leased files; directory orchestrators reconcile and integrate
  completed handoffs. Preserve history and unrelated work. File workers and
  reviewers must not delegate or spawn agents.
- Reverify the actual available capacity and live occupancy before spawning;
  use the current session limit rather than a prior campaign's recorded limit.
  Count the lead and every live directory orchestrator, worker and reviewer. Queue
  work when full; never reuse a retired thread. Logical directory roles do not add slots or permit
  hidden parallel agents. Release completed leases and slots before assigning
  successors, and reserve capacity for independent review.

## Security and authorization review

- Treat client user, guild, channel, role, permission and administrator claims as
  untrusted. Verify Discord OAuth exchanges, least-privilege scopes, launch and
  interaction provenance, redirect/origin constraints, session binding, expiry,
  renewal and replay/CSRF defenses against the accepted identity contract. Keep
  bot tokens, OAuth credentials, sessions and board content out of logs and URLs
  where they could leak; use the private reporting route in `SECURITY.md`.
- Enforce deny-by-default policy on the backend for every read, mutation, command,
  upload, export and socket operation. UI read-only state is only feedback.
  Check current membership, role mapping, board visibility, mode, restrictions,
  object ownership and grant expiry as applicable. Prevent self-escalation,
  self-approval and moderator escalation. A socket handshake is not continuing
  authorization: role removal, revocation and emergency lockdown must fence
  in-flight writes and already-connected clients using the accepted policy
  generation/ordering contract. Use server time for grant expiry.
- Scope database queries, joins, caches, room names, operation/idempotency IDs,
  asset references, audit access and broadcasts by verified tenant and board.
  Attempt forged and guessed IDs, cross-guild and cross-board access, stale roles,
  expired grants and replay. Denials must have no unauthorized durable or broadcast
  side effects and must not leak another tenant's existence or content.
- Authorize request-to-draw, grant/revoke, lock/unlock and restriction transitions;
  record scoped actor, action, policy generation and outcome with audit integrity
  and appropriate retention. Lockdown must override ordinary writer grants.
- Validate imports/uploads by content as well as declared type; bound file size,
  decoded dimensions, element count and parser work. Prevent active-content/XSS,
  SQL injection, path traversal, unsafe filenames and unsafe remote fetch/SSRF.
  Keep assets private and scoped; authorize retrieval and deletion. Bound HTTP/WS
  payloads, rates, queues, connections, timers and storage per user/board/guild.
  Test resource exhaustion, slow consumers and cleanup without dropping accepted
  durable operations or affecting other tenants.

## Collaboration, persistence and recovery review

- Authenticate and scope WSS upgrades, room joins and reconnects; enforce accepted
  origin/proxy rules and versioned operation schemas. Server-sequence accepted
  intent with monotonic per-board revisions, scoped idempotency and explicit base
  revisions. Preserve canonical element identity, deterministic same-object
  conflicts, compound atomicity and revision-aware undo. Do not use naive
  full-document last-write-wins as a concurrency shortcut.
- Commit the operation, resulting durable state and receipt atomically before
  acknowledging acceptance. Test concurrent duplicate IDs, retry after lost ACK,
  rollback, process crash and restart; do not equate delivery exactly once with
  logical idempotency. Separate bounded, lossy ephemeral presence from durable
  edits and avoid exposing hidden participants.
- Test simultaneous edits, deletion/groups, mode and presenter changes, grant
  revocation races, delayed/duplicate/reordered frames, disconnect/reconnect,
  late join and slow clients. Compare canonical board hashes and revision history
  after quiescence. Snapshots need a consistent cut, bounded snapshot-plus-tail
  replay, lineage and retention rules; stale epochs must not resurrect content.
- Review MySQL/MariaDB tenant constraints, indexes, transactions and locking under
  concurrency. Migrations need version compatibility, interruption/retry behavior,
  data preservation and a documented rollback or forward recovery path. Prove
  backup plus assets/logs can restore into an isolated environment; measure achieved
  RPO/RTO. A backup file or a model-only test does not prove recoverability.

## Configuration, deployment and user experience

- Apply `planning/configuration-contract.md` exactly; invalid configuration must
  produce names-only diagnostics without secret values or side effects in pure
  parsing. Successful configuration contains credentials and must not be logged.
  Runtime entry points fail before binding on invalid config. Keep environment
  secrets separate, ignored and outside source/images; review rotation and access.
- Production targets a GoDaddy Linux VPS with Nginx HTTPS/WSS, private database
  and persistent assets. Review TLS renewal, Discord Activity proxy mappings,
  DNS/origins, WebSocket timeouts, least-privilege services, health checks, graceful
  shutdown, migration ordering, secret handling and rollback. Do not silently
  replace mandatory hosting or infer real Discord/VPS behavior from local mocks.
- For Activity/UI changes verify keyboard and focus behavior, labels and screen
  reader feedback, contrast, touch, reduced motion and responsive Discord
  viewports. Cover permission/request outcomes, loading, save state, reconnect and
  errors. Canvas interactions need practical accessible alternatives; automated
  accessibility scores alone are not acceptance.

## Validation and review

- Run `python3 scripts/github-bootstrap/validate.py` for planning changes and
  applicable focused behavior, integration, security and regression checks for
  implementation. Use the commands present on the current branch; do not invent
  a working app/build. Add meaningful allow/deny and no-side-effect tests for each
  changed authorization boundary, plus relevant concurrency and failure cases.
- Record exact commands, environment, tested full commit SHA, results and limits.
  Distinguish model/fixture tests, local integration, hosted CI, real Discord
  clients, real GoDaddy verification and post-merge acceptance. Research, a green
  planning check, a review request or merged documentation proves none of the
  untested runtime claims. Mark unavailable checks as pending or blocked.
- When an owner-authorized campaign requires Copilot review, obtain adequate
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

- Identify changed paths that [GitHub Copilot excludes from review](https://docs.github.com/en/copilot/reference/review-excluded-files).
  Record each excluded path and the reason. When the campaign allows it, a
  qualified independent reviewer covers those paths and their affected
  integration at the same full PR head SHA. This complements the required
  Copilot review of eligible paths. If GitHub excludes every changed path,
  record that scope and obtain authorized independent coverage of every
  path and affected integration. Keep the gate pending for any uncovered path. Honor any explicit Copilot-only STOP for both complementary review
  and fallback.
- On confirmed Copilot quota, access or service failure, record the evidence
  and reason. An inadequate completed review remains pending unless such a
  failure is confirmed. If the campaign explicitly authorizes fallback in that
  situation, a qualified independent reviewer may review the full PR at its
  current full head SHA, including relevant integration. Keep the gate pending
  if the authorized fallback is unavailable or incomplete.
- Independent reviewers must be fresh and qualified under the campaign's
  role, runtime and model policy. They must have no implementation role,
  make no writes and perform no delegation. Record reviewer identity,
  model/effort, full reviewed SHA, scope, findings, checks and limitations
  in a durable receipt. The technical gate requires current-head coverage
  of the complete delta through Copilot for eligible paths and complementary
  review for excluded paths, or an explicitly authorized complete fallback. Required functional
  and security expertise, CODEOWNER approval and all other native approvals
  still apply. This guidance authorizes no additional spend or delegation.
- Maintain a findings ledger covering every inline and summary finding from applicable
  reviews, its disposition, remediation SHA and verification evidence, including
  reasons for non-applicable findings. Remediate valid actionable findings and
  obtain qualified review again after any pushed head change, including code fixes;
  earlier reviews do not cover the new SHA. Read back the live full PR head,
  matching review evidence, findings dispositions and current checks before merge.
  Required native approvals, prerequisite gates and passing CI remain separate.
  Never bypass branch protection, use an administrator override, weaken tests or
  relabel blockers to manufacture readiness. Merge only with explicit authority.
- Link the relevant issue without closing directives until its full Definition
  of Done is satisfied. Do not close parent issues with incomplete mandatory
  descendants or claim a production release/deployment without dated evidence.
