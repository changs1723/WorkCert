WorkCert v0.2 extended selector and exact-objective benchmark

The protocol is baselines_protocol.txt. The 70 numerical references are unchanged
from the credited source archive. All numerical rows retain dataset identifiers;
pooled medians describe this benchmark rather than a manufacturing population.

Run with Python 3.10+ and NumPy; full exact-DP acceleration additionally uses
Numba (tested Python 3.12.14 / NumPy 2.3.5 / Numba 0.68.1). Third-party selector checks
add rdp 0.8 and simplification 2.0.0. These are validation dependencies only.
The tested Python 3.12 environment is pinned in requirements-baselines-locked.txt;
install it with python -m pip install -r validation/requirements-baselines-locked.txt.

Commands from the revision project root:
  python validation/check_baselines.py
  python validation/extended_benchmark.py
  python validation/optimal_dp.py
  python validation/extended_benchmark.py --finish-dp
  python validation/verify_extended_benchmark.py

The last command evaluates the already computed optimal paths using WorkCert
and reports matched-objective greedy/optimal ratios. It does not rerun selection
or reinterpret the DP paths as globally optimal prefix/window approximations.

Selectors
Work priority and vertical priority share a largest-vertical-residual insertion
rule. Fixed-budget RDP chooses the largest perpendicular-distance segment after
normalizing each axis to unit range; it is a best-first fixed-budget adaptation,
not an epsilon-to-point-count wrapper. Visvalingam--Whyatt selects the vertex
with smallest current neighboring-triangle area and records nondecreasing
effective removal areas. Endpoints and the first absolute force maximum remain
fixed for these selectors and uniform-with-peak. The plain uniform baseline
deliberately omits the peak constraint and is labelled separately.

Native algorithm checks
Unanchored epsilon RDP agrees in 80/80 cases with rdp 0.8. Epsilon effective-area
VW agrees in 80/80 cases with simplification 2.0.0. Fixed-budget selectors pass
200 additional endpoint/anchor/count checks. These seeded synthetic inputs
verify implementations; they are not additional experimental specimens.
Details: results_v02/third_party_validation.json.

Exact dynamic programming
All 58 original references with n <= 1000 are included: 46 PLA+ and 12 CX steel.
The other 12 larger originals (11 steel records and the EDAH record) are listed as excluded. No original
is downsampled to make an optimality claim. For every eligible reference,
all candidate edges are evaluated for continuous absolute residual area eta
and maximum vertical residual delta. Paths of exactly 9, 17, 33 or 65 vertices
minimize sum(edge eta) or max(edge delta), respectively, and retain the same
endpoints/absolute-peak node. Cost precomputation is O(n^3), DP O(K n^2), and
memory O(n^2+K n). A compiled loop makes n = 1000 practical on the recorded host;
the n ceiling remains explicit rather than implying arbitrary-size scalability.
The prefix and window errors of those optimal-objective paths are measured
separately. Neither objective makes their prefix/window errors globally optimal.

Artifacts
selector_metrics.csv: 2100 force-based and 350 work-only fixed-budget rows.
stopping_metrics.csv: 560 runs (70 records x 2 hierarchies x 4 error measures), 1% tol.
terminal_controls.csv: 70 exact terminal-work scalar controls.
tables/:actual portable JSON records and their checksums.
comparative_summary.json:per-cohort medians, paired outcomes and same-task
  eta-versus-window stopping counts. Prefix stopping is a distinct query task.
dp_solutions.json,dp_verification.json:optimal paths, cost values, eligibility,
  objective definitions and exhaustive-enumeration verification.
dp_metrics.csv,optimality_gaps.csv,dp_summary.json,dp_cohort_summary.json:measured errors and objective
  gaps for the optimal paths and matching greedy objectives.

There is no automatic winning selector. The main evidence for requiring an
explicit method choice is preserved in all per-record outcomes, including
records where VW or vertical allocation improves on work allocation.
Build timings in selector_metrics are single descriptive construction samples;
performance claims use the separately controlled scaling experiment instead.
