Checked chronological composition example

Purpose
WorkCert 0.3.0 intentionally returns a table even when its cap prevents tolerance attainment. Its tolerance_met metadata records the outcome; ordinary query methods do not automatically enforce that budget. This application example makes the acceptance decision explicit before any downstream path-energy calculation. The published WorkCert runtime and original branch composer are unchanged.

Run from the source root, with Python >=3.10 and NumPy installed:
  python -B revision_r1/test_checked_cyclic_path.py
  python -B revision_r1/recompute_cyclic_recovery.py

Using the guard
  import json
  from revision_r1.checked_cyclic_path import compose_checked_path
  manifest = json.load(open('revision_r1/results/cyclic_checked_manifest_after.json'))
  accepted = compose_checked_path(manifest['records'],
      source_points=manifest['source_points'], work_unit=manifest['work_unit'])
  # Only after this call returns should a consumer use the path for a
  # calculation whose acceptance requires these prescribed branch budgets.

The default strict=True raises PathToleranceError if any branch has a false,
missing or unknown tolerance_met flag, invalid budget metadata, or an observed
error above its requested budget. Both the stored flag and the comparison are
checked. A diagnostic call with strict=False retains failed_branch_ids and
valid_for_downstream_use=False; it is for inspection, not budget-qualified use.
Never omit a failed branch: chronological coverage checks reject missing edges.
A zero-displacement event retains its edge and contributes zero work.

Every branch record stores its ID, direction, source interval, work unit,
terminal/minimum/maximum residual primitive, error measures, reference work and
stopping metadata copied from its checked serialized WorkCert table. Units must
match across records. Labels describe units without rescaling values. These
records must originate from validated tables whose errors were checked against
the numerical source. A payload checksum is not cryptographic authentication
of the source; this gate does not verify an unavailable dense reference. The enriched manifest is deliberately distinct from the
older error-only manifest, which cannot establish branch acceptance by itself.

Recovery policy and executed example
Request more points from the source only for rejected branches, retaining their
original requested errors. If increasing the cap is infeasible or fails, retain
the complete branch and verify it against the source, or keep the path rejected.
Do not silently loosen a requested tolerance. The demonstrated branch 2533 has
1,663 source nodes. Raising its cap from 129 to 257 uses 153 nodes and satisfies
its unchanged 0.087193736275 J interval budget with 0.082025231808 J error.
All 2,971 branches then pass. Total branch nodes increase from 13,890 to 13,914;
the other 2,970 tables and 1,984 zero-work events remain unchanged. Every original
table is hash-checked and verified against its source before this computation.

Scope of acceptance
Path tolerance_met means all prescribed LOCAL branch budgets have passed; it is
not a claim of any prescribed GLOBAL relative path tolerance. For such a policy,
compare the combined prefix/window error to the separately chosen path budget.
The combined residual primitive applies to signed chronological integral F dx.
For a closed quasi-static hysteresis loop, with matching start/end mechanical
state and the stated sign convention, its loop integral measures hysteretic
energy loss. An open history can include changes in stored energy. The archived
record begins at (0 mm, 0 kN) and ends at (3.1154 mm, 13.0479 kN); its net path
work must therefore not be relabeled as a sum of closed-cycle dissipation.

Numerical semantics
The composition formulas are real-arithmetic identities, evaluated here with
sequential float64 operations. They do not enclose floating-point error. For
example sequential terminal errors [1e16, 1, -1e16] produce 0 rather than the
real-arithmetic value 1; a regression preserves this explicit interpretation.
The independent scalar compensated residual integration is a consistency check,
not an outward-rounded bound. In the actual recovered path its largest
reported-summary difference is 7.105427357601002e-14 J (allowed comparison
threshold 1e-8 J).

Files
checked_cyclic_path.py: standalone acceptance wrapper.
test_checked_cyclic_path.py: 25 tests of the policy and composition semantics.
recompute_cyclic_recovery.py: archived-source rejection/recovery demonstration.
results/cyclic_recovery_summary.json: numerical summary and provenance.
results/cyclic_checked_manifest_before.json and cyclic_checked_manifest_after.json:
  enriched ordered branch/event metadata, with source coverage and local budgets.
results/cyclic_path_assessment_before.json and cyclic_path_assessment_after.json:
  per-branch acceptance states, failed IDs and combined error summaries.
results/cyclic_branch_2533_recovered.json: the only replacement WorkCert table.
results/cyclic_acceptance_tests.log: test output.
results/cyclic_runtime_identity.json: submitted-runtime identity checks.

New R1 scripts and tests were developed and executed with Codex assistance.
They are not described as independently authored or executed by a human.
