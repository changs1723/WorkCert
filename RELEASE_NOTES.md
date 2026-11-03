# WorkCert 0.2.0

This version includes built-in Visvalingam–Whyatt selection, exact-coordinate adapters, retained-peak query bounds, chronological metadata composition, source-indicator and replicate checks, and incremental reconstruction-error aggregation, directed monotone
branches for cyclic histories, explicit selector choice, sign-aware peak modes,
unassigned unit labels and an interface for externally selected nodes.

The complete scientific tree includes original numerical sources, preparation
programs, a database-exchange example with measured masses and engineering
indicators, a full cyclic-bending path, geometric comparators, objective-matched
dynamic programming and figure-generation programs.

Earlier local wheel and source-distribution installations passed the original 39 tests on Windows
with Python/NumPy 3.10.0/2.2.6, 3.12.14/2.3.5 and 3.14.7/2.5.4. The tagged
publication workflow creates release assets after the Linux, macOS and Windows
matrix passes for Python 3.10–3.14. Actual run conclusions are available in
GitHub Actions. The updated acceptance workflow has not been run remotely.

The complete-repository suite now includes 28 additional independent numerical
acceptance tests (67 total). On 2026-11-03 all 67 passed locally using installed
WorkCert 0.2.0, Windows, Python 3.12.14 and NumPy 2.3.5. The new suite records
759 per-check comparisons and separate raw logs in `validation/hou_acceptance`.
This is additional evidence for that environment only. Saisai Hou wrote and
executed the additional tests with Codex assistance and manually verified
them, as confirmed by the author on 2026-11-03. The separate record is
`validation/author_verification_2026-11-03.json`; original run logs and
derivations are preserved. The confirmation concerns the tests, not all
three authors' final approval of the revised manuscript.

Install the wheel or source distribution, or run `python -m pip install ./software`
from the complete source archive. See `REPRODUCE.md` for scientific verification
and recomputation. Code uses the MIT License; credited experimental inputs retain
their CC BY 4.0 licenses.
