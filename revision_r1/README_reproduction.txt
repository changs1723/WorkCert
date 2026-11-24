WORKCERT: SOFTWAREX R1 SCIENTIFIC OVERLAY

Purpose and input layout
------------------------
This supplement adds the R1 scientific analyses to the fixed original article
inputs. The WorkCert 0.3.0 runtime, original datasets, original results and
original article files are unchanged. The original package contains 7,341
manifest-listed payload files and its MANIFEST.sha256 (7,342 files in total).

Obtain the fixed original article archive from:
https://github.com/changs1723/WorkCert/tree/article-v0.3.0-final
Use its release/archive download, preserving its bytes. A Git checkout with
line-ending conversion can fail the checksum check. Extract Supplementary S2
so that revision_r1/ is beside the ORIGINAL root MANIFEST.sha256, article/,
data/, software/ and validation/ folders. Do not replace the original article/
folder. The revised manuscript and technical supplement are in
revision_r1/article/. All paths below assume the original input root as the
current directory.

Environment
-----------
The recorded R1 environment uses Python 3.12.14, NumPy 2.3.5 and openpyxl 3.1.5.
The unchanged software declares Python >=3.10 support; this R1 reproduction
configuration is pinned to the recorded library versions. Create a virtual
environment OUTSIDE the input root and install revision_r1/requirements-r1.txt.
For example, on Windows:

  py -3.12 -m venv ..\workcert-r1-env
  ..\workcert-r1-env\Scripts\python -m pip install -r revision_r1/requirements-r1.txt

On Linux/macOS, replace the interpreter path with
../workcert-r1-env/bin/python. The arithmetic, policy tests and data audits
need NumPy and openpyxl; the remaining pinned packages support optional figure
and document generation. TeX (pdflatex and bibtex) is an external dependency
for rebuilding PDFs, not for the numerical validation below.

Read-only acceptance command
----------------------------
  ..\workcert-r1-env\Scripts\python -B revision_r1/run_revision_checks.py --output ..\r1-checks

Choose a NEW output directory outside the source root. An existing nonempty
directory, the source itself, an ancestor of the source, and any directory
inside the source are refused. Source identity is recorded before and after
the run, including on failure. Recomputation takes place only in an isolated
working copy under the output directory; that copy is removed afterward.

A successful sealed run writes check_report.json with status PASS and
source_unchanged=true. It verifies:

* The pinned original MANIFEST.sha256 and every original payload file, with
  an exact original file-set comparison (the revision_r1 subtree is excluded).
* Every scientific file listed in revision_r1/MANIFEST.sha256. Paths in this
  second manifest are relative to revision_r1/ and exclude the manifest itself.
  The manifest must include all R1 code executed by the runner and every
  scientific result used for comparison. This is otherwise a LISTED-FILES
  check: local editorial correspondence, marked copies
  or build logs not included in the scientific supplement are listed in the
  report as unlisted_files; they are not silently claimed to be covered by
  the scientific manifest. The before/after comparison includes ALL actual
  files, listed or unlisted. The distributed S2 file set is checked separately
  when the submission package is assembled.
* The cyclic safety-policy and exchange-diagnostic unit tests (currently
  25 and 4 test methods). Counts are read from the actual test output.
* All 560 stopping cases and 230 workbook-indicator rows; 3,360 independent
  scalar field comparisons are recorded separately from test-method counts.
* The full 2,971-branch path, reference-hash checks and targeted recovery of
  branch 2533. The restored branch and recomposed scientific results must
  agree with the supplied results. Branchwise tolerances are local budgets;
  their satisfaction does not imply an additional global relative tolerance.
* The saved timing records: 7,440 positive individual durations, 490 case
  median chains and 312 cohort-statistic checks, with source/runtime identity
  and cancellation-fallback diagnostics. No new timing result is implied by
  validating arithmetic on saved timing records.

The new R1 test methods are separate from the unchanged released-package
suite of 81 methods and its 759 recorded checks. The latter can be run after
installing the original wheel by using validation/run_installed_suite.py with
its own NEW external --output directory. A local installed-wheel rerun is
recorded in the authors' QA files; it does not imply a new remote CI run.

Outputs and interpretation
--------------------------
check_report.json is the summary. Individual subprocess logs, full source
identity snapshots and regenerated scientific results are retained outside
the source. The returned exit status is zero only for PASS or an explicitly
requested DEVELOPMENT_PASS. Missing or mismatched sealed scientific files,
failing tests, a changed source, or differing regenerated scientific results
cause FAIL and a nonzero exit status. If failure occurs after source hashing,
the final source comparison is still attempted and reported.

The --development switch is for authors preparing an unsealed candidate: it
allows ONLY a missing revision_r1/MANIFEST.sha256 and reports
DEVELOPMENT_PASS rather than PASS. It does not ignore a malformed or
mismatching manifest. Distributed supplements should be checked without this
switch. Checksums identify consistent bytes; they do not authenticate their
publisher. Use the fixed, trusted base archive and supplied supplement.

New performance measurements (optional)
--------------------------------------
Add --remeasure to the acceptance command and choose another new output
folder. This explicitly reruns benchmark_exchange.py in the working copy.
New host- and load-dependent durations are saved separately under
fresh_timing_measurements/ and checked for internal arithmetic consistency.
They are not required to equal the published durations and do not overwrite
the supplied results. Ordinary measurements use one warm-up, five timed
repeats per process and three independent processes. The constructed
cancellation-fallback diagnostic uses three timed repeats. The deliberately
bypassed fallback is a diagnostic comparison, not a supported query mode.
The minimal raw-dense loader parses JSON and converts its two arrays to
NumPy arrays; it omits
the schema validation, digest checks and cache setup of the WorkCert loader.

Optional working copy and article files
--------------------------------------
--keep-work-copy retains output/working_copy/source/ for inspection or a
separate rebuild. Any subsequent figure or PDF build should be performed in
that retained copy, not in the sealed input root. The supplied manuscript,
technical supplement and figures are already provided for reading. Running
build_revision_figures.py regenerates the two R1 figures from recorded data;
LaTeX source in revision_r1/article/ allows a separate document rebuild.
Editorial response documents and portal replies belong to the submission
correspondence and are not members of the public scientific overlay.

Audit scope
-----------
The R1 scripts audit the finite, piecewise-linear reference data. Floating-
point evaluation is not a directed-rounding enclosure of physical truth.
The checked path wrapper is a fail-closed application protocol for trusted,
verified branch records with explicit common work units; hashes are not a
cryptographic authenticity proof. Diagnostics with unresolved branches are
not usable downstream. The measured cyclic record has open endpoints, so
its signed path work is not automatically closed-cycle dissipated energy.
