import { types } from "node:util";

type Dimension = "component" | "outcome" | "cohort";
type Dimensions = Readonly<Partial<Record<Dimension, readonly string[]>>>;
type Kind = "counter" | "gauge" | "histogram";
type Unit = "items" | "bytes" | "millicores" | "milliseconds" | "boolean";

const MAX_FINITE_BUCKETS = 32;
const openCohorts = ["cold", "warm", "unknown"];
const editCohorts = ["solo", "collaborative", "unknown"];
const journeyOutcomes = [
  "success",
  "invalid_input",
  "authorization_denied",
  "dependency_unavailable",
  "saturated",
  "deadline_elapsed",
  "coverage_unknown",
];
const editOutcomes = [...journeyOutcomes, "commit_unknown"];
const probeOutcomes = ["success", "dependency_unavailable", "deadline_elapsed", "coverage_unknown"];
const operationOutcomes = [
  "success",
  "dependency_unavailable",
  "saturated",
  "deadline_elapsed",
  "commit_unknown",
  "coverage_unknown",
];

function signal(kind: Kind, unit: Unit, domains: Dimensions) {
  const dimensions = Object.freeze(
    Object.fromEntries(
      Object.entries(domains).map(([key, values]) => [key, Object.freeze([...values])]),
    ),
  ) as Dimensions;
  const seriesUpperBound = Object.values(dimensions).reduce(
    (product, values) => product * values.length,
    1,
  );
  return Object.freeze({
    kind,
    unit,
    dimensions,
    seriesUpperBound,
    maxFiniteBuckets: kind === "histogram" ? MAX_FINITE_BUCKETS : 0,
  });
}

export const OPERATIONAL_METRICS_V1 = Object.freeze({
  board_open_outcome: signal("counter", "items", { outcome: journeyOutcomes, cohort: openCohorts }),
  edit_outcome: signal("counter", "items", { outcome: editOutcomes, cohort: editCohorts }),
  reconnect_outcome: signal("counter", "items", { outcome: journeyOutcomes }),
  probe_outcome: signal("counter", "items", { outcome: probeOutcomes }),
  operation_latency: signal("histogram", "milliseconds", { outcome: operationOutcomes }),
  board_open_latency: signal("histogram", "milliseconds", {
    outcome: journeyOutcomes,
    cohort: openCohorts,
  }),
  edit_latency: signal("histogram", "milliseconds", { outcome: editOutcomes, cohort: editCohorts }),
  reconnect_latency: signal("histogram", "milliseconds", { outcome: journeyOutcomes }),
  probe_latency: signal("histogram", "milliseconds", { outcome: probeOutcomes }),
  active_sockets: signal("gauge", "items", { component: ["collaboration"] }),
  active_boards: signal("gauge", "items", { component: ["collaboration"] }),
  admission_depth: signal("gauge", "items", { component: ["api", "collaboration"] }),
  admission_capacity: signal("gauge", "items", { component: ["api", "collaboration"] }),
  output_depth: signal("gauge", "items", { component: ["collaboration"] }),
  output_capacity: signal("gauge", "items", { component: ["collaboration"] }),
  cpu_used: signal("gauge", "millicores", { component: ["host"] }),
  cpu_allocatable: signal("gauge", "millicores", { component: ["host"] }),
  resident_memory: signal("gauge", "bytes", { component: ["host"] }),
  allocatable_memory: signal("gauge", "bytes", { component: ["host"] }),
  persistent_disk_used: signal("gauge", "bytes", { component: ["host"] }),
  persistent_disk_usable: signal("gauge", "bytes", { component: ["host"] }),
  database_health: signal("gauge", "boolean", { component: ["persistence"] }),
  verified_recovery_point_age: signal("gauge", "milliseconds", { component: ["recovery"] }),
  backup_job_outcome: signal("counter", "items", {
    outcome: [
      "success",
      "dependency_unavailable",
      "deadline_elapsed",
      "coverage_unknown",
      "interrupted",
      "integrity_failed",
    ],
  }),
});

export type OperationalMetricNameV1 = keyof typeof OPERATIONAL_METRICS_V1;
type MetricLabels = Readonly<Partial<Record<Dimension, string>>>;
type MetricHeader = Readonly<{
  version: 1;
  startUtc: string;
  endUtc: string;
  signal: OperationalMetricNameV1;
  unit: Unit;
  dimensions: MetricLabels;
}>;
export type OperationalMetricV1 = MetricHeader &
  (
    | Readonly<{ kind: "counter" | "gauge"; value: number }>
    | Readonly<{
        kind: "histogram";
        buckets: readonly number[];
        counts: readonly number[];
        total: number;
      }>
  );

function isMetricName(value: unknown): value is OperationalMetricNameV1 {
  return typeof value === "string" && Object.hasOwn(OPERATIONAL_METRICS_V1, value);
}

// Read only plain own data properties without invoking accessors or proxy traps.
function dataRecord(value: unknown): Readonly<Record<string, unknown>> | undefined {
  if (typeof value !== "object" || value === null || types.isProxy(value)) return;
  const prototype: unknown = Object.getPrototypeOf(value);
  if (prototype !== null && prototype !== Object.prototype) return;
  const copy: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
  const keys = Reflect.ownKeys(value);
  if (keys.length > 10) return;
  for (const key of keys) {
    if (typeof key !== "string") return;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor?.enumerable || !Object.hasOwn(descriptor, "value")) return;
    copy[key] = descriptor.value;
  }
  return copy;
}

function utcMillis(value: unknown): number | undefined {
  if (typeof value !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z$/.test(value)) {
    return;
  }
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return;
  const canonical = value.length === 20 ? value.replace("Z", ".000Z") : value;
  if (new Date(time).toISOString() === canonical) return time;
}

function validCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function numberList(value: unknown): number[] | undefined {
  if (
    types.isProxy(value) ||
    !Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Array.prototype
  )
    return;
  const length = value.length;
  if (length === 0 || length > MAX_FINITE_BUCKETS || Reflect.ownKeys(value).length !== length + 1)
    return;
  const list: number[] = [];
  for (let index = 0; index < length; index += 1) {
    const item = Object.getOwnPropertyDescriptor(value, index);
    if (!item?.enumerable || !Object.hasOwn(item, "value") || !validCount(item.value)) return;
    list.push(item.value);
  }
  return list;
}

function parseLabels(value: unknown, domains: Dimensions): MetricLabels | undefined {
  const labels = dataRecord(value);
  const names = Object.keys(domains) as Dimension[];
  if (!labels || Object.keys(labels).length !== names.length) return;
  const result: Partial<Record<Dimension, string>> = {};
  for (const name of names) {
    const label = labels[name];
    if (typeof label !== "string" || !domains[name]?.includes(label)) return;
    result[name] = label;
  }
  return Object.freeze(result);
}

type BucketLayouts = Readonly<Partial<Record<OperationalMetricNameV1, readonly number[]>>>;

export function createOperationalMetricParserV1(
  approvedBuckets: unknown = {},
): ((input: unknown) => OperationalMetricV1 | undefined) | undefined {
  const layouts = dataRecord(approvedBuckets);
  if (!layouts) return;
  const approved = Object.create(null) as Partial<
    Record<OperationalMetricNameV1, readonly number[]>
  >;
  for (const [name, layout] of Object.entries(layouts)) {
    if (!isMetricName(name) || OPERATIONAL_METRICS_V1[name].kind !== "histogram") return;
    const bounds = numberList(layout);
    if (!bounds) return;
    let previous = -1;
    for (const bound of bounds) {
      if (bound <= previous) return;
      previous = bound;
    }
    approved[name] = Object.freeze(bounds);
  }
  const fixedLayouts = Object.freeze(approved);
  return (input) => parseOperationalMetricV1(input, fixedLayouts);
}

const headerFields = ["version", "startUtc", "endUtc", "signal", "unit", "kind", "dimensions"];

function parseOperationalMetricV1(
  input: unknown,
  approvedBuckets: BucketLayouts,
): OperationalMetricV1 | undefined {
  const record = dataRecord(input);
  if (!record || record.version !== 1 || !isMetricName(record.signal)) return;
  const definition = OPERATIONAL_METRICS_V1[record.signal];
  if (definition.kind !== record.kind || definition.unit !== record.unit) return;
  const fields = [
    ...headerFields,
    ...(definition.kind === "histogram" ? ["buckets", "counts", "total"] : ["value"]),
  ];
  if (
    Object.keys(record).length !== fields.length ||
    !fields.every((key) => Object.hasOwn(record, key))
  )
    return;
  const { startUtc, endUtc } = record;
  if (typeof startUtc !== "string" || typeof endUtc !== "string") return;
  const start = utcMillis(startUtc);
  const end = utcMillis(endUtc);
  if (start === undefined || end === undefined || start >= end) return;
  const dimensions = parseLabels(record.dimensions, definition.dimensions);
  if (!dimensions) return;
  const header: MetricHeader = {
    version: 1,
    startUtc,
    endUtc,
    signal: record.signal,
    unit: definition.unit,
    dimensions,
  };
  if (definition.kind !== "histogram") {
    if (!validCount(record.value) || (definition.unit === "boolean" && record.value > 1)) return;
    return Object.freeze({ ...header, kind: definition.kind, value: record.value });
  }
  const expected = approvedBuckets[record.signal];
  const buckets = numberList(record.buckets);
  const counts = numberList(record.counts);
  if (!expected || !buckets || !counts || !validCount(record.total)) return;
  if (buckets.length !== expected.length || counts.length !== expected.length) return;
  let previous = 0;
  for (const [index, count] of counts.entries()) {
    if (buckets[index] !== expected[index] || count < previous || count > record.total) return;
    previous = count;
  }
  return Object.freeze({
    ...header,
    kind: "histogram",
    buckets: Object.freeze(buckets),
    counts: Object.freeze(counts),
    total: record.total,
  });
}
