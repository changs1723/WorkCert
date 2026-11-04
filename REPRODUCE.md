# Reproducing WorkCert 0.3.0

The scientific source, the installable package, and the manuscript are distinct
versioned objects. The source contains the original numerical inputs,
preparation programs, saved results, verification programs and plotting code.
An article snapshot and its build manifest identify the corresponding PDF and
editable manuscript separately. A software DOI identifies the contents of its
software record; it does not by itself identify a manuscript PDF.

## Install and test the actual package

The runtime requires Python 3.10 or later and NumPy 1.24 or later.

```text
python -m pip install ./software
python validation/run_installed_suite.py --output ../workcert-installed-checks
python validation/test_reproduction_contract.py
```

Choose a new, empty output directory. The installed-suite runner verifies that
all runtime modules are imported from the installed distribution and match the
source hashes. It discovers every `test_*.py` file once, and records three
phases: the 39 baseline methods, the 28 Hou acceptance methods, and the current
0.3 numerical-stability regressions. The original Hou tests retain their
separate per-check ledger. Test method counts and the number of ledger rows are
different quantities; the generated summary reports both. The CLI contract
checks separately verify successful and failing audits, mutation detection,
output isolation, and refusal to overwrite earlier reports.

`environment.json` records Python, NumPy, WorkCert, import locations and hashes.
Each phase has a raw log; failures also appear in the terminal. `cases.csv`,
`results.jsonl`, `results.csv` and `summary.json` preserve the checks actually
performed. This entry point does not regenerate scientific outputs. Earlier
0.2 acceptance logs and the author's dated test-verification statement concern
that recorded run; they are not recast as human verification of new 0.3 tests.

## Research dependencies

Comparisons, workbook audits, plotting and dynamic programming have additional
dependencies beyond the NumPy-only runtime:

```text
python -m pip install -r validation/requirements-reproduce.txt
```

`requirements-baselines-locked.txt` records the comparative environment. Timings
record their actual environment and implementation hashes separately.

## Verify the frozen source without changing it

```text
python validation/reproduce_v03.py --verify-only --output-dir ../workcert-verification
```

Verification first checks the supplied `MANIFEST.sha256`, when present. It
copies the frozen scientific files to `working_copy` in the new output directory,
checks copied bytes against the initial source snapshot, and runs the numerical
validators there. Existing validators may write reports inside that isolated
copy. They never replace the original data, saved tables, exported connector
input, or recorded scientific results. No cyclic or connector generator runs
in verification mode, and no result is silently regenerated before it is checked.

The final `verification_summary.json` records the source hashes before and after,
all command exit codes, and `source_unchanged`. The same source-immutability
check runs after a failing validator. The isolated working copy and logs remain
available for inspection. With no `--output-dir`, a new system temporary folder
is created and its path is printed. Outputs inside `software`, `data`,
`validation`, `examples`, `references`, `authoring`, `release_evidence`, `article`,
`article_inputs` or `figures` are
rejected. The repository's private `qa` directory or a sibling directory is
suitable. Use a new output folder for every run.

For a quick byte-integrity check of a published archive:

```text
python validation/reproduce_v03.py --verify-only --checks integrity --output-dir ../workcert-integrity
```

This mode requires the published manifest and is explicitly an integrity check,
not numerical recomputation. A development tree without a root manifest can
use full verification, whose table and source validators inspect their own
manifests. Hash identity, independent arithmetic and rerunning an optimization
problem are recorded as different forms of evidence.

Full numerical verification checks preparation, the saved comparative tables,
exact rational controls, client indicators, cyclic outputs and the frozen
connector export. `independent_archive_arithmetic.py` uses standard-library
scalar arithmetic rather than WorkCert queries to recompute all saved force-table
errors, work-only errors and terminal scalars. Small-reference dynamic-programming
optimality checks supplement those path-cost checks. They do not imply that
verification has rerun all 580 full-size optimizations. When present, the new
`decision_verify.py` independently checks the decision-focused case as well.

The earlier `reproduce_v02.py` command is a compatibility alias for this same
read-only protocol. Direct invocation of an older component verifier can still
write its own report; use the unified entry point to preserve the source tree.

## Explicitly recompute the scientific results

```text
python validation/reproduce_v03.py --recompute
```

This mode intentionally replaces derived results in the source tree. It verifies
or acquires included fixed inputs, prepares references, checks selectors,
rebuilds comparisons, solves objective-matched dynamic programmes, and rebuilds
the exchange, cyclic, connector and decision examples. Original input files are
verified before any acquisition request. This operation differs from a read-only
audit. Run it in a development checkout or a fresh copy when preserving a release.

To regenerate timings and figures as well:

```text
python validation/reproduce_v03.py --recompute --include-scaling --figures
```

`--figures` and `--include-scaling` require `--recompute`; they cannot be added to
a verification-only command. Timings use a synthetic signal, a specified host,
paired processes and recorded software hashes. New measurements depend on the
host and load. They do not describe every possible experimental response.

## Scientific outputs and consumers

| Directory | Contents |
|---|---|
| `data/raw`, `data/reference_inputs`, `data/source_context`, `data/extended` | Credited original numerical inputs and source metadata |
| `data/prepared` | 70 numerical compression references |
| `validation/results_v02` | Comparative tables, scalar/stopping controls and objective-matched DP paths; the directory name retains the established data layout |
| `validation/workflow_results_round2` | Specimen and configuration queries, repeated controls and source-workbook comparisons |
| `validation/workflow_results` | Exchange tables and chronological branch tables |
| `validation/cyclic_round2_results` | Branch diagnostics, directed residual summaries and deadband diagnostics |
| `validation/connector_results` | Saved 33-point connector-format export and its numerical round trip |
| `validation/decision_results` | Initial adjacent rankings and query-driven candidate refinements |
| `validation/results/scaling` | Timings with implementation, software and hardware records |

The source data keep their CC BY 4.0 attribution and software code uses MIT terms.
The established directory names identify scientific datasets and compatibility
layouts; they do not mean that cached 0.2 arithmetic is accepted as 0.3 evidence.

`examples/query_exchange.py` reads a saved table and reported mass without
loading its dense reference. For example:

```text
python examples/query_exchange.py validation/workflow_results_round2/tables/STWC-1.json --mass-g 16.2 --strokes 10 20 30 40
```

`validation/decision_results/mass_rounding.json` reports the initial, refined and
full-reference SEA intervals for configurations 26 and 35, using both reported
masses and a +/-0.05 g rounding scenario. The refined tables separate the
reported-mass values; rounding leaves the pair unresolved even with full source
curves. `decision_workflow.py` regenerates this result and `decision_verify.py`
checks it using independent Decimal arithmetic.

`examples/compose_branch_errors.py` enforces the exact ordering invariant that
each summary's extrema contain zero and its terminal value, without a work-unit
tolerance floor. Composition uses sequential binary64 arithmetic; the
real-arithmetic identity does not enclose rounding error. Its regression suite
includes equivalent unit scales, invalid zero extrema, directed records and
strong cancellation:

```text
python validation/test_branch_summary_validation.py
```

The connector example is a loading-table exchange and an independent numerical
reader. It is not a record of a finite-element solver run. The consumer does not
infer unloading laws or solver regularization from the force table.

## Manuscript and publication-state provenance

Scientific tables and figures are rebuilt from the fixed inputs. Mutable facts
such as a later release URL, CI conclusion or newly registered DOI are publication
metadata, not scientific observations. The manuscript snapshot and its hash/build
record specify exactly which metadata were used for the accompanying article.
Use those editable sources to regenerate that article; do not infer that an older
software archive's generator recreates later editorial changes. New version URLs
and DOI claims must be bound to their actual published records. The 0.2 DOI
`10.5281/zenodo.23915585` remains the preceding software archive and must not be
presented as the 0.3.0 version DOI.
