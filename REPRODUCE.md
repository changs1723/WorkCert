# Reproducing WorkCert 0.2

Run commands from the repository root. Runtime installation and scientific
validation use separate dependencies. The complete reference and raw numerical
inputs are included; acquisition scripts verify existing files before making
any network request.

## Runtime installation and package checks

```text
python -m pip install ./software
python -m unittest discover -s software/tests -v
```

The supported runtime starts at Python 3.10. Source-distribution and wheel
installation evidence is in `software/release_validation.json`; it records
only the original 39-test suite and remains unchanged. The rebuilt November 3
wheel and source distribution are recorded separately in
`software/release_validation_round3.json`: each exact asset passed all 67 tests
and 759 additional comparisons after installation in a new Python 3.12 virtual
environment using the existing base NumPy and build dependencies.

## Independent numerical acceptance

The complete repository adds 28 tests, for a current total of 67. Use the
installed package and retain the repository's `data/`, `validation/` and
`examples/` directories. No research packages beyond WorkCert and NumPy are
needed for this acceptance run; its oracles use Python's standard library.

```text
python validation/run_hou_acceptance.py --phase all --output validation/hou_acceptance_run
```

`--phase baseline` runs only the original 39 installation checks;
`--phase independent` runs only the 28 additional tests. The default `all`
executes them in that order and records separate logs. Use a new output
directory each time: prior results cannot be overwritten. The runner verifies
that all installed runtime files match the workspace and refuses a direct
source-tree import.

The saved `environment.json` records Python, NumPy and WorkCert versions,
import paths and file hashes. `baseline.log` and `independent.log` are raw
unittest logs; `results.csv`/`results.jsonl` contain every new comparison's
expected value, actual value, difference, tolerance and PASS/FAIL;
`case_summary.csv` and `summary.json` record case and suite counts. New tests
cover analytical formulas (including interior residual zeros), work windows,
signed peaks and CFE, chronological branches and dwells, persistence/rejection,
Table 2, specimen 05 and both triplicate controls. Analytical tolerances are
normally 1e-12 absolute; real-data work uses 1e-9 J and other indicators use
1e-10, with separate half-last-digit checks for printed values.

The archived 2026-11-03 run is in `validation/hou_acceptance`: 39 original plus
28 new tests passed, with 759 new comparisons and no failures or skips, on
Windows/Python 3.12.14/NumPy 2.3.5/installed WorkCert 0.2.0. The new evidence
covers that environment only; current remote results are reported in GitHub Actions. This acceptance
does not rerun all 580 DP controls or million-point timing experiments.
Saisai Hou wrote and executed the additional tests with Codex assistance and
manually verified them, as confirmed by the author on 2026-11-03. This author
confirmation is recorded in
[`validation/author_verification_2026-11-03.json`](validation/author_verification_2026-11-03.json),
separately from the automated evidence. Original run logs and derivations
remain unchanged. This confirmation concerns the new tests; it does not
record all three authors' final approval of the revised manuscript.

## Research environment

Use Python 3.12 for the recorded comparative and dynamic-programming environment:

```text
python -m pip install -r validation/requirements-reproduce.txt
python -m pip install ./software
```

`validation/requirements-baselines-locked.txt` records the tested NumPy, Numba,
llvmlite, RDP and simplification versions. These packages are research
dependencies; WorkCert's runtime dependency is NumPy.

## Verify the archived evidence

```text
python validation/reproduce_v02.py --verify-only
```

The verification checks source preparation, the 3660 comparative/optimal-path
tables and their source hashes, exhaustive small-reference controls, and the
database-exchange and chronological-branch outputs. The figure programs use the
archived numerical results directly.

Individual verification commands are:

```text
python data/source_context/verify_preparation.py
python validation/verify_extended_benchmark.py
python validation/verify_workflow.py
```

## Recompute the scientific examples

```text
python validation/reproduce_v02.py --recompute
```

The unified entry point verifies/acquires the included fixed inputs, reconstructs
the prepared references, runs native selector checks, evaluates the six-selector
comparison, solves the objective-matched dynamic programmes, and reruns the
database-exchange and cyclic-path examples. Add `--figures` to regenerate the
plots after these numerical computations. Detailed component commands
and definitions are in `validation/BASELINES_README.txt` and
`validation/WORKFLOW_README.txt`.

The default recomputation reuses the archived construction timings. To rerun all
scaling cases and the three independent paired headline repeats as well:

```text
python validation/reproduce_v02.py --recompute --include-scaling --figures
python authoring/collect_v02_values.py
```

Run timings without other CPU-heavy jobs. New times depend on the host and load;
the supplied measurements record their Python/NumPy versions, signal definition,
node cap, tolerance, repeated measurements and implementation hashes. The
million-point signal is explicitly synthetic and is separate from the
experimental validation.

The November 3 timing run records CPU model, OS-visible physical memory and
software versions in `validation/results/scaling/hardware.json`, and embeds
hardware metadata in the measurement summaries. The earlier timings are retained
in the internal research archive rather than mixed with the current figure.

## Regenerate figures and inspect a consumer query

```text
python authoring/build_v02_figures.py
python examples/query_exchange.py validation/workflow_results_round2/tables/STWC-1.json --mass-g 16.2 --strokes 10 20 30 40
```

The five figures are exported as vector PDF, preview PNG and 600 dpi TIFF.
`examples/query_exchange.py` reads only the JSON response and measured mass; it
does not read the dense source curve. `validation/review_round2_verify_workflow.py` compares
all 46 initial client responses with the corresponding producer outputs.

Optional manuscript generation uses `authoring/collect_v02_values.py` and
`authoring/build_v02_manuscript.py`; typesetting additionally requires a standard
TeX installation with `elsarticle`. The journal's editable manuscript source
archive contains the class and bibliography style used for typesetting.

## Output map

| Directory | Contents |
|---|---|
| `data/raw`, `data/reference_inputs`, `data/source_context`, `data/extended` | Original numeric sources, credited metadata, archived prepared inputs and preparation checks |
| `data/prepared` | 70 unchanged numerical compression references |
| `validation/results_v02` | 3080 comparison/stopping/scalar tables, 580 optimal-path tables, per-case CSVs, summaries and independent checks |
| `validation/workflow_results_round2` | 46 current exchange tables, 42 configuration summaries, replicate scatter and source-workbook checks |
| `validation/cyclic_round2_results` | Branch-size and deadband diagnostics; exact chronological metadata and verifiers |
| `validation/connector_results` | 33-point connector-format round trip on a loading branch |
| `validation/workflow_results` | 123 exchanged compression tables, 2971 cyclic branch tables, client queries, scalar responses, source links and checks |
| `validation/results/scaling` | Recorded construction timings and paired repeats |
| `validation/scaling` | Archived 0.1 implementation used as the full-scan control |
| `authoring` | Reproducible value collection, scientific plotting and manuscript generation |

The root `MANIFEST.sha256` covers the files actually present in the published
tree, including dotfiles, and excludes itself and Git's internal files. Code
uses MIT terms; the experimental datasets retain CC BY 4.0 attribution.

The connector example uses vertical priority over the measured 0–50.005 mm
loading branch. `validation/connector_exchange.py` writes full-precision data,
reads the force/displacement columns independently, and checks force and
continuous work errors against the original polyline. This is a table exchange
test; solver regularization and unloading laws are separate modelling choices.
