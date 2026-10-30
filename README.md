# WorkCert

WorkCert reduces a force-displacement response to a vertex-subset piecewise-linear
table and attaches computable bounds on work-query errors. It provides force,
prefix-work and arbitrary-window work queries, preserves a selected global peak,
and exports portable JSON records with reference and payload checksums.

Version: **0.1.0**. Authors: **Saisai Hou, Yunzhi Zhu, Sen Zhang**.
Correspondence: **szhang@niit.edu.cn**.
Affiliation: Department of Public Basic Courses, Nanjing University of Industry Technology.

## Installation

WorkCert requires Python 3.8 or later and NumPy 1.24 or later. Python 3.8 requires
NumPy 1.24.x; newer Python versions should use a compatible NumPy release.

From the supplied source directory:

```text
python -m pip install .
python -m workcert --version
```

From a supplied wheel:

```text
python -m pip install workcert-0.1.0-py3-none-any.whl
```

## Python example

```python
from workcert import ReducedResponse, reduce_response

x = [0, 1, 2, 3, 4, 5]
force = [0, 1, 2, 0, 3, 0]
table = reduce_response(x, force, max_points=4)
print(table.force_at([1.5, 3.5]))
print(table.work([1.5, 3.5]))
print(table.window_work(1.5, 3.5))
print(table.certificate.prefix, table.certificate.window)
table.save("response.json")
restored = ReducedResponse.load("response.json")
assert restored.verify_reference(x, force)
```

Use `tolerance=0.01, relative=True, certificate="prefix"` to stop at the first
current representation meeting a 1% prefix-work bound. The default maximum is
33 retained points. Inspect `table.metadata["tolerance_met"]`: `False` means the
point limit was reached before the requested bound was met. Increasing the point
budget need not monotonically decrease an intermediate greedy error.

## Command line

Input CSVs have a header row. The default columns are `stroke_mm` and `force_kN`.
The example below uses synthetic values, not experimental data.

```text
workcert reduce examples/synthetic_response.csv response.json --max-points 5
workcert inspect response.json
workcert query response.json --at 2.5 4.5
workcert query response.json --window 1 6
workcert verify response.json examples/synthetic_response.csv
```

Use `--x-column`, `--force-column`, `--x-unit` and `--force-unit` for other input
column names and unit labels. Unit labels do not rescale values.

## What the certificates mean

The full supplied piecewise-linear curve is the numerical reference. For the
residual `r = F - F_hat` and its primitive `D(u)` from the reference origin:

| Field | Definition | Meaning |
|---|---|---|
| `eta` | integral of `abs(r)` | Absolute-area work bound |
| `xi` | `(eta + abs(D(U))) / 2` | Sign-informed work bound |
| `prefix` | `max(abs(D))` | Tight uniform prefix-work bound |
| `window` | `max(D) - min(D)` | Tight uniform arbitrary-window work bound |
| `delta` | `max(abs(r))` | Force error bound |

Continuous extrema include interior residual zeros. Computation uses float64
analytic formulas; there is no outward-rounded interval arithmetic. These bounds
quantify reconstruction of a specified numerical curve, independently of any
measurement or manufacturing uncertainty.

Signed forces and a nonzero displacement origin are supported. Relative bounds
divide by `abs(reference_work)` and reject exactly zero terminal reference work;
absolute tolerances remain available. Near-zero terminal work can produce large
relative ratios. Unit products are native: kN and mm give J; N and mm give mJ.
The library performs no contact detection, branch selection, smoothing or force
clipping. Perform and document those operations before constructing a table.

## Selection methods

`work` and `vertical` use best-first interval refinement. Both initialize with
endpoints and, by default, the first maximum-force node. They split an interval
at its largest absolute vertical residual; interval priority is absolute area or
vertical error, respectively. `uniform` uses nearest reference nodes to an
equally spaced grid; pass `preserve_peak=False` for a plain uniform baseline.
`uniform_peak` always reserves the global peak. Endpoint/peak constraints may
require at least three points. The algorithm is deterministic and greedy.

Reduction produces a compact retained representation; query savings depend on
the response and workload. Construction uses the full reference. A single
terminal-work query is best served
by storing that scalar directly. Force-response tables are useful when query
locations or intervals vary, or when force and work are both needed.

## Integrity and reproducibility

JSON records contain the selected reference indices, native-unit coordinates,
certificate values, source-reference SHA-256 and an envelope checksum. Loading
checks the schema, checksum and numerical invariants. A checksum detects
accidental changes; it is not an authenticity signature. Recompute against the
full source using `verify_reference` when source consistency must be established.

Package numerical tests and CLI checks use the standard library:

```text
python -m unittest discover -s tests -v
```

The study's separately supplied benchmark has the original dataset attribution,
data parsing rules, archive checksums and observed results. Package examples are
small, explicitly synthetic inputs for learning the interface.

## License and citation

Code is released under the MIT License in `LICENSE`. Original experimental data
retain their own licenses and attribution. Cite the software metadata in
`CITATION.cff` and the original dataset authors when reusing benchmark data.

## Use of AI

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted with research planning, literature and public-data collection, implementation and debugging, numerical analysis and verification, figure preparation, drafting, language editing and typesetting. The authors are responsible for the research design, interpretation, software, results and final manuscript.

Further technical details are in [the API reference](docs/API.md).

