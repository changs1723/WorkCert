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

The 31 numerical/CLI/persistence/branch tests pass for installed wheel and source
distributions on Windows with Python/NumPy 3.10.0/2.2.6, 3.12.14/2.3.5 and
3.14.7/2.5.4. The 3.10 and 3.14 virtual environments use independently installed
dependencies; the 3.12 environment shares a preinstalled NumPy. Package imports
are checked to resolve to the installed environment. Fifteen original v0.1.0
JSON responses were additionally loaded and verified against their references.
Artifact hashes and precise runtime evidence are in `release_validation.json`.

The supplied CI workflow targets Python 3.10-3.13 on Linux, macOS and Windows.
A workflow specification alone is not evidence of a completed remote run.
The README and this file do not claim cross-platform results before execution.

Scaling measurements are in `validation/results/scaling/` at the repository
root. Final measurements use supported Python 3.12.14/NumPy 2.3.5. The three-pair
million-node test reaches 0.1% window error at 107 points in both versions, with
median construction times 14.275704 s (0.1.0) and 1.052961 s (0.2.0). These
include construction, source hashing and final complete error evaluation. The
full-reference error-pass count falls from 105 to one. The waveform is synthetic;
the timing comparison concerns these implementations and this recorded host.
