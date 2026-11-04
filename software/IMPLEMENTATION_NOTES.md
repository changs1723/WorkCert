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

## Stable binary64 integration and metadata comparison (0.3.0)

Residuals use local force offsets, `(F-F_left)-slope*(x-x_left)`, with
separately materialized NumPy operations. This avoids subtracting two
independently rounded large force baselines. Retained residuals are zero.

An O(n) balanced up/down scan replaces serial cumulative addition. Tree
nodes carry a high sum and a low correction with the standard TwoSum
addition identity. Segment endpoint means also retain their low component;
`math.fsum` computes each terminal sum. The scan has O(log n) dependency
depth and O(n) storage. Products, subnormal arithmetic and final float64
outputs still round; neither the scan nor the PL-error formulas constitute
outward-rounded arithmetic.

A response caches an analogous O(K)-size compensated segment tree. Prefix
and interval queries combine complete-segment ranges with directly integrated
endpoint pieces. The endpoint integral uses the midpoint's convex weights
on the original endpoint forces; it does not first round two interpolated
endpoint forces. Each ordinary query takes O(log K) work. Directed branch queries
use the local interval interface as well. This avoids loss caused solely by
subtracting large global prefixes. It cannot make a binary64 return value
resolve a term smaller than that value's own spacing.

A twofold cache alone cannot preserve arbitrarily many widely separated
scales. Each response therefore also caches absolute sums of the original
leaf components. If the computed net is no larger than eps64 times this
absolute sum, the query is recomputed with `math.fsum` over its original
segment components and endpoint pieces. This detects internal cancellation
that may already have reduced a signed subtree to zero. The fallback costs
O(m) for a query spanning m retained segments; this changes the worst-case
query complexity to O(K). The eps64 condition is a precision policy, not an
outward error estimate. Path-reference integration uses the same endpoint-
mean components and summation policy as the response integrals.

Reference verification keeps source identity exact. Its numeric comparison
allows at most 16 ULPs at the larger nonzero field magnitude and requires
zero/nonzero agreement exactly. The 16-ULP budget is an explicit metadata
comparison policy tested with final-bit and material perturbations, not a
bound on integration error or a safety/security guarantee. In particular,
large force magnitudes do not relax an error field's comparison.

Internal range/identity relationships use their own work-valued scales
and a 16-ULP consistency budget, with no unit-sized floor. Consequently a
small physical unit does not turn a materially inconsistent file into a
valid object. Resolved reconstruction errors cannot be replaced by zero
under the former source-force-scaled allowance. If an old saved table fails
these stronger checks, regenerate its metadata from its trusted full source.

The 0.2.0 installation and source records remain historical evidence;
they are not evidence that the revised 0.3.0 runtime passed those runs.
New strict-review tests are in `tests/test_numerical_stability.py`. They
cover constant and exactly representable affine families, actual binary
non-affine samples, short windows, signed cancellation, small-unit corruption,
source checks and API/CLI overflow. The new tests were developed with AI
assistance and do not extend the authors' earlier manual-verification record.
Current installed-suite and platform evidence are recorded with the actual
runtime hashes by the repository validation workflow.

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
