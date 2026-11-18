import { types } from "node:util";

const sizeClasses = [
  "encoded-bytes",
  "decoded-bytes",
  "decoded-width",
  "decoded-height",
  "parse-depth",
  "fields",
  "elements",
  "compound-changes",
] as const;

const quotaClasses = [
  "parser-work",
  "work-duration",
  "requests",
  "connections",
  "inbound-queue-bytes",
  "durable-queue-bytes",
  "presence-queue-bytes",
  "storage-bytes",
] as const;

export type ResourceClass = (typeof sizeClasses)[number] | (typeof quotaClasses)[number];

export interface ResourceScopeV1 {
  readonly guildRef: string;
  readonly principalRef: string;
  readonly boardRef: string | null;
  readonly socketRef: string | null;
}

interface ScopedAmounts {
  readonly global: number;
  readonly guild: number;
  readonly principal: number;
  // Explicit null means the profile does not meter this scope.
  readonly board: number | null;
  readonly socket: number | null;
}

interface ResourceEpoch {
  readonly version: 1;
  readonly resourceClass: ResourceClass;
  // Server-owned revision identity for the approved profile.
  readonly profileRef: string;
}

export interface ResourceProfileV1 extends ResourceEpoch {
  readonly maxPerAttempt: number;
  readonly limits: ScopedAmounts;
}

export interface ResourceDemandV1 extends ResourceEpoch {
  readonly scope: ResourceScopeV1;
  readonly amount: number;
}

export interface ResourceAccountingV1 extends ResourceEpoch {
  readonly scope: ResourceScopeV1;
  readonly used: ScopedAmounts;
}

export type ResourceAdmission =
  | { readonly ok: true }
  | {
      readonly ok: false;
      readonly code:
        "DEPENDENCY_UNAVAILABLE" | "INVALID_MESSAGE" | "PAYLOAD_TOO_LARGE" | "RATE_LIMITED";
    };

function ownData(record: unknown, key: string): unknown {
  if (typeof record !== "object" || record === null || types.isProxy(record)) return undefined;
  const prototype: unknown = Object.getPrototypeOf(record);
  if (prototype !== Object.prototype && prototype !== null) return undefined;
  const field = Object.getOwnPropertyDescriptor(record, key);
  return field?.enumerable && Object.hasOwn(field, "value") ? field.value : undefined;
}

function isRef(value: unknown): value is string {
  return typeof value === "string" && value.length <= 128 && /^[A-Za-z0-9_-]+$/.test(value);
}

function isAmount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function scopeOf(value: unknown): ResourceScopeV1 | undefined {
  const guildRef = ownData(value, "guildRef");
  const principalRef = ownData(value, "principalRef");
  const boardRef = ownData(value, "boardRef");
  const socketRef = ownData(value, "socketRef");
  if (
    !isRef(guildRef) ||
    !isRef(principalRef) ||
    (boardRef !== null && !isRef(boardRef)) ||
    (socketRef !== null && !isRef(socketRef))
  ) {
    return undefined;
  }
  return { guildRef, principalRef, boardRef, socketRef };
}

function amountsOf(value: unknown): ScopedAmounts | undefined {
  const global = ownData(value, "global");
  const guild = ownData(value, "guild");
  const principal = ownData(value, "principal");
  const board = ownData(value, "board");
  const socket = ownData(value, "socket");
  if (
    !isAmount(global) ||
    !isAmount(guild) ||
    !isAmount(principal) ||
    (board !== null && !isAmount(board)) ||
    (socket !== null && !isAmount(socket))
  ) {
    return undefined;
  }
  return { global, guild, principal, board, socket };
}

function matchesEpoch(value: unknown, resourceClass: string, profileRef: string): boolean {
  return (
    ownData(value, "version") === 1 &&
    ownData(value, "resourceClass") === resourceClass &&
    ownData(value, "profileRef") === profileRef
  );
}

const scopeKeys = ["global", "guild", "principal", "board", "socket"] as const;

/**
 * Evaluate one resource class using server-owned inputs. The caller selects an
 * approved profile and supplies a current snapshot under its accounting fence.
 * An allow decision creates no reservation. Apply every required admission check
 * and account for the result in the same serialized operation before effects.
 * Only read the fixed set of own data fields; wire parsing belongs to the caller.
 */
export function evaluateResourceAdmission(
  approvedProfile: ResourceProfileV1 | undefined,
  demand: ResourceDemandV1,
  accounting: ResourceAccountingV1 | undefined,
): ResourceAdmission {
  const className = ownData(demand, "resourceClass");
  const profileRef = ownData(demand, "profileRef");
  const amount = ownData(demand, "amount");
  const scope = scopeOf(ownData(demand, "scope"));
  const isSize = sizeClasses.some((known) => known === className);
  if (
    typeof className !== "string" ||
    (!isSize && !quotaClasses.some((known) => known === className)) ||
    !isRef(profileRef) ||
    ownData(demand, "version") !== 1 ||
    !isAmount(amount) ||
    !scope
  ) {
    return { ok: false, code: "INVALID_MESSAGE" };
  }

  const maxPerAttempt = ownData(approvedProfile, "maxPerAttempt");
  const limits = amountsOf(ownData(approvedProfile, "limits"));
  const used = amountsOf(ownData(accounting, "used"));
  const countedScope = scopeOf(ownData(accounting, "scope"));
  if (
    !matchesEpoch(approvedProfile, className, profileRef) ||
    !matchesEpoch(accounting, className, profileRef) ||
    !isAmount(maxPerAttempt) ||
    !limits ||
    !used ||
    !countedScope ||
    scope.guildRef !== countedScope.guildRef ||
    scope.principalRef !== countedScope.principalRef ||
    scope.boardRef !== countedScope.boardRef ||
    scope.socketRef !== countedScope.socketRef ||
    (limits.board !== null && scope.boardRef === null) ||
    (limits.socket !== null && scope.socketRef === null) ||
    scopeKeys.some((key) => (limits[key] === null) !== (used[key] === null))
  ) {
    return { ok: false, code: "DEPENDENCY_UNAVAILABLE" };
  }

  if (amount > maxPerAttempt) {
    return { ok: false, code: isSize ? "PAYLOAD_TOO_LARGE" : "RATE_LIMITED" };
  }

  for (const key of scopeKeys) {
    const limit = limits[key];
    const consumed = used[key];
    // Compare against the remaining amount without an unsafe integer sum.
    if (limit !== null && consumed !== null && amount > limit - consumed) {
      return { ok: false, code: "RATE_LIMITED" };
    }
  }
  return { ok: true };
}
