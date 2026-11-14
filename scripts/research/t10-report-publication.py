"""Pure bounded report I/O; callers own cancellation state and exit policy."""
import os
from pathlib import Path
import select
import stat
import sys
import tempfile
import time

REPORT_STDOUT_SECONDS = 2.0


def report_notice(message):
    # Diagnostics are best effort: a full stderr pipe must not hold cancellation.
    try:
        descriptor = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        try:
            print(message, file=sys.stderr)
        except (OSError, ValueError):
            pass
        return
    if os.name != "posix":
        try:
            print(message, file=sys.stderr)
        except (OSError, ValueError):
            pass
        return
    try:
        blocking = os.get_blocking(descriptor)
        try:
            os.set_blocking(descriptor, False)
            os.write(descriptor, (message + "\n").encode("utf-8", errors="replace"))
        finally:
            os.set_blocking(descriptor, blocking)
    except (OSError, ValueError):
        pass


def write_regular_report(path, output):
    # Do not let a FIFO/device (including a symlink to one) block publication
    # while signals are deferred. Inspect the opened object before truncating.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | getattr(os, "O_NONBLOCK", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("report destination must be a regular file")
        os.ftruncate(descriptor, 0)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = None
            stream.write(output)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def report_copy(output, output_path, *, label="probe", prefix="guildboard-t10-report-"):
    requested_ok = True
    if output_path is not None:
        try:
            write_regular_report(output_path, output)
            return output_path, False, requested_ok
        except (OSError, ValueError) as error:
            requested_ok = False
            report_notice("Cannot write " + label + " report: " + str(error))
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".json")
    path, stream = Path(name), None
    try:
        stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        with stream:
            stream.write(output)
    except BaseException:
        if stream is None:
            os.close(descriptor)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path, True, requested_ok


def write_report_stdout(output):
    try:
        descriptor = sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        # In-memory test/library streams have no descriptor or pipe backpressure.
        sys.stdout.write(output)
        sys.stdout.flush()
        return
    if os.name != "posix":
        sys.stdout.write(output)
        sys.stdout.flush()
        return
    blocking = os.get_blocking(descriptor)
    try:
        os.set_blocking(descriptor, False)
        sys.stdout.flush()
        pending = memoryview(output.encode("utf-8"))
        deadline = time.monotonic() + REPORT_STDOUT_SECONDS
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [descriptor], [], max(0, remaining))[1]:
                raise TimeoutError("stdout report publication deadline exceeded")
            try:
                written = os.write(descriptor, pending)
            except BlockingIOError:
                continue
            if written <= 0:
                raise BrokenPipeError("stdout accepted no report bytes")
            pending = pending[written:]
    finally:
        os.set_blocking(descriptor, blocking)


def discard_stdout_buffer():
    # An interrupted TextIOWrapper flush must not block again at interpreter exit.
    try:
        descriptor = sys.stdout.fileno()
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, descriptor)
        finally:
            os.close(sink)
    except (AttributeError, OSError, ValueError):
        pass


