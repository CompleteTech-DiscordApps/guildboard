type GuildTarget = { readonly guildRef: string };
type BoardTarget = GuildTarget & { readonly boardRef: string };
type SubjectTarget = GuildTarget & { readonly subjectRef: string };

export type DeletionScope =
  | { readonly kind: "guild"; readonly target: GuildTarget }
  | { readonly kind: "board"; readonly target: BoardTarget }
  | { readonly kind: "subject"; readonly target: SubjectTarget };

export type DeletionJobV1 = DeletionScope & {
  readonly version: 1;
  readonly jobId: string;
} & (
    | { readonly phase: "fenced" | "live_complete" | "complete"; readonly failure?: never }
    | { readonly phase: "propagating"; readonly failure?: "propagation-interrupted" }
  );

export type DeletionAuthority = {
  readonly current: true;
  readonly scope: DeletionScope;
  readonly action: "start" | "advance";
};

export type DeletionTransition =
  | { readonly action: "propagate" | "interrupt" | "retry" }
  | {
      readonly action: "finish-live";
      readonly jobId: string;
      readonly scope: DeletionScope;
      readonly liveReferencesReconciled: true;
      readonly liveCopiesRemovedOrUnderApprovedIsolation: true;
    }
  | {
      readonly action: "finish";
      readonly jobId: string;
      readonly scope: DeletionScope;
      readonly requiredCopiesReconciled: true;
      readonly remainingExceptionsExpiredOrHaveApprovedDisposition: true;
    };

export type DeletionDecision =
  | { readonly ok: true; readonly job: DeletionJobV1 }
  | { readonly ok: false; readonly code: "INVALID_JOB" | "FORBIDDEN" | "PRECONDITION_FAILED" };

function fieldsOf(value: unknown, maxFields: number): Record<string, unknown> | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  try {
    const prototype: unknown = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) return undefined;
    const keys = Reflect.ownKeys(value);
    if (keys.length > maxFields) return undefined;
    const fields = Object.create(null) as Record<string, unknown>;
    for (const key of keys) {
      if (typeof key !== "string") return undefined;
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor?.enumerable || !Object.hasOwn(descriptor, "value")) return undefined;
      fields[key] = descriptor.value;
    }
    return fields;
  } catch {
    return undefined;
  }
}

function opaqueRef(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length === 36 &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value)
  );
}

function parseScope(kind: unknown, value: unknown): DeletionScope | undefined {
  const target = fieldsOf(value, 2);
  if (!target || !opaqueRef(target.guildRef)) return undefined;
  const { guildRef, boardRef, subjectRef } = target;
  const count = Object.keys(target).length;
  if (kind === "guild" && count === 1) return { kind, target: { guildRef } };
  if (kind === "board" && count === 2 && opaqueRef(boardRef)) {
    return { kind, target: { guildRef, boardRef } };
  }
  if (kind === "subject" && count === 2 && opaqueRef(subjectRef)) {
    return { kind, target: { guildRef, subjectRef } };
  }
  return undefined;
}

export function parseDeletionJobV1(value: unknown): DeletionJobV1 | undefined {
  const fields = fieldsOf(value, 6);
  if (!fields) return undefined;
  const { version, jobId, kind, target, phase, failure } = fields;
  if (version !== 1 || !opaqueRef(jobId)) return undefined;
  const scope = parseScope(kind, target);
  if (!scope) return undefined;
  const identity = { version, jobId, ...scope } as const;
  if (Object.hasOwn(fields, "failure")) {
    if (
      Object.keys(fields).length === 6 &&
      phase === "propagating" &&
      failure === "propagation-interrupted"
    ) {
      return { ...identity, phase, failure };
    }
    return undefined;
  }
  if (
    Object.keys(fields).length === 5 &&
    (phase === "fenced" ||
      phase === "propagating" ||
      phase === "live_complete" ||
      phase === "complete")
  ) {
    return { ...identity, phase };
  }
  return undefined;
}

function sameScope(job: DeletionScope, other: DeletionScope): boolean {
  if (job.target.guildRef !== other.target.guildRef) return false;
  if (job.kind === "board" && other.kind === "board") {
    return job.target.boardRef === other.target.boardRef;
  }
  if (job.kind === "subject" && other.kind === "subject") {
    return job.target.subjectRef === other.target.subjectRef;
  }
  return job.kind === "guild" && other.kind === "guild";
}

function authorized(
  job: DeletionJobV1,
  authority: DeletionAuthority | undefined,
  action: DeletionAuthority["action"],
): boolean {
  if (authority?.current !== true || authority.action !== action) return false;
  const scope = parseScope(authority.scope?.kind, authority.scope?.target);
  return scope !== undefined && sameScope(job, scope);
}

// Call inside the authority fence. Persist the initial job and invalidate access
// and stale writers/delivery in the same transaction using the scoped server ID.
export function decideDeletionJobStart(
  value: unknown,
  authority: DeletionAuthority | undefined,
): DeletionDecision {
  const job = parseDeletionJobV1(value);
  if (!job || job.phase !== "fenced") return { ok: false, code: "INVALID_JOB" };
  if (!authorized(job, authority, "start")) return { ok: false, code: "FORBIDDEN" };
  return { ok: true, job };
}

// Commit against the current durable revision of this fenced job. Retries share
// the same job identity, and work/evidence must remain in that scoped fence.
export function decideDeletionJobTransition(
  value: unknown,
  authority: DeletionAuthority | undefined,
  transition: DeletionTransition,
): DeletionDecision {
  const job = parseDeletionJobV1(value);
  if (!job) return { ok: false, code: "INVALID_JOB" };
  if (!authorized(job, authority, "advance")) return { ok: false, code: "FORBIDDEN" };
  const { failure, ...state } = job;
  switch (transition?.action) {
    case "propagate":
      if (job.phase === "fenced" || (job.phase === "propagating" && failure === undefined)) {
        return { ok: true, job: { ...state, phase: "propagating" } };
      }
      break;
    case "interrupt":
      if (job.phase === "propagating") {
        return {
          ok: true,
          job: { ...state, phase: "propagating", failure: "propagation-interrupted" },
        };
      }
      break;
    case "retry":
      if (job.phase === "propagating") {
        return { ok: true, job: { ...state, phase: "propagating" } };
      }
      break;
    case "finish-live":
    case "finish": {
      const scope = parseScope(transition.scope?.kind, transition.scope?.target);
      if (transition.jobId !== job.jobId || !scope || !sameScope(job, scope)) break;
      if (
        transition.action === "finish-live" &&
        (job.phase === "propagating" || job.phase === "live_complete") &&
        failure === undefined &&
        transition.liveReferencesReconciled === true &&
        transition.liveCopiesRemovedOrUnderApprovedIsolation === true
      ) {
        return { ok: true, job: { ...state, phase: "live_complete" } };
      }
      if (
        transition.action === "finish" &&
        (job.phase === "live_complete" || job.phase === "complete") &&
        transition.requiredCopiesReconciled === true &&
        transition.remainingExceptionsExpiredOrHaveApprovedDisposition === true
      ) {
        return { ok: true, job: { ...state, phase: "complete" } };
      }
    }
  }
  return { ok: false, code: "PRECONDITION_FAILED" };
}

export type IsolatedRestore = {
  readonly guildRef: string;
  readonly restoreRef: string;
  readonly appliedCut: bigint;
};

type RestoreFence = {
  readonly guildRef: string;
  readonly restoreRef: string;
  readonly fenceRef: string;
};

type DeletionMarker = {
  readonly sequence: bigint;
  readonly markerRef: string;
};

// The caller obtains this window from the independent authoritative marker
// source for the live exposure fence, including the authoritative high water.
export type CurrentDeletionWindow = RestoreFence & {
  readonly highWater: bigint;
  readonly markers: readonly DeletionMarker[];
};

export type RestoreReconciliation = RestoreFence & {
  readonly through: bigint;
  readonly applied: readonly (DeletionMarker & {
    readonly contentHidden: true;
    readonly assetsHidden: true;
    readonly exportsHidden: true;
    readonly referencesHidden: true;
  })[];
  readonly revocationsReapplied: true;
  readonly currentAuthorityVerified: true;
  readonly lineageVerified: true;
  readonly receiptsVerified: true;
};

const maxCounter = (1n << 64n) - 1n;
export const DELETION_MAX_RESTORE_MARKERS = 4096;

function validCounter(value: bigint): boolean {
  return typeof value === "bigint" && value >= 0n && value <= maxCounter;
}

// This decision is valid only while caller-held isolation and the same
// exposure fence remain in effect. A later fence requires fresh evidence.
export function canReleaseIsolatedRestore(
  restore: IsolatedRestore,
  fence: RestoreFence,
  current: CurrentDeletionWindow | undefined,
  reconciliation: RestoreReconciliation | undefined,
): boolean {
  if (
    !restore ||
    !fence ||
    !current ||
    !reconciliation ||
    !opaqueRef(restore.guildRef) ||
    !opaqueRef(restore.restoreRef) ||
    !opaqueRef(fence.fenceRef) ||
    !validCounter(restore.appliedCut) ||
    !validCounter(current.highWater) ||
    ![fence, current, reconciliation].every(
      (entry) =>
        entry.guildRef === restore.guildRef &&
        entry.restoreRef === restore.restoreRef &&
        entry.fenceRef === fence.fenceRef,
    ) ||
    reconciliation.through !== current.highWater ||
    reconciliation.revocationsReapplied !== true ||
    reconciliation.currentAuthorityVerified !== true ||
    reconciliation.lineageVerified !== true ||
    reconciliation.receiptsVerified !== true
  ) {
    return false;
  }

  const count = current.highWater - restore.appliedCut;
  if (
    count < 0n ||
    count > BigInt(DELETION_MAX_RESTORE_MARKERS) ||
    !Array.isArray(current.markers) ||
    !Array.isArray(reconciliation.applied) ||
    current.markers.length !== Number(count) ||
    reconciliation.applied.length !== Number(count)
  ) {
    return false;
  }

  const seen = new Set<string>();
  for (let index = 0; index < Number(count); index += 1) {
    const marker = current.markers[index];
    const applied = reconciliation.applied[index];
    const sequence = restore.appliedCut + BigInt(index) + 1n;
    if (
      marker?.sequence !== sequence ||
      !opaqueRef(marker.markerRef) ||
      seen.has(marker.markerRef) ||
      applied?.sequence !== sequence ||
      applied.markerRef !== marker.markerRef ||
      applied.contentHidden !== true ||
      applied.assetsHidden !== true ||
      applied.exportsHidden !== true ||
      applied.referencesHidden !== true
    ) {
      return false;
    }
    seen.add(marker.markerRef);
  }
  return true;
}
