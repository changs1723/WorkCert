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
installation evidence is in `software/release_validation.json`.

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

The verification checks source preparation, the 3544 comparative/optimal-path
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

## Regenerate figures and inspect a consumer query

```text
python authoring/build_v02_figures.py
python examples/query_exchange.py validation/workflow_results/pla_exchange/tables/stage_0/STWC-1.json --mass-g 16.2 --strokes 10 20 30 40
```

The five figures are exported as vector PDF, preview PNG and 600 dpi TIFF.
`examples/query_exchange.py` reads only the JSON response and measured mass; it
does not read the dense source curve. `validation/verify_workflow.py` compares
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
| `validation/results_v02` | 3080 comparison/stopping/scalar tables, 464 optimal-path tables, per-case CSVs, summaries and independent checks |
| `validation/workflow_results` | 123 exchanged compression tables, 2971 cyclic branch tables, client queries, scalar responses, source links and checks |
| `validation/results/scaling` | Recorded construction timings and paired repeats |
| `validation/scaling` | Archived 0.1 implementation used as the full-scan control |
| `authoring` | Reproducible value collection, scientific plotting and manuscript generation |

The root `MANIFEST.sha256` covers the files actually present in the published
tree, including dotfiles, and excludes itself and Git's internal files. Code
uses MIT terms; the experimental datasets retain CC BY 4.0 attribution.
