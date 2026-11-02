# WorkCert

WorkCert attaches reconstruction-error metadata to reduced force–displacement
tables and provides force, prefix-work and interval-work queries after exchange.
It supports explicit selectors, nodes from external simplification tools,
native-unit labels, checked JSON persistence and directed monotone branches of
cyclic loading histories.

**Version:** 0.2.0. **Authors:** Saisai Hou, Yunzhi Zhu and Sen Zhang.
**Correspondence:** szhang@niit.edu.cn.

## Install and test

The runtime package requires Python 3.10 or later and NumPy 1.24 or later.
From this repository root:

```text
python -m pip install ./software
python -m workcert --help
python -m unittest discover -s software/tests -v
```

The 39 package tests passed for both wheel and source-distribution installations
on Windows with Python/NumPy 3.10.0/2.2.6, 3.12.14/2.3.5 and 3.14.7/2.5.4.
The recorded installation checks are in
[`software/release_validation.json`](software/release_validation.json).
The CI workflow targets Linux, macOS and Windows with Python 3.10–3.14; completed
run status is shown in the repository's Actions tab.

## Construct and reuse a response

This small input is synthetic and illustrates the interface:

```python
from workcert import ReducedResponse, reduce_response

x = [0.0, 1.0, 2.0, 3.0]
force = [0.0, 3.0, 1.0, 0.0]
table = reduce_response(x, force, method="work", max_points=3,
                        x_unit="mm", force_unit="kN")
table.save("response.json")
received = ReducedResponse.load("response.json")
print(received.work(2.5))
print(received.window_work(1.0, 2.5))
print(received.certificate.prefix, received.certificate.window)
```

The selector is explicit. `work`, `vertical`, `vw`, `uniform` and `uniform_peak` are
available. `from_indices` accepts external nodes; `indices_from_coordinates` maps exact returned coordinates back to reference indices. Peak
retention can use absolute, positive or negative force. Omitted unit labels
remain `unspecified`; labels do not rescale the supplied numbers. Use
`tolerance=...`, `certificate="window"` or `certificate="prefix"` for a query
requirement and inspect `metadata["tolerance_met"]` when imposing a point cap.

The numerical reference is the complete supplied piecewise-linear curve.
`prefix` and `window` report its continuous maximum work-reconstruction errors;
`eta` and `xi` are conservative integral bounds and `delta` is the force error.
The evaluation uses analytic float64 formulas. These values describe numerical
reconstruction, independently of experimental measurement uncertainty.

See the [package README](software/README.md) and
[API reference](software/docs/API.md) for complete signatures, units, branch
orientation, validation and persistence behavior.

## Public-data reuse and source-indicator checks

The worked example uses 46 PLA+ specimens representing 42 configurations:
40 singletons and two triplicate controls. It evaluates EA, SEA, MCF, peak force
and CFE at changing strokes. Post-global-peak queries use exact retained-peak
summaries; reconstruction errors are compared with the actual control-specimen
scatter. Configuration comparisons use the control means and singleton values.
They describe numerical resolution, not experimental significance.

With Python 3.12, prepare the research environment before running examples:

```text
python -m pip install -r validation/requirements-reproduce.txt
python validation/review_round2_workflow.py
python validation/review_round2_verify_workflow.py
python examples/query_exchange.py validation/workflow_results_round2/tables/STWC-1.json --mass-g 16.2 --strokes 10 20 30 40
python validation/connector_exchange.py
```

The client reads the received JSON and reported mass, without the full curve.
All eight repeated-control/stroke cases have stored work errors below their
observed sample EA standard deviations. Source-workbook checks cover 45/46
nominal-stroke EA/SEA/MCF/CFE values and all 46 peaks. The separate endpoint audit
explains all 13 source-EA discrepancies: workbook 50 mm labels accompany
actual endpoints of 50.004–50.009 mm. Both conventions and all residuals are saved.
The connector example exports a 33-point loading-branch input table and checks
it with an independent reader; it does not run a finite-element solver.

A cyclic example preserves negative forces, reversals and dwells:

```text
python validation/user_workflow.py --case cyclic
python validation/cyclic_round2.py
python validation/verify_cyclic_round2.py
python examples/compose_branch_errors.py validation/cyclic_round2_results/branch_error_manifest.json
```

The 2,971 exact branches are not 2,971 physical loading reversals. A deadband
sweep is diagnostic only and leaves the reference path unchanged. The last
command uses only saved branch metadata to compose chronological work-error
extrema; it needs neither WorkCert nor the dense reference. Legacy selective
refinement files remain numerical controls, with no claim of experimental
significance for arbitrarily close specimens.

## Comparative validation and reproduction

The compression comparison contains 70 numerical references, six force
selectors, work-only and scalar controls, and separate stopping requirements.
It saves 3660 actual JSON results, including 580 fixed-count dynamic-programming
paths at all five budgets on the 58 eligible original references with at most 1000 nodes. Area and
vertical-error optima are compared only with their matching objectives.

```text
python validation/verify_extended_benchmark.py
python validation/reproduce_v02.py --verify-only
```

The independent checks include native RDP/VW implementation comparisons,
exhaustive small-reference optima, continuous query checks, source checksums and
every saved table. The incremental scaling study includes the byte-preserved
0.1 implementation, deterministic synthetic inputs and three independent paired
million-sample repeats. Complete commands, environment requirements and output
locations are in [REPRODUCE.md](REPRODUCE.md) and
[`validation/BASELINES_README.txt`](validation/BASELINES_README.txt).

## Public data and licenses

| Source | Role in the examples | Version-specific DOI |
|---|---|---|
| Afkhami, metal honeycombs | 23 prepared CX-steel responses; acquisition records and preparation mapping included | [10.17632/8bxkdw4nfw.1](https://doi.org/10.17632/8bxkdw4nfw.1) |
| Wu, enhanced double-arrow honeycomb | One signed force–travel record | [10.5281/zenodo.16399749](https://doi.org/10.5281/zenodo.16399749) |
| Saber, PLA+ absorbers | 46 archived compression curves, measured masses and auxiliary workbooks | [10.17632/v7p6y654ft.4](https://doi.org/10.17632/v7p6y654ft.4) |
| González-de-León et al., cyclic stainless-steel member | One complete 125,157-point cyclic-bending history, assessed separately | [10.5281/zenodo.10829958](https://doi.org/10.5281/zenodo.10829958) |

All four experimental sources use CC BY 4.0. The original files, creator
attribution, checksums and transformation rules are retained under `data/`.
See [data/DATA_ATTRIBUTION.txt](data/DATA_ATTRIBUTION.txt) and
[data/extended/DATA_ATTRIBUTION.txt](data/extended/DATA_ATTRIBUTION.txt).
Code uses the MIT License. `LICENSE` is the conventional filename and
`Licence.txt` is the filename required by SoftwareX; their identical terms are
kept at the repository and package roots. Dataset ownership is unchanged.

## Citation and maintenance

Software citation metadata are in [CITATION.cff](CITATION.cff). Cite the original
dataset contributors when reusing the experimental records. The package
changelog is [software/CHANGELOG.md](software/CHANGELOG.md). The scientific
evidence consists of the executable examples and comparative validation;
independent adoption and commercial use have not been documented.

## Use of AI

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted with research planning, literature and public-data collection, implementation and debugging, numerical analysis and verification, figure preparation, drafting, language editing and typesetting. The authors are responsible for the research design, interpretation, software, results and final manuscript. Sen Zhang reviewed the full manuscript.
