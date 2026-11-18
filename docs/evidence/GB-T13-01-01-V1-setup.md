# GB-T13.01.01.V1 contributor setup and architecture verification

[Verification #425][verification] follows [setup #424][setup], which GitHub
reported closed as completed. The verification claim is recorded in
[comment 6966394357][claim]. This evidence is for the contributor journey and
feeds [GB-T13.01.01][parent] and the [T13 documentation gate][t13].

## Revision and environment

- Source: `f84a5f911c01dc9a02d7707bde19435a8157b0da`, extracted with
  `git archive --format=tar`. Archive SHA-256:
  `a69869e338e8f413114f1c08b6db6c98a12bb1ed0b568072d3719ee1b005bc67`.
- Local run began at `2026-11-18T01:41:00Z` on x86_64 Linux
  `7.2.15-1-omarchy`, Git 2.56.0, Node 24.22.3, npm 11.19.1 and Python 3.14.8.
  The archive began without Git metadata, dependencies, a populated
  `.env`, build manifests or workspace output. Installation used the
  prepopulated npm cache and isolated empty user/global npm configuration.
  The locked install exercised the setup guide's cached path.
- Evidence levels are local source review, local fixture and tool execution,
  and the specified hosted CI runs. No product server shipped with this
  setup, and Discord, database and GoDaddy credentials were unnecessary.

## Guide findings

| Guide and claim | Check and result |
| --- | --- |
| [README repository status][status] | The root package provides engineering scripts and a locked workspace. The Activity and bot source entry points are empty module boundaries. The API exposes bounded source modules for audit evidence, deletion jobs and resource admission without a serving entry point. All three application packages are private and have no executable or startup script. The README accurately describes the foundation and the absence of a runnable product, public website, Discord installation link or production deployment. |
| [Prerequisites and build][setup-guide] | Git supplies the revision, Node 24 and npm run the workspace checks, and Python runs planning validation. The guide allows either registry access or a populated cache. The locked install, generated manifest, missing-tool behavior and interrupted-build retry are covered below. |
| [Workspace boundaries][boundaries] | Compared all eight rows against the boundary checker's allow-list and verified the additional browser built-in restrictions for Activity, canvas and contracts. The independent boundary harness exercised permitted and denied edges and syntax forms. |
| [Configuration][config] | The five names, allowed ports and environments, structural MySQL URL checks, decimal Discord client ID and secret length/blank rules agree with the accepted parser contract. The example preserves blank secret values and labels future credentials separately. An invalid-input probe checked the exact names-only object. Configuration startup integration and credential verification belong to the service work. |
| [Planned system][system] and [interaction architecture][architecture] | Compared against accepted GB-T0.S1 and the [T0 handoff][t0]. The guides describe the server deriving identity and tenant scope from verified Discord and session evidence. HTTP/WSS and the bot share the command path with current permission checks, durable state/revision/receipt/outbox commit before an ACK, and a separate authorization fence for live delivery and recovery. SQL and assets stay private. ADR 0002 is proposed and the architecture presents these behaviors as planned. |
| Local cross-references | All 26 relative links in the README, architecture and setup guide resolved, including their referenced anchors. |

## Clean setup and failure scenarios

| Scenario | Command or observation | Evidence |
| --- | --- | --- |
| Locked install | `npm ci --ignore-scripts --offline` | 108 packages installed. SHA-256 of `package-lock.json` before and after was `79b589818e65a2694671013b5460681593dfdd2901ada23664a1549832e79e80`. |
| Tool unavailable | With `PATH` pointing to an empty directory, run `/bin/sh -c 'node --version'`. Verify dependencies and the build directory remain absent, then restore the supported Node path. | Shell returned 127 with `node: command not found`. The supported toolchain reported `v24.22.3` when restored. |
| Invalid configuration | Call the built parser with synthetic invalid port, URL and secret values and compare the exact result. | `{"ok":false,"error":{"code":"CONFIG_INVALID","invalidKeys":["DATABASE_URL","PORT","SESSION_SECRET"]}}` |
| Interrupt and recover | Run `node scripts/engineering/build.mjs` with the recipe's existing `ENGINEERING_BUILD_TEST_READY` and `ENGINEERING_BUILD_TEST_CONTINUE` barrier files in a temporary directory. Wait for readiness, send `SIGKILL`, then run `npm run build` and `npm run test:config` with the barrier variables unset. | Exit 137 left a nonempty pending manifest and no completed manifest. The retry published the original manifest hash, removed the pending file and passed all 20 configuration tests. |
| Other setup checks | `python3 scripts/github-bootstrap/validate.py`, `python3 scripts/verification/verify_architecture.py`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run boundaries`, and `node scripts/verification/verify_engineering.mjs`. | All commands exited 0. Planning validated 471 items, architecture matched seven accepted digests, and the boundary verifier passed 70 scenarios. |
| Full engineering suite | `npm run test:engineering` via [engineering workflow][hosted-exact]. | Passed on Ubuntu 26.04.1 LTS with Node 24.22.2 and npm 11.19.1. 61 engineering and 20 configuration tests passed with zero failures and skips. The interruption fixture passed and the independent boundary verifier passed 70 scenarios. |
| Configuration CI | `npm ci --ignore-scripts`, `npm run typecheck:config`, `npm run test:config`, `node scripts/verification/verify_config.mjs`, and `node scripts/verification/verify_config_failure_paths.mjs` via [configuration workflow][hosted-config]. | Passed on Ubuntu 26.04.1 LTS with Node 24.22.2 and npm 11.19.1. 20 tests passed with zero failures and skips. The parser harness reported 131,125 scenarios, 262,252 assertions and zero effects. The failure harness passed all three probes. |

The earlier [engineering job for #424][hosted-prereq] covered
`ff85c0b84e47a32cdc40295ef6133e2d640a6b07` and passed 35 engineering
and 20 configuration tests. A local broad run at that earlier revision
passed 34 of 35 engineering tests and failed with
`build never reached handshake:` at the roughly 60-second interruption
fixture limit. The separate local interruption of the real recipe at that
revision returned 137, left a pending manifest and no completed manifest,
and the clean retry succeeded with 20 configuration tests passing.
Git trees for the three guides are identical at the earlier and tested
revisions. The build recipe and engineering tests changed, so exact
`f84a5f911c01dc9a02d7707bde19435a8157b0da` results have their own entries above.

No guide mismatch was found in the reviewed scope. Discord Activity launch,
iframe, proxy and real-client behavior and GoDaddy HTTPS/WSS, private database,
assets and deployment remain separate acceptance work. The reproducible
fixture and tooling results here cover the scope of the contributor setup.

## Raw results

Both linked hosted job logs show checkout at the full tested SHA, toolchain
versions, per-test output and the complete workflow result. Relevant raw
output lines appear below.

```text
✔ interruption before publication leaves no completion (9780.857957ms)
ℹ tests 61
ℹ pass 61
ℹ fail 0
ℹ skipped 0
PASS 70 independent scenarios
ℹ tests 20
ℹ pass 20
ℹ fail 0
{"status":"passed","scenarios":131125,"assertions":262252,"effects":0}
{"status":"passed","checks":["missing-compiled-module","interrupted-before-continuation","handshake-continuation"]}
```

The local content and link check reported:

```text
PASS README.md: 10 local links and referenced anchors
PASS docs/architecture.md: 8 local links and referenced anchors
PASS docs/development.md: 8 local links and referenced anchors
PASS development import table: 8 exact workspace rows
PASS Activity/API/bot are private module workspaces with no executable or service script
```

Selected lines from the clean archive transcript are reproduced below. The interruption assertions run before the retry.

```text
/bin/sh: line 1: node: command not found
+ missing_status=127
+ test 127 -eq 127
  "result": "pass",
  "item_count": 471,
PASS: seven accepted artifact digests match; runtime behavior not tested
added 108 packages in 18s
All matched files use Prettier code style!
Workspace boundaries valid
+ npm run build
+ test -s engineering-build/manifest.json
PASS 70 independent scenarios
{"ok":false,"error":{"code":"CONFIG_INVALID","invalidKeys":["DATABASE_URL","PORT","SESSION_SECRET"]}}
7fbe82d22aa92707255eb6cd92d9a299694cb5ce69a658b36a3f693ef2f9120f  engineering-build/manifest.json
+ interruption_status=137
+ test 137 -eq 137
+ test -s engineering-build/manifest.pending
+ test '!' -e engineering-build/manifest.json
+ npm run build
+ test -s engineering-build/manifest.json
+ test '!' -e engineering-build/manifest.pending
7fbe82d22aa92707255eb6cd92d9a299694cb5ce69a658b36a3f693ef2f9120f  engineering-build/manifest.json
+ npm run test:config
ℹ tests 20
ℹ pass 20
ℹ fail 0
ℹ skipped 0
Focused clean setup and negatives complete
```

[verification]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/425
[setup]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/424
[claim]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/425#issuecomment-6966394357
[parent]: https://github.com/CompleteTech-DiscordApps/guildboard/issues/423
[t13]: ../workstreams/T13.md#evidence-and-handoff
[status]: ../../README.md#foundation-status
[system]: ../../README.md#planned-system
[setup-guide]: ../development.md#local-foundation-setup
[boundaries]: ../development.md#workspace-boundaries
[config]: ../development.md#configuration-parser
[architecture]: ../architecture.md#interaction-architecture-gb-t00102t1
[t0]: ../workstreams/T0.md#t0-integration-and-handoff
[hosted-prereq]: https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/44213341436
[hosted-exact]: https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/44217461932/job/134510764795
[hosted-config]: https://github.com/CompleteTech-DiscordApps/guildboard/actions/runs/44217461929/job/134510765026
