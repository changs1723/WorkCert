# WorkCert 0.2.0

WorkCert stores a selected-node piecewise-linear force-displacement table with
analytical reconstruction error metadata. Saved responses support force,
prefix-work and arbitrary-window work queries, source verification and explicit
native units. A branch extractor handles chronological unloading and hysteresis
without turning a multivalued path into a single force-displacement function.

Authors: Saisai Hou, Yunzhi Zhu, Sen Zhang. Correspondence: szhang@niit.edu.cn.
Department of Public Basic Courses, Nanjing University of Industry Technology.

## Installation

Python 3.10 or later and NumPy 1.24 or later are required. Install a NumPy release
compatible with your Python version. From the repository root:

```text
python -m pip install ./software
python -m workcert --version
```

From this source directory use `python -m pip install .`; from an archived wheel
use `python -m pip install workcert-0.2.0-py3-none-any.whl`.

## A response table with a stated error budget

These small values illustrate the interface and are synthetic.

```python
from workcert import ReducedResponse, reduce_response

x = [0, 1, 2, 3, 4, 5]
force = [0, 1, 2, 0, 3, 0]
r = reduce_response(x, force, method="work", max_points=6,
    tolerance=0.01, relative=True, certificate="window",
    x_unit="mm", force_unit="kN")
assert r.metadata["tolerance_met"]
r.save("response.json")
s = ReducedResponse.load("response.json")
print(s.force_at([1.5, 3.5]))
print(s.work([1.5, 3.5]))
print(s.window_work(1.5, 3.5), s.certificate.window)
assert s.verify_reference(x, force)
```

Choose `method` explicitly: `work`, `vertical`, `uniform`, or `uniform_peak`.
The adaptive selectors share the largest-vertical-residual split location and
prioritize a segment by absolute area or vertical deviation. Method choice is
application dependent. Plain uniform selection requires `preserve_peak=False`;
`uniform_peak` always reserves a peak. `peak_mode="absolute"` retains the first
maximum absolute force and supports either compression sign convention.
`"positive"` and `"negative"` select the maximum and minimum signed force.
Endpoints are always retained. A point budget too small for required nodes is
rejected.

## Using another simplifier

External RDP, Visvalingam-Whyatt or other selectors can supply reference indices:

```python
from workcert import from_indices
r = from_indices(x, force, [0, 2, 4, 5], x_unit="mm", force_unit="kN",
    provenance={"selector": "external algorithm"})
print(r.certificate.window, r.window_work(1.5, 3.5))
```

Indices must refer to original nodes, be strictly increasing, and include both
endpoints. This separates point selection from querying and error evaluation.

## Error measures and incremental construction

For the reference minus reconstructed force `r`, let `D(u)` be its primitive
from the reference origin. All bounds use the supplied piecewise-linear reference.

| Field | Definition | Supported query error |
|---|---|---|
| `eta` | integral of `abs(r)` | Prefixes and arbitrary windows |
| `xi` | `(eta + abs(D(U))) / 2` | Prefixes and arbitrary windows |
| `prefix` | `max(abs(D))` | Tight uniform prefix bound |
| `window` | `max(D) - min(D)` | Tight uniform arbitrary-window bound |
| `delta` | `max(abs(r))` | Force-query bound |

Extrema include residual zeros inside cells. `Certificate` and `certify` remain
API names for compatibility; `ErrorMetadata` is an alias. Evaluation uses
float64 analytical formulas relative to the numerical reference, not measurement
uncertainty or outward-rounded arithmetic.

Tolerance stopping checks the current representation after every insertion;
intermediate greedy error need not decrease. The adaptive implementation caches
local primitive ranges and uses an augmented AVL tree to combine them after a
split. It globally recomputes the complete error once when a candidate first
meets the threshold or reaches its point cap. Relative stopping divides by
absolute terminal reference work; use absolute units when net work is zero.
Inspect `metadata["tolerance_met"]` when imposing a cap.

Local interval evaluation can still take O(nK) work in the worst case. The tree
adds O(log K) update work and O(K) nodes and removes a complete reference scan
at each tolerance step. Actual scaling measurements, including the small-input
overhead, are supplied in `validation/results/scaling/`.

## Chronological unloading and hysteresis

```python
from workcert import split_monotone_branches, reduce_response

# Synthetic closed displacement path, with different loading/unloading forces.
path = split_monotone_branches([0, 1, 2, 1, 0], [0, 2, 4, 1, 0])
work = 0.0
for branch in path.branches:
    r = reduce_response(branch.x, branch.force, method="work",
        max_points=len(branch.x), x_unit="mm", force_unit="kN")
    work += branch.directed_work(r)
assert work == path.reference_work == 1.0
```

Each branch has ascending query coordinates, chronological `start_x`, `end_x`,
`direction`, and original `source_indices`. Turning nodes are shared. Directed
work is `response.work(end_x)-response.work(start_x)`, so unloading preserves the
sign of F dx. Equal-displacement pairs remain explicit zero-work `events`,
including force jumps. `duplicate_policy="error"` rejects these pairs instead.
The extractor applies no noise threshold, smoothing or contact alignment;
record such preparation explicitly for measured signals.

## Command line and units

```text
workcert reduce examples/synthetic_response.csv response.json --method work --max-points 5 --x-unit mm --force-unit kN
workcert inspect response.json
workcert query response.json --at 2.5 4.5
workcert query response.json --window 1 6
workcert verify response.json examples/synthetic_response.csv
```

CSV headers default to `stroke_mm` and `force_kN`; use `--x-column` and
`--force-column` to change them. Column names never assign units. Omitted unit
options are labelled `unspecified`. Labels do not rescale values. Explicit mm/kN
and m/N products are J; mm/N is mJ; m/kN is kJ.

## Persistence, tests and reproducibility

The JSON schema stores selected indices, source SHA-256, units, error metadata
and a payload checksum. Loading checks structure and numerical relationships;
`verify_reference` recomputes errors and checks the retained source values.
Checksums detect accidental change; source authenticity requires a trusted hash.

```text
python -m unittest discover -s tests -v
```

The repository's `validation/`, `data/` and `authoring/` folders contain source
preparation, credited public inputs, benchmark scripts, per-case results and
scientific plotting code. The 12-job GitHub Actions matrix targets Windows,
Linux and macOS with Python 3.10-3.13. A workflow file is a test specification;
completed runs and local installation evidence are recorded separately.

## License, citation and migration

MIT terms appear in `LICENSE` and `Licence.txt`. The latter filename is required
by SoftwareX; the two files are identical and tested. Experimental data retain
their own licenses and attribution. See `CITATION.cff`.

Version 0.2.0 requires an explicit selector, labels unassigned units as
`unspecified`, and defaults peak retention to absolute force. To reproduce a
0.1.0 call, supply `method="work", peak_mode="positive", x_unit="mm",
force_unit="kN"`. Stored schema-1.0 responses remain readable.

## Use of AI

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted with research planning, literature and public-data collection, implementation and debugging, numerical analysis and verification, figure preparation, drafting, language editing and typesetting. The authors are responsible for the research design, interpretation, software, results and final manuscript.

Detailed signatures are in [the API reference](docs/API.md).
