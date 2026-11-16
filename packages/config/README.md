# @guildboard/config

Private ESM TypeScript package targeting ES2022. Includes the pure `parseConfig` facade for [GB-T0.03.02.T1 / #23](https://github.com/CompleteTech-DiscordApps/guildboard/issues/23), built on the secret-safe diagnostics (#451) and numeric/URL helpers (#452). Service startup wiring is separate. Independent acceptance (#24), required reviews, merge and post-merge verification remain outstanding.

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

## Numeric and URL checks

[GB-T0.03.02.T1.S2 / #452](https://github.com/CompleteDotTech/guildboard/issues/452) adds pure `parsePort(value)` and `parseDatabaseUrl(value)` helpers. Each takes `string | undefined` and returns the accepted value (`number` or original URL string), or `undefined` for a failed check. `parseConfig` aggregates failed names through `createConfigFailure`; helper success alone does not establish valid configuration.

`parsePort` accepts ASCII decimal digits, including leading zeroes, only when the numeric value is in 1–65535. Signs, whitespace (including a final newline), fractions, exponents, alternate bases, Unicode digits and overflow fail. `parseDatabaseUrl` uses the platform URL parser and requires normalized protocol `mysql:`, a nonempty hostname and a path beyond `/`; query/fragment text cannot supply a missing database path. Scheme case follows URL parsing rules. Accepted URL input is preserved exactly, including credentials/encoding; **do not log it**. Caught URL errors are discarded because they may retain the input.

This is structural validation, not a database connection, driver compatibility, hostname reachability, TLS-policy or production readiness check. URL normalization and connector behavior need separate integration coverage. The helpers never read global environment, mutate input, open connections or exit. Both helper test files run through `npm run test:config`; boundary, malformed-input and no-output/caller-continuation checks require no credentials or infrastructure.

## Full configuration parser

```ts
import { parseConfig } from "@guildboard/config";
import type { AppConfig, ConfigResult } from "@guildboard/config";

const result: ConfigResult = parseConfig(environmentProvidedByCaller);
if (!result.ok) {
  // Only CONFIG_INVALID and canonical invalid/missing names are present.
  // The service caller decides how to report this and stop before binding.
  handleInvalidConfiguration(result.error);
} else {
  const config: AppConfig = result.value;
  // Pass config directly to trusted startup code; never log or serialize it.
}
```

All five keys are required. `NODE_ENV` is exactly `development`, `test` or
`production`. `DISCORD_CLIENT_ID` contains only nonempty ASCII decimal digits
and remains a string, preserving leading zeroes and values beyond numeric safe
integer precision. `SESSION_SECRET` must have at least 32 JavaScript string
characters and cannot consist entirely of whitespace; accepted secrets are not
trimmed. This structural length check is not an entropy or strength guarantee.
Generate and rotate secrets securely in the separate deployment/security work.

The parser reads only the five named properties from its input and never mutates
or retains the input map. Unrelated variables are ignored. It collects every
failed name and returns a fresh failure object with sorted unique canonical
names, never input values or thrown URL exceptions. Successful values include
credentials: **do not log the success result, configuration or raw environment**.
There are no defaults, global `process.env` reads, logging, network calls,
listeners or exit calls. The TypeScript API expects an environment record of
strings/undefined, not arbitrary objects with throwing property accessors.

The full facade tests cover all-missing/empty values, simultaneous failures,
required boundaries and malformed forms, exact string preservation, unrelated
properties, immutable input, unexpected JavaScript field types, a throwing global
environment guard and captured child-process stdout/stderr with sentinel secrets.
No real Discord application, database, VPS or runtime service is verified.
