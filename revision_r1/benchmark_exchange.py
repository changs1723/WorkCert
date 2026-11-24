"""Measure complete JSON exchange and unmodified WorkCert 0.3.0 query costs.

Run from any directory with Python >=3.10 and NumPy >=1.24:
    python revision_r1/benchmark_exchange.py

The parent runs three separate workers sequentially. Timings are descriptive
wall-clock observations, not performance guarantees. Only the explicitly named
fallback-bypassed diagnostic changes a method; published-path measurements use
the unmodified software. Disk files are written before their sizes are measured.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import types

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "revision_r1" / "results"
sys.path.insert(0, str(ROOT / "software" / "src"))
sys.path.insert(0, str(ROOT / "validation"))
from workcert import ReducedResponse, from_indices, reduce_response
from benchmark_scaling import hardware_environment

SEED = 20261123
QUERY_COUNT = 10000
REPEATS = 5
FALLBACK_BATCH = 256


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf8")


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + "\n", encoding="utf8")


def csv_write(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def measured(fn, repeats=REPEATS):
    # A full untimed warm-up populates caches. Timed loads include opening and
    # reading the file, JSON/checksum/invariant checks and query-cache creation.
    fn()
    values = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        value = fn()
        elapsed = (time.perf_counter_ns() - start) / 1e6
        values.append(elapsed)
        del value
    return values


def reference(entry):
    path = ROOT / entry["prepared"]
    assert sha(path) == entry["prepared_sha256"]
    with path.open("r", encoding="utf8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    # float() round-trips the archived 17-significant-digit strings.
    return (np.array([float(row["x_mm"]) for row in rows]),
            np.array([float(row["force_kN"]) for row in rows]))


def load_raw_json(path):
    # Deliberately minimal baseline, with no work caches, error information,
    # invariants or payload checksum. It is not a substitute for WorkCert.load.
    p = json.loads(Path(path).read_text(encoding="utf8"))
    return np.asarray(p["x"], dtype=float), np.asarray(p["force"], dtype=float)


@contextmanager
def count_fallback(table):
    """Untimed diagnostic using the exact runtime predicate, preserving output."""
    original = table._cancellation_fallback
    counts = {"queries": 0, "fallback_queries": 0, "summed_leaf_segments": 0}

    def observed(self, result, magnitude, first, stop, *ends):
        affected = (magnitude > 0.) & (np.abs(result) <= np.finfo(float).eps * magnitude)
        counts["queries"] += int(np.size(result))
        counts["fallback_queries"] += int(np.count_nonzero(affected))
        starts, stops = np.broadcast_arrays(first, stop)
        counts["summed_leaf_segments"] += int(np.sum((stops - starts)[affected]))
        return original(result, magnitude, first, stop, *ends)

    table._cancellation_fallback = types.MethodType(observed, table)
    try:
        yield counts
    finally:
        table._cancellation_fallback = original


@contextmanager
def bypass_fallback(table):
    """Diagnostic ablation only. This can return an incorrect work value."""
    original = table._cancellation_fallback
    table._cancellation_fallback = types.MethodType(lambda self, result, *unused: result, table)
    try:
        yield
    finally:
        table._cancellation_fallback = original


def query_inputs(x):
    rng = np.random.default_rng(SEED)
    prefix = x[0] + rng.random(QUERY_COUNT) * (x[-1] - x[0])
    windows = np.sort(x[0] + rng.random((QUERY_COUNT, 2)) * (x[-1] - x[0]), axis=1)
    return prefix, windows[:, 0], windows[:, 1]


def one_curve(entry, folder, worker):
    x, force = reference(entry)
    sparse = reduce_response(x, force, method="work", max_points=33,
                             preserve_peak=True, peak_mode="absolute",
                             x_unit="mm", force_unit="kN")
    dense = from_indices(x, force, np.arange(len(x)), x_unit="mm", force_unit="kN")
    assert sparse.verify_reference(x, force) and dense.verify_reference(x, force)
    prefix, a, b = query_inputs(x)
    paths = {name: folder / (entry["curve"] + "__" + name + ".json")
             for name in ("reduced", "full_schema", "raw_dense")}
    sparse.save(paths["reduced"])
    dense.save(paths["full_schema"])
    raw = {"schema": "workcert.benchmark.dense/1.0", "x": x.tolist(), "force": force.tolist(),
           "units": {"displacement": "mm", "force": "kN", "work": "mm*kN"},
           "reference_sha256": dense.certificate.reference_sha256}
    paths["raw_dense"].write_bytes(compact(raw))
    # Overhead excludes the numerical x/force/index array contents while keeping
    # their empty brackets, every certificate and metadata field, and checksum.
    empty = json.loads(sparse.to_bytes())
    for field in ("x", "force", "indices"):
        empty["payload"][field] = []
    overhead = len(compact(empty))
    row = {"worker": worker, "curve": entry["curve"], "dataset": entry["dataset"],
           "reference_points": len(x), "retained_points": len(sparse.x),
           "prepared_sha256": entry["prepared_sha256"],
           "reference_sha256": dense.certificate.reference_sha256,
           "reduced_json_bytes": paths["reduced"].stat().st_size,
           "dense_schema_json_bytes": paths["full_schema"].stat().st_size,
           "dense_minimal_json_bytes": paths["raw_dense"].stat().st_size,
           "reduced_fixed_fields_and_empty_arrays_bytes": overhead,
           "reduced_json_sha256": sha(paths["reduced"]),
           "dense_schema_json_sha256": sha(paths["full_schema"]),
           "dense_minimal_json_sha256": sha(paths["raw_dense"]),
           "reduced_window_error_J": sparse.certificate.window}
    series = []
    order = ("reduced", "full_schema", "raw_dense") if worker % 2 else ("raw_dense", "full_schema", "reduced")
    for name in order:
        fn = (lambda p=paths[name]: load_raw_json(p)) if name == "raw_dense" else (lambda p=paths[name]: ReducedResponse.load(p))
        values = measured(fn)
        row[name + "_load_median_ms"] = statistics.median(values)
        series.extend({"worker": worker, "curve": entry["curve"], "representation": name,
                       "operation": "load", "repeat": j+1, "milliseconds": t}
                      for j, t in enumerate(values))
    for name, table in (("reduced", sparse), ("full_schema", dense)):
        for op, fn in (("prefix", lambda: table.work(prefix)),
                       ("window", lambda: table.window_work(a, b))):
            values = measured(fn)
            row[name + "_" + op + "_10000_median_ms"] = statistics.median(values)
            series.extend({"worker": worker, "curve": entry["curve"], "representation": name,
                           "operation": op, "repeat": j+1, "milliseconds": t}
                          for j, t in enumerate(values))
        with count_fallback(table) as counts:
            table.work(prefix)
            table.window_work(a, b)
        row[name + "_observed_queries"] = counts["queries"]
        row[name + "_fallback_queries"] = counts["fallback_queries"]
        row[name + "_fallback_leaf_segments"] = counts["summed_leaf_segments"]
    # Numerical comparisons are outside timing. Arithmetic allowance here is
    # a diagnostic tolerance, not part of a reconstruction-error enclosure.
    p_error = float(np.max(np.abs(sparse.work(prefix) - dense.work(prefix))))
    w_error = float(np.max(np.abs(sparse.window_work(a, b) - dense.window_work(a, b))))
    slack = max(1e-10, abs(dense.certificate.reference_work) * 1e-12)
    assert p_error <= sparse.certificate.prefix + slack
    assert w_error <= sparse.certificate.window + slack
    row["prefix_sample_error_J"] = p_error
    row["window_sample_error_J"] = w_error
    row["query_reconstruction_checks"] = "PASS"
    for path in paths.values():
        path.unlink()
    return row, series


def synthetic_case(folder, worker):
    n = 100001
    x = np.linspace(0., 1., n)
    f = (1-np.exp(-40*x))*(1+.15*np.sin(40*np.pi*x)+.08*np.sin(113*np.pi*x))+.8*x**8
    sparse = reduce_response(x, f, method="work", max_points=1025, tolerance=.001,
                             certificate="window", relative=True, x_unit="mm", force_unit="kN")
    assert sparse.metadata["tolerance_met"]
    dense = from_indices(x, f, np.arange(n), x_unit="mm", force_unit="kN")
    q, a, b = query_inputs(x)
    row = {"worker": worker, "curve": "synthetic_positive_100001", "dataset": "synthetic",
           "reference_points": n, "retained_points": len(sparse.x),
           "window_error_fraction": sparse.certificate.bound("window", True)}
    series = []
    for name, table in (("reduced", sparse), ("full_schema", dense)):
        path = folder / (name + "_synthetic.json")
        table.save(path)
        row[name + "_json_bytes"] = path.stat().st_size
        row[name + "_json_sha256"] = sha(path)
        for op, fn in (("load", lambda: ReducedResponse.load(path)),
                       ("prefix", lambda: table.work(q)),
                       ("window", lambda: table.window_work(a, b))):
            values = measured(fn)
            row[name + "_" + op + "_median_ms"] = statistics.median(values)
            series.extend({"worker": worker, "curve": row["curve"], "representation": name,
                           "operation": op, "repeat": j+1, "milliseconds": t}
                          for j, t in enumerate(values))
        with count_fallback(table) as counts:
            table.work(q)
            table.window_work(a, b)
        row[name + "_observed_queries"] = counts["queries"]
        row[name + "_fallback_queries"] = counts["fallback_queries"]
        path.unlink()
    return row, series


def fallback_case(n, worker):
    x, force = np.arange(n, dtype=float), np.zeros(n)
    force[[1, 3, 5, 7, 9]] = 2*np.array([1e100, 1., 1e-100, -1e100, -1.])
    table = from_indices(x, force, np.arange(n), x_unit="mm", force_unit="kN")
    # Exact binary-input triangle areas cancel in pairs, leaving two copies
    # of the representable float 1e-100. No decimal-to-binary ambiguity enters.
    expected = 2e-100
    a, b = np.zeros(FALLBACK_BATCH), np.full(FALLBACK_BATCH, n-1., dtype=float)
    with count_fallback(table) as counts:
        actual = table.window_work(a, b)
    assert counts["fallback_queries"] == FALLBACK_BATCH
    assert np.array_equal(actual, np.full(FALLBACK_BATCH, expected))
    enabled = measured(lambda: table.window_work(a, b), repeats=3)
    with bypass_fallback(table):
        bypassed_values = table.window_work(a, b)
        bypassed = measured(lambda: table.window_work(a, b), repeats=3)
    row = {"worker": worker, "retained_points": n, "queries_in_batch": FALLBACK_BATCH,
           "fallback_queries": counts["fallback_queries"],
           "summed_leaf_segments": counts["summed_leaf_segments"],
           "expected_work_J": expected, "actual_work_J": float(actual[0]),
           "diagnostic_fallback_bypassed_work_J": float(bypassed_values[0]),
           "enabled_median_ms": statistics.median(enabled),
           "diagnostic_bypassed_median_ms": statistics.median(bypassed),
           "enabled_repeats_ms": enabled, "diagnostic_bypassed_repeats_ms": bypassed,
           "reconstruction_window_error_J": table.certificate.window,
           "scope": "synthetic ill-conditioned arithmetic stress case, not physical measurements"}
    assert row["reconstruction_window_error_J"] == 0.
    return row


def worker_main(worker):
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((ROOT / "data/metadata/reference_audit.json").read_text(encoding="utf8"))["curves"]
    assert len(inventory) == 70
    runtime_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "software/src/workcert").glob("*.py"))}
    rows, all_series = [], []
    with tempfile.TemporaryDirectory(prefix="exchange_tmp_", dir=OUT) as folder_name:
        folder = Path(folder_name)
        for entry in inventory:
            row, series = one_curve(entry, folder, worker)
            rows.append(row)
            all_series.extend(series)
        synthetic, series = synthetic_case(folder, worker)
        all_series.extend(series)
        fallback = [fallback_case(n, worker) for n in (33, 1001, 100001)]
    assert runtime_hashes == {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "software/src/workcert").glob("*.py"))}
    output = {"worker": worker, "hardware": hardware_environment(), "runtime_sha256": runtime_hashes,
              "script_sha256": sha(__file__), "curves": rows, "synthetic": synthetic,
              "fallback": fallback, "individual_timings": all_series}
    path = OUT / f"exchange_worker_{worker}.json"
    dump(path, output)
    print(json.dumps({"worker": worker, "status": "PASS", "curves": len(rows),
                      "timing_samples": len(all_series), "output": path.name}), flush=True)


def median_range(values):
    return {"median": statistics.median(values), "minimum": min(values), "maximum": max(values)}


def aggregate():
    outputs = [json.loads((OUT / f"exchange_worker_{i}.json").read_text(encoding="utf8")) for i in (1,2,3)]
    assert all(p["runtime_sha256"] == outputs[0]["runtime_sha256"] for p in outputs)
    curves = []
    for curve in [r["curve"] for r in outputs[0]["curves"]]:
        rows = [next(r for r in p["curves"] if r["curve"] == curve) for p in outputs]
        row = {k:v for k,v in rows[0].items() if not k.endswith("_median_ms") and k != "worker"}
        for key in rows[0]:
            if key.endswith("_median_ms"):
                values = [r[key] for r in rows]
                row[key] = statistics.median(values)
                row[key.replace("_median_ms", "_process_min_ms")] = min(values)
                row[key.replace("_median_ms", "_process_max_ms")] = max(values)
        for key in ("reduced_json_sha256", "dense_schema_json_sha256", "dense_minimal_json_sha256"):
            assert len({r[key] for r in rows}) == 1
        for op in ("load", "prefix_10000", "window_10000"):
            row["dense_to_reduced_" + op + "_time_ratio"] = row["full_schema_"+op+"_median_ms"] / row["reduced_"+op+"_median_ms"]
        row["minimal_dense_to_reduced_byte_ratio"] = row["dense_minimal_json_bytes"] / row["reduced_json_bytes"]
        curves.append(row)
    csv_write(OUT / "exchange_per_curve.csv", curves)
    timing_rows = [r for p in outputs for r in p["individual_timings"]]
    csv_write(OUT / "exchange_individual_timings.csv", timing_rows)
    cohorts = {}
    numeric = [k for k,v in curves[0].items() if isinstance(v,(int,float)) and not k.endswith("_min_ms") and not k.endswith("_max_ms")]
    for cohort in ("ALL", "CX_steel", "EDAH", "PLA_plus"):
        selected = curves if cohort == "ALL" else [r for r in curves if r["dataset"] == cohort]
        cohorts[cohort] = {"curves": len(selected), "metrics": {key: median_range([r[key] for r in selected]) for key in numeric}}
    synthetic = {"curve": outputs[0]["synthetic"]["curve"], "reference_points": 100001,
                 "retained_points": outputs[0]["synthetic"]["retained_points"]}
    for key,v in outputs[0]["synthetic"].items():
        if key.endswith("_median_ms"):
            synthetic[key] = median_range([p["synthetic"][key] for p in outputs])
        elif key not in ("worker", "curve", "reference_points", "retained_points"):
            synthetic[key] = v
    fallback = []
    for n in (33,1001,100001):
        rows = [next(r for r in p["fallback"] if r["retained_points"] == n) for p in outputs]
        row = {k:v for k,v in rows[0].items() if k != "worker" and not k.endswith("repeats_ms") and not k.endswith("median_ms")}
        for key in ("enabled_median_ms", "diagnostic_bypassed_median_ms"):
            row[key] = median_range([r[key] for r in rows])
        fallback.append(row)
    natural = {name: {"query_locations": sum(r[name+"_observed_queries"] for r in curves),
                      "fallback_queries": sum(r[name+"_fallback_queries"] for r in curves)}
               for name in ("reduced", "full_schema")}
    summary = {"status": "PASS", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "software_version": "0.3.0", "runtime_modified": False, "runtime_sha256": outputs[0]["runtime_sha256"],
               "script_sha256": sha(__file__), "hardware": outputs[0]["hardware"],
               "protocol": {"workers":3, "processes":"new sequential Python process for each repetition",
                            "per_process_load_and_query_repeats":REPEATS,"warmups":1,
                            "query_batch_size":QUERY_COUNT,"query_seed":SEED,
                            "query_locations":"uniform random prefixes and independent sorted uniform window endpoints",
                            "timing":"perf_counter_ns; milliseconds per complete operation or vectorized batch; median of five per worker, then median of three worker medians",
                            "loading":"warm file cache; read UTF-8 JSON, parse, validate checksum/schema/invariants and construct integration caches; OS cold-cache effects not measured",
                            "size":"actual file stat after deterministic compact JSON save; no ZIP compression",
                            "reduced":"work-priority, fixed 33 nodes, endpoints and absolute peak retained",
                            "dense_schema":"all source nodes in the same WorkCert schema via from_indices, including units, source identity, certificate, payload checksum and method metadata",
                            "dense_minimal":"x, force, units and reference hash in compact JSON, without indices, error metadata, checksum verification or integration caches",
                            "fallback_counter":"untimed wrapper implements exact runtime predicate and delegates unchanged call; absent during timing",
                            "fallback_diagnostic":"private method bypass only in explicitly labelled ablation; not an alternative public implementation"},
               "cohorts":cohorts, "natural_fallback":natural,"synthetic":synthetic,"fallback_stress":fallback,
               "representative_curves":[r for r in curves if r["curve"] in ("PLA_STWC-1","EDAH")],
               "case_rows_file":"exchange_per_curve.csv","all_timing_samples_file":"exchange_individual_timings.csv",
               "timing_samples":len(timing_rows), "source_records":70,
               "cautions":["These small files are already inexpensive to exchange in full.",
                           "The minimal dense JSON load performs less validation and supplies no queries.",
                           "Fallback stress cases deliberately use nonphysical dynamic ranges.",
                           "Timing results characterize this host and workload, not universal speedups."]}
    dump(OUT / "exchange_summary.json", summary)
    print(json.dumps({"status":"PASS", "summary":"exchange_summary.json", "natural_fallback":natural,
                      "reduced_bytes":cohorts["ALL"]["metrics"]["reduced_json_bytes"],
                      "dense_minimal_bytes":cohorts["ALL"]["metrics"]["dense_minimal_json_bytes"]}), flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",type=int,choices=(1,2,3))
    parser.add_argument("--aggregate-only",action="store_true")
    args=parser.parse_args()
    if args.worker:
        worker_main(args.worker)
        return
    OUT.mkdir(parents=True,exist_ok=True)
    if not args.aggregate_only:
        for worker in (1,2,3):
            subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",str(worker)],check=True)
    aggregate()


if __name__ == "__main__":
    main()
