# WorkCert 0.3.0 API

## Reduction

```python
reduce_response(x, force, *, max_points=33, tolerance=None,
    certificate="prefix", relative=False, method=None, preserve_peak=True,
    peak_mode="absolute", x_unit="unspecified", force_unit="unspecified",
    provenance=None)
```

Supply `method` explicitly: `work`, `vertical`, `uniform`, `uniform_peak`, or `vw`.
Inputs are aligned finite one-dimensional real arrays, length at least two,
with strictly increasing x. Signed forces are retained. Endpoints are forced;
`peak_mode` selects the first maximum absolute force (`absolute`), maximum
signed force (`positive`) or minimum signed force (`negative`). Set
`preserve_peak=False` to disable a peak except for `uniform_peak`.

`max_points` is an integer cap, limited to the reference size; required nodes
must fit. `vw` removes the smallest current triangle in normalized coordinates,
protecting endpoints and the selected peak; equal areas are ordered by source
index. It provides fixed-count Visvalingam–Whyatt simplification. A finite
nonnegative `tolerance` is supported only by `work` and `vertical`.
`certificate` selects `eta`, `xi`, `prefix`, or `window`. Relative bounds divide
by absolute reference terminal work; exactly zero net work requires absolute
units. A capped unmet tolerance returns a valid response with
`metadata["tolerance_met"] == False`.

The parameter name `certificate` and the `Certificate` type are retained for
API compatibility. They select or store numerical reconstruction-error metadata.

Native unit labels describe values without conversion; defaults are unassigned.
Products mm/kN and m/N give J, mm/N gives mJ, and m/kN gives kJ.
`provenance` is a finite JSON-serializable dictionary.

## Error metadata

`certify(x, force, indices)` evaluates continuous errors for a vertex subset.
Indices are strictly increasing integers including endpoints. The immutable
`Certificate` (`ErrorMetadata` alias) has fields `eta`, `xi`, `prefix`, `window`,
`delta`, `signed_terminal_error`, `reference_work`, `min_cumulative_error`,
`max_cumulative_error`, `reference_points`, and `reference_sha256`.

`bound(kind="prefix", relative=False)` selects a work error measure;
`to_dict()` returns serializable scalars. `prefix` is max|D| and `window` is
max D - min D, evaluated at nodes and interior residual zeros. These describe
reconstruction of the supplied PL numerical reference using float64 formulas.

The adaptive constructor combines local residual summaries in an augmented AVL
tree and checks a candidate stopping point with a complete global recomputation.
`metadata["global_error_evaluations"]` records these passes. Worst-case local
segment rescanning is O(nK); AVL updates take O(log K) work and O(K) memory.

## ReducedResponse

Read-only `x`, `force` and `indices` arrays have immutable backing storage.
`metadata` returns a deep copy. Properties include `certificate`, `x_unit`,
`force_unit`, and `work_unit`.

- `force_at(q)` returns PL force at scalar or array coordinates.
- `peak_force(q)` returns the maximum signed retained force from the origin
  through q, including the interpolated force at q.
- `peak_bounds(q)` returns `(lower, upper)` for the corresponding source peak.
- `work(q)` integrates from the first reference x to q using compensated cached range sums.
- `window_work(a,b)` broadcasts endpoints and requires a <= b.
- Nonfinite and out-of-domain queries raise `ValueError`; no extrapolation.
- `to_bytes()` produces deterministic compact UTF-8 JSON.
- `save(path)` and `ReducedResponse.load(path)` persist and validate a response.
- `verify_reference(x,force)` checks source hash, selected values and errors.

Three numerical meanings are separate:

1. `eta`, `xi`, `prefix`, `window` and `delta` are the exact-real PL
   reconstruction quantities defined by the supplied binary64 coordinates.
   Their returned values are float64 evaluations of those formulas.
2. Integration and queries also round. Compensated pairwise sums retain low
   components of segment means and sums; terminal sums use `math.fsum`.
   Products, interpolation and the final returned number still round. The
   reconstruction values do not include those arithmetic effects and are
   not outward-rounded enclosures. Large positive and negative contributions
   or a very small requested error need an independent precision check.
3. File/reference checks compare metadata, rather than proving arithmetic
   enclosures or engineering tolerances. SHA-256, source size, retained
   coordinates and peak summaries match exactly. Recomputed and stored
   **nonzero** numerical fields may differ by at most 16 ULPs at the larger
   field magnitude; if either field is zero, both must be exactly zero.
   This local serialization policy has no force-baseline or one-unit floor.
   It permits final-bit variation without letting a large source force mask
   an erased reconstruction error. It is not a general forward-error theorem.

`window_work` integrates endpoint pieces and compensated complete-segment
range sums in O(log K) work per ordinary query. It never subtracts two global prefix
values. For a full table `x=[0,1,2]`, `force=[1e16,0,1]`, the interval
`window_work(1,2)` is `0.5` while manually subtracting `work(2)-work(1)`
returns zero: both huge prefixes round to the same binary64 number.
Use `window_work` for local intervals. A cached absolute-original-component
sum detects severe cancellation even when a signed subtree has already lost
small terms: if `abs(net) <= eps64 * sum(abs(components))`, the query is
recomputed by `math.fsum` over its original retained-segment components and
endpoint pieces. This precision-triggered fallback costs O(m) for the m
segments spanned by that query. The condition estimate is not an error bound.
The public example
`software/examples/numerical_stability_probe.py` reproduces this distinction,
long constant references and rejected inconsistent metadata as JSON.

Loading checks relationships using their work-valued scales; terminal-work
consistency uses the retained absolute-work quadrature and error scale.
Neither check inserts a one-unit floor. Their 16-ULP consistency budgets
are distinct from the reconstruction quantities. A source-verification
mismatch names the field, recomputed value, stored value and allowance;
verification never changes the saved file.

The JSON schema remains `workcert.response/1.0`. Earlier files can be read
when their stored numerical identities meet these checks. The strengthened
0.3.0 recomputation can reject metadata from earlier evaluation algorithms,
even with the same source hash. In that case regenerate the table with
`from_indices` and the trusted full reference; do not widen a tolerance or
silently replace a bound. Payload checksums detect accidental changes and
do not authenticate a source.

New tables carry a `retained_global_maximum` summary only when the first global
signed maximum of the supplied source is retained. Its reference index,
coordinate and force are checked against the retained table on load and against
the complete source by `verify_reference`. At and after this coordinate the
source and retained prefix peaks coincide, so `peak_bounds` returns identical
limits. Before it, or for old files without a summary, the bounds use `delta`
and already retained source values. This tightens CFE denominators after a
retained global maximum without treating the force-error bound as measurement
uncertainty. Like stored work-error values, this source summary must be verified
against the numerical source when its provenance is being checked.

## Chronological branches

```python
split_monotone_branches(displacement, force, *, duplicate_policy="split")
```

Finite aligned inputs follow acquisition order and may reverse. The `BranchSeries`
result has `branches`, `events`, `reference_work` and `source_points`. Each
`MonotoneBranch` has ascending immutable `x`, `force` and original
`source_indices`, plus chronological `start_x`, `end_x`, and `direction` (+1/-1).
A reversal node is shared by adjacent branches.

`branch.directed_work(response,q=None)` evaluates physical F dx from its
chronological start to q (default end): a signed `response.window_work` call on the corresponding interval.
The response must have the same branch domain and reference hash. Loading and unloading stay
separate even when they share displacement values.

Equal-displacement pairs remain `ZeroDisplacementEvent` records with original
indices, displacement and both forces; their work is zero. `duplicate_policy="error"`
rejects such pairs. Constant displacement input yields events and no branches.
No noise filter, smoothing, sign conversion or contact alignment is implicit.

## CLI

`workcert reduce` requires `--method` and accepts `--peak-mode`, `--no-peak`,
`--max-points`, `--certificate`, `--tolerance`, `--relative`, column names and
unit labels. Unit defaults are `unspecified` even if a header suggests mm or kN.
`query`, `inspect` and `verify` operate on saved responses. Invalid inputs
return exit code 2 with a concise diagnostic.

## External selectors

`from_indices(x, force, indices, *, x_unit="unspecified", force_unit="unspecified", provenance=None)`
creates a response for an external algorithm's endpoint-preserving vertex subset.
It validates integer indices, evaluates complete error metadata, and enables the
same queries, persistence and reference verification as built-in selectors.

`indices_from_coordinates(x, force, coordinates)` maps external `(x, force)`
vertices (for example `np.asarray(shapely.simplify(line, tolerance).coords)`)
to source indices. Every pair must match a source vertex exactly, both endpoints
must be present, and source order must be increasing. Changed coordinates,
rounding, repeated or reversed vertices are rejected; the adapter never silently
projects or snaps geometric output onto the reference.
