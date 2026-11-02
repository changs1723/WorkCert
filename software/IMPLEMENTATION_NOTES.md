# Implementation and validation notes

The reduction core combines a segment heap with an augmented AVL tree keyed by
the segment's first reference index. A local summary stores absolute residual
area, terminal residual work, minimum and maximum primitive, and force error.
Concatenation shifts a right summary's primitive by the left terminal residual.
An insertion replaces one summary by two and updates O(log K) ancestors.
The same local arrays determine segment priorities and split locations.

At a candidate stopping point the constructor independently evaluates the full
reference residual with `certify`; the returned error metadata always come from
that evaluation. Thus a rounding discrepancy in the tree cannot return a
response whose reported stopping bound exceeds its declared tolerance.
The worst-case cost of repeatedly scanning selected source intervals remains
O(nK), while the avoidable full-reference scan at each insertion is removed.

The new `split_monotone_branches` retains turning nodes on both neighboring
branches and records each equal-coordinate pair as a zero-work event. Every
branch has immutable ascending arrays, chronological endpoint information and
a cached source hash. `directed_work` checks this identity before integrating,
which prevents mixing loading and unloading tables with the same domain.

`from_indices` attaches the same query and reconstruction-error interface to an
external selector's indices. No universal preference among selectors is built
into the API; choosing a method is explicit.

The 39 numerical/CLI/persistence/branch/peak/geometric tests pass for installed wheel and source
distributions on Windows with Python/NumPy 3.10.0/2.2.6, 3.12.14/2.3.5 and
3.14.7/2.5.4. The 3.10 and 3.14 virtual environments use independently installed
dependencies; the 3.12 environment shares a preinstalled NumPy. Package imports
are checked to resolve to the installed environment. Fifteen original v0.1.0
JSON responses were additionally loaded and verified against their references.
Artifact hashes and precise runtime evidence are in `release_validation.json`.

The supplied CI workflow targets Python 3.10-3.14 on Linux, macOS and Windows.
A workflow specification alone is not evidence of a completed remote run.
The README and this file do not claim cross-platform results before execution.

Scaling measurements are in `validation/results/scaling/` at the repository
root, with implementation hashes, runtime versions and independent paired
measurements. Construction includes source hashing and final complete error
evaluation. The waveform is synthetic; timings concern the recorded
implementations and host. The results files are the source of the numerical
timing values, avoiding a second set of copied measurements in this document.

The revised API also exposes fixed-count effective-area VW removal. The package
implementation agrees with the scientific benchmark's VW ordering on the
recorded reference cases; a separate small-reference oracle repeatedly enumerates
all surviving triangles. A strict coordinate adapter supports external geometric
output without silently changing its points.
The VW heap uses O(n log n) time and O(n) memory, separately from the adaptive
segment-tree costs above.

Peak bounds use the force residual and retained source values. When the first
source global signed maximum is retained, the producer records its index and
coordinates. Load validates that this is a retained maximum, and source
verification recomputes the summary. For queries at/after its coordinate both
peak bounds equal its force. This uses the same source-relative trust model as
the work metadata, not a cryptographic proof of unknown source values.
