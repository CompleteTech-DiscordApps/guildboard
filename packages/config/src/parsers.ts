/** Parse ASCII decimal whole ports. Undefined represents a failed check. */
export function parsePort(value: string | undefined): number | undefined {
  if (typeof value !== "string" || value.length === 0 || /[^0-9]/.test(value)) {
    return undefined;
  }
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535 ? port : undefined;
}

/**
 * Check the URL structure required by the configuration contract, without IO.
 * Preserve accepted input exactly; it may contain credentials and must not be logged.
 */
export function parseDatabaseUrl(value: string | undefined): string | undefined {
  if (typeof value !== "string" || value.length === 0) {
    return undefined;
  }
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "mysql:" || parsed.hostname.length === 0 || parsed.pathname.length <= 1) {
      return undefined;
    }
    return value;
  } catch {
    // URL exceptions may retain the original credential-bearing input.
    return undefined;
  }
}
