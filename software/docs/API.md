# WorkCert 0.2.0 API

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
- `work(q)` integrates from the first reference x to q using cached primitives.
- `window_work(a,b)` broadcasts endpoints and requires a <= b.
- Nonfinite and out-of-domain queries raise `ValueError`; no extrapolation.
- `to_bytes()` produces deterministic compact UTF-8 JSON.
- `save(path)` and `ReducedResponse.load(path)` persist and validate a response.
- `verify_reference(x,force)` checks source hash, selected values and errors.

The schema remains `workcert.response/1.0`; version-0.1.0 files can be loaded.
Payload checksums detect accidental corruption and do not authenticate a source.

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
chronological start to q (default end): `response.work(q)-response.work(start_x)`.
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
