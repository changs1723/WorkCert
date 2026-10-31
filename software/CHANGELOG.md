# Changelog

## 0.2.0 — prepared 31 October 2026

- Require an explicit selection method and label unassigned units explicitly.
- Add absolute, positive and negative peak rules.
- Vectorize residual stationary points and update tolerance metadata through an
  augmented AVL tree, with a complete error evaluation before stopping.
- Preserve chronological loading and unloading branches and zero-displacement
  force transitions through a new preprocessing interface.
- Add regression tests, a 12-job cross-platform CI specification and Python
  3.10 minimum metadata. Completed test runs are reported separately.
- Keep schema-1.0 responses readable and expose `ErrorMetadata` as an alias for
  the existing `Certificate` class.

## 0.1.0 — 30 October 2026

Initial public response-table API, continuous work-query errors, JSON
persistence and source verification. The original public commit is
`4703d7d24ec6481a4a10a20f82ec36de1efc2c73`.
