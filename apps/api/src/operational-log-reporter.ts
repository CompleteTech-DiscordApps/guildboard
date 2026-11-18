import { addAbortListener } from "node:events";
import { performance } from "node:perf_hooks";
import {
  createOperationalLogBoundary,
  type OperationalJourneyScope,
  type OperationalLogResult,
  type OperationalLogV1,
} from "./operational-logs.js";

type Counters = { rejected: number; saturated: number; lost: number; delivered: number };
type ClassifiedCounts = Counters & Pick<OperationalLogV1, "component" | "outcome">;
type Submission = "queued" | "invalid_record" | "coverage_unknown" | "saturated" | "closed";
type FlushOutcome = "drained" | "deadline_elapsed" | "interrupted";
type Options = Readonly<{
  boundary: Parameters<typeof createOperationalLogBoundary>[0];
  /** Total retained records, including the one in flight. Synthetic mechanics only. */
  capacity: number;
  counterLimit: number;
  sink: (record: OperationalLogV1, signal: AbortSignal) => PromiseLike<void> | void;
}>;

const emptyCounts = (): Counters => ({ rejected: 0, saturated: 0, lost: 0, delivered: 0 });
const maxBudgetMs = 2_147_483_647;

/** Internal, explicitly injected port. This helper does not enable collection. */
export function createOperationalLogReporter({
  boundary: config,
  capacity,
  counterLimit,
  sink,
}: Options) {
  if (
    !Number.isSafeInteger(capacity) ||
    capacity < 1 ||
    capacity > 4096 ||
    !Number.isSafeInteger(counterLimit) ||
    counterLimit < 1 ||
    typeof sink !== "function"
  )
    throw new RangeError("Invalid operational reporter configuration");

  const boundary = createOperationalLogBoundary(config);
  const queue: OperationalLogV1[] = [];
  const counts = emptyCounts();
  // Only boundary-created component/outcome pairs can allocate these <= 90 rows.
  const classes = new Map<string, ClassifiedCounts>();
  let countsCapped = false;
  let coverageUnknown = false;
  let accepting = true;
  let stopped = false;
  let scheduled = false;
  let active: { controller: AbortController; record: OperationalLogV1; lost: boolean } | undefined;
  let observeDrain: (() => void) | undefined;
  let pendingFlush: Promise<FlushResult> | undefined;
  let closedFlush: Promise<FlushResult> | undefined;

  function count(name: keyof Counters, record?: OperationalLogV1): void {
    function increment(target: Counters): void {
      if (target[name] === counterLimit) countsCapped = true;
      else target[name]++;
    }
    increment(counts);
    if (name === "lost") coverageUnknown = true;
    if (!record) return;
    const key = `${record.component}:${record.outcome}`;
    let row = classes.get(key);
    if (!row) {
      row = { component: record.component, outcome: record.outcome, ...emptyCounts() };
      classes.set(key, row);
    }
    increment(row);
  }

  function snapshot() {
    return Object.freeze({
      accepting,
      capacity,
      pending: queue.length + (active ? 1 : 0),
      inFlight: active ? 1 : 0,
      coverage: coverageUnknown ? ("unknown" as const) : ("no_loss_observed" as const),
      counts: Object.freeze({ ...counts }),
      countsCapped,
      classes: Object.freeze([...classes.values()].map((row) => Object.freeze({ ...row }))),
    });
  }
  type FlushResult = Readonly<{ outcome: FlushOutcome; observation: ReturnType<typeof snapshot> }>;

  function scheduleDelivery(): void {
    if (stopped || scheduled || active || queue.length === 0) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      // A delayed flush timer must not let another delivery pass its cutoff.
      observeDrain?.();
      if (stopped || active) return;
      const record = queue.shift();
      if (!record) return;
      const delivery = { controller: new AbortController(), record, lost: false };
      active = delivery;
      const settled = (failed: boolean) => {
        observeDrain?.();
        if (!delivery.lost) count(failed ? "lost" : "delivered", record);
        active = undefined;
        observeDrain?.();
        scheduleDelivery();
      };
      try {
        Promise.resolve(sink(record, delivery.controller.signal)).then(
          () => settled(false),
          () => settled(true),
        );
      } catch {
        settled(true);
      }
    });
  }

  function submit(result: OperationalLogResult): Submission {
    if (result.status !== "record") {
      if (result.status === "invalid_record") count("rejected");
      count("lost");
      return result.status;
    }
    if (queue.length + (active ? 1 : 0) >= capacity) {
      count("saturated", result.record);
      count("lost", result.record);
      return "saturated";
    }
    queue.push(result.record);
    scheduleDelivery();
    return "queued";
  }

  function report(
    input: unknown,
    scope: OperationalJourneyScope | undefined,
    errorOnly: boolean,
  ): Submission {
    observeDrain?.();
    if (!accepting) {
      count("rejected");
      count("lost");
      return "closed";
    }
    return submit(
      errorOnly
        ? boundary.createClassifiedError(input, scope)
        : boundary.createRecord(input, scope),
    );
  }

  function stop(): void {
    accepting = false;
    stopped = true;
    for (const record of queue) count("lost", record);
    queue.length = 0;
    if (active && !active.lost) {
      active.lost = true;
      count("lost", active.record);
      // Retain this slot until actual settlement, even if the sink ignores abort.
      active.controller.abort();
    }
  }

  function validateFlush(budgetMs: number, signal?: AbortSignal): void {
    if (
      !Number.isSafeInteger(budgetMs) ||
      budgetMs < 1 ||
      budgetMs > maxBudgetMs ||
      (signal !== undefined && !(signal instanceof AbortSignal))
    ) {
      throw new RangeError("Invalid operational reporter flush configuration");
    }
  }

  /** Concurrent calls share the first caller's finite budget and signal. */
  function flush(budgetMs: number, signal?: AbortSignal): Promise<FlushResult> {
    validateFlush(budgetMs, signal);
    if (closedFlush) return closedFlush;
    if (pendingFlush) return pendingFlush;
    const deadline = performance.now() + budgetMs;
    let resolveResult!: (result: FlushResult) => void;
    const completion = new Promise<FlushResult>((resolve) => {
      resolveResult = resolve;
    });
    pendingFlush = completion;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let abortListener: ReturnType<typeof addAbortListener> | undefined;
    let finished = false;

    function finish(outcome: FlushOutcome): void {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      abortListener?.[Symbol.dispose]();
      observeDrain = undefined;
      pendingFlush = undefined;
      if (outcome !== "drained") {
        closedFlush = completion;
        stop();
      }
      resolveResult(Object.freeze({ outcome, observation: snapshot() }));
    }
    function check(): void {
      if (signal?.aborted) finish("interrupted");
      else if (performance.now() >= deadline) finish("deadline_elapsed");
      else if (!active && queue.length === 0) finish("drained");
    }
    function tick(): void {
      check();
      if (!finished) timer = setTimeout(tick, Math.ceil(deadline - performance.now()));
    }
    observeDrain = check;
    check();
    if (!finished) {
      if (signal) abortListener = addAbortListener(signal, check);
      tick();
    }
    return completion;
  }

  return Object.freeze({
    issueCorrelation(scope: OperationalJourneyScope): "available" | "coverage_unknown" {
      observeDrain?.();
      if (!accepting || boundary.issueCorrelation(scope) !== "available") {
        count("lost");
        return "coverage_unknown";
      }
      return "available";
    },
    report: (input: unknown, scope?: OperationalJourneyScope) => report(input, scope, false),
    reportError: (input: unknown, scope?: OperationalJourneyScope) => report(input, scope, true),
    snapshot,
    flush,
    close(budgetMs: number, signal?: AbortSignal): Promise<FlushResult> {
      validateFlush(budgetMs, signal);
      accepting = false;
      closedFlush ??= flush(budgetMs, signal);
      return closedFlush;
    },
  });
}
