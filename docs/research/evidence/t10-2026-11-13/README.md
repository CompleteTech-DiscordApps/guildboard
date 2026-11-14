# T10 validation at eee0ad43

These artifacts record code revision `eee0ad43bcbcc4a262b352eb115d8ac11a04b59d`.
Historical publication `34642fb` changes documentation/evidence only. Its code,
configuration and tests match the SHA-256 manifest in [receipt.json](receipt.json).
No result is attributed to an untested publication revision.

- [Normal suite log](suite-normal.log): 48 tests pass, no skips.
- [Optimized suite log](suite-optimized.log): 48 tests pass, no skips.
- [Baseline report](baseline.sanitized.json): 12 actual local Nginx checks pass.
- [Six control reports](controls.sanitized.json): stripped Upgrade, Connection,
  key and version; exposed private assets; excessive read timeout all detected.
- [Control invocation](capture-controls-command.txt): sanitized capture command.
- [Windows capability log](suite-windows-capability.log): 14 portable passes,
  7 POSIX skips in a simulation; no actual Windows acceptance.
- [Planning validation](planning-validation.json): zero errors.

Each network report includes tested revision, timestamp, fixture hashes,
environment, binary hash and cleanup. Known local paths use placeholders;
results and hashes are unchanged. Artifact hashes, commands, provenance and
limits are in the receipt. This is synthetic loopback research, with no actual
Docker, public TLS, Discord, GoDaddy or production acceptance claim.

## Later cancellation validation

[Code a00c229 cancellation evidence](cancellation-a00c229/README.md) records
52 normal/optimized tests and new network/cancellation reports. The eee0ad43
artifacts above remain historical and unchanged.

[First-signal normal-cleanup follow-up](cleanup-3acb22b/README.md) records 55 normal/optimized tests, eight cleanup signal reports and repeated real-Nginx baseline/six controls at `3acb22b`. Earlier cancellation evidence did not establish first-signal safety during normal cleanup and remains historical.

[Acquisition follow-up](acquisition-f0bf9c7/README.md) adds post-spawn/pre-assignment and other resource-creation signal coverage: 59 normal/optimized tests, 20 signal reports, baseline/six controls at `f0bf9c7`. The earlier normal-cleanup bundle did not establish acquisition safety.

The [acquisition before-run provenance audit](acquisition-f0bf9c7/before-provenance.json) distinguishes checkout metadata from dynamically imported old executable Git blobs and links a reproducible three-failure rerun. Original reports and fixed-head test results remain unchanged.

[Reproducer validation under optimization](acquisition-f0bf9c7/reproducer-checks-4cca655.json) replaces removable provenance/outcome assertions with explicit checks. Real old-code reruns pass their expected-failure checks under normal/-O, and ten malformed-input/outcome cases are explicitly rejected. Production code/results are unchanged.

[Post-upgrade idle timing](idle-6950c3e/README.md) records 62 normal/optimized tests and real Nginx baseline/six controls at `6950c3e`. A delayed two-second handshake plus immediate EOF reproduces the old false acceptance and is rejected after separating handshake and postvalidated idle clocks.
