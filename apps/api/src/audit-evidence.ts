import { createHash, randomUUID } from "node:crypto";
import { types } from "node:util";

type ActorKind = "user" | "system" | "operator";
type Outcome = "accepted" | "denied" | "failed";
type Reason = "completed" | "forbidden" | "stale-authority" | "dependency-unavailable";
export type AuditScope =
  | { readonly kind: "system" }
  | { readonly kind: "guild"; readonly guildRef: string }
  | { readonly kind: "board"; readonly guildRef: string; readonly boardRef: string };

// Finite v1 profile for this server module. A production adopter needs the
// registry, rights matrix and retention/custody approval in GB-T9.S1.
const actions = {
  grant: { scopes: ["board"], actors: ["user", "system"], policy: true },
  revoke: { scopes: ["board"], actors: ["user", "system"], policy: true },
  lock: { scopes: ["board"], actors: ["user", "system"], policy: true },
  unlock: { scopes: ["board"], actors: ["user", "system"], policy: true },
  restriction: { scopes: ["guild", "board"], actors: ["user", "system"], policy: true },
  "role-mapping": { scopes: ["guild"], actors: ["user", "system"], policy: true },
  deletion: { scopes: ["guild", "board"], actors: ["operator", "system"], policy: true },
  restore: { scopes: ["guild", "board"], actors: ["operator", "system"], policy: true },
  "evidence-access": { scopes: ["system", "guild", "board"], actors: ["operator"], policy: false },
  "security-administration": {
    scopes: ["system", "guild"],
    actors: ["operator", "system"],
    policy: true,
  },
} satisfies Record<string, { scopes: AuditScope["kind"][]; actors: ActorKind[]; policy: boolean }>;

export type AuditAction = keyof typeof actions;
export interface AuditEventV1 {
  readonly version: 1;
  readonly eventId: string;
  readonly occurredAt: string;
  readonly actorKind: ActorKind;
  readonly actorRef: string;
  readonly scope: AuditScope;
  readonly action: AuditAction;
  readonly outcome: Outcome;
  readonly reason: Reason;
  readonly policyGeneration?: string;
  readonly correlationId: string;
}

type ParseResult =
  | { readonly ok: true; readonly event: AuditEventV1 }
  | { readonly ok: false; readonly fields: readonly string[] };

const eventFields = [
  "version",
  "eventId",
  "occurredAt",
  "actorKind",
  "actorRef",
  "scope",
  "action",
  "outcome",
  "reason",
  "correlationId",
] as const;
const actorKinds: readonly ActorKind[] = ["user", "system", "operator"];
const reasons: Record<Outcome, readonly Reason[]> = {
  accepted: ["completed"],
  denied: ["forbidden", "stale-authority"],
  failed: ["dependency-unavailable"],
};
const maxCounter = "18446744073709551615";
const rootHash = "0".repeat(64);
export const AUDIT_MAX_RECORDS = 4096;

function fieldsOf(value: unknown): Record<string, unknown> | undefined {
  if (typeof value !== "object" || value === null || types.isProxy(value)) return undefined;
  const prototype: unknown = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return undefined;
  const fields: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
  // No inherited values, accessors, symbols or hidden fields.
  const keys = Reflect.ownKeys(value);
  if (keys.length > eventFields.length + 1) return undefined;
  for (const key of keys) {
    if (typeof key !== "string") return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor?.enumerable || !Object.hasOwn(descriptor, "value")) return undefined;
    fields[key] = descriptor.value;
  }
  return fields;
}

function hasOnly(fields: Record<string, unknown>, names: readonly string[]): boolean {
  return Object.keys(fields).every((key) => names.includes(key));
}

function opaqueId(value: unknown): value is string {
  // Internally minted lowercase v4 UUIDs, never raw Discord identifiers.
  return (
    typeof value === "string" &&
    value.length === 36 &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value)
  );
}

function utc(value: unknown): value is string {
  if (
    typeof value !== "string" ||
    value.length !== 24 ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)
  )
    return false;
  const date = new Date(value);
  return Number.isFinite(date.valueOf()) && date.toISOString() === value;
}

function counter(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= maxCounter.length &&
    /^(?:0|[1-9][0-9]*)(?![\s\S])/.test(value) &&
    (value.length < maxCounter.length || value <= maxCounter)
  );
}

function parseScope(value: unknown): AuditScope | undefined {
  const scope = fieldsOf(value);
  if (!scope) return undefined;
  if (scope.kind === "system" && hasOnly(scope, ["kind"])) return { kind: "system" };
  const { guildRef, boardRef } = scope;
  if (!opaqueId(guildRef)) return undefined;
  if (scope.kind === "guild" && hasOnly(scope, ["kind", "guildRef"])) {
    return { kind: "guild", guildRef };
  }
  if (
    scope.kind === "board" &&
    opaqueId(boardRef) &&
    hasOnly(scope, ["kind", "guildRef", "boardRef"])
  ) {
    return { kind: "board", guildRef, boardRef };
  }
  return undefined;
}

function sameScope(left: AuditScope, right: AuditScope): boolean {
  return (
    left.kind === right.kind &&
    (left.kind === "system" || (right.kind !== "system" && left.guildRef === right.guildRef)) &&
    (left.kind !== "board" || (right.kind === "board" && left.boardRef === right.boardRef))
  );
}

function actionName(value: unknown): value is AuditAction {
  return typeof value === "string" && Object.hasOwn(actions, value);
}

/** Internal logical object codec. No wire JSON parsing or client-facing route. */
export function parseAuditEventV1(input: unknown): ParseResult {
  const data = fieldsOf(input);
  if (!data || !hasOnly(data, [...eventFields, "policyGeneration"])) {
    return { ok: false, fields: ["record"] };
  }
  const bad = (field: string): ParseResult => ({ ok: false, fields: [field] });
  const {
    version,
    eventId,
    occurredAt,
    actorKind,
    actorRef,
    action,
    outcome,
    reason,
    correlationId,
    policyGeneration,
  } = data;
  const scope = parseScope(data.scope);
  if (version !== 1) return bad("version");
  if (!opaqueId(eventId)) return bad("eventId");
  if (!utc(occurredAt)) return bad("occurredAt");
  if (typeof actorKind !== "string" || !actorKinds.includes(actorKind as ActorKind))
    return bad("actorKind");
  if (!opaqueId(actorRef)) return bad("actorRef");
  if (!scope) return bad("scope");
  if (!actionName(action)) return bad("action");
  const profile: {
    scopes: readonly AuditScope["kind"][];
    actors: readonly ActorKind[];
    policy: boolean;
  } = actions[action];
  if (!profile.scopes.includes(scope.kind)) return bad("scope");
  if (!profile.actors.includes(actorKind as ActorKind)) return bad("actorKind");
  if (outcome !== "accepted" && outcome !== "denied" && outcome !== "failed") return bad("outcome");
  if (typeof reason !== "string" || !reasons[outcome].includes(reason as Reason))
    return bad("reason");
  if (!opaqueId(correlationId)) return bad("correlationId");
  const generationRequired = scope.kind !== "system" && profile.policy && outcome === "accepted";
  if (
    Object.hasOwn(data, "policyGeneration")
      ? scope.kind === "system" || !profile.policy || !counter(policyGeneration)
      : generationRequired
  )
    return bad("policyGeneration");

  return {
    ok: true,
    event: Object.freeze({
      version,
      eventId,
      occurredAt,
      actorKind: actorKind as ActorKind,
      actorRef,
      scope: Object.freeze(scope),
      action,
      outcome,
      reason: reason as Reason,
      ...(typeof policyGeneration === "string" ? { policyGeneration } : {}),
      correlationId,
    }),
  };
}

type AppendAction = Exclude<AuditAction, "evidence-access">;
type Operation =
  | { readonly right: "append"; readonly action: AppendAction }
  | { readonly right: "verify" }
  | { readonly right: "preserve" };
interface AuditFence {
  readonly scope: AuditScope;
  readonly operation: Operation;
  readonly actorKind: ActorKind;
  readonly actorRef: string;
  readonly now: string;
  readonly expiresAt: string;
  readonly policyGeneration?: string;
}

export interface AuditPosition {
  readonly sequence: string;
  readonly hash: string;
}
export interface AuditRecordV1 extends AuditPosition {
  readonly event: AuditEventV1;
}
export interface IndependentAuditAnchor {
  readonly scope: AuditScope;
  readonly observedAt: string;
  readonly expiresAt: string;
  readonly checkpoint: AuditPosition;
  readonly acceptedHead: AuditPosition;
}
export interface AuditHistory {
  readonly acceptedSequence: string;
  readonly records: readonly unknown[];
}

type Failure = {
  readonly ok: false;
  readonly code:
    | "INVALID_MESSAGE"
    | "FORBIDDEN"
    | "DEPENDENCY_UNAVAILABLE"
    | "INTEGRITY_FAILED"
    | "COMMIT_UNKNOWN";
};
type Result = { readonly ok: true } | Failure;
type CommitResult = "committed" | "rejected" | "unknown";

/** The authority adapter is internal and must resolve a verified server identity,
 * operation-specific right, exact scope, policy generation and trusted time. It
 * keeps the callback ordered against expiry/revocation, including result release.
 * The adapter awaits the callback if invoked. Returning undefined denies before
 * invoking the callback or suppresses its result when release authority is lost. */
export interface AuditAuthority<Subject> {
  withFence<T>(
    subject: Subject,
    scope: AuditScope,
    operation: Operation,
    use: (fence: AuditFence) => Promise<T>,
  ): Promise<T | undefined>;
}

export interface AuditEvidencePorts<Subject, Change> {
  readonly authority: AuditAuthority<Subject>;
  readonly clock: {
    /** Fresh trusted time from the same source used by the authority fence. */
    now(): string;
  };
  readonly access: {
    /** Durably account for the named operator's access before any privileged read.
     * This independent path must remain usable when the audited history is
     * unavailable or damaged. "recorded" confirms durable accounting only. */
    record(
      scope: AuditScope,
      right: "verify" | "preserve",
      event: AuditEventV1,
    ): Promise<"recorded" | "unavailable">;
  };
  readonly anchor: {
    /** Fetch the independently held live accepted head and checkpoint for this
     * exact scope. observedAt is the trusted time of observation during this
     * call. Cached, self-derived or unverifiably fresh values are unavailable. */
    readCurrent(scope: AuditScope): Promise<IndependentAuditAnchor | undefined>;
  };
  readonly history: {
    /** Return a consistent, bounded snapshot including the primary accepted watermark. */
    read(scope: AuditScope, maximumRecords: number): Promise<AuditHistory>;
  };
  readonly acceptance: {
    /** Compare expected head and apply the scoped authoritative change, its audit
     * record and accepted-anchor publication with the accepted ordering guarantees.
     * A rejected result guarantees zero effects. Ambiguous results must be unknown. */
    commitChange(
      scope: AuditScope,
      expected: AuditPosition,
      record: AuditRecordV1,
      change: Change,
    ): Promise<CommitResult>;
    /** Retain only validated records in independently controlled private custody.
     * Atomically account for the custody transfer with its audit record and head
     * advancement. Before acknowledgement verify integrity at custody transfer. */
    preserve(
      scope: AuditScope,
      expected: AuditPosition,
      records: readonly AuditRecordV1[],
      access: AuditRecordV1,
    ): Promise<CommitResult>;
  };
}

function position(value: unknown): AuditPosition | undefined {
  const data = fieldsOf(value);
  if (
    !data ||
    !hasOnly(data, ["sequence", "hash"]) ||
    !counter(data.sequence) ||
    typeof data.hash !== "string" ||
    data.hash.length !== 64 ||
    !/^[a-f0-9]+$/.test(data.hash) ||
    (data.sequence === "0" && data.hash !== rootHash)
  )
    return undefined;
  return Object.freeze({ sequence: data.sequence, hash: data.hash });
}

function nextRecord(prior: AuditPosition, event: AuditEventV1): AuditRecordV1 {
  const sequence = String(BigInt(prior.sequence) + 1n);
  const hash = createHash("sha256")
    .update(JSON.stringify(["guildboard.audit.record.v1", sequence, prior.hash, event]))
    .digest("hex");
  return Object.freeze({ sequence, hash, event });
}

function failure(code: Failure["code"]): Failure {
  return { ok: false, code };
}

type Verified = {
  readonly ok: true;
  readonly head: AuditPosition;
  readonly records: readonly AuditRecordV1[];
};

async function verifyHistory<Subject, Change>(
  ports: AuditEvidencePorts<Subject, Change>,
  scope: AuditScope,
  fenceTime: string,
): Promise<Verified | Failure> {
  const startedAt = ports.clock.now();
  if (!utc(startedAt) || startedAt < fenceTime) return failure("DEPENDENCY_UNAVAILABLE");
  const anchor = await ports.anchor.readCurrent(scope);
  const now = ports.clock.now();
  if (
    !anchor ||
    !utc(now) ||
    now < startedAt ||
    !utc(anchor.observedAt) ||
    !utc(anchor.expiresAt) ||
    anchor.observedAt < startedAt ||
    anchor.observedAt > now ||
    anchor.expiresAt <= now
  )
    return failure("DEPENDENCY_UNAVAILABLE");
  const anchorScope = parseScope(anchor.scope);
  const head = position(anchor.acceptedHead);
  const checkpoint = position(anchor.checkpoint);
  if (
    !anchorScope ||
    !sameScope(scope, anchorScope) ||
    !head ||
    !checkpoint ||
    BigInt(checkpoint.sequence) > BigInt(head.sequence)
  )
    return failure("DEPENDENCY_UNAVAILABLE");
  if (BigInt(head.sequence) > BigInt(AUDIT_MAX_RECORDS)) return failure("DEPENDENCY_UNAVAILABLE");

  const { expiresAt } = anchor;
  const history = await ports.history.read(scope, AUDIT_MAX_RECORDS);
  const proofTime = ports.clock.now();
  if (!utc(proofTime) || proofTime < now || proofTime >= expiresAt)
    return failure("DEPENDENCY_UNAVAILABLE");
  if (
    history.acceptedSequence !== head.sequence ||
    !Array.isArray(history.records) ||
    history.records.length !== Number(head.sequence)
  )
    return failure("INTEGRITY_FAILED");

  let prior = { sequence: "0", hash: rootHash };
  const records: AuditRecordV1[] = [];
  for (const input of history.records) {
    const record = fieldsOf(input);
    if (!record || !hasOnly(record, ["sequence", "hash", "event"]))
      return failure("INTEGRITY_FAILED");
    const parsed = parseAuditEventV1(record.event);
    if (!parsed.ok || !sameScope(scope, parsed.event.scope)) return failure("INTEGRITY_FAILED");
    const next = nextRecord(prior, parsed.event);
    if (
      next.sequence !== record.sequence ||
      next.hash !== record.hash ||
      (next.sequence === checkpoint.sequence && next.hash !== checkpoint.hash)
    ) {
      return failure("INTEGRITY_FAILED");
    }
    records.push(next);
    prior = next;
  }
  if (prior.hash !== head.hash) return failure("INTEGRITY_FAILED");
  // Prove the independently observed head while its observation is still
  // fresh. The authority fence governs release, and effect adapters compare
  // against this expected head.
  const completedAt = ports.clock.now();
  if (!utc(completedAt) || completedAt < proofTime || completedAt >= expiresAt)
    return failure("DEPENDENCY_UNAVAILABLE");
  return { ok: true, head, records: Object.freeze(records) };
}

function acceptedEvent(fence: AuditFence, scope: AuditScope, action: AuditAction): ParseResult {
  const policyGeneration =
    scope.kind !== "system" && actions[action].policy ? fence.policyGeneration : undefined;
  return parseAuditEventV1({
    version: 1,
    eventId: randomUUID(),
    occurredAt: fence.now,
    actorKind: fence.actorKind,
    actorRef: fence.actorRef,
    scope,
    action,
    outcome: "accepted",
    reason: "completed",
    ...(policyGeneration === undefined ? {} : { policyGeneration }),
    correlationId: randomUUID(),
  });
}

async function commit(apply: () => Promise<CommitResult>): Promise<Result> {
  try {
    const result = await apply();
    if (result === "committed") return { ok: true };
    if (result === "rejected") return failure("DEPENDENCY_UNAVAILABLE");
  } catch {
    // An adapter failure after dispatch cannot prove rollback.
  }
  return failure("COMMIT_UNKNOWN");
}

export function createAuditEvidenceService<Subject, Change>(
  ports: AuditEvidencePorts<Subject, Change>,
) {
  async function run(
    subject: Subject,
    selector: unknown,
    operation: Operation,
    use: (scope: AuditScope, fence: AuditFence) => Promise<Result>,
  ): Promise<Result> {
    const scope = parseScope(selector);
    if (!scope) return failure("INVALID_MESSAGE");
    Object.freeze(scope);
    const { right } = operation;
    let possibleCommit = false;
    try {
      const result = await ports.authority.withFence(subject, scope, operation, async (fence) => {
        const verifiedScope = parseScope(fence.scope);
        if (
          !verifiedScope ||
          !sameScope(scope, verifiedScope) ||
          fence.operation.right !== right ||
          (operation.right === "append" &&
            (fence.operation.right !== "append" || fence.operation.action !== operation.action)) ||
          !utc(fence.now) ||
          !utc(fence.expiresAt) ||
          fence.expiresAt <= fence.now ||
          !opaqueId(fence.actorRef) ||
          !actorKinds.includes(fence.actorKind) ||
          (right !== "append" && fence.actorKind !== "operator")
        )
          return failure("FORBIDDEN");
        const outcome = await use(scope, fence);
        possibleCommit = right !== "verify" && (outcome.ok || outcome.code === "COMMIT_UNKNOWN");
        return outcome;
      });
      return result ?? failure(possibleCommit ? "COMMIT_UNKNOWN" : "FORBIDDEN");
    } catch {
      return failure(possibleCommit ? "COMMIT_UNKNOWN" : "DEPENDENCY_UNAVAILABLE");
    }
  }

  async function accountAccess(
    scope: AuditScope,
    fence: AuditFence,
    right: "verify" | "preserve",
  ): Promise<Result> {
    // This event records admission to read. The preservation transaction owns
    // the separate record for successful transfer into custody.
    const parsed = acceptedEvent(fence, scope, "evidence-access");
    if (!parsed.ok) return failure("DEPENDENCY_UNAVAILABLE");
    const result = await ports.access.record(scope, right, parsed.event);
    return result === "recorded" ? { ok: true } : failure("DEPENDENCY_UNAVAILABLE");
  }

  return {
    append(subject: Subject, scope: unknown, action: AppendAction, change: Change) {
      if (!actionName(action) || (action as AuditAction) === "evidence-access") {
        return Promise.resolve(failure("INVALID_MESSAGE"));
      }
      return run(
        subject,
        scope,
        Object.freeze({ right: "append", action }),
        async (resolved, fence) => {
          const parsed = acceptedEvent(fence, resolved, action);
          if (!parsed.ok) return failure("INVALID_MESSAGE");
          const verified = await verifyHistory(ports, resolved, fence.now);
          if (!verified.ok) return verified;
          if (verified.records.length === AUDIT_MAX_RECORDS)
            return failure("DEPENDENCY_UNAVAILABLE");
          const record = nextRecord(verified.head, parsed.event);
          return commit(() =>
            ports.acceptance.commitChange(resolved, verified.head, record, change),
          );
        },
      );
    },
    verify(subject: Subject, scope: unknown) {
      return run(subject, scope, Object.freeze({ right: "verify" }), async (resolved, fence) => {
        const access = await accountAccess(resolved, fence, "verify");
        if (!access.ok) return access;
        const verified = await verifyHistory(ports, resolved, fence.now);
        return verified.ok ? { ok: true } : verified;
      });
    },
    preserve(subject: Subject, scope: unknown) {
      return run(subject, scope, Object.freeze({ right: "preserve" }), async (resolved, fence) => {
        const access = await accountAccess(resolved, fence, "preserve");
        if (!access.ok) return access;
        const parsed = acceptedEvent(fence, resolved, "evidence-access");
        if (!parsed.ok) return failure("INVALID_MESSAGE");
        const verified = await verifyHistory(ports, resolved, fence.now);
        if (!verified.ok) return verified;
        if (verified.records.length === AUDIT_MAX_RECORDS) return failure("DEPENDENCY_UNAVAILABLE");
        const record = nextRecord(verified.head, parsed.event);
        return commit(() =>
          ports.acceptance.preserve(resolved, verified.head, verified.records, record),
        );
      });
    },
  };
}
