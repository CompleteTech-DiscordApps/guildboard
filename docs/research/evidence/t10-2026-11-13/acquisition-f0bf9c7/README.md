# Cancellation during owned resource acquisition

Tested code: `f0bf9c78cfaccd17e4b8f423039760b661427435`.
Later documentation publication preserves [source hashes](receipt.json).

[Normal](suite-normal.log) and [optimized](suite-optimized.log) suites each pass
59 tests without skips. [Actual network reports](network.sanitized.json) record
the 12-check local Nginx baseline and all six detected unsafe controls.

[Twenty signal reports](signal-reports.sanitized.json) include first SIGTERM/SIGINT
after real Nginx master/worker spawn and source-worker spawn, before caller handle
assignment; backend construction, thread startup, temporary directory and stderr
file creation; plus the earlier normal-cleanup phases. Passing regressions assert
reaped children, exited Nginx workers, closed sockets/pipes/files, removed temporary
directories and truthful cleanup flags. Transient-command spawn/reap is also tested.
[Capture log](signal-capture.log) and [capture command](capture-command.txt) preserve
how these reports were collected.

[Original raw reports](before-acquisition.sanitized.json) are preserved unchanged.
Their embedded `tested_sha` and runner hash describe checkout `f0bf9c7`, because
old `run_local` reads HEAD/source files through `ROOT`. The implementation was
dynamically imported from old Git-extracted files. [Provenance audit](before-provenance.json)
verifies those saved files against exact `9802c81` Git blob IDs/SHA-256 hashes,
records the `f0bf9c7` test harness and import/monkeypatch mappings, and distinguishes
checkout metadata from executed code. A [saved reproduction script](reproduce-before.py)
extracts fresh old Git blobs and records executable module paths/hashes explicitly.
Its [verified rerun](before-verified.sanitized.json) and [failure log](before-verified.log)
confirm all three acquisition methods fail on that old implementation, with only
captured owned resources rescued. The earlier [failure log](before-regressions.log)
remains historical. The fixed-head 59-test validation remains unchanged.

Acquisition now occurs inside cleanup-covered try blocks with catchable signals
deferred through handle assignment. Pending signals then unwind into cleanup.
Short subprocess.run commands defer through bounded spawn/reap (five seconds for
local git/Nginx checks, thirty seconds for Docker CLI, plus scheduling/cleanup).
Active worker/network probes remain cancellable between protected phases.

Docker is simulated; source-spawn fixtures are actual disposable children with
synthetic bodies. Local Nginx spawn uses actual masters/workers. Historical evidence
is preserved. No SIGKILL, host/power failure, forced termination or real external
platform guarantee is claimed. Native acceptance and fresh independent review
remain open. See [planning validation](planning-validation.json) and receipt limits.
