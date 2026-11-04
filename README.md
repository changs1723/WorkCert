# WorkCert

WorkCert stores selected-node force-displacement tables with reconstruction-error
metadata, work queries, checked JSON persistence and directed branches for cyclic
histories. It accepts externally selected source nodes and keeps native unit labels.

**Version:** 0.3.0, released 4 November 2026. **Authors:** Saisai Hou, Yunzhi Zhu and
Sen Zhang. **Correspondence:** szhang@niit.edu.cn.

The released software is fixed at [v0.3.0](https://github.com/changs1723/WorkCert/tree/v0.3.0)
and archived under [10.5281/zenodo.23934502](https://doi.org/10.5281/zenodo.23934502).
The [final article sources](https://github.com/changs1723/WorkCert/tree/article-v0.3.0-final)
bind the manuscript PDF, figures and build inputs to that unchanged runtime.

## Install and use

Python 3.10 or later and NumPy 1.24 or later are required.

```text
python -m pip install ./software
python -m workcert --help
python validation/run_installed_suite.py --output ../workcert-installed-checks
```

The test runner checks that every runtime module comes from the installed package
and matches the current source. Local installation evidence is in
`release_evidence/local_installation.json`, with the actual Python/NumPy versions,
distribution hashes, test phases and dependency-isolation details. The
[tag workflow](https://github.com/changs1723/WorkCert/actions/runs/41753993817)
passed all 15 Linux/macOS/Windows and Python 3.10-3.14 jobs, followed by installation
tests of the actual release wheel and source distribution.
Each installation's `evidence` entry resolves to its archived acceptance outputs in
`release_evidence/installations`: summaries, environments, cases, check results and
test logs. The public summary records the SHA-256 of the original internal record
and the sizes and hashes of these unchanged outputs. Absolute import paths in the
environment records identify where the tested package was loaded during that run.

```python
from workcert import ReducedResponse, reduce_response

# Synthetic values illustrate the API.
x = [0.0, 1.0, 2.0, 3.0]
force = [0.0, 3.0, 1.0, 0.0]
table = reduce_response(x, force, method="work", max_points=3,
                        x_unit="mm", force_unit="kN")
table.save("response.json")
received = ReducedResponse.load("response.json")
print(received.work(2.5))
print(received.window_work(1.0, 2.5))
```

Choose the selector explicitly. Methods include work priority, vertical priority,
Visvalingam-Whyatt and uniform strategies; `from_indices` accepts external nodes.
Peak retention supports either force sign convention. Omitted units remain
`unspecified`; labels do not rescale numbers. Inspect `tolerance_met` when imposing
a point cap.

## Numerical queries and precision

Error metadata describe reconstruction relative to the supplied piecewise-linear
numerical reference. Compensated pairwise integration and local range queries
avoid serial accumulation drift and subtraction of two large global prefixes.
Use `window_work(a, b)` for a local interval. Floating-point quadrature and returned
values still round; reconstruction bounds do not include query arithmetic error.

Source hashes and retained coordinates are checked exactly. Numerical metadata
use a field-local ULP comparison policy, with exact zero agreement. This checks
file consistency rather than providing a forward-error theorem. The API explains
the arithmetic model and limits. Reproduce the numerical examples with:

```text
python software/examples/numerical_stability_probe.py --output ../stability.json
```

## Scientific workflows

The included public inputs cover 70 compression references and a chronological
cyclic-bending response. The scripts provide preparation, geometric comparators,
objective-matched dynamic programming, per-case outputs, source-workbook checks,
cyclic summaries and plotting programs.

The decision example asks for the best configuration at a requested stroke. The
consumer identifies overlapping intervals, requests smaller work budgets only for
the contenders, and checks the resulting numerical separation at reported masses.
For configurations 26 and 35, a +/-0.05 g mass-rounding scenario leaves overlapping
SEA intervals even with full source curves. More precise mass information is
needed to resolve that choice; further curve refinement alone is insufficient.
A separate inverse
query converts a prescribed quasi-static work capacity into a stroke interval.
These are comparisons of numerical references, not statistical tests of material
or manufacturing reliability.

The standalone `examples/compose_branch_errors.py` checks that each directed
summary contains both zero and its terminal error. This ordering check has no
work-unit tolerance floor. The composition identity holds in real arithmetic;
the example evaluates it with sequential binary64 operations and supplies no
rounding-error enclosure. For example, terminal values `[1e16, 1, -1e16]` sum to
zero in this implementation, whereas their real-arithmetic sum is one.

```text
python validation/test_branch_summary_validation.py
```

```text
python validation/decision_workflow.py
python validation/decision_verify.py
```

These construction commands intentionally replace derived case-study results.
To audit the supplied results without modifying the source, use:

```text
python validation/reproduce_v03.py --verify-only --output-dir ../workcert-verification
```

Reports and any validator-generated files stay in the separate output copy.
`--recompute` explicitly rebuilds scientific results. Details, dependency records
and the distinction between hash checks, independent arithmetic and optimization
reruns are in [REPRODUCE.md](REPRODUCE.md).

## The corresponding article object

The `article` folder fixes the actual manuscript and cover PDFs, their editable
LaTeX sources and figures. `article/article_manifest.json` binds these bytes to
the seven software modules, exact scientific inputs and article-building programs.
`article_inputs/publication_snapshot.json` pins the metadata used in the article;
regeneration does not consult live CI, the network or mutable development QA.
`article_inputs/scientific_fingerprints.json` detects changes to the pinned inputs.

```text
python authoring/build_documents_v03.py --keep-figures
```

This rebuilds from the supplied exact figure PDFs. Omit `--keep-figures` to recreate
the plots as well. Exact PDF bytes are checked in the recorded TeX environment;
different TeX or font versions can change the binary output. The frozen PDF hash
always identifies the accompanying article object independently of a software DOI.

The software DOI archives the released software snapshot. The article tag fixes
the final manuscript and its updated publication inputs separately. Package
documentation inside the archived software is retained as built; this root guide
and the article manifest describe the final article object.

## Authorship, licenses and evidence

The runtime software uses MIT terms; `LICENSE` and the SoftwareX-required
`Licence.txt` are identical. Third-party experimental inputs keep their credited
CC BY 4.0 licenses. The article snapshot is a separate manuscript object and does
not imply journal publication or a manuscript publication license.

The dated Hou acceptance records and author-verification statement are preserved
under `validation/hou_acceptance` and
`validation/author_verification_2026-11-03.json`. Their original scope is recorded
there. Current 0.3 installation results are separate, and new automated regressions
are not relabelled as additional human review.

## Use of AI

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted with research planning, literature and public-data collection, implementation and debugging, numerical analysis and verification, figure preparation, drafting, language editing and typesetting. The authors are responsible for the research design, interpretation, software, results and final manuscript.

See the [package documentation](software/README.md) and
[API reference](software/docs/API.md) for signatures, units and persistence rules.
