# Changelog

## 0.3.0 — prepared 3 November 2026

- Replace serial cumulative sums with compensated pairwise integration.
- Integrate local work windows without subtracting large global primitives.
- Recompute severely cancelling queries from original components and keep path-reference arithmetic consistent.
- Evaluate residuals in local force offsets and strengthen metadata checks.
- Remove unit-sized consistency floors and require exact zero/nonzero agreement.
- Unify finite-range overflow as API ValueError and concise CLI exit 2.
- Add strict-review regressions and a machine-readable numerical-stability example.


## 0.2.0 — prepared 31 October 2026; revised 2 November 2026

- Require an explicit selection method and label unassigned units explicitly.
- Add absolute, positive and negative peak rules.
- Vectorize residual stationary points and update tolerance metadata through an
  augmented AVL tree, with a complete error evaluation before stopping.
- Preserve chronological loading and unloading branches and zero-displacement
  force transitions through a new preprocessing interface.
- Add regression tests, a 15-job cross-platform CI specification and Python
  3.10 minimum metadata. Completed test runs are reported separately.
- Keep schema-1.0 responses readable and expose `ErrorMetadata` as an alias for
  the existing `Certificate` class.
- Add fixed-count Visvalingam–Whyatt selection and an exact coordinate-to-index
  adapter for external simplifiers.
- Store a retained-source-global-maximum summary and expose query-specific
  peak bounds, with full-source verification and conservative old-file fallback.

## 0.1.0 — 30 October 2026

Initial public response-table API, continuous work-query errors, JSON
persistence and source verification. The original public commit is
`4703d7d24ec6481a4a10a20f82ec36de1efc2c73`.
