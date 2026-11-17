# T12 catchable cancellation evidence — 2026-11-13 UTC

Exact tested code and tests: `b4ba0adcf6d3da878a19510591ff20b23e40ddb0`. File SHA-256 values,
commands, raw logs, environment and limitations are in [receipt.json](receipt.json).
This publication is research-tool evidence; it does not establish platform acceptance.

At baseline `8dca9ec1d98ce121ff20e254ccb651c8b56758b3`, the same owned
loopback signal regressions expose four remaining fetch workers after SIGTERM and
no collector exit within four seconds after SIGINT. See [before.log](before.log).
The fixture cleans up only its recorded fetch workers after checking the leak.

At the tested revision, all 36 focused tests pass normally and with `-O`.
Both raw signal probes preserve the completed healthy source and completed
403-then-pinned-fallback source, return the other eight source rows as failed
observations, reap all seven launched workers, and prevent queued cancelled
sources from launching children. The exit codes are 143 and 130. An additional fake-CLI probe delivers the first
signal during normal successful-fetch cleanup for each signal; it reaps the child
and returns nonzero while retaining the successful row. Raw outputs are
[normal-cleanup SIGTERM](normal-cleanup-sigterm-output.json) and
[normal-cleanup SIGINT](normal-cleanup-sigint-output.json). Prior signal
handlers are restored after collection, including exceptions. [signals.log](signals.log)
records the assertions; [SIGTERM output](sigterm-output.json) and
[SIGINT output](sigint-output.json) retain literal collector stdout/stderr and exit codes.
Reproduce with `python docs/research/evidence/t12-cancellation-2026-11-13/signal-probe.py`.
All traffic goes to owned loopback fixtures, with Discord URLs routed locally.

The parent polls cancellation every 50ms and gives each killed direct child a
one-second communicate/reap budget; OS scheduling adds overhead. No guarantee is
made for parent SIGKILL, host loss or uninterruptible OS states. No shared process
group or arbitrary descendant cleanup is claimed. Historical source observations
are unchanged. Fresh schedule and matrix JSON equal historical evidence; ten
external scenarios remain not-run. Native acceptance and independent review gates
remain open.
