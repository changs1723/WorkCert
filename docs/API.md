# WorkCert API reference

## `reduce_response`

```python
reduce_response(x, force, *, max_points=33, tolerance=None,
                certificate="prefix", relative=False, method="work",
                preserve_peak=True, x_unit="mm", force_unit="kN",
                provenance=None)
```

`x` and `force` are aligned one-dimensional arrays of finite values, with at
least two points. `x` is strictly increasing. Forces may be signed. A response
returns retained coordinates and a `Certificate`.

`max_points` is an integer upper budget. Budgets greater than the reference size
are capped to that size. A budget below the number of forced endpoint/peak nodes
is rejected. `method` is `work`, `vertical`, `uniform` or `uniform_peak`.
`preserve_peak=True` retains the first index attaining the global maximum.

`tolerance=None` runs to the fixed budget. A finite nonnegative tolerance runs
adaptive selection until the chosen current bound meets the threshold or the
point limit is reached. Tolerance mode is supported by `work` and `vertical`.
`certificate` is `eta`, `xi`, `prefix` or `window`. Relative stopping uses the
absolute value of terminal reference work as scale. Exactly zero terminal work
requires absolute tolerance. The current value is evaluated after every
insertion, without a monotonicity assumption. An unmet tolerance returns a
valid table with `metadata["tolerance_met"] == False`.

Unit labels describe the supplied numbers and never convert them. Known work
labels are mm/kN -> J, m/N -> J, m/kN -> kJ and mm/N -> mJ. Other products are
displayed as `force_unit*x_unit`. `provenance` must be a JSON-serializable object; it is
stored in `metadata["provenance"]`.

## `certify(x, force, indices)`

Evaluate continuous residual extrema and integrals for any vertex subset.
Integer indices are strictly increasing, unique and include both endpoints.
The subset need not preserve the peak. The returned immutable `Certificate`
has work-unit fields `eta`, `xi`, `prefix`, `window`, `signed_terminal_error`,
`reference_work`, `min_cumulative_error`, `max_cumulative_error`; force-unit
field `delta`; and `reference_points`, `reference_sha256`.

`Certificate.bound(kind="prefix", relative=False)` selects and optionally
normalizes a work bound. `Certificate.to_dict()` returns plain scalar metadata.

## `ReducedResponse`

`x`, `force` and `indices` expose NumPy arrays backed by immutable bytes;
`setflags(write=True)` is rejected. `certificate`
contains the evaluated bounds; `metadata` returns a copy. `x_unit`, `force_unit`
and `work_unit` expose native unit labels.

`force_at(q)` evaluates retained PL force. `work(q)` evaluates its exact
piecewise-quadratic primitive from the original reference origin. `window_work(a,
b)` returns the primitive difference for broadcastable arrays with `a <= b`.
Queries may be scalars or arrays; results preserve broadcast shape. All query
locations must be finite and within the retained/reference domain. Out-of-domain
queries raise `ValueError` rather than extrapolating or clamping.

Construction caches slopes and cumulative trapezoids at the retained nodes.
A batch of Q queries uses binary interval searches: O(Q log K) search work and
O(Q) arithmetic for K retained points. The cache is rebuilt from K values when
loading, so it does not enlarge the portable representation.

`to_bytes()` returns deterministic compact UTF-8 JSON. `save(path)` writes these
bytes. `ReducedResponse.load(path)` checks schema version, payload SHA-256,
coordinate validity and certificate relationships. Files store source hashes
but not the dense reference. `verify_reference(x, force)` validates that source
hash, selected coordinates and recomputed certificate against the full source.
JSON SHA-256 is a corruption check, not an adversarial signature.

## Numerical interpretation

For PL references and reconstructions, residuals are affine per reference cell.
Absolute areas split at residual zero crossings; extrema of the error primitive
are at cell endpoints and those interior zeros. Consequently the reported
`prefix` and `window` values are tight in exact real arithmetic for the supplied
reference. Their numerical evaluation uses ordinary float64 arithmetic.

The original reference is available offline during certification. The exact
prefix and window bounds can therefore be stored directly; eta and xi are
also exposed for additive-area diagnostics and comparison. Peak retention alone
does not preserve every earlier prefix peak. For prefix force constraints,
evaluate the corresponding peak or use the force error bound.

## Errors and lifecycle

Invalid numeric input, unsupported modes, domain violations, checksum failure,
inconsistent certificate fields and a mismatched reference raise `ValueError`.
File errors retain `OSError`. CLI failures exit with status 2 and a short message.
No method performs network access, modifies source CSVs or changes global state.

Version 0.1.0 uses schema `workcert.response/1.0`. Retain the schema,
software-version fields and reference hash together with dataset attribution
when archiving output tables.
