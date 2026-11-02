Specimen-aware database exchange: internal revision of 2 November 2026

Run from the repository root with the installed research dependencies:

python validation/review_round2_workflow.py
python validation/review_round2_verify_workflow.py

The current source package is imported directly so the example uses the same
peak-bound implementation that is being tested. The output directory is
validation/workflow_results_round2/. Previous workflow_results/ files describe
the preceding numerical specimen-ranking example and are preserved separately.

Inputs and units
The 46 original PLA+ source CSVs contain 1000 archived displacement/force pairs
each, in mm/kN. Mass_and_Crash_Indicators.xlsx supplies mass in grams and each
specimen's assessment displacement delta_max. The original workbook and source
CSV hashes are stored in summary.json and source_mapping.csv. Source data:
10.17632/v7p6y654ft.4, CC BY 4.0; associated paper 10.1515/mt-2026-0038.

Specimens and configurations
The data repository describes forty LHS configurations, plus straight-wall
STWC and nominal N-SCMC controls. The workbook explicitly contains STWC-1/2/3
and N-SCMC-1/2/3 as numeric rows, followed by Mean +/- SD rows. Thus there are
42 configurations and 46 specimen curves. The 4140 specimen-pair comparisons
over four common strokes include 24 comparisons within a repeated control.
Configuration queries use the arithmetic mean for each triplicate control and
the original singleton value for each LHS configuration. This gives 3444
numerical configuration-pair comparisons; it does not supply experimental
uncertainty for the forty unreplicated configurations.

Construction and client
Each specimen table uses work priority, absolute-peak retention, a 1 J window
error tolerance and at most 129 nodes. The same 46 tables serve all common
strokes: 10, 20, 30 and 40 mm. The client examples/query_exchange.py reads only
the received table and reported mass. It computes EA, SEA, MCF, positive peak
force and CFE, with reference-reconstruction intervals. Positive peak bounds
become exact at/after a source-verified retained positive global maximum.
Before that point the error/anchor bounds remain conservative. The plotting
example STWC-1 has its peak before all four common strokes, so its CFE bounds
only propagate the stored prefix-work error.

Repeat scatter and mass sensitivity
repeat_scatter.csv reports the sample standard deviation (ddof=1), CV and range
of the three actual STWC specimens and the three actual N-SCMC specimens at
each common stroke. This is descriptive between-specimen dispersion for those
two controls, not a confidence interval, isolated measurement uncertainty or
uncertainty estimate for the forty singletons. The achieved reconstruction
bounds and actual errors are compared directly with those observed SDs.
rounding_sensitivity_pairs.csv separately examines mass +/-0.05 g, corresponding
to hypothetical rounding to the nearest 0.1 g. It is an arithmetic sensitivity
scenario based on displayed decimals; no balance calibration or instrument
uncertainty is inferred from it.

Published-indicator cross-check
published_indicator_comparison.csv evaluates every table at the workbook's own
delta_max. Published EA, PCF, MCF, SEA and CFE are copied from the immutable
source workbook and compared with reduced values, numerical-reference values
and reconstruction intervals. The published workbook is an independently
provided set of derived quantities from the same experimental dataset. This
check is distinct from the deterministic client-contract test and is not a
claim of independent software adoption or a new experimental cohort.

All 46 source-reference values are covered. Published EA/SEA/MCF/CFE values are
covered in 45 of 46 cases; PCF is covered in all 46. Specimen 05 is the honest
exception: the source PL work is 290.800436 J whereas the workbook reports
290.865173 J. Its reduced EA upper bound is 290.800440 J, so the published value
is outside while the source-reference value is inside. No bound is expanded
to absorb this discrepancy. All thirteen nonzero work disagreements occur at
reported delta_max=50 mm with archived endpoints of 50.004--50.009 mm. Their
published EA values equal integrals to those actual archived endpoints within
5.69e-13 J; the other 33 cases match the stated delta_max integral. Specimen 05
ends at 50.009 mm. This source-window diagnostic is recorded without silently
changing the nominal query or the source's reported MCF denominator. The
maximum EA disagreement at the stated assessment displacement is 0.117816 J
over all specimens. Endpoint convention and reconstruction are kept separate.

Output map
summary.json: source links, construction choices, all headline values.
tables/: 46 received response JSONs, 1520 retained nodes in total.
queries.csv: 184 common-stroke client queries, reference values and intervals.
configuration_queries.csv: mean/singleton values for 42 configurations.
repeat_scatter.csv: eight control/stroke descriptive dispersion rows.
published_indicator_comparison.csv: all 46 published delta_max comparisons.
specimen_pairs.csv: numerical pairs, including flagged within-configuration pairs.
configuration_pairs.csv: 3444 mean/singleton numerical comparisons.
rounding_sensitivity_pairs.csv: separate reported-mass rounding scenario.
verification.json: source, table, client-contract and workbook audit results.

The verifier uses completed-source-segment integration plus a separately
evaluated final partial segment. It recomputes repeat scatter and all published
indicator comparisons from the original workbook and CSVs, rather than treating
client/producer agreement as external validation. A separate analytic example
checks CFE intervals both before and after a retained source maximum.
