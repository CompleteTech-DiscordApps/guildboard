"""Bounded SRE research fixture; no service, network, SQL or product protocol.

Only synthetic data in an owned TemporaryDirectory is used. Queue times are
virtual; file timings are wall clock. Neither is a Guildboard performance claim.
"""
import argparse
from collections import deque
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time


def percentiles(values):
    values = sorted(values)
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    return {f"p{p}": round(values[math.ceil(len(values) * p / 100) - 1], 6)
            for p in (50, 95, 99)}


def queue_model(rate, seconds, service_ms, limit):
    """Single virtual worker; limit includes in-service work; no real sleeping."""
    if (not all(type(x) in (int, float) and x > 0
                and (type(x) is int or math.isfinite(x))
                for x in (rate, seconds, service_ms))
            or type(limit) is not int or limit < 1):
        raise ValueError("invalid or unbounded model configuration")
    # Interpret numeric inputs by their decimal spelling. Exact event times
    # ensure a completion at an arrival releases its slot before admission;
    # binary rounding or an epsilon must not invent/hide queue saturation.
    exact_rate, exact_seconds, exact_service_ms = (
        Fraction(str(x)) for x in (rate, seconds, service_ms))
    offered = exact_rate * exact_seconds
    if offered > 100_000:
        raise ValueError("invalid or unbounded model configuration")
    completions = deque()
    latencies = []
    rejected = peak = 0
    count = int(offered)
    for i in range(count):
        arrival = i / exact_rate
        while completions and completions[0] <= arrival:
            completions.popleft()
        if len(completions) >= limit:
            rejected += 1
            continue
        finished = max(arrival, completions[-1] if completions else arrival) + exact_service_ms / 1000
        completions.append(finished)
        latencies.append(float((finished - arrival) * 1000))
        peak = max(peak, len(completions))
    return {"arrival_rate_per_second": rate, "virtual_seconds": seconds,
            "assumed_service_ms": service_ms, "outstanding_limit": limit,
            "offered": count, "accepted_and_eventually_completed": len(latencies),
            "rejected": rejected, "peak_outstanding": peak,
            "accepted_virtual_latency_ms": percentiles(latencies),
            "last_completion_virtual_seconds": round(float(completions[-1]), 6) if completions else 0}


def record(index):
    # Harness-only format; deliberately unrelated to a board operation contract.
    return (json.dumps({"fixture_index": index, "synthetic": "x" * 2048},
                       separators=(",", ":")) + "\n").encode("ascii")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path, expected_digest, count):
    if digest(path) != expected_digest:
        raise ValueError("fixture digest mismatch")
    rows = path.read_bytes().splitlines(keepends=True)
    if len(rows) != count or any(row != record(i) for i, row in enumerate(rows)):
        raise ValueError("fixture sequence/content mismatch")
    return len(rows)


def child_writer(path):
    # An owned child exits abruptly after a flushed prefix. No shared process dies.
    with path.open("wb") as handle:
        for i in range(32):
            handle.write(record(i))
        handle.flush()
        os.fsync(handle.fileno())
    os._exit(23)


def file_experiment(root):
    journal = root / "journal"
    latencies = []
    start = time.perf_counter()
    with journal.open("wb") as handle:
        for i in range(300):
            before = time.perf_counter()
            handle.write(record(i))
            handle.flush()
            os.fsync(handle.fileno())
            latencies.append((time.perf_counter() - before) * 1000)
    elapsed = time.perf_counter() - start
    expected = digest(journal)
    backup = root / "backup"
    before = time.perf_counter()
    shutil.copyfile(journal, backup)
    verify(backup, expected, 300)
    backup_ms = (time.perf_counter() - before) * 1000
    restored = root / "restored"
    before = time.perf_counter()
    shutil.copyfile(backup, restored)
    restored_count = verify(restored, expected, 300)
    restore_ms = (time.perf_counter() - before) * 1000
    restored.write_bytes(restored.read_bytes()[:-1])
    rejected_corruption = False
    try:
        verify(restored, expected, 300)
    except ValueError:
        rejected_corruption = True
    abrupt = root / "abrupt"
    before = time.perf_counter()
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            "--child-write", str(abrupt)], timeout=15, check=False,
                           capture_output=True)
    expected_prefix = hashlib.sha256(b"".join(record(i) for i in range(32))).hexdigest()
    prefix_count = verify(abrupt, expected_prefix, 32)
    child_ms = (time.perf_counter() - before) * 1000
    if child.returncode != 23 or not rejected_corruption:
        raise RuntimeError("fault experiment did not match expected outcome")
    return {"records": 300, "synthetic_content_bytes_per_record": 2048,
            "journal_bytes": journal.stat().st_size, "journal_sha256": expected,
            "write_flush_fsync_ms": percentiles(latencies),
            "write_total_wall_seconds": round(elapsed, 6),
            "observed_records_per_wall_second": round(300 / elapsed, 3),
            "copy_and_verify_backup_ms": round(backup_ms, 6),
            "copy_and_verify_restore_ms": round(restore_ms, 6),
            "restored_records": restored_count, "truncated_copy_rejected": rejected_corruption,
            "abrupt_owned_child_exit_code": child.returncode,
            "abrupt_child_prefix_verified_records": prefix_count,
            "child_start_exit_and_prefix_verify_wall_ms": round(child_ms, 6)}


def run():
    before = time.process_time()
    with tempfile.TemporaryDirectory(prefix="guildboard-t11-research-") as directory:
        files = file_experiment(Path(directory))
    return {"experiment": "GB-T11.R1-local-fixture-v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "os": platform.system(),
            "os_release": platform.release(), "machine": platform.machine(),
            "script_sha256": digest(Path(__file__)),
            "source_base_commit": "c108b552a660e12a3b3998e1e1ad944fbd7a894d",
            "scope": "virtual queue plus local synthetic files; no application/SQL/network/VPS",
            "queues": {"steady": queue_model(100, 60, 4, 128),
                       "burst": queue_model(1000, 10, 4, 128),
                       "slow_dependency": queue_model(100, 10, 20, 128)},
            "files": files, "parent_cpu_seconds": round(time.process_time() - before, 6)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child-write", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child_write:
        child_writer(args.child_write)
    result = json.dumps(run(), indent=2) + "\n"
    if args.output:
        # Exclusive creation preserves any earlier measurement receipt.
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(result)
    else:
        print(result, end="")
