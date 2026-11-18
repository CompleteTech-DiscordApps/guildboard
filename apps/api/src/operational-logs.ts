import { randomBytes } from "node:crypto";
import { clearTimeout, setTimeout } from "node:timers";
import { types } from "node:util";

const components = [
  "activity",
  "api",
  "bot",
  "collaboration",
  "persistence",
  "edge",
  "host",
  "recovery",
  "probe",
] as const;
const events = [
  "journey",
  "dependency",
  "admission",
  "durability",
  "lifecycle",
  "backup",
  "restore",
] as const;
const outcomes = [
  "success",
  "invalid_input",
  "authorization_denied",
  "dependency_unavailable",
  "saturated",
  "deadline_elapsed",
  "commit_unknown",
  "coverage_unknown",
  "interrupted",
  "integrity_failed",
] as const;
const logFields = ["schema_version", "utc", "component", "event", "outcome"] as const;
const scopeFields = ["journey", "board", "session", "startedAt"] as const;

export type OperationalLogV1 = Readonly<{
  schema_version: 1;
  utc: string;
  component: (typeof components)[number];
  event: (typeof events)[number];
  outcome: (typeof outcomes)[number];
  correlation?: string;
}>;

export type ClassifiedOperationalErrorV1 = OperationalLogV1 &
  Readonly<{ outcome: Exclude<OperationalLogV1["outcome"], "success"> }>;

/** Private server references established by the caller's authorization boundary. */
export type OperationalJourneyScope = Readonly<{
  journey: object;
  board: object;
  session: object;
  /** Time of first submission, from the boundary's monotonic clock. */
  startedAt: number;
}>;

export type OperationalLogResult<RecordType = OperationalLogV1> =
  | Readonly<{ status: "record"; record: RecordType }>
  | Readonly<{ status: "invalid_record" }>
  | Readonly<{ status: "coverage_unknown" }>;

type Options = Readonly<{
  maxCorrelations: number;
  correlationTtlMs: number;
  monotonicNow: () => number;
  /** Server-owned scheduler. Invoke the callback once, asynchronously, after the delay. */
  scheduleExpiry?: (expire: () => void, delayMs: number) => () => void;
}>;

type Correlation = Readonly<{
  token: string;
  expiresAt: number;
  cancelExpiry: () => void;
}>;

type JourneyIdentity = Readonly<{
  board: WeakRef<object>;
  session: WeakRef<object>;
  startedAt: number;
}>;

const maxTimerDelayMs = 2_147_483_647;

function scheduleHostExpiry(expire: () => void, delayMs: number): () => void {
  const timer = setTimeout(expire, delayMs).unref();
  return () => clearTimeout(timer);
}

function ownFields<Key extends string>(
  value: unknown,
  names: readonly Key[],
): Record<Key, unknown> | undefined {
  if (typeof value !== "object" || value === null || types.isProxy(value)) return undefined;
  const prototype: unknown = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return undefined;
  if (Reflect.ownKeys(value).length !== names.length) return undefined;
  const fields = Object.create(null) as Record<Key, unknown>;
  for (const name of names) {
    const descriptor = Object.getOwnPropertyDescriptor(value, name);
    if (!descriptor?.enumerable || !Object.hasOwn(descriptor, "value")) return undefined;
    fields[name] = descriptor.value;
  }
  return fields;
}

function hasValue<T extends string>(values: readonly T[], value: unknown): value is T {
  return typeof value === "string" && values.some((candidate) => candidate === value);
}

function isUtc(value: unknown): value is string {
  if (
    typeof value !== "string" ||
    (value.length !== 20 && value.length !== 24) ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$/.test(value)
  )
    return false;
  const canonical = value.length === 20 ? value.slice(0, -1) + ".000Z" : value;
  const time = new Date(value);
  return Number.isFinite(time.valueOf()) && time.toISOString() === canonical;
}

function privateReference(value: unknown): value is object {
  return typeof value === "object" && value !== null && !types.isProxy(value);
}

function readScope(value: unknown): OperationalJourneyScope | undefined {
  const scope = ownFields(value, scopeFields);
  if (!scope) return undefined;
  const { journey, board, session, startedAt } = scope;
  if (
    !privateReference(journey) ||
    !privateReference(board) ||
    !privateReference(session) ||
    typeof startedAt !== "number" ||
    !Number.isFinite(startedAt) ||
    startedAt < 0
  )
    return undefined;
  return { journey, board, session, startedAt };
}

function sameScope(identity: JourneyIdentity, scope: OperationalJourneyScope): boolean {
  return (
    identity.board.deref() === scope.board &&
    identity.session.deref() === scope.session &&
    identity.startedAt === scope.startedAt
  );
}

/** Build bounded records for a future approved sink. Options are server-owned. */
export function createOperationalLogBoundary({
  maxCorrelations,
  correlationTtlMs,
  monotonicNow,
  scheduleExpiry = scheduleHostExpiry,
}: Options) {
  if (
    !Number.isSafeInteger(maxCorrelations) ||
    maxCorrelations <= 0 ||
    !Number.isSafeInteger(correlationTtlMs) ||
    correlationTtlMs <= 0 ||
    typeof monotonicNow !== "function" ||
    typeof scheduleExpiry !== "function"
  )
    throw new RangeError("Invalid operational correlation configuration");

  const entries = new Map<object, Correlation>();
  // The journey owns its first identity even after its token is reclaimed.
  const identities = new WeakMap<object, JourneyIdentity>();
  const issued = new WeakSet<object>();
  let lastTime = 0;

  function readTime(): number | undefined {
    try {
      const now = monotonicNow();
      if (!Number.isFinite(now) || now < lastTime || now > Number.MAX_SAFE_INTEGER) return;
      lastTime = now;
      return now;
    } catch {
      return undefined;
    }
  }

  function removeEntry(journey: object, entry: Correlation): void {
    entries.delete(journey);
    entry.cancelExpiry();
  }

  function startExpiry(journey: object, remainingMs: number): () => void {
    let active = true;
    let cancel = scheduleNext(remainingMs);
    return () => {
      active = false;
      cancel();
    };

    function scheduleNext(remaining: number): () => void {
      const delay = Math.min(Math.ceil(remaining), maxTimerDelayMs);
      return scheduleExpiry(() => {
        if (!active) return;
        if (remaining > delay) {
          const now = readTime();
          const entry = entries.get(journey);
          if (now !== undefined && entry && entry.expiresAt > now) {
            try {
              cancel = scheduleNext(Math.min(remaining - delay, entry.expiresAt - now));
              return;
            } catch {
              // Reclaim immediately when the remaining lifetime cannot be scheduled.
            }
          }
        }
        active = false;
        entries.delete(journey);
      }, delay);
    }
  }

  function issueCorrelation(scope: OperationalJourneyScope): "available" | "coverage_unknown" {
    const trusted = readScope(scope);
    if (!trusted) return "coverage_unknown";
    const identity = identities.get(trusted.journey);
    if (identity && !sameScope(identity, trusted)) return "coverage_unknown";
    if (!identity) {
      identities.set(trusted.journey, {
        board: new WeakRef(trusted.board),
        session: new WeakRef(trusted.session),
        startedAt: trusted.startedAt,
      });
    }
    const now = readTime();
    if (now === undefined || trusted.startedAt > now) return "coverage_unknown";
    const expiresAt = trusted.startedAt + correlationTtlMs;
    if (expiresAt <= now || expiresAt > Number.MAX_SAFE_INTEGER) return "coverage_unknown";

    for (const [journey, entry] of entries) {
      if (entry.expiresAt <= now) removeEntry(journey, entry);
    }
    if (entries.has(trusted.journey)) return "available";
    if (issued.has(trusted.journey) || entries.size >= maxCorrelations) return "coverage_unknown";

    try {
      const token = randomBytes(16).toString("hex");
      const cancelExpiry = startExpiry(trusted.journey, expiresAt - now);
      entries.set(trusted.journey, { token, expiresAt, cancelExpiry });
      issued.add(trusted.journey);
      return "available";
    } catch {
      return "coverage_unknown";
    }
  }

  function makeRecord(
    input: unknown,
    scope: OperationalJourneyScope | undefined,
    errorOnly: true,
  ): OperationalLogResult<ClassifiedOperationalErrorV1>;
  function makeRecord(
    input: unknown,
    scope: OperationalJourneyScope | undefined,
    errorOnly: false,
  ): OperationalLogResult;
  function makeRecord(
    input: unknown,
    scope: OperationalJourneyScope | undefined,
    errorOnly: boolean,
  ): OperationalLogResult {
    const fields = ownFields(input, logFields);
    if (!fields) return { status: "invalid_record" };
    const { schema_version, utc, component, event, outcome } = fields;
    if (
      schema_version !== 1 ||
      !isUtc(utc) ||
      !hasValue(components, component) ||
      !hasValue(events, event) ||
      !hasValue(outcomes, outcome) ||
      (errorOnly && outcome === "success")
    )
      return { status: "invalid_record" };

    const record = { schema_version, utc, component, event, outcome } as const;
    if (scope === undefined) return { status: "record", record: Object.freeze(record) };

    const trusted = readScope(scope);
    if (!trusted) return { status: "coverage_unknown" };
    const entry = entries.get(trusted.journey);
    const identity = identities.get(trusted.journey);
    if (!entry || !identity || !sameScope(identity, trusted)) return { status: "coverage_unknown" };
    const now = readTime();
    if (now === undefined) return { status: "coverage_unknown" };
    if (entry.expiresAt <= now) {
      removeEntry(trusted.journey, entry);
      return { status: "coverage_unknown" };
    }
    return { status: "record", record: Object.freeze({ ...record, correlation: entry.token }) };
  }

  return {
    issueCorrelation,
    createRecord(input: unknown, scope?: OperationalJourneyScope): OperationalLogResult {
      return makeRecord(input, scope, false);
    },
    createClassifiedError(
      input: unknown,
      scope?: OperationalJourneyScope,
    ): OperationalLogResult<ClassifiedOperationalErrorV1> {
      return makeRecord(input, scope, true);
    },
  };
}
