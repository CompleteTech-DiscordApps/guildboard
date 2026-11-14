# Post-upgrade idle timing at 6950c3e

Tested code/configuration/tests: `6950c3e253ead359d621102ebf068e03b5f3fef7`. A later documentation-only publication retains the [source hashes and provenance](receipt.json); its HEAD is not presented as the tested revision.

- [Normal](suite-normal.log) and [optimized](suite-optimized.log) suites: 62 tests each, zero skips.
- [Raw sanitized capture](capture.sanitized.json): delayed two-second handshake followed by immediate EOF falsely passes old `623dd1f`, but fails the fixed idle window. A valid two-second interval after validated 101 passes.
- The same capture records all 12 real local Nginx checks and six detected unsafe controls, including the excessive 60-second read timeout.
- [Portable capture](capture.py) verifies unchanged tested source bytes, imports the exact old fixture Git blob for the before case, checks expected outcomes and writes JSON only afterward. [Invocation result](capture.log) records its successful rerun. Run from a checkout with both Git objects, passing repository, owned Nginx binary and output paths as shown in the receipt.
- [Planning validation](planning-validation.json): zero errors.

The idle clock now starts only after complete validated upgrade headers. A separate total connection/handshake deadline also rejects a slow drip rather than extending per-read timeouts indefinitely. Ordinary frame-return behavior is retained. The pre-upgrade and post-upgrade budgets are separate, so total elapsed exchange time can include both.

The before reproduction uses old fixture code with the fixed-head test harness; it is not an old full-suite result. Earlier public evidence remains unchanged. Results establish synthetic loopback behavior only, with no Docker, GoDaddy, public TLS, Discord, production or independent approval claim.
