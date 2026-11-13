# @guildboard/config

Private ESM TypeScript package targeting ES2022. Current deliverable: [GB-T0.03.02.T1.S1 / #451](https://github.com/CompleteDotTech/guildboard/issues/451), the secret-safe diagnostic failure variant. The complete `parseConfig` function and service startup wiring remain [parent issue #23](https://github.com/CompleteDotTech/guildboard/issues/23) work.

```ts
import { createConfigFailure } from "@guildboard/config";

const failure = createConfigFailure(["PORT", "DATABASE_URL", "PORT"]);
// { ok: false, error: { code: "CONFIG_INVALID", invalidKeys: ["DATABASE_URL", "PORT"] } }
```

Pass names of failed checks, never their values. The helper returns only a fixed code and sorted, unique names from the five-key contract. Unknown runtime names/values are omitted defensively; they do not establish valid configuration. Even an empty name list returns failure. Validation and identifying missing/invalid keys belong to the caller. Each returned array is independent.

The helper does not read `process.env`, log, perform IO or exit. A future service entry point can translate a `parseConfig` failure into a nonzero exit before binding any listener. Do not log successful configuration objects: they contain the database URL and session secret. Never attach raw environment maps or validation-library exceptions to an error response. Diagnostics are suitable for internal startup logs, not a public configuration-discovery endpoint.

From the repository root, with Node 24 and npm:

```sh
npm ci --ignore-scripts
npm run typecheck:config
npm run test:config
```

Tests compile TypeScript and run Node's built-in test/assert runner against the output. Coverage includes a names-only snapshot, sorting/deduplication, immutable inputs, sentinel-value rejection, hostile conversion hooks, fresh arrays and a child process that must continue without stdout/stderr leakage. No Discord, database or GoDaddy access is required or tested.

Tooling is pinned in the root lockfile. See [tooling dependency notes](../../docs/tooling-dependencies.md) for the limited license/audit review; application supply-chain acceptance remains separate work.
