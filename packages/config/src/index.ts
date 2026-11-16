import { parseDatabaseUrl, parsePort } from "./parsers.js";

/** Names allowed in diagnostics. Values and arbitrary environment names are never copied. */
const CONFIG_KEYS = Object.freeze([
  "DATABASE_URL",
  "DISCORD_CLIENT_ID",
  "NODE_ENV",
  "PORT",
  "SESSION_SECRET",
] as const);

export type ConfigKey = (typeof CONFIG_KEYS)[number];

export { parseDatabaseUrl, parsePort } from "./parsers.js";

export type ConfigFailure = {
  ok: false;
  error: {
    code: "CONFIG_INVALID";
    invalidKeys: string[];
  };
};

/**
 * Build the failure variant consumed by parseConfig.
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

export type AppConfig = Readonly<{
  port: number;
  nodeEnv: "development" | "test" | "production";
  databaseUrl: string;
  discordClientId: string;
  sessionSecret: string;
}>;

export type ConfigResult = { ok: true; value: AppConfig } | ConfigFailure;

/** Validate only the supplied environment. Never log the credential-bearing result. */
export function parseConfig(env: Readonly<Record<string, string | undefined>>): ConfigResult {
  const port = parsePort(env.PORT);
  const databaseUrl = parseDatabaseUrl(env.DATABASE_URL);
  const nodeEnv = env.NODE_ENV;
  const discordClientId = env.DISCORD_CLIENT_ID;
  const sessionSecret = env.SESSION_SECRET;
  const validNodeEnv = nodeEnv === "development" || nodeEnv === "test" || nodeEnv === "production";
  const validClientId = typeof discordClientId === "string"
    && discordClientId.length > 0 && !/[^0-9]/.test(discordClientId);
  const validSecret = typeof sessionSecret === "string"
    && sessionSecret.length >= 32 && /\S/u.test(sessionSecret);

  const invalid: ConfigKey[] = [];
  if (port === undefined) invalid.push("PORT");
  if (databaseUrl === undefined) invalid.push("DATABASE_URL");
  if (!validNodeEnv) invalid.push("NODE_ENV");
  if (!validClientId) invalid.push("DISCORD_CLIENT_ID");
  if (!validSecret) invalid.push("SESSION_SECRET");

  if (port === undefined || databaseUrl === undefined || !validNodeEnv || !validClientId || !validSecret) {
    return createConfigFailure(invalid);
  }
  return { ok: true, value: { port, nodeEnv, databaseUrl, discordClientId, sessionSecret } };
}
