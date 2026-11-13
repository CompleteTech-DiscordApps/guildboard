# T6 presenter/follow experiment v0 — research only

Issue: [GB-T6.R1 / #196](https://github.com/CompleteTech-DiscordApps/guildboard/issues/196).
Evidence date: 2026-10-25. Base: `da811252acc975a0e5a1b087ab653b523443f3fa`.
This is **not product integration, an accepted architecture, or the blocked #197
specification**. It imports no runtime dependencies and does not implement T2
roles/grants, T4 transport or canvas rendering. #196 remains incomplete.

## Scope and live readiness evidence

Exact API reads on the evidence date: #196 full body, its comments (empty),
`issues/196/dependencies/blocked_by` (empty), parent #195 and consumer #197.
#196 explicitly permits independent research; #197 has one native blocker (#196).
The initial Ready field in the issue is not a claim that the live Project was
revalidated. No claim/assignment, Project, issue or PR was changed. Parent T6
consumes T2 write grants, T4 transport and T7 accessible shell controls. This
experiment consumes trusted policy decisions rather than choosing their contracts.

## Decision candidates and concrete counterexamples

1. **Presenter user + sequence only:** rejected by the executable Alice → revoked
   → Alice counterexample. An old Alice packet at seq 99 is still the same user
   and can overwrite a new seq 0 stream. Candidate: a board-scoped authority epoch
   advanced on every accepted control transition, plus monotone packet sequence.
2. **Presentation as a content-write mode:** not selected. Candidate: presentation
   is an orthogonal authority overlay on open/moderated/locked/request-to-draw.
   Follow and presenter status cannot produce write rights. T2 supplies the
   current mode-aware write decision; locked is an additional hard denial.
   The final mode/role/grant matrix belongs to #197 and T2, not this model.
3. **Save displayed viewport on every Follow click:** rejected by the second
   executable counterexample: clicking Follow twice overwrites personal navigation
   with the presenter's viewport. Candidate: keep personal and displayed state
   separate, make Follow idempotent, and restore personal view on Unfollow.
4. **Implicit follow after reconnect/change:** not selected in this experiment.
   Candidate: trusted snapshot clears follow, restores personal view and requires
   explicit rejoin. Mode transitions conservatively revoke presenter unless an
   explicit presenter is supplied atomically. Whether continuity is preferable,
   how grants/requests survive mode changes, and disconnect grace duration remain
   product/specification decisions; no guessed timers or grant lifecycle added.
5. **Retain the sequence watermark without its presenter viewport:** rejected by
   the follow/rejoin regression. After seq10, Unfollow or a same-stream reconnect
   restores personal navigation; explicit Follow must restore the cached seq10
   presenter viewport immediately while duplicate seq10 remains rejected. Cache
   the latest admitted presenter view with its watermark even while unfollowed,
   preserving both across same-stream snapshots. A scope switch resets displayed
   and personal navigation, while retaining only that scope's stream cache for
   safe explicit rejoin. An epoch change clears that stream's cache. New streams
   show personal navigation until their first admitted packet. Personal navigation
   remains separate throughout.

These are recommendations for review, not accepted policy. Sequence-only can be
made safe with an independently scoped stream identifier: that is equivalent to
adding the missing lifetime fence, not evidence against epochs.

## Model boundary and results

`Authority` is trusted board-scoped current state. `control_allowed`,
`current_t2_write_allowed`, `session_valid`, and `scope_matches` are trusted
hypothetical server decisions, **not values accepted from a browser**. Likewise
`Packet.sender` represents authenticated session identity after identity binding,
not a client-asserted user field. Tests using Mallory exercise this identity
comparison, not OAuth/Discord authentication. `snapshot` receives a trusted
current authority snapshot, not an arbitrary untrusted wire object. No JSON
schema, socket, database transaction, membership resolution, or authorization
cache is implemented.

The publication gate checks current read/session eligibility and presenter scope,
identity and epoch. It does not track server sequence replay or rate limits;
receiver ordering prevents duplicate/old delivery from moving a following viewer.
A production protocol must bind sequence state to authenticated stream lifetime,
bound publication frequency, and invalidate sessions/tenant membership correctly.
Revocation becomes visible to the model receiver when a trusted snapshot arrives;
this does **not** prove immediate client-side revocation over a delayed network.
The server rejects newly submitted old-epoch events after its transition step.

Suggested viewport bounds for this experiment only: finite x/y ±1,000,000,
zoom 0.1–10, safe-integer sequence 0–2^53−1. Bool-as-number, NaN, infinity,
wrong board/guild, wrong presenter, stale epoch and invalid sequence are rejected
without state changes. Wire parsing and malicious object types are not modeled.

Reproduce from repository root (Python **3.12+**, standard library only):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiments/t6-presentation -v
python3 scripts/github-bootstrap/validate.py
git diff --check
```

Initial v0 evidence used Python **3.12.14** with 12 tests. Review remediation on
2026-10-25 used Python **3.14.3** on Windows: **14 tests pass**, including all 64
combinations of four mode values,
trusted T2 allow/deny, session valid/invalid, scope match/mismatch and presenter
present/absent; 24 packet permutations replayed twice; both concurrent CAS control
orders; negative publication/control cases and the research counterexamples. Regression
cases additionally reject huge integers without float overflow and retain the
same-stream sequence watermark across reconnect (seq10 then delayed seq1).
Displayed-viewport regressions cover Unfollow/rejoin, navigation/rejoin and
same-stream reconnect/rejoin without a newer packet, plus epoch and guild/board
reset. The three rejoin assertions failed before that remediation and passed
after it. That historical version reset the watermark and cached presenter
viewport on a scope change; the follow-up below corrects its round-trip gap. These are
bounded deterministic schedules, not exhaustive distributed-state verification.
Calls serialize atomically in memory; there is no claim about transaction locks,
multi-process behavior, fairness, persistence, liveness, or real network ordering.

## 2026-11-12 follow-up: passive receipt and scope round trips

The current model passes **18 tests**. New regressions first failed against the
previous candidate `d480b5d99af8acfd4b493fac94e958392f9493d0`: a valid update while
unfollowed was lost, and A → B → A reopened A's old sequence numbers. `receive`
now updates the current stream's sequence/cache while unfollowed without changing
personal or displayed navigation. Explicit first Follow and rejoin use the latest
admitted view even if the presenter sends nothing afterward. Invalid, stale-epoch,
foreign-scope and duplicate packets cannot change that cache.

A trusted snapshot switch retains per-scope authority revision, sequence and
presenter view in an **eight-scope maximum** in-memory history. Returning to A
resets personal/displayed navigation; explicit Follow restores only A's own
same-epoch view and watermark. Older authority snapshots for a known scope are
rejected. A newer epoch resets that scope's stream, and packets from its old
epoch remain rejected. The history never caches personal navigation or imports
another scope's view into the active display.

This finite research model never evicts a replay fence: a ninth distinct scope
raises `ValueError` without changing the caller's immutable Viewer. Recovery
requires a fresh validated stream baseline, which is deliberately not modeled.
The limit is an experiment bound, not an accepted UI limit, wire contract, or
production subscription design. The tests cover first Follow, rejoin after an
unfollowed update, same-guild/cross-guild round trips, stale authority, new epochs,
invalid packets and no-state-change history exhaustion. Exact candidate and raw
validation logs are in the campaign handoff; no real transport or client ran.

## Primary sources and evaluated versions

- [Discord Activities overview](https://docs.discord.com/developers/activities/overview),
  live unversioned documentation retrieved 2026-10-25: Activities run in iframes on
  desktop, mobile and web. This motivates separate client validation; it supplies
  no Guildboard presenter protocol or permission guarantee. **No SDK version is
  evaluated** here, since no SDK is installed/executed.
- [Excalidraw props](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props/),
  live unversioned documentation retrieved 2026-10-25: exposes `viewModeEnabled`
  and `onScrollChange`. These are potential UI adapter surfaces, not a security
  boundary. **No Excalidraw package version is evaluated** here. The separate
  #98 pinned-library experiment remains the source for its own versioned evidence.
- Repository [T6 requirements](../../docs/workstreams/T6.md) and
  [initial architecture constraints](../../docs/architecture.md), evaluated at
  the base commit above: current policy and tenant scope must govern mutations.
  That document itself labels its architecture a proposal.

The only executable evaluated version is model **v0**, initially on Python
**3.12.14** and on Python **3.14.3** for the follow/rejoin remediation.
No primary source is being represented as proving a candidate product choice.

## Acceptance mapping and remaining evidence

| #196 scope | Observable evidence | Still open |
| --- | --- | --- |
| Presenter authority / concurrent mode changes | CAS both orders; revoke/regrant ABA test; stale and forged identity tests | Reviewed T2/T4 contracts, server integration, disconnect policy |
| Follow / personal navigation | Idempotence, personal-view restore, immediate explicit rejoin from cached presenter view, replay rejection, scoped/epoch snapshot tests | Real canvas coordinate conversion and UI behavior |
| Across Discord clients | Primary source identifies desktop/web/mobile applicability | All actual desktop/web/mobile results; iframe/proxy behavior |
| Alternatives / versions / uncertainty | Counterexamples and source/version notes above | Functional, security and consumer review; accepted decision |

Required later real-client matrix: desktop, web and mobile, each with viewer and
writer, run designate/revoke/reassign presenter; follow, pan/zoom, unfollow and
rejoin; reconnect after mode change; late/duplicate delivery; cross-board switch.
Record exact SDK/editor/build/OS/client versions and dates. Check keyboard-only
controls, focus retention, screen-reader status announcements without cursor
noise, narrow layouts and reduced-motion behavior. None is tested by Python.
Do not retry the previously denied browser launch to manufacture this evidence.
GoDaddy Linux VPS HTTPS/WSS remains mandatory; infrastructure, proxy and load
claims are not applicable to this pure model and require later real-environment
verification. No credentials or production infrastructure are touched.

For #197 review: decide overlay versus mutually exclusive presentation mode,
mode/grant/queue lifecycle, disconnect/reconnect continuity, trusted snapshot
ordering, stream sequencing and rate bounds, viewport representation and
accessibility acceptance. Route functional review to Frontend & Canvas expertise,
security review to policy/identity expertise and integration review to T2/T4/T7
consumers. No actual human approval, merge, deployment or issue completion is
claimed by these artifacts.
