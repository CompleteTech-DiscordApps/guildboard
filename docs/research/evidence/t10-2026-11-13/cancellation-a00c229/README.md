# Catchable cancellation validation at a00c229

Tested code: `a00c22929c224d9b35975c90c461a34501719192`.
A separate documentation/evidence commit publishes these results; source,
configuration and test hashes match [receipt.json](receipt.json).

- [Normal](suite-normal.log) and [optimized](suite-optimized.log) suites: 52 tests
  pass in each, no Linux skips.
- [Network reports](network.sanitized.json): baseline 12 checks and all six
  unsafe controls; each report includes code revision, fixture/binary hashes,
  timestamp, environment and cleanup.
- [Cancellation reports](cancellations.sanitized.json) and [capture log](cancellation-capture.log):
  actual SIGTERM/SIGINT owner JSON for local Nginx and source capture. Passing
  regressions verify process/worker cleanup and completed-source retention.
- [Before control](before-sigterm.json): historical unhandled SIGTERM failure at
  `34642fb`, followed by bounded external cleanup of the captured owned group.
- [Network/suite commands](capture-commands.txt), [raw cancellation capture](capture-cancellations-command.txt), [Windows capability simulation](suite-windows-capability.log)
  and [planning output](planning-validation.json).

Known owned paths are replaced with placeholders; results and fixture hashes
are unchanged. These are catchable-signal guarantees after handlers install,
not SIGKILL, power-loss or forced Windows process-termination guarantees.
Docker cancellation uses a simulated command boundary; no external platform or
production acceptance is claimed. Fresh whole-head review remains required.
