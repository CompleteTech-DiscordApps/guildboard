# First signal during normal cleanup

Tested code: `3acb22bc8c5df924e5c2277aa68ff168dde34c2c`.
The later documentation-only publication preserves the [source hashes](receipt.json).

[Normal](suite-normal.log) and [optimized](suite-optimized.log) suites each pass
55 tests with no skips. [Network reports](network.sanitized.json) preserve the
12-check real local Nginx baseline and six detected unsafe controls.

[Eight first-signal reports](cleanup-reports.sanitized.json) cover SIGTERM and
SIGINT during normal Docker inspection, local Nginx stop, backend shutdown and
fetch-worker reaping. Docker is simulated. Local cleanup uses actual owned Nginx
and backend resources with a synthetic successful probe body; source cleanup
uses actual children with synthetic response envelopes. Passing tests verify
nonzero 143/130 status, original signal identity, completed cleanup and retained
body results or cancelled source rows. [Capture log](cleanup-capture.log) and
[reproduction command](capture-command.txt) describe the capture.

[Before reports](before-cleanup.sanitized.json) preserve the old owned-container
leak and surviving backend thread; [new tests against old code](before-regressions.log)
fail. Only captured owned resources were rescued. Prior evidence is preserved.

Signals are deferred throughout owned cleanup, including when the first signal
arrives there. Source workers now use explicit kill/reap/pipe closure instead of
implicit subprocess.run cleanup. Repeated catchable signals retain the first
signal. SIGKILL, host/power failure and forced termination remain outside these
claims. Actual Docker/GoDaddy/Discord/TLS and native approvals remain unverified;
fresh whole-head review is required. See [planning validation](planning-validation.json).
