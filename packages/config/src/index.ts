/** Names allowed in diagnostics. Values and arbitrary environment names are never copied. */
const CONFIG_KEYS = Object.freeze([
  "DATABASE_URL",
  "DISCORD_CLIENT_ID",
  "NODE_ENV",
  "PORT",
  "SESSION_SECRET",
] as const);

export type ConfigKey = (typeof CONFIG_KEYS)[number];

export type ConfigFailure = {
  ok: false;
  error: {
    code: "CONFIG_INVALID";
    invalidKeys: string[];
  };
};

/**
 * Build the failure variant consumed by the future parseConfig implementation.
 * Select from canonical names rather than serializing the caller's input. This
 * also prevents unexpected runtime values from becoming diagnostic content.
 * The caller owns validation; this function does not inspect the environment.
 */
export function createConfigFailure(invalidKeys: readonly ConfigKey[]): ConfigFailure {
  const invalid = new Set(invalidKeys);
  return {
    ok: false,
    error: {
      code: "CONFIG_INVALID",
      invalidKeys: CONFIG_KEYS.filter((key) => invalid.has(key)),
    },
  };
}
