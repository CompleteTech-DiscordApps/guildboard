import { OPERATIONAL_METRICS_V1, createOperationalMetricParserV1 } from "./operational-metrics.js";
import type { OperationalMetricNameV1, OperationalMetricV1 } from "./operational-metrics.js";

type Rejection = "invalid" | "disabled" | "capacity" | "overflow";
const MAX_COUNT = Number.MAX_SAFE_INTEGER;
const REGISTRY_SERIES_BOUND = Object.values(OPERATIONAL_METRICS_V1).reduce(
  (sum, definition) => sum + definition.seriesUpperBound,
  0,
);

function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function metricName(value: unknown): value is OperationalMetricNameV1 {
  return typeof value === "string" && Object.hasOwn(OPERATIONAL_METRICS_V1, value);
}

// Private, offline mechanics only: callers own interval provenance and coverage.
export function createOperationalMetricRecorderV1(
  startUtc: unknown,
  endUtc: unknown,
  approvedBuckets: unknown = {},
  maxSeries: unknown = REGISTRY_SERIES_BOUND,
) {
  const configuredParser = createOperationalMetricParserV1(approvedBuckets);
  if (!configuredParser || !count(maxSeries) || maxSeries > REGISTRY_SERIES_BOUND) return;
  const parse = configuredParser;
  const seriesLimit = maxSeries;
  const interval = { version: 1, startUtc, endUtc };
  if (
    !parse({
      ...interval,
      signal: "active_sockets",
      unit: "items",
      kind: "gauge",
      dimensions: { component: "collaboration" },
      value: 0,
    })
  )
    return;

  // The parser already validated plain own data properties and copied every layout.
  // Recover those immutable copies through ordinary v1 records, without maintaining
  // a second configuration validator or reading a caller-supplied array iterator.
  const layouts = new Map<OperationalMetricNameV1, readonly number[]>();
  for (const [name, definition] of Object.entries(OPERATIONAL_METRICS_V1)) {
    if (definition.kind !== "histogram") continue;
    const descriptor = Object.getOwnPropertyDescriptor(approvedBuckets, name);
    if (!descriptor) continue;
    const buckets: unknown = descriptor.value;
    const length: number = Object.getOwnPropertyDescriptor(buckets, "length")?.value as number;
    const dimensions = Object.fromEntries(
      Object.entries(definition.dimensions).map(([label, values]) => [label, values[0]]),
    );
    const record = parse({
      ...interval,
      signal: name,
      kind: definition.kind,
      unit: definition.unit,
      dimensions,
      buckets,
      counts: Array.from({ length }, () => 0),
      total: 0,
    });
    if (!record || record.kind !== "histogram") return;
    layouts.set(name as OperationalMetricNameV1, record.buckets);
  }

  const series = new Map<string, OperationalMetricV1>();
  const rejected: Record<Rejection, number> = { invalid: 0, disabled: 0, capacity: 0, overflow: 0 };
  let acceptedUpdates = 0;
  let reportedMissing = 0;
  let lossDetected = false;
  let accountingSaturated = false;
  function add(left: number, right: number): number {
    if (left > MAX_COUNT - right) {
      accountingSaturated = true;
      return MAX_COUNT;
    }
    return left + right;
  }
  function reject(reason: Rejection): false {
    lossDetected = true;
    rejected[reason] = add(rejected[reason], 1);
    return false;
  }

  // This parser only checks labels for disabled histograms, using synthetic
  // one-bucket layouts. They never enable recording or appear in snapshots.
  const labelParser = createOperationalMetricParserV1(
    Object.fromEntries(
      Object.entries(OPERATIONAL_METRICS_V1)
        .filter(([, definition]) => definition.kind === "histogram")
        .map(([name]) => [name, [0]]),
    ),
  );
  if (!labelParser) return;
  const validateLabels = labelParser;

  function update(
    kind: "counter" | "gauge" | "histogram",
    signal: unknown,
    dimensions: unknown,
    value: unknown,
    occurrences: unknown = 1,
  ): boolean {
    if (
      !metricName(signal) ||
      OPERATIONAL_METRICS_V1[signal].kind !== kind ||
      !count(value) ||
      !count(occurrences) ||
      occurrences === 0
    )
      return reject("invalid");
    const definition = OPERATIONAL_METRICS_V1[signal];
    const buckets = layouts.get(signal);
    // Validate labels before classifying a valid histogram as disabled. A small
    // temporary parser record never allocates a retained series.
    const validate = buckets || kind !== "histogram" ? parse : validateLabels;
    const candidate = validate({
      ...interval,
      signal,
      kind,
      unit: definition.unit,
      dimensions,
      ...(kind === "histogram"
        ? { buckets: buckets ?? [0], counts: (buckets ?? [0]).map(() => 0), total: 0 }
        : { value }),
    });
    if (!candidate) return reject("invalid");
    if (kind === "histogram" && !buckets) return reject("disabled");
    const key = JSON.stringify([signal, candidate.dimensions]);
    const previous = series.get(key);
    let next: OperationalMetricV1 = candidate;
    if (candidate.kind === "histogram") {
      const old = previous?.kind === "histogram" ? previous : undefined;
      const total = (old?.total ?? 0) + occurrences;
      if (!count(total)) return reject("overflow");
      const counts = candidate.buckets.map(
        (bound, index) => (old?.counts[index] ?? 0) + (value <= bound ? occurrences : 0),
      );
      if (!counts.every(count)) return reject("overflow");
      next = Object.freeze({ ...candidate, counts: Object.freeze(counts), total });
    } else if (kind === "counter") {
      const old = previous && previous.kind !== "histogram" ? previous.value : 0;
      const total = old + value;
      if (!count(total)) return reject("overflow");
      next = Object.freeze({ ...candidate, value: total });
    }
    if (!previous && series.size >= seriesLimit) return reject("capacity");
    series.set(key, next);
    acceptedUpdates = add(acceptedUpdates, 1);
    return true;
  }

  return Object.freeze({
    increment: (signal: unknown, dimensions: unknown, amount: unknown = 1) =>
      update("counter", signal, dimensions, amount),
    setGauge: (signal: unknown, dimensions: unknown, value: unknown) =>
      update("gauge", signal, dimensions, value),
    // Occurrences represents repeated equal samples, without an unbounded loop.
    observe: (signal: unknown, dimensions: unknown, sample: unknown, occurrences: unknown = 1) =>
      update("histogram", signal, dimensions, sample, occurrences),
    reportMissing: (observations: unknown = 1): boolean => {
      if (!count(observations) || observations === 0) return reject("invalid");
      reportedMissing = add(reportedMissing, observations);
      lossDetected = true;
      return true;
    },
    snapshot: (): readonly OperationalMetricV1[] =>
      Object.freeze(
        Array.from(series.values(), (record) => {
          // Reparse to detach every nested dimension/bucket/count from prior snapshots.
          const detached = parse(record);
          if (!detached) throw new Error("Invalid internal metric record");
          return detached;
        }),
      ),
    status: () =>
      Object.freeze({
        // Local recording cannot establish expected schedules, eligibility or delivery.
        coverage: "unknown" as const,
        lossDetected,
        allocatedSeries: series.size,
        maxSeries: seriesLimit,
        acceptedUpdates,
        reportedMissing,
        rejected: Object.freeze({ ...rejected }),
        accountingSaturated,
      }),
  });
}
