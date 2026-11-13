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
