# ADR 0003: Architecture change controls

Status: selected within delegated section authority for issue #30; independent architecture, security and consumer review and native maintainer/protected review remain required. This records a design decision, not an approval of a pull request or runtime behavior. It does not modify ADR 0001, ADR 0002, the accepted system contract or its acceptance history.

## Context and evidence

Issue GB-T0.04.02.T1 requires decisions, requirement-to-control traceability and detection of undocumented boundary changes. `docs/requirements/GB-T0-01-01-requirements.md`, UC01–UC20, `docs/architecture.md`, GB-T0.S1 and its canonical fixtures specify design obligations. `scripts/verification/verify_architecture.py` checks accepted artifact identity; it must remain intact. Its result and declarative scenarios do not verify product behavior or approve a semantic change.

## Decision and alternatives

Use a bounded, machine-readable trace linking requirement IDs to concrete interfaces, security controls and acceptance evidence; compare boundary inputs to an explicit previous baseline and require a specific versioned decision plus linked control and acceptance evidence for each change. The independent reviewer must inspect the actual semantic diff and evidence. A checker can enforce structure, linkage and change detection but cannot decide whether natural-language security semantics are correct. Baseline changes require actual review and must not be automatically resealed by the checker. Unavailable or malformed inputs, unknown shapes and interrupted checks fail closed without publishing success or changing a baseline.

An ADR filename alone is rejected because an unrelated ADR does not explain a particular changed boundary. An unchecked fixed hash or automatic reseal is rejected because it can bless changed material without review. Relying only on manual review is rejected because changed boundary inputs may be overlooked. Replacing the existing accepted-artifact checker is rejected because it would discard its distinct identity guarantee.

## Consequences and follow-through

The manager UUID `01a1d2c4-663a-7181-824d-febb00e1dd4a` owns native integration and validation of the executable schema, baseline comparison, regression and PR checks, and coordinating independent #31 verification. The gate must be least privilege, offline-capable for local checks and not deploy an app or require secrets. Reviewers must assess actual diffs, changed trust boundaries, alternatives, acceptance evidence and downstream effects. Maintainer/native protected review remains necessary; this ADR does not assert review, runtime, platform or release results.
