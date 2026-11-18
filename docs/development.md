# Development setup

<a id="local-foundation-setup"></a>
## Build and test the repository foundation

Use a fresh Linux checkout, Git, Node.js 24 with npm, Python 3.11 or later, and writable checkout and temporary directories. Dependency installation needs access to the npm registry or a populated cache for the committed lockfile. The checks use local fixtures and require no `.env`, Discord credentials, database server or GoDaddy VPS.

From the checkout root, confirm the toolchain and run the checks in order.

```sh
git rev-parse HEAD
node --version
npm --version
python3 --version
python3 scripts/github-bootstrap/validate.py
npm ci --ignore-scripts
npm run lint
npm run typecheck
npm run format:check
npm run boundaries
npm run test:engineering
npm run build
npm run test:config
node scripts/verification/verify_engineering.mjs
```

Use Node 24 if the version check shows a different major. If a tool is missing, install it or select the installed toolchain on your PATH, check its version, and repeat the sequence from the root. If dependency installation fails, resolve the registry or cache failure and rerun `npm ci --ignore-scripts`. Use npm to regenerate the lockfile when changing dependencies.

The build compiles workspace sources and emits `engineering-build/manifest.json` after every workspace succeeds. Typecheck removes the previous manifest and emits declarations for workspace resolution. If a build fails or is interrupted, partial `dist` files can remain. After the build process stops, rerun `npm run build` and confirm it exits successfully and produces a fresh manifest. Then rerun `npm run test:config`. The manifest attests to a completed engineering build. The Activity, API and bot remain scaffolds.

GitHub CLI is needed only for remote planning operations. Authenticate with the required read access for `python3 scripts/github-bootstrap/audit.py`. Follow the [bootstrap guide](../scripts/github-bootstrap/README.md) for any authorized remote mutation.

<a id="configuration-parser"></a>
## Configuration

The pure [configuration parser](../packages/config/README.md) accepts an environment map supplied by its caller. The [configuration contract](../planning/configuration-contract.md) requires these five names and defines their validation.

| Name | Required value |
| --- | --- |
| `PORT` | ASCII decimal port from 1 to 65535 |
| `NODE_ENV` | `development`, `test` or `production` |
| `DATABASE_URL` | MySQL URL with a host and database path |
| `DISCORD_CLIENT_ID` | Nonempty string of ASCII decimal digits |
| `SESSION_SECRET` | At least 32 JavaScript string characters with at least one non-whitespace character |

Invalid input returns `CONFIG_INVALID` and sorted, unique variable names. The parser performs structural checks without reading the process environment, opening a connection or binding a port. Keep populated `.env` files out of source control and keep development, staging and production secrets separate. Avoid logging a successful result or the raw environment because they can contain credentials. `DISCORD_CLIENT_SECRET` and `DISCORD_BOT_TOKEN` in [the environment example](../.env.example) are placeholders for future service integration. Startup wiring and credential verification remain separate work.

<a id="workspace-boundaries"></a>
## Workspace boundaries

| Workspace | Permitted workspace imports | Intended responsibility |
| --- | --- | --- |
| `apps/activity` | contracts, canvas | Discord Activity UI and HTTPS/WSS client |
| `apps/api` | contracts, config, auth, collaboration | Server-side session and HTTP/WSS entry points |
| `apps/bot` | contracts, config, auth, collaboration | Verified Discord interactions and moderation commands |
| `packages/contracts` | None | Shared versioned interfaces |
| `packages/canvas` | contracts | Editor adapter |
| `packages/auth` | contracts | Identity evidence and scoped access policy |
| `packages/collaboration` | contracts, auth | Authorized operations, sequencing and recovery |
| `packages/config` | None | Server-only configuration parsing |

Apps cannot import each other. Activity, canvas and contracts cannot import Node built-ins. The [boundary checker](../scripts/engineering/boundaries.mjs) evaluates workspace source and tests, including type imports and local aliases. The checker enforces repository import rules. Runtime authorization belongs to the service boundaries.

<a id="planned-auth-and-data-flow"></a>
## Planned authentication and data flow

The [architecture guide](architecture.md) describes the Activity, API, bot, collaboration and data flows under the [accepted T0 boundaries](workstreams/T0.md#t0-integration-and-handoff). In the planned runtime, the server verifies session and Discord evidence before deriving tenant scope. Client-supplied roles and board selectors carry no authority. HTTP, WSS and bot mutations use a shared authorization and command path. State, revision, receipt and accepted event commit together in private storage. The server rechecks read authority before releasing protected data and before replay or snapshot recovery. SQL and assets stay private behind the service boundary.

<a id="setup-verification-handoff"></a>
## Setup verification handoff

The maintainer and documentation owner coordinates setup and architecture consumer review for [GB-T13.01.01.T1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/424). For [GB-T13.01.01.V1](https://github.com/CompleteTech-DiscordApps/guildboard/issues/425), record the exact archive revision, OS, tool versions and raw command outputs. Alongside the clean run, exercise a missing local tool, the names-only invalid-config result, and an engineering build interrupted before manifest publication followed by a successful retry. The engineering and configuration test suites contain focused scenarios for those build and parser boundaries.

The [T13 handoff](workstreams/T13.md#evidence-and-handoff) tracks independent verification. Runtime behavior, Discord client/proxy integration and GoDaddy deployment require separate acceptance evidence.
