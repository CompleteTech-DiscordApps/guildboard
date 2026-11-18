import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import { pathToFileURL } from "node:url";

const output = mkdtempSync(
  path.join(process.env.ENGINEERING_TEST_TMP || os.tmpdir(), "gb-deletion-"),
);
after(() => rmSync(output, { recursive: true, force: true }));
writeFileSync(path.join(output, "package.json"), '{"type":"module"}');
const build = spawnSync(
  process.execPath,
  ["node_modules/typescript/lib/tsc.js", "-p", "apps/api/tsconfig.json", "--outDir", output],
  { encoding: "utf8" },
);
assert.equal(build.status, 0, build.stderr + build.stdout);
const {
  DELETION_MAX_RESTORE_MARKERS,
  canReleaseIsolatedRestore,
  decideDeletionJobStart,
  decideDeletionJobTransition,
  parseDeletionJobV1,
} = await import(pathToFileURL(path.join(output, "deletion-job.js")));

const ref = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const guild = { kind: "guild", target: { guildRef: ref(1) } };
const board = { kind: "board", target: { guildRef: ref(1), boardRef: ref(2) } };
const subject = { kind: "subject", target: { guildRef: ref(1), subjectRef: ref(3) } };
const foreign = { ...board, target: { ...board.target, guildRef: ref(4) } };
const peer = { ...board, target: { ...board.target, boardRef: ref(5) } };
const job = { version: 1, jobId: ref(6), ...board, phase: "fenced" };
const authority = (action, scope = board) => ({ current: true, scope, action });
const denied = { ok: false, code: "FORBIDDEN" };
const invalid = { ok: false, code: "INVALID_JOB" };
const precondition = { ok: false, code: "PRECONDITION_FAILED" };
const transition = (state, changes) =>
  decideDeletionJobTransition(state, authority("advance"), changes);
const finishLive = {
  action: "finish-live",
  jobId: job.jobId,
  scope: board,
  liveReferencesReconciled: true,
  liveCopiesRemovedOrUnderApprovedIsolation: true,
};
const finish = {
  action: "finish",
  jobId: job.jobId,
  scope: board,
  requiredCopiesReconciled: true,
  remainingExceptionsExpiredOrHaveApprovedDisposition: true,
};

test("parses a closed v1 job for each exact target and phase", () => {
  for (const scope of [guild, board, subject]) {
    for (const phase of ["fenced", "propagating", "live_complete", "complete"]) {
      const candidate = { ...job, ...scope, phase };
      assert.deepEqual(parseDeletionJobV1(candidate), candidate);
    }
    const candidate = { ...job, ...scope };
    assert.deepEqual(decideDeletionJobStart(candidate, authority("start", scope)), {
      ok: true,
      job: candidate,
    });
  }
  const interrupted = { ...job, phase: "propagating", failure: "propagation-interrupted" };
  assert.deepEqual(parseDeletionJobV1(interrupted), interrupted);
  assert.equal(Object.hasOwn(parseDeletionJobV1(job), "failure"), false);
});

test("rejects malformed jobs before a fencing or propagation decision", () => {
  const getter = Object.defineProperty({ ...job }, "target", {
    enumerable: true,
    get() {
      assert.fail("read job accessor");
    },
  });
  const revoked = Proxy.revocable(job, {});
  revoked.revoke();
  for (const candidate of [
    null,
    [],
    { ...job, version: "1" },
    { ...job, version: 2 },
    { ...job, jobId: "12345" },
    { ...job, kind: "unknown" },
    { ...job, phase: "pending" },
    { ...job, target: guild.target },
    { ...job, kind: "guild" },
    { ...job, target: { ...board.target, subjectRef: subject.target.subjectRef } },
    { ...job, target: Object.create(board.target) },
    { ...job, target: { ...board.target, boardRef: "12345" } },
    { ...job, debug: ref(7) },
    { ...job, [Symbol("extra")]: true },
    { ...job, failure: undefined },
    { ...job, failure: "propagation-interrupted" },
    { ...job, phase: "propagating", failure: ref(8) },
    Object.defineProperty({ ...job }, "extra", { value: true }),
    getter,
    revoked.proxy,
  ]) {
    assert.equal(parseDeletionJobV1(candidate), undefined);
    assert.deepEqual(decideDeletionJobStart(candidate, authority("start")), invalid);
    assert.deepEqual(transition(candidate, { action: "propagate" }), invalid);
  }
  assert.deepEqual(
    decideDeletionJobStart({ ...job, phase: "complete" }, authority("start")),
    invalid,
  );
});

test("requires affirmative scoped authority for each action", () => {
  for (const grant of [
    undefined,
    { ...authority("start"), current: false },
    authority("advance"),
    authority("start", foreign),
    authority("start", peer),
    authority("start", guild),
    authority("start", subject),
  ]) {
    assert.deepEqual(decideDeletionJobStart(job, grant), denied);
  }
  for (const grant of [undefined, authority("start"), authority("advance", foreign)]) {
    assert.deepEqual(decideDeletionJobTransition(job, grant, { action: "propagate" }), denied);
  }
});

test("preserves the fence through interrupted, repeated and out-of-order calls", () => {
  for (const action of [{ action: "interrupt" }, { action: "retry" }, finishLive, finish]) {
    assert.deepEqual(transition(job, action), precondition);
  }
  const running = transition(Object.freeze(job), { action: "propagate" });
  assert.deepEqual(running, { ok: true, job: { ...job, phase: "propagating" } });
  assert.deepEqual(transition(running.job, { action: "propagate" }), running);
  const interrupted = transition(Object.freeze(running.job), { action: "interrupt" });
  assert.deepEqual(interrupted, {
    ok: true,
    job: { ...running.job, failure: "propagation-interrupted" },
  });
  assert.deepEqual(transition(interrupted.job, { action: "interrupt" }), interrupted);
  assert.deepEqual(transition(interrupted.job, { action: "propagate" }), precondition);
  assert.deepEqual(transition(interrupted.job, finishLive), precondition);
  assert.deepEqual(transition(interrupted.job, { action: "retry" }), running);
  assert.deepEqual(transition(running.job, { action: "retry" }), running);
  assert.deepEqual(transition(running.job, finish), precondition);

  const live = transition(running.job, finishLive);
  assert.deepEqual(live, { ok: true, job: { ...job, phase: "live_complete" } });
  assert.deepEqual(transition(live.job, finishLive), live);
  assert.deepEqual(transition(live.job, { action: "retry" }), precondition);
  assert.deepEqual(transition(live.job, { action: "interrupt" }), precondition);
  const complete = transition(live.job, finish);
  assert.deepEqual(complete, { ok: true, job: { ...job, phase: "complete" } });
  assert.deepEqual(transition(complete.job, finish), complete);
  assert.deepEqual(transition(complete.job, finishLive), precondition);
  assert.deepEqual(transition(complete.job, { action: "propagate" }), precondition);
});

test("verifies completion evidence against the milestone, identity and scope", () => {
  const running = { ...job, phase: "propagating" };
  const live = { ...job, phase: "live_complete" };
  for (const [state, proof, flags] of [
    [
      running,
      finishLive,
      ["liveReferencesReconciled", "liveCopiesRemovedOrUnderApprovedIsolation"],
    ],
    [
      live,
      finish,
      ["requiredCopiesReconciled", "remainingExceptionsExpiredOrHaveApprovedDisposition"],
    ],
  ]) {
    for (const changes of [
      { scope: foreign },
      { scope: peer },
      { jobId: ref(9) },
      ...flags.map((flag) => ({ [flag]: false })),
    ]) {
      assert.deepEqual(transition(state, { ...proof, ...changes }), precondition);
    }
  }
});

function restoreEvidence() {
  const scope = { guildRef: guild.target.guildRef, restoreRef: ref(10) };
  const restore = { ...scope, appliedCut: 7n };
  const fence = { ...scope, fenceRef: ref(11) };
  const markers = [
    { sequence: 8n, markerRef: ref(12) },
    { sequence: 9n, markerRef: ref(13) },
  ];
  const current = { ...fence, highWater: 9n, markers };
  const reconciliation = {
    ...fence,
    through: 9n,
    applied: markers.map((marker) => ({
      ...marker,
      contentHidden: true,
      assetsHidden: true,
      exportsHidden: true,
      referencesHidden: true,
    })),
    revocationsReapplied: true,
    currentAuthorityVerified: true,
    lineageVerified: true,
    receiptsVerified: true,
  };
  return { restore, fence, current, reconciliation };
}

test("authorizes a reconciled restore only through the current exposure fence", () => {
  const { restore, fence, current, reconciliation } = restoreEvidence();
  assert.equal(canReleaseIsolatedRestore(restore, fence, current, reconciliation), true);
  assert.equal(
    canReleaseIsolatedRestore(
      { ...restore, appliedCut: 9n },
      fence,
      { ...current, markers: [] },
      { ...reconciliation, applied: [] },
    ),
    true,
  );

  // The marker source observes a deletion ordered after reconciliation.
  const later = { sequence: 10n, markerRef: ref(14) };
  const newFence = { ...fence, fenceRef: ref(15) };
  const latest = { ...current, ...newFence, highWater: 10n, markers: [...current.markers, later] };
  assert.equal(canReleaseIsolatedRestore(restore, newFence, current, reconciliation), false);
  assert.equal(canReleaseIsolatedRestore(restore, newFence, latest, reconciliation), false);
  assert.equal(
    canReleaseIsolatedRestore(restore, newFence, latest, { ...reconciliation, ...newFence }),
    false,
  );
  assert.equal(
    canReleaseIsolatedRestore(restore, newFence, latest, {
      ...reconciliation,
      ...newFence,
      through: 10n,
      applied: [...reconciliation.applied, { ...reconciliation.applied[0], ...later }],
    }),
    true,
  );
});

test("keeps restore isolated for missing, stale, oversized or inconsistent marker coverage", () => {
  const { restore, fence, current, reconciliation } = restoreEvidence();
  const [first, second] = current.markers;
  for (const authorityWindow of [
    undefined,
    { ...current, guildRef: foreign.target.guildRef },
    { ...current, restoreRef: ref(16) },
    { ...current, fenceRef: ref(17) },
    { ...current, highWater: 6n },
    { ...current, highWater: 9 },
    { ...current, highWater: 7n + BigInt(DELETION_MAX_RESTORE_MARKERS) + 1n },
    { ...current, highWater: 1n << 64n },
    { ...current, markers: [second] },
    { ...current, markers: [second, first] },
    { ...current, markers: [first, { ...second, sequence: 10n }] },
    { ...current, markers: [first, { ...second, markerRef: first.markerRef }] },
    { ...current, markers: [first, { ...second, markerRef: "invalid" }] },
  ]) {
    assert.equal(canReleaseIsolatedRestore(restore, fence, authorityWindow, reconciliation), false);
  }
  for (const cut of [-1n, 7, 10n]) {
    assert.equal(
      canReleaseIsolatedRestore({ ...restore, appliedCut: cut }, fence, current, reconciliation),
      false,
    );
  }
});

test("keeps restore isolated until all markers and current recovery rules are verified", () => {
  const { restore, fence, current, reconciliation } = restoreEvidence();
  const [first, second] = reconciliation.applied;
  const deny = (proof) =>
    assert.equal(canReleaseIsolatedRestore(restore, fence, current, proof), false);
  deny(undefined);
  deny({ ...reconciliation, through: 8n });
  deny({ ...reconciliation, guildRef: foreign.target.guildRef });
  deny({ ...reconciliation, restoreRef: ref(18) });
  deny({ ...reconciliation, fenceRef: ref(19) });
  deny({ ...reconciliation, applied: [first] });
  deny({ ...reconciliation, applied: [first, { ...second, markerRef: ref(20) }] });
  for (const flag of ["contentHidden", "assetsHidden", "exportsHidden", "referencesHidden"]) {
    deny({ ...reconciliation, applied: [first, { ...second, [flag]: false }] });
  }
  for (const flag of [
    "revocationsReapplied",
    "currentAuthorityVerified",
    "lineageVerified",
    "receiptsVerified",
  ]) {
    deny({ ...reconciliation, [flag]: false });
  }
});
