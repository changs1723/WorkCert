"""Consumer-driven best-candidate refinement and inverse energy-capacity queries.

Selection and refinement requests use exchanged tables only. Dense references
are opened by the producer and, separately, by the post-decision evaluator.
The numerical ordering is conditional on the supplied records and reported
masses; it is not a statement about a manufacturing population.
"""
from pathlib import Path
from collections import Counter
import bisect
import csv
import hashlib
import json
import math
import statistics
import sys
from fractions import Fraction

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software/src"))
from workcert import ReducedResponse, reduce_response, __version__

OUT = ROOT / "validation/decision_results"
STROKES = (10.0, 20.0, 30.0, 40.0)
METHODS = ("work", "vertical", "rdp", "vw", "uniform_peak", "uniform")
INITIAL_BUDGET_J = 1.0
POINT_CAP = 129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf8")


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def configuration(specimen):
    for group in ("N-SCMC", "STWC"):
        if specimen.startswith(group + "-"):
            return group
    return specimen


def source_records():
    path = ROOT / "data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx"
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = [row for row in book.active.values if isinstance(row[1], (int, float))]
    book.close()
    assert len(rows) == 46
    records = []
    for row in rows:
        specimen = str(row[0])
        source = ROOT / "data/prepared" / ("PLA_" + specimen + ".csv")
        with source.open(newline="", encoding="utf8") as stream:
            data = list(csv.DictReader(stream))
        records.append({"specimen": specimen, "configuration": configuration(specimen),
                        "mass_g": float(row[1]), "source": source,
                        "x": np.array([float(r["x_mm"]) for r in data]),
                        "force": np.array([float(r["force_kN"]) for r in data])})
    return path, records


def independent_work(x, force, q):
    """Clipped PL integral using scalar interpolation and math.fsum, no WorkCert."""
    q = float(q)
    if q < x[0] or q > x[-1]:
        raise ValueError("Query outside the supplied reference")
    pieces = []
    for i in range(len(x) - 1):
        left, right = float(x[i]), float(x[i + 1])
        if q <= left:
            break
        end = min(q, right)
        value = float(force[i]) + (float(force[i + 1]) - float(force[i])) * ((end - left) / (right - left))
        pieces.append((end - left) * (0.5 * float(force[i]) + 0.5 * value))
        if end == q:
            break
    return math.fsum(pieces)


def construct(record, budget, stage):
    table = reduce_response(
        record["x"], record["force"], method="work", max_points=POINT_CAP,
        tolerance=budget, certificate="window", peak_mode="absolute",
        x_unit="mm", force_unit="kN", provenance={
            "specimen": record["specimen"], "configuration": record["configuration"],
            "mass_g": record["mass_g"], "source_doi": "10.17632/v7p6y654ft.4",
            "source_csv_sha256": sha(record["source"]),
            "consumer_requested_work_budget_J": budget})
    path = OUT / "tables" / stage / (record["specimen"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    table.save(path)
    received = ReducedResponse.load(path)
    assert received.verify_reference(record["x"], record["force"])
    return received, path


def consumer_configurations(exchanged, masses, stroke):
    """Consumer boundary: inputs are reduced responses, masses and a query only."""
    members = {}
    for specimen, table in exchanged.items():
        mass = masses[specimen]
        value = float(table.work(stroke)) / mass
        error = table.certificate.prefix / mass
        members.setdefault(configuration(specimen), []).append((value, value - error, value + error))
    records = []
    for group, values in sorted(members.items()):
        records.append({"configuration": group, "stroke_mm": stroke, "specimens": len(values),
                        "SEA_kJ_kg": statistics.mean(v[0] for v in values),
                        "SEA_lower_kJ_kg": statistics.mean(v[1] for v in values),
                        "SEA_upper_kJ_kg": statistics.mean(v[2] for v in values)})
    assert len(records) == 42
    return records


def consumer_request(configurations):
    """Identify every response that can still challenge the largest lower bound."""
    leader = max(configurations, key=lambda r: (r["SEA_lower_kJ_kg"], r["configuration"]))
    challengers = [r for r in configurations if r["configuration"] != leader["configuration"]
                   and r["SEA_upper_kJ_kg"] >= leader["SEA_lower_kJ_kg"]]
    other_upper = max(r["SEA_upper_kJ_kg"] for r in configurations
                      if r["configuration"] != leader["configuration"])
    requested = sorted({leader["configuration"], *(r["configuration"] for r in challengers)}) if challengers else []
    return {"leader": leader["configuration"], "challengers": sorted(r["configuration"] for r in challengers),
            "request_configurations": requested, "winner_separated": not challengers,
            "leader_lower_kJ_kg": leader["SEA_lower_kJ_kg"],
            "largest_other_upper_kJ_kg": other_upper,
            "separation_margin_kJ_kg": leader["SEA_lower_kJ_kg"] - other_upper}


def evaluate_tables(configurations, sources, stroke):
    """Post-decision assessment; reference order never enters consumer_request."""
    truth = {}
    for record in sources:
        truth.setdefault(record["configuration"], []).append(
            independent_work(record["x"], record["force"], stroke) / record["mass_g"])
    truth = {group: statistics.mean(values) for group, values in truth.items()}
    records = [dict(row, reference_SEA_kJ_kg=truth[row["configuration"]]) for row in configurations]
    for row in records:
        assert row["SEA_lower_kJ_kg"] - 1e-10 <= row["reference_SEA_kJ_kg"] <= row["SEA_upper_kJ_kg"] + 1e-10
    ordered = sorted(records, key=lambda r: (r["reference_SEA_kJ_kg"], r["configuration"]))
    pairs = []
    for lower, higher in zip(ordered, ordered[1:]):
        pairs.append({"stroke_mm": stroke, "lower_configuration": lower["configuration"],
                      "higher_configuration": higher["configuration"],
                      "reference_gap_kJ_kg": higher["reference_SEA_kJ_kg"] - lower["reference_SEA_kJ_kg"],
                      "separation_margin_kJ_kg": higher["SEA_lower_kJ_kg"] - lower["SEA_upper_kJ_kg"],
                      "separated": higher["SEA_lower_kJ_kg"] > lower["SEA_upper_kJ_kg"]})
    all_pairs = sum(a["SEA_lower_kJ_kg"] > b["SEA_upper_kJ_kg"] or b["SEA_lower_kJ_kg"] > a["SEA_upper_kJ_kg"]
                    for i, a in enumerate(records) for b in records[i + 1:])
    return records, pairs, all_pairs


def inverse_work(table, target, lower, upper):
    if not float(table.work(lower)) <= target <= float(table.work(upper)):
        raise ValueError("Energy target outside the chosen loading interval")
    for _ in range(70):
        middle = lower + 0.5 * (upper - lower)
        if middle == lower or middle == upper:
            break
        if float(table.work(middle)) < target:
            lower = middle
        else:
            upper = middle
    return lower + 0.5 * (upper - lower)


def inverse_energy_example(table, source):
    target, lower, upper = 100.0, 10.0, 40.0
    evaluation_nodes = np.r_[lower, table.x[(table.x > lower) & (table.x < upper)], upper]
    reference_force_lower = float(np.min(table.force_at(evaluation_nodes))) - table.certificate.delta
    assert reference_force_lower > 0
    source_nodes = np.r_[lower, source["x"][(source["x"] > lower) & (source["x"] < upper)], upper]
    source_force_minimum = float(np.min(np.interp(source_nodes, source["x"], source["force"])))
    assert source_force_minimum > 0
    error = table.certificate.prefix
    lo = inverse_work(table, target - error, lower, upper)
    hi = inverse_work(table, target + error, lower, upper)
    estimate = inverse_work(table, target, lower, upper)
    a, b = lower, upper
    for _ in range(55):
        mid = (a + b) * 0.5
        if independent_work(source["x"], source["force"], mid) < target:
            a = mid
        else:
            b = mid
    reference = (a + b) * 0.5
    assert lo <= reference <= hi
    return {"specimen": "STWC-1", "energy_target_J": target, "loading_interval_mm": [lower, upper],
            "retained_points": len(table.x), "prefix_bound_J": error,
            "source_force_lower_bound_kN": reference_force_lower,
            "reference_minimum_force_on_loading_interval_kN": source_force_minimum,
            "table_inverse_mm": estimate, "stroke_lower_mm": lo, "stroke_upper_mm": hi,
            "stroke_interval_width_mm": hi - lo, "reference_inverse_mm": reference,
            "reference_contained": True,
            "scope": "Inverse quasi-static work capacity of a fixed loading record; not an impact-dynamics prediction"}


def mass_rounding_example(sources, final_tables, stroke, leader, challenger):
    """Post-decision sensitivity of a singleton comparison to reported mass rounding.

    Positive work divided by positive mass is increasing in work and decreasing
    in mass. The rounding scenario is deterministic, with no probability model.
    It does not enter the consumer's fixed-reported-mass refinement requests.
    """
    half_width = 0.05
    by_name = {record["specimen"]: record for record in sources}
    stages = {stage: [] for stage in ("initial", "refined", "dense_reference")}
    for specimen in (leader, challenger):
        source = by_name[specimen]
        assert configuration(specimen) == specimen
        mass = source["mass_g"]
        assert mass > half_width
        initial = ReducedResponse.load(OUT / "tables/initial" / (specimen + ".json"))
        dense_work = independent_work(source["x"], source["force"], stroke)
        for stage, table in (("initial", initial), ("refined", final_tables[specimen]),
                             ("dense_reference", None)):
            work = dense_work if table is None else float(table.work(stroke))
            error = 0.0 if table is None else table.certificate.prefix
            assert work > error >= 0
            lower_work, upper_work = work - error, work + error
            stages[stage].append({
                "specimen": specimen, "reported_mass_g": mass,
                "mass_interval_g": [mass - half_width, mass + half_width],
                "retained_points": len(source["x"]) if table is None else len(table.x),
                "work_estimate_J": work, "prefix_bound_J": error,
                "work_interval_J": [lower_work, upper_work],
                "reported_mass_SEA_interval_kJ_kg": [lower_work / mass, upper_work / mass],
                "rounded_mass_SEA_interval_kJ_kg": [lower_work / (mass + half_width),
                                                    upper_work / (mass - half_width)]})
    comparisons = {}
    for stage, records in stages.items():
        higher, lower = records
        reported = higher["reported_mass_SEA_interval_kJ_kg"][0] - lower["reported_mass_SEA_interval_kJ_kg"][1]
        rounded = higher["rounded_mass_SEA_interval_kJ_kg"][0] - lower["rounded_mass_SEA_interval_kJ_kg"][1]
        comparisons[stage] = {"records": records, "reported_mass_worst_lead_kJ_kg": reported,
                              "rounded_mass_worst_lead_kJ_kg": rounded,
                              "reported_mass_order_separated": reported > 0,
                              "rounded_mass_order_separated": rounded > 0}
    assert comparisons["refined"]["reported_mass_order_separated"]
    assert not comparisons["refined"]["rounded_mass_order_separated"]
    assert comparisons["dense_reference"]["rounded_mass_worst_lead_kJ_kg"] < 0
    return {"schema": "workcert.mass-rounding-sensitivity/1.0", "stroke_mm": stroke,
            "leader_at_reported_masses": leader, "challenger": challenger,
            "mass_half_width_g": half_width,
            "unit_identity": "J/g equals kJ/kg",
            "formula": "For W_hat > E >= 0 and m > h > 0, SEA lies in [(W_hat-E)/(m+h), (W_hat+E)/(m-h)]. Worst lead is the leader lower endpoint minus the challenger upper endpoint.",
            "role": "Post-decision deterministic mass-rounding sensitivity; no change to the consumer's fixed-mass refinement rule",
            "interpretation": "The reported-mass ordering is separated after curve refinement, but the +/-0.05 g scenario overlaps even with the dense references. Further curve refinement cannot resolve the missing mass information.",
            "source_workbook_sha256": sha(ROOT / "data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx"),
            "source_csv_sha256": {name: sha(by_name[name]["source"]) for name in (leader, challenger)},
            "stages": comparisons}


def weighted_median(values, weights):
    """Weighted empirical median, midpoint at exact half of rational weights."""
    pairs = sorted((value, Fraction(weight).limit_denominator(1000000)) for value, weight in zip(values, weights))
    halfway = sum((weight for value, weight in pairs), Fraction(0)) / 2
    cumulative = Fraction(0)
    for i, (value, weight) in enumerate(pairs):
        cumulative += weight
        if cumulative == halfway and i + 1 < len(pairs):
            return 0.5 * (value + pairs[i + 1][0])
        if cumulative > halfway:
            return value
    return pairs[-1][0]


def configuration_weight(row):
    return 1.0 / 3.0 if row["dataset"] == "PLA_plus" and row["curve"].startswith(("PLA_STWC-", "PLA_N-SCMC-")) else 1.0


def sensitivity():
    source = ROOT / "validation/results_v02/selector_metrics.csv"
    with source.open(newline="", encoding="utf8") as stream:
        rows = [row for row in csv.DictReader(stream) if int(row["budget"]) == 33 and row["method"] in METHODS]
    cohort_counts = Counter(row["dataset"] for row in rows if row["method"] == "work")
    assert dict(cohort_counts) == {"CX_steel": 23, "EDAH": 1, "PLA_plus": 46}, cohort_counts
    records = []
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        for metric in ("prefix_error_percent", "window_error_percent"):
            values = [float(row[metric]) for row in selected]
            for scheme, weights in (
                    ("equal_records", [1.0] * len(selected)),
                    ("equal_cohorts", [1.0 / cohort_counts[row["dataset"]] for row in selected]),
                    ("equal_configurations", [configuration_weight(row) for row in selected])):
                # Preserve the conventional midpoint definition for an even unweighted sample.
                median = statistics.median(values) if scheme == "equal_records" else weighted_median(values, weights)
                records.append({"method": method, "metric": metric, "weighting": scheme,
                                "weighted_median_percent": median, "records": len(selected),
                                "total_weight": math.fsum(weights)})
    cohorts = []
    for cohort in cohort_counts:
        for method in METHODS:
            selected = [row for row in rows if row["dataset"] == cohort and row["method"] == method]
            cohorts.append({"dataset": cohort, "records": len(selected), "method": method,
                            "median_prefix_error_percent": statistics.median(float(r["prefix_error_percent"]) for r in selected),
                            "median_window_error_percent": statistics.median(float(r["window_error_percent"]) for r in selected)})
    dp_file = ROOT / "validation/results_v02/optimality_gaps.csv"
    with dp_file.open(newline="", encoding="utf8") as stream:
        dp = [row for row in csv.DictReader(stream) if int(row["budget"]) == 33]
    dp_counts = Counter(row["dataset"] for row in dp if row["method"] == "work" and row["objective"] == "eta")
    assert dict(dp_counts) == {"CX_steel": 12, "PLA_plus": 46}, dp_counts
    dp_rows = []
    for objective in ("eta", "vertical"):
        for method in METHODS[:-1]:
            selected = [row for row in dp if row["objective"] == objective and row["method"] == method]
            if not selected:
                continue
            values = [float(row["ratio"]) for row in selected]
            for scheme, weights in (
                    ("equal_records", [1.0] * len(selected)),
                    ("equal_cohorts", [1.0 / dp_counts[row["dataset"]] for row in selected]),
                    ("equal_configurations", [configuration_weight(row) for row in selected])):
                dp_rows.append({"objective": objective, "method": method, "weighting": scheme,
                                "weighted_median_ratio": statistics.median(values) if scheme == "equal_records" else weighted_median(values, weights),
                                "records": len(selected), "total_weight": math.fsum(weights)})
    write_csv(OUT / "weighting_sensitivity.csv", records)
    write_csv(OUT / "cohort_medians.csv", cohorts)
    write_csv(OUT / "dp_weighting_sensitivity.csv", dp_rows)
    return {"force_cohort_counts": dict(cohort_counts), "DP_cohort_counts": dict(dp_counts),
            "PLA_share_force_records_percent": 46 / 70 * 100, "PLA_share_DP_records_percent": 46 / 58 * 100,
            "configuration_weight_total_force": 66, "configuration_weight_total_DP": 54,
            "weighted_median_definition": "Weighted empirical median using rational cohort/configuration weights; if cumulative weight equals one half exactly, use the midpoint of the bracketing values, recovering the conventional even-sample median",
            "weighting_schemes": {"equal_records": "Every recorded specimen has unit weight",
                "equal_cohorts": "Each available cohort has equal total weight; EDAH remains one observation",
                "equal_configurations": "The three trials in each repeated PLA control share unit total weight; all other recorded configurations have unit weight"},
            "cohort_window_error_rankings": {cohort: [r["method"] for r in sorted([v for v in cohorts if v["dataset"] == cohort], key=lambda v: v["median_window_error_percent"])] for cohort in cohort_counts},
            "sensitivity_window_error_rankings": {scheme: [r["method"] for r in sorted([v for v in records if v["weighting"] == scheme and v["metric"] == "window_error_percent"], key=lambda v: v["weighted_median_percent"])] for scheme in ("equal_records", "equal_cohorts", "equal_configurations")},
            "selector_metrics_sha256": sha(source), "optimality_gaps_sha256": sha(dp_file)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    workbook, sources = source_records()
    masses = {record["specimen"]: record["mass_g"] for record in sources}
    by_name = {record["specimen"]: record for record in sources}
    exchanged, paths, budgets = {}, {}, {}
    for record in sources:
        table, path = construct(record, INITIAL_BUDGET_J, "initial")
        exchanged[record["specimen"]] = table
        paths[record["specimen"]] = path
        budgets[record["specimen"]] = INITIAL_BUDGET_J
    initial_points = sum(len(t.x) for t in exchanged.values())
    initial_hashes = {specimen: sha(path) for specimen, path in paths.items()}
    query_rows, adjacent_rows, query_counts = [], [], []
    for stroke in STROKES:
        received = consumer_configurations(exchanged, masses, stroke)
        records, adjacent, all_separated = evaluate_tables(received, sources, stroke)
        query_rows.extend(dict(row, stage="initial") for row in records)
        adjacent_rows.extend(adjacent)
        query_counts.append({"stroke_mm": stroke, "adjacent_pairs": len(adjacent),
                             "adjacent_separated": sum(r["separated"] for r in adjacent),
                             "all_pairs": 861, "all_pairs_separated": all_separated})
    trace, refinement_rows, refined_names = [], [], set()
    stroke = 20.0
    for stage in range(9):
        received = consumer_configurations(exchanged, masses, stroke)
        decision = consumer_request(received)
        trace.append({"stage": stage, "stroke_mm": stroke, "total_retained_nodes": sum(len(t.x) for t in exchanged.values()),
                      "consumer_received_configurations": received,
                      "consumer_read_dense_references": False, **decision})
        if decision["winner_separated"]:
            break
        wanted = [name for name in exchanged if configuration(name) in decision["request_configurations"]]
        for specimen in sorted(wanted):
            before = exchanged[specimen]
            budget = budgets[specimen] * 0.5
            after, path = construct(by_name[specimen], budget, "refinement_%02d" % (stage + 1))
            refinement_rows.append({"stage": stage + 1, "specimen": specimen,
                                    "configuration": configuration(specimen), "stroke_mm": stroke,
                                    "requested_window_budget_J": budget, "previous_points": len(before.x),
                                    "points": len(after.x), "window_bound_J": after.certificate.window,
                                    "prefix_bound_J": after.certificate.prefix,
                                    "tolerance_met": bool(after.metadata["tolerance_met"]),
                                    "previous_table_sha256": sha(paths[specimen]), "table_sha256": sha(path),
                                    "table": path.relative_to(ROOT).as_posix()})
            if not after.metadata["tolerance_met"]:
                raise RuntimeError("Requested refinement reached the point cap; increase the documented cap or query the source")
            exchanged[specimen], paths[specimen], budgets[specimen] = after, path, budget
            refined_names.add(specimen)
    else:
        raise RuntimeError("No separated best candidate within the declared refinement rounds")
    final_records, final_adjacent, final_all = evaluate_tables(received, sources, stroke)
    query_rows.extend(dict(row, stage="final") for row in final_records)
    truth_order = sorted(final_records, key=lambda r: r["reference_SEA_kJ_kg"], reverse=True)
    assert trace[-1]["leader"] == truth_order[0]["configuration"]
    assert all(sha(paths[name]) == initial_hashes[name] for name in exchanged if name not in refined_names)
    for stage in trace:
        truth = {row["configuration"]: row["reference_SEA_kJ_kg"] for row in final_records}
        for row in stage["consumer_received_configurations"]:
            assert row["SEA_lower_kJ_kg"] - 1e-10 <= truth[row["configuration"]] <= row["SEA_upper_kJ_kg"] + 1e-10
    inverse = inverse_energy_example(exchanged["STWC-1"], by_name["STWC-1"])
    mass_rounding = mass_rounding_example(sources, exchanged, stroke,
                                         truth_order[0]["configuration"], truth_order[1]["configuration"])
    write_csv(OUT / "configuration_queries.csv", query_rows)
    write_csv(OUT / "adjacent_comparisons.csv", adjacent_rows)
    write_csv(OUT / "query_difficulty.csv", query_counts)
    write_csv(OUT / "refinement_steps.csv", refinement_rows)
    write_json(OUT / "consumer_trace.json", trace)
    write_json(OUT / "energy_to_stroke.json", inverse)
    write_json(OUT / "mass_rounding.json", mass_rounding)
    weights = sensitivity()
    write_json(OUT / "weighting_sensitivity.json", weights)
    write_json(OUT / "protocol_history.json", {
        "protocol_origin_date": "2026-10-31", "original_DP_budgets": [9, 17, 33, 65],
        "extended_DP_budgets": [9, 17, 33, 65, 129],
        "extension_recorded_date": "2026-11-02", "documentation_correction_date": "2026-11-03",
        "prior_public_version": "0.2.0", "prior_public_archive_doi": "10.5281/zenodo.23915585",
        "prior_public_protocol_sha256": "4a007dcc22492ed92761857a1af073d8e647edccb109b6a0bed993d91165c4ed",
        "current_protocol_sha256": sha(ROOT / "validation/baselines_protocol.txt"),
        "interpretation": "The 129-node DP budget was added in an internal revision after the initial four-budget plan. It is not represented as a preregistered decision."})
    manifest = []
    for specimen, path in sorted(paths.items()):
        manifest.append({"specimen": specimen, "mass_g": masses[specimen],
                         "source_csv": by_name[specimen]["source"].relative_to(ROOT).as_posix(),
                         "source_csv_sha256": sha(by_name[specimen]["source"]),
                         "final_table": path.relative_to(ROOT).as_posix(), "final_sha256": sha(path),
                         "initial_table": (OUT / "tables/initial" / (specimen + ".json")).relative_to(ROOT).as_posix(),
                         "initial_sha256": initial_hashes[specimen], "refined": specimen in refined_names,
                         "final_points": len(exchanged[specimen].x)})
    write_json(OUT / "table_manifest.json", manifest)
    cyclic_path = ROOT / "validation/workflow_results/cyclic_path/branch_metrics.csv"
    with cyclic_path.open(newline="", encoding="utf8") as stream:
        cyclic_failures = [row for row in csv.DictReader(stream) if row["tolerance_met"] == "False"]
    cyclic_diagnostic = [{"branch": int(row["branch"]), "source_points": int(row["source_points"]),
                         "retained_points": int(row["retained_points"]),
                         "allocated_bound_J": float(row["allocated_bound_J"]),
                         "window_bound_J": float(row["window_bound_J"]),
                         "achieved_to_requested_ratio": float(row["window_bound_J"]) / float(row["allocated_bound_J"])}
                        for row in cyclic_failures]
    scatter_path = ROOT / "validation/workflow_results_round2/repeat_scatter.csv"
    with scatter_path.open(newline="", encoding="utf8") as stream:
        scatter = list(csv.DictReader(stream))
    closest = max(scatter, key=lambda row: float(row["bound_to_sample_SD_ratio"]))
    summary = {"software_version": __version__, "core_sha256": sha(ROOT / "software/src/workcert/core.py"),
               "workflow_sha256": sha(__file__), "source_workbook_sha256": sha(workbook),
               "initial_work_budget_J": INITIAL_BUDGET_J, "point_cap": POINT_CAP,
               "configuration_count": 42, "specimens": 46,
               "initial_total_retained_points": initial_points,
               "initial_adjacent_pairs": sum(r["adjacent_pairs"] for r in query_counts),
               "initial_adjacent_separated": sum(r["adjacent_separated"] for r in query_counts),
               "initial_all_pairs": sum(r["all_pairs"] for r in query_counts),
               "initial_all_pairs_separated": sum(r["all_pairs_separated"] for r in query_counts),
               "per_stroke_difficulty": query_counts,
               "best_candidate_query": {"stroke_mm": stroke, "initial_decision": {k: v for k, v in trace[0].items() if k != "consumer_received_configurations"},
                   "final_decision": {k: v for k, v in trace[-1].items() if k != "consumer_received_configurations"},
                   "refined_specimens": sorted(refined_names), "unchanged_specimens": 46 - len(refined_names),
                   "refinement_rounds": len(trace) - 1, "final_total_retained_points": sum(len(t.x) for t in exchanged.values()),
                   "net_retained_points_added": sum(len(t.x) for t in exchanged.values()) - initial_points,
                   "retained_points_transmitted_in_refinement_responses": sum(row["points"] for row in refinement_rows),
                   "reference_best": truth_order[0]["configuration"], "reference_runner_up": truth_order[1]["configuration"],
                   "reference_best_runner_up_gap_kJ_kg": truth_order[0]["reference_SEA_kJ_kg"] - truth_order[1]["reference_SEA_kJ_kg"],
                   "truth_used_to_select_requests": False, "final_all_pairs_separated_at_query": final_all,
                   "final_adjacent_separated_at_query": sum(r["separated"] for r in final_adjacent)},
               "energy_to_stroke": inverse,
               "cyclic_point_cap_diagnostic": cyclic_diagnostic,
               "closest_control_SD_comparison": {"configuration": closest["configuration"],
                   "stroke_mm": float(closest["stroke_mm"]), "n": int(closest["n"]),
                   "maximum_prefix_bound_J": float(closest["maximum_prefix_bound_J"]),
                   "EA_sample_SD_J": float(closest["EA_sample_SD_J"]),
                   "bound_to_sample_SD_ratio": float(closest["bound_to_sample_SD_ratio"])},
               "supporting_inputs": {cyclic_path.relative_to(ROOT).as_posix(): sha(cyclic_path),
                                     scatter_path.relative_to(ROOT).as_posix(): sha(scatter_path)},
               "sampling_scope": "The four strokes reuse the same two triplicate controls; eight descriptive control/stroke summaries are not eight independent experiments. One joule is an illustrative reconstruction budget.",
               "decision_scope": "Separation certifies ordering of the supplied numerical configurations at the reported masses, not experimental distinguishability of manufactured designs.",
               "weighting_sensitivity": weights}
    write_json(OUT / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("weighting_sensitivity",)}, indent=2))


if __name__ == "__main__":
    main()
