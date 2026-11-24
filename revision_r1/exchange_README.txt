Exchange performance benchmark for SoftwareX revision R1

Reproduce
  python -B revision_r1/benchmark_exchange.py
  python -B revision_r1/test_exchange_benchmark.py

No runtime changes
The measurements use the archived WorkCert 0.3.0 runtime in software/src/workcert.
All seven runtime module hashes are recorded before/after each worker. Only the
explicitly labelled diagnostic ablation temporarily bypasses the private
cancellation-fallback method. That ablation is not a supported alternative and
returns incorrect zero work in the deliberately ill-conditioned fixture.

Population and representations
The 70 archived, hash-checked prepared numerical references contain 23 CX-steel,
1 EDAH and 46 PLA+ records. Every reference is reduced to 33 nodes by work-priority
selection with endpoints and absolute peak retained. Construction and independent
source verification precede the timed operations. The 33-node representation is
not a claim that every application can use the same error tolerance.

Three uncompressed compact UTF-8 JSON files are actually written for each curve:
1. Reduced WorkCert JSON, including x, force, source indices, unit labels, every
   reconstruction-error field, source identity, selection metadata and checksum.
2. A full-node WorkCert JSON using the identical response schema, via from_indices.
   It retains all x/force/index values and records zero reconstruction error.
   Method metadata differ appropriately; the schema and loading semantics match.
3. Minimal dense JSON, containing x, force, units, schema identifier and source
   hash, but no error metadata, source indices, payload checksum or query caches.
   Its load baseline only reads/parses JSON and creates the two NumPy arrays.

Sizes are the actual filesystem byte counts, not the uncompressed coordinate
array sizes or the bytes saved by ZIP. The fixed-field overhead is measured by
emptying x/force/indices contents in a copy of the serialized envelope and
counting the remaining bytes. Empty-array brackets remain in this count. This
copy is only a size decomposition, not a valid response for loading.

Timing protocol
Three separate Python processes run sequentially. For each operation, a complete
warm-up is followed by five measurements using perf_counter_ns. Per-curve values
are the median of five in each worker, then the median of the three worker
medians. CSV columns also preserve minimum/maximum worker medians. All individual
samples are archived. Each load includes file reading, JSON parsing, schema and
payload-digest checks, certificate/retained-data invariants, and integration-cache
construction; OS filesystem caches are warm. No cold-cache claim is made.

Each prefix/window timing is for one vectorized batch of 10,000 queries. Prefixes
are uniform random coordinates in the reference domain. Each window is made by
sorting an independent pair of uniform random coordinates. The NumPy generator
seed is 20261123. Query inputs and timing loops are identical for the reduced and
full-node WorkCert objects. No construction, serialization, numerical source
verification, fallback instrumentation or comparison with the reference is inside
these query timings. Query error comparisons are performed separately.

An untimed wrapper counts the exact existing fallback predicate and delegates to
the original method. Published-path timing has no counting wrapper installed.
Across the 70 curves this diagnoses 700,000 prefixes plus 700,000 windows for each
representation. The same deterministic locations are repeated in the three
processes; the summary counts each location once, rather than presenting repeated
process execution as extra independent query samples.

A separate positive 100,001-node synthetic curve uses the analytic signal from the
prior scaling experiment, with 0.1% relative window tolerance and a 1,025-point cap.
It provides a larger loading/query example rather than extra experimental data.

Fallback stress experiment
For n=33, 1,001 and 100,001 retained nodes, x_i=i and all forces are zero except
f_[1,3,5,7,9]=2*[1e100,1,1e-100,-1e100,-1]. The exact binary-input integral is
2e-100 J. A batch contains 256 complete-domain window queries. All trigger direct
summation. Enabled and bypassed versions have an untimed warm-up and three timed
batches per worker. The bypassed diagnostic returns zero. A Fraction-based
acceptance test checks the expected integral independently. These extreme
amplitudes are an arithmetic stress test, not a material-response model.

Outputs
results/exchange_per_curve.csv: source hashes, sizes, loading/query medians,
  worker ranges, sampled reconstruction errors and fallback counts for every curve.
results/exchange_individual_timings.csv: every ordinary timed operation.
results/exchange_worker_[1-3].json: individual process records including stress
  measurements, source/runtime identity and machine information.
results/exchange_summary.json: pooled and separate-cohort descriptive summaries,
  the large synthetic example and fallback stress results.
results/exchange_diagnostics_tests.log: four independent acceptance checks.

Interpretation
The small compression records remain inexpensive to exchange in full. The
interface adds source/error metadata and supports selective refinement; its
value does not require claiming large absolute memory savings or universal
query acceleration. Minimal dense JSON loading performs substantially less work
and should not be described as an equivalent WorkCert consumer. Timings depend
on this machine, OS caches and query distribution. Direct fallback trades speed
for recovery of small signed work and has linear cost in the number of retained
segments scanned.
