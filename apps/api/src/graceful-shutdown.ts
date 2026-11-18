import { performance } from "node:perf_hooks";

type ShutdownPhaseOutcome = "completed" | "failed" | "deadline-elapsed";

export type GracefulShutdownResult = Readonly<{
  drain: Readonly<{
    outcome: "settled" | "deadline-elapsed";
    pendingOperations: number;
    failedOperations: number;
  }>;
  reconnect: ShutdownPhaseOutcome;
  telemetry: ShutdownPhaseOutcome;
}>;

export type GracefulShutdownOptions = Readonly<{
  drainMs: number;
  reconnectMs: number;
  flushMs: number;
  closeSocketsWithReconnectGuidance: (signal: AbortSignal) => PromiseLike<void> | void;
  flushTelemetry: (signal: AbortSignal) => PromiseLike<void> | void;
}>;

type Admission<T> =
  Readonly<{ admitted: false }> | Readonly<{ admitted: true; completion: Promise<T> }>;

export type GracefulShutdownCoordinator = Readonly<{
  isAcceptingWork: () => boolean;
  admit: <T>(run: () => T) => Admission<Awaited<T>>;
  shutdown: () => Promise<GracefulShutdownResult>;
}>;

// Keep the combined budget within Node's supported timer range.
const maxBudgetMs = 2_147_483_647;

function scheduleDeadline(deadline: number, expire: () => void): () => void {
  let timer: ReturnType<typeof setTimeout>;
  const check = () => {
    const remaining = deadline - performance.now();
    if (remaining <= 0) expire();
    else timer = setTimeout(check, Math.ceil(remaining));
  };
  timer = setTimeout(check, Math.ceil(deadline - performance.now()));
  return () => clearTimeout(timer);
}

function runBoundedPhase(
  budgetMs: number,
  run: (signal: AbortSignal) => PromiseLike<void> | void,
): Promise<ShutdownPhaseOutcome> {
  const controller = new AbortController();
  const deadline = performance.now() + budgetMs;

  return new Promise((resolve) => {
    let finished = false;
    const finish = (outcome: ShutdownPhaseOutcome) => {
      if (finished) return;
      finished = true;
      cancelDeadline();
      if (performance.now() >= deadline) outcome = "deadline-elapsed";
      if (outcome === "deadline-elapsed") controller.abort();
      resolve(outcome);
    };
    const cancelDeadline = scheduleDeadline(deadline, () => finish("deadline-elapsed"));

    try {
      Promise.resolve(run(controller.signal)).then(
        () => finish("completed"),
        () => finish("failed"),
      );
    } catch {
      finish("failed");
    }
  });
}

export function createGracefulShutdownCoordinator(
  options: GracefulShutdownOptions,
): GracefulShutdownCoordinator {
  const { drainMs, reconnectMs, flushMs, closeSocketsWithReconnectGuidance, flushTelemetry } =
    options;
  if (
    ![drainMs, reconnectMs, flushMs].every(
      (budget) => Number.isSafeInteger(budget) && budget > 0,
    ) ||
    drainMs + reconnectMs + flushMs > maxBudgetMs ||
    typeof closeSocketsWithReconnectGuidance !== "function" ||
    typeof flushTelemetry !== "function"
  ) {
    throw new TypeError("Invalid graceful shutdown configuration");
  }

  let acceptingWork = true;
  let pendingOperations = 0;
  let failedOperations = 0;
  let observeSettlement: ((failed: boolean) => void) | undefined;
  let shutdownResult: Promise<GracefulShutdownResult> | undefined;

  const settled = (failed: boolean) => {
    observeSettlement?.(failed);
    pendingOperations--;
  };

  function admit<T>(run: () => T): Admission<Awaited<T>> {
    if (!acceptingWork) return { admitted: false };
    pendingOperations++;

    try {
      const completion = Promise.resolve(run()).then(
        (value) => {
          settled(false);
          return value;
        },
        (error: unknown) => {
          settled(true);
          throw error;
        },
      );
      return { admitted: true, completion };
    } catch (error) {
      settled(true);
      return { admitted: true, completion: Promise.reject(error) };
    }
  }

  function drain(): Promise<GracefulShutdownResult["drain"]> {
    const deadline = performance.now() + drainMs;
    return new Promise((resolve) => {
      const finish = (outcome: GracefulShutdownResult["drain"]["outcome"], pending: number) => {
        cancelDeadline();
        observeSettlement = undefined;
        resolve(Object.freeze({ outcome, pendingOperations: pending, failedOperations }));
      };

      if (pendingOperations === 0) {
        resolve(Object.freeze({ outcome: "settled", pendingOperations: 0, failedOperations: 0 }));
        return;
      }

      const cancelDeadline = scheduleDeadline(deadline, () =>
        finish("deadline-elapsed", pendingOperations),
      );
      observeSettlement = (failed) => {
        if (performance.now() >= deadline) {
          finish("deadline-elapsed", pendingOperations);
          return;
        }
        if (failed) failedOperations++;
        if (pendingOperations === 1) finish("settled", 0);
      };
    });
  }

  function shutdown(): Promise<GracefulShutdownResult> {
    if (shutdownResult) return shutdownResult;
    acceptingWork = false;
    shutdownResult = drain().then(async (drainResult) => {
      const reconnect = await runBoundedPhase(reconnectMs, closeSocketsWithReconnectGuidance);
      const telemetry = await runBoundedPhase(flushMs, flushTelemetry);
      return Object.freeze({ drain: drainResult, reconnect, telemetry });
    });
    return shutdownResult;
  }

  return { isAcceptingWork: () => acceptingWork, admit, shutdown };
}
