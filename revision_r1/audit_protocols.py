"""Independent audits of source indicators, stopping populations and DP scope.

Reads the archived study without changing its original results. Original PLA
workbooks are integrated with Fraction arithmetic on their stored binary input
values. WorkCert query/integration routines are not used. Stopping quantities
are independently checked with a scalar piecewise-linear residual integrator.

Run: python revision_r1/audit_protocols.py
Outputs: revision_r1/results/protocol_*.{json,csv}
"""
from __future__ import annotations
import csv
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
from statistics import median

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "revision_r1/results"
METRICS = ("EA_J", "SEA_kJ_kg", "MCF_kN", "PCF_kN", "CFE")
UNITS = {"EA_J": "J", "SEA_kJ_kg": "kJ/kg", "MCF_kN": "kN", "PCF_kN": "kN", "CFE": "dimensionless"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def save_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def raw_curve(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(workbook.active.values)
    workbook.close()
    assert rows[0] == ("Displacement (mm)", "Force (kN)")
    values = [(float(x), float(f)) for x, f in rows[1:]]
    assert len(values) == 1000
    assert all(math.isfinite(v) for row in values for v in row)
    assert values[0][0] == 0.0
    assert all(b[0] > a[0] for a, b in zip(values, values[1:]))
    return values


def exact_work_and_peak(values, query):
    """Integrate the PL binary-input reference exactly before one float conversion."""
    q = Fraction.from_float(float(query))
    total = Fraction(0)
    peak = Fraction.from_float(values[0][1])
    for (xa, fa), (xb, fb) in zip(values, values[1:]):
        a, b = Fraction.from_float(xa), Fraction.from_float(xb)
        f, g = Fraction.from_float(fa), Fraction.from_float(fb)
        if a >= q:
            break
        right = min(b, q)
        endpoint = f + (g - f) * (right - a) / (b - a)
        total += (right - a) * (f + endpoint) / 2
        peak = max(peak, f, endpoint)
        if b >= q:
            break
    return total, peak


def indicators(work, peak, mass, denominator):
    m = Fraction.from_float(float(mass))
    u = Fraction.from_float(float(denominator))
    return {"EA_J": float(work), "SEA_kJ_kg": float(work / m),
            "MCF_kN": float(work / u), "PCF_kN": float(peak),
            "CFE": float(work / u / peak)}


def audit_workbooks():
    raw = ROOT / "data/raw/pla_v7p6y654ft_v4"
    workbook_path = raw / "Mass_and_Crash_Indicators.xlsx"
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    rows = [row for row in book.active.values if isinstance(row[1], (int, float))]
    book.close()
    assert len(rows) == 46
    prior = {row["specimen"]: row for row in read_csv(ROOT / "validation/workflow_results_round2/published_indicator_comparison.csv")}
    manifest = json.loads((ROOT / "data/metadata/pla_download_manifest.json").read_text(encoding="utf-8"))
    manifest_by_path = {Path(r["local_path"]).name: r["sha256"] for r in manifest["downloaded"]}
    assert sha(workbook_path) == manifest_by_path[workbook_path.name]
    details, mismatch, coverage, denominators = [], [], {key: [] for key in METRICS}, []
    for row in rows:
        name, mass, reported = str(row[0]), float(row[1]), float(row[2])
        path = raw / (name + ".xlsx")
        assert sha(path) == manifest_by_path[path.name]
        values = raw_curve(path)
        actual = values[-1][0]
        source = {"EA_J": float(row[4]) * 1000.0, "SEA_kJ_kg": float(row[7]),
                  "MCF_kN": float(row[6]), "PCF_kN": float(row[5]), "CFE": float(row[8])}
        nominal = indicators(*exact_work_and_peak(values, reported), mass, reported)
        # Only the nominal-50mm rows use their small 0.004--0.009mm
        # archived-endpoint overshoot. Other rows keep the workbook's cutoff;
        # their raw records may extend farther into subsequent compression.
        use_overshoot = reported == 50.0 and 50.0 < actual <= 50.01
        aligned_endpoint = actual if use_overshoot else reported
        # The MCF denominator remains the reported stroke in every case.
        aligned = indicators(*exact_work_and_peak(values, aligned_endpoint), mass, reported)
        if abs(nominal["EA_J"] - source["EA_J"]) >= 1e-8:
            mismatch.append({"specimen": name, "reported_stroke_mm": reported,
                             "actual_endpoint_mm": actual,
                             "endpoint_offset_mm": actual - reported})
        denominators.append(abs(source["MCF_kN"] - source["EA_J"] / reported))
        frozen = prior[name]
        table_path = ROOT / "validation/workflow_results_round2/tables" / (name + ".json")
        table = json.loads(table_path.read_text(encoding="utf-8"))["payload"]
        reduced_work, reduced_peak = exact_work_and_peak(list(zip(table["x"], table["force"])), aligned_endpoint)
        reduced = indicators(reduced_work, reduced_peak, mass, reported)
        ep = table["certificate"]["prefix"]
        peak_record = table["metadata"]["retained_global_maximum"]
        if peak_record["x"] <= aligned_endpoint:
            assert peak_record["force"] == reduced["PCF_kN"]
            peak_lower = peak_upper = reduced["PCF_kN"]
        else:
            # These eleven queries are unchanged. Keep their published archived
            # prefix-peak bounds rather than pretending the later global peak
            # was reached at the workbook cutoff.
            assert not use_overshoot
            peak_lower = float(frozen["PCF_kN_lower"])
            peak_upper = float(frozen["PCF_kN_upper"])
        bounds = {"EA_J": (reduced["EA_J"] - ep, reduced["EA_J"] + ep),
            "SEA_kJ_kg": ((reduced["EA_J"] - ep) / mass, (reduced["EA_J"] + ep) / mass),
            "MCF_kN": ((reduced["EA_J"] - ep) / reported, (reduced["EA_J"] + ep) / reported),
            "PCF_kN": (peak_lower, peak_upper),
            "CFE": ((reduced["EA_J"] - ep) / reported / peak_upper,
                    (reduced["EA_J"] + ep) / reported / peak_lower)}
        for metric in METRICS:
            lower, upper = float(frozen[metric + "_lower"]), float(frozen[metric + "_upper"])
            covered = lower - 1e-9 <= source[metric] <= upper + 1e-9
            assert covered == (frozen[metric + "_published_in_interval"] == "True")
            if covered:
                coverage[metric].append(name)
            diff = aligned[metric] - source[metric]
            assert abs(diff) <= 1e-9, (name, metric, aligned_endpoint, aligned[metric], source[metric])
            aligned_lower, aligned_upper = bounds[metric]
            aligned_covered = aligned_lower - 1e-9 <= source[metric] <= aligned_upper + 1e-9
            assert aligned_covered, (name, metric, source[metric], bounds[metric])
            details.append({"specimen": name, "metric": metric, "unit": UNITS[metric],
                "mass_g": mass, "reported_stroke_mm": reported,
                "raw_record_endpoint_mm": actual, "integration_endpoint_mm": aligned_endpoint,
                "endpoint_rule": "nominal_50mm_overshoot" if use_overshoot else "reported_stroke",
                "MCF_denominator_mm": reported,
                "published": source[metric], "nominal_endpoint_recalculation": nominal[metric],
                "aligned_endpoint_recalculation": aligned[metric], "aligned_signed_difference": diff,
                "aligned_absolute_difference": abs(diff),
                "aligned_relative_difference": abs(diff) / abs(source[metric]),
                "original_reduced_lower": lower, "original_reduced_upper": upper,
                "original_interval_slack_native_unit": 1e-9,
                "original_published_in_interval": covered,
                "aligned_reduced": reduced[metric], "aligned_reduced_lower": aligned_lower,
                "aligned_reduced_upper": aligned_upper, "aligned_published_in_interval": aligned_covered,
                "source_workbook_sha256": sha(path)})
    assert len(mismatch) == 13 and all(x["reported_stroke_mm"] == 50.0 for x in mismatch)
    counts = {metric: len(coverage[metric]) for metric in METRICS}
    assert counts == {"EA_J": 45, "SEA_kJ_kg": 45, "MCF_kN": 45, "PCF_kN": 46, "CFE": 45}
    stats = {}
    for metric in METRICS:
        selected = [row for row in details if row["metric"] == metric]
        largest = max(selected, key=lambda r: r["aligned_absolute_difference"])
        stats[metric] = {"unit": UNITS[metric], "cases": 46,
            "maximum_absolute_difference": largest["aligned_absolute_difference"],
            "maximum_absolute_difference_specimen": largest["specimen"],
            "maximum_relative_difference": max(r["aligned_relative_difference"] for r in selected),
            "median_absolute_difference": median(r["aligned_absolute_difference"] for r in selected),
            "exact_float_matches": sum(r["aligned_absolute_difference"] == 0.0 for r in selected),
            "within_1e_minus_9_native_unit": sum(r["aligned_absolute_difference"] <= 1e-9 for r in selected),
            "aligned_reduced_interval_coverage": sum(r["aligned_published_in_interval"] for r in selected)}
    save_csv(OUT / "protocol_workbook_aligned.csv", details)
    return {"reference_source": "Original XLSX workbooks, not the prepared CSV or WorkCert queries",
        "arithmetic": "Fraction arithmetic on exact binary input values, then rounded once per indicator",
        "original_acceptance": "Published value in [reduced lower - 1e-9, reduced upper + 1e-9] at reported stroke",
        "acceptance_slack": {metric: {"value": 1e-9, "unit": UNITS[metric]} for metric in METRICS},
        "original_coverage": {metric: {"count": len(coverage[metric]), "total": 46,
            "uncovered": sorted(set(prior) - set(coverage[metric]))} for metric in METRICS},
        "original_coverage_is_point_estimate_equality": False,
        "nominal_endpoint_EA_mismatches": mismatch,
        "endpoint_alignment_changes_original_archived_results": False,
        "aligned_metrics": stats,
        "integration_endpoint_rule": "For reported 50mm and raw endpoint in (50,50.01]mm, integrate to raw endpoint (13 records); otherwise keep reported stroke (33 records). The rule is not extended to later raw samples of other curves.",
        "denominator_convention": "MCF retains workbook reported stroke for all 46 records; CFE=MCF/PCF; SEA=EA/mass",
        "aligned_interval_calculation": "Integrate retained tables independently at aligned cutoff and reuse saved prefix-error budget. Retained global peak gives exact peak bounds when reached; eleven unchanged earlier queries retain their archived prefix-peak bounds.",
        "maximum_published_MCF_minus_published_EA_over_reported_stroke_kN": max(denominators),
        "mass_workbook_sha256": sha(workbook_path)}


def residual_measures(x, f, ids):
    """Independent scalar PL residual calculation, with compensated prefixes."""
    residual = [0.0] * len(x)
    for a, b in zip(ids, ids[1:]):
        slope = (f[b] - f[a]) / (x[b] - x[a])
        for i in range(a + 1, b):
            residual[i] = (f[i] - f[a]) - slope * (x[i] - x[a])
    terms, areas = [], []
    cumulative, correction, low, high = 0.0, 0.0, 0.0, 0.0
    for i in range(len(x) - 1):
        left, right, h = residual[i], residual[i + 1], x[i + 1] - x[i]
        term = h * (left + right) * 0.5
        if left * right < 0:
            frac = -left / (right - left)
            interior = math.fsum((cumulative, correction, h * (left * frac + (right - left) * frac * frac / 2)))
            low, high = min(low, interior), max(high, interior)
            areas.append(h * (left * left + right * right) / (2 * (abs(left) + abs(right))))
        else:
            areas.append(h * (abs(left) + abs(right)) * 0.5)
        total = cumulative + term
        correction += (cumulative - total) + term if abs(cumulative) >= abs(term) else (term - total) + cumulative
        cumulative = total
        prefix = math.fsum((cumulative, correction))
        low, high = min(low, prefix), max(high, prefix)
        terms.append(term)
    terminal, eta = math.fsum(terms), math.fsum(areas)
    reference = math.fsum((b - a) * (ff + gg) * 0.5 for a, b, ff, gg in zip(x, x[1:], f, f[1:]))
    return {"eta": eta, "xi": (eta + abs(terminal)) / 2,
            "prefix": max(abs(low), abs(high)), "window": high - low,
            "delta": max(abs(v) for v in residual), "reference_work": reference}


def audit_stopping():
    inventory = {r["curve"]: r for r in json.loads((ROOT / "data/metadata/reference_audit.json").read_text())["curves"]}
    rows = read_csv(ROOT / "validation/results_v02/stopping_metrics.csv")
    expected = {(name, method, measure) for name in inventory for method in ("work", "vertical") for measure in ("eta", "xi", "prefix", "window")}
    assert len(rows) == 560
    assert {(r["curve"], r["method"], r["measure"]) for r in rows} == expected
    refs, detail, checks = {}, [], 0
    worst_relative_difference = 0.0
    for row in rows:
        entry = inventory[row["curve"]]
        if row["curve"] not in refs:
            p = ROOT / entry["prepared"]
            assert sha(p) == entry["prepared_sha256"]
            data = read_csv(p)
            refs[row["curve"]] = ([float(r["x_mm"]) for r in data], [float(r["force_kN"]) for r in data])
        x, f = refs[row["curve"]]
        p = ROOT / row["table"]
        assert sha(p) == row["sha256"]
        payload = json.loads(p.read_text(encoding="utf-8"))["payload"]
        meta, cert, ids = payload["metadata"], payload["certificate"], payload["indices"]
        assert meta["requested_max_points"] == len(x)
        assert meta["requested_tolerance"] == 0.01 and meta["relative_tolerance"] is True
        assert meta["selection_method"] == row["method"] and meta["certificate_for_stopping"] == row["measure"]
        peak = max(range(len(f)), key=lambda i: abs(f[i]))
        assert meta["peak_mode"] == "absolute" and meta["preserve_peak"] is True
        assert ids[0] == 0 and ids[-1] == len(x) - 1 and peak in ids
        assert len(ids) == int(row["points"]) and ids == sorted(set(ids))
        assert payload["x"] == [x[i] for i in ids] and payload["force"] == [f[i] for i in ids]
        calculated = residual_measures(x, f, ids)
        for key, value in calculated.items():
            assert math.isclose(value, cert[key], rel_tol=3e-11, abs_tol=1e-12), (row["curve"], key, value, cert[key])
            if cert[key] != 0:
                worst_relative_difference = max(worst_relative_difference, abs(value - cert[key]) / abs(cert[key]))
            checks += 1
        met = calculated[row["measure"]] / abs(calculated["reference_work"]) <= 0.01
        assert meta["tolerance_met"] == (row["tolerance_met"] == "True") == met
        detail.append({"curve": row["curve"], "dataset": row["dataset"], "method": row["method"],
            "measure": row["measure"], "reference_points": len(x), "point_cap": meta["requested_max_points"],
            "first_absolute_peak_index": peak, "retained_points": len(ids), "relative_tolerance": 0.01,
            "independent_relative_error": calculated[row["measure"]] / abs(calculated["reference_work"]),
            "tolerance_met": met, "table_sha256": sha(p)})
    summaries = {}
    for method in ("work", "vertical"):
        summaries[method] = {}
        for measure in ("eta", "xi", "prefix", "window"):
            selected = [r for r in detail if r["method"] == method and r["measure"] == measure]
            assert len(selected) == 70
            summaries[method][measure] = {"cases": len(selected), "median_nodes": median(r["retained_points"] for r in selected),
                "minimum_nodes": min(r["retained_points"] for r in selected), "maximum_nodes": max(r["retained_points"] for r in selected),
                "failures": sum(not r["tolerance_met"] for r in selected),
                "at_point_cap": sum(r["retained_points"] == r["point_cap"] for r in selected)}
    assert summaries["work"]["eta"]["median_nodes"] == 27
    assert summaries["work"]["window"]["median_nodes"] == 14
    save_csv(OUT / "protocol_stopping_cases.csv", detail)
    return {"cases": len(rows), "expected_full_factorial_cases": len(expected), "missing_cases": 0,
        "curves": len(inventory), "cohorts": dict(Counter(r["dataset"] for r in inventory.values())),
        "point_cap": "n, the complete original reference length, for each case",
        "anchors": "both endpoints and first index of absolute maximum force",
        "tolerance": "0.01 times absolute terminal reference work; all 70 reference works are nonzero",
        "failures": sum(not r["tolerance_met"] for r in detail), "failed_cases_excluded": 0,
        "independent_scalar_field_checks": checks, "maximum_field_relative_difference": worst_relative_difference,
        "scalar_comparison_tolerance": {"relative": 3e-11, "absolute": 1e-12},
        "groups": summaries,
        "interpretation": "27 versus 14 compares eta and window stopping of the same work-priority selector on all 70 curves, not competing selectors. Prefix cases are separate tasks."}


def audit_dp_scope():
    inventory = json.loads((ROOT / "data/metadata/reference_audit.json").read_text())["curves"]
    verification = json.loads((ROOT / "validation/results_v02/dp_verification.json").read_text())
    solutions = json.loads((ROOT / "validation/results_v02/dp_solutions.json").read_text())
    eligible = [r for r in inventory if r["points"] <= 1000]
    assert len(eligible) == 58
    assert {r["curve"] for r in eligible} == {r["curve"] for r in verification["eligible_records"]}
    assert len(solutions) == 580
    assert {(s["curve"], s["budget"], s["objective"]) for s in solutions} == {(r["curve"], k, obj) for r in eligible for k in (9, 17, 33, 65, 129) for obj in ("eta", "vertical")}
    for s in solutions:
        ids = s["indices"]
        assert len(ids) == s["budget"] and ids == sorted(set(ids))
    return {"eligibility_ceiling": 1000, "eligible_references": 58,
        "eligible_cohorts": dict(Counter(r["dataset"] for r in eligible)), "excluded_references": len(inventory) - len(eligible),
        "solutions": len(solutions), "budgets": [9, 17, 33, 65, 129],
        "exclusion_criterion": "Original reference length only, before computing errors; no downsampling or error-based selection",
        "ceiling_is": "A documented computational ceiling for benchmark controls, not a package input-size or numerical-accuracy limit",
        "edge_precomputation": "O(n^3) time for all intervals scanned over their contained source cells; O(n^2) storage",
        "DP": "O(K*n^2) time and O(K*n) state storage in addition to the edge matrices",
        "total_complexity": "O(n^3 + K*n^2) time; O(n^2 + K*n) storage",
        "two_float64_edge_matrices_bytes_at_n1000": 2 * 1000 * 1000 * 8,
        "objectives": ["continuous absolute-area residual eta", "maximum vertical residual delta"],
        "not_optimized": ["prefix work error", "window work error"],
        "budget_129_history": "Added during internal revision on 2026-11-02; not described as preregistered",
        "source_script_sha256": sha(ROOT / "validation/optimal_dp.py"),
        "protocol_sha256": sha(ROOT / "validation/baselines_protocol.txt")}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"status": "PASS", "python": platform.python_version(), "openpyxl": openpyxl.__version__,
        "script_sha256": sha(Path(__file__)), "workbook": audit_workbooks(),
        "stopping": audit_stopping(), "dp_scope": audit_dp_scope()}
    (OUT / "protocol_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "aligned_metrics": report["workbook"]["aligned_metrics"],
        "original_coverage": report["workbook"]["original_coverage"], "stopping_groups": report["stopping"]["groups"],
        "independent_scalar_field_checks": report["stopping"]["independent_scalar_field_checks"],
        "maximum_field_relative_difference": report["stopping"]["maximum_field_relative_difference"]}, indent=2))


if __name__ == "__main__":
    main()
