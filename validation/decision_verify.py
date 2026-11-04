"""Read-only mathematical check of the decision workflow, without WorkCert imports.

Decimal arithmetic at 80-digit precision operates on exact binary64 input values.
Only an explicitly requested --output file is written; source/results are read-only.
"""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/decision_results"
CHECKS = 0
MAXIMUM_DIFFERENCE = 0.0


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def csv_rows(path):
    with Path(path).open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(actual, expected, tolerance=1e-8):
    global CHECKS, MAXIMUM_DIFFERENCE
    difference = abs(float(actual) - float(expected))
    assert difference <= tolerance, (actual, expected, difference, tolerance)
    CHECKS += 1
    MAXIMUM_DIFFERENCE = max(MAXIMUM_DIFFERENCE, difference)


class Reference:
    def __init__(self, x, force):
        self.x_float = x
        self.x = list(map(Decimal.from_float, x))
        self.force = list(map(Decimal.from_float, force))
        self.prefix = [Decimal(0)]
        for i in range(len(x) - 1):
            increment = (self.x[i + 1] - self.x[i]) * (self.force[i] + self.force[i + 1]) / 2
            self.prefix.append(self.prefix[-1] + increment)

    def force_at(self, q):
        i = min(bisect.bisect_right(self.x_float, q) - 1, len(self.x) - 2)
        q = Decimal.from_float(float(q))
        return self.force[i] + (q - self.x[i]) * (self.force[i + 1] - self.force[i]) / (self.x[i + 1] - self.x[i])

    def work(self, q):
        i = min(bisect.bisect_right(self.x_float, q) - 1, len(self.x) - 2)
        query = Decimal.from_float(float(q))
        width = query - self.x[i]
        end_force = self.force[i] + width * (self.force[i + 1] - self.force[i]) / (self.x[i + 1] - self.x[i])
        return self.prefix[i] + width * (self.force[i] + end_force) / 2


def certificate(reference, table):
    reduced = Reference(table["x"], table["force"])
    residual = [force - reduced.force_at(x) for x, force in zip(reference.x_float, reference.force)]
    primitive, absolute = Decimal(0), Decimal(0)
    lower = upper = Decimal(0)
    for i, (left, right) in enumerate(zip(residual, residual[1:])):
        width = reference.x[i + 1] - reference.x[i]
        lower, upper = min(lower, primitive), max(upper, primitive)
        if left * right < 0:
            t = -left / (right - left)
            stationary = primitive + width * t * left / 2
            lower, upper = min(lower, stationary), max(upper, stationary)
            absolute += width * (left * left + right * right) / (2 * (abs(left) + abs(right)))
        else:
            absolute += width * (abs(left) + abs(right)) / 2
        primitive += width * (left + right) / 2
    lower, upper = min(lower, primitive), max(upper, primitive)
    return {"eta": absolute, "xi": (absolute + abs(primitive)) / 2,
            "prefix": max(abs(lower), abs(upper)), "window": upper - lower,
            "signed_terminal_error": primitive, "min_cumulative_error": lower,
            "max_cumulative_error": upper, "delta": max(map(abs, residual)),
            "reference_work": reference.prefix[-1]}


def group_records(paths, masses, tables, stroke):
    groups = defaultdict(list)
    for specimen, path in paths.items():
        table = tables[path]
        mean = float(Reference(table["x"], table["force"]).work(stroke)) / masses[specimen]
        error = table["certificate"]["prefix"] / masses[specimen]
        group = specimen.split("-", 1)[0] if specimen.startswith("STWC-") else "N-SCMC" if specimen.startswith("N-SCMC-") else specimen
        groups[group].append((mean, mean - error, mean + error))
    return {group: {"SEA_kJ_kg": statistics.mean(v[0] for v in values),
                    "SEA_lower_kJ_kg": statistics.mean(v[1] for v in values),
                    "SEA_upper_kJ_kg": statistics.mean(v[2] for v in values)}
            for group, values in groups.items()}


def weighted_median(values, weights):
    items = sorted(zip(values, weights))
    total = sum(weights, Fraction(0))
    cumulative = Fraction(0)
    for i, (value, weight) in enumerate(items):
        cumulative += weight
        if 2 * cumulative > total:
            return value
        if 2 * cumulative == total:
            return (value + items[i + 1][0]) / 2


def weight(row, scheme, counts):
    if scheme == "equal_records":
        return Fraction(1)
    if scheme == "equal_cohorts":
        return Fraction(1, counts[row["dataset"]])
    repeat = row["dataset"] == "PLA_plus" and row["curve"].startswith(("PLA_STWC-", "PLA_N-SCMC-"))
    return Fraction(1, 3) if repeat else Fraction(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Explicit destination for the JSON verification report")
    args = parser.parse_args()
    summary = read_json(OUT / "summary.json")
    manifests = read_json(OUT / "table_manifest.json")
    steps = csv_rows(OUT / "refinement_steps.csv")
    trace = read_json(OUT / "consumer_trace.json")
    assert summary["software_version"] == "0.3.0"
    assert summary["core_sha256"] == sha(ROOT / "software/src/workcert/core.py")
    assert summary["workflow_sha256"] == sha(ROOT / "validation/decision_workflow.py")
    assert len(manifests) == 46
    source_values, source_refs, masses, initial, final = {}, {}, {}, {}, {}
    tables = {}
    for item in manifests:
        specimen = item["specimen"]
        source = ROOT / item["source_csv"]
        assert sha(source) == item["source_csv_sha256"]
        rows = csv_rows(source)
        x, f = [float(row["x_mm"]) for row in rows], [float(row["force_kN"]) for row in rows]
        source_values[specimen] = (x, f)
        source_refs[specimen] = Reference(x, f)
        masses[specimen] = item["mass_g"]
        initial[specimen], final[specimen] = item["initial_table"], item["final_table"]
        for key, digest_key in (("initial_table", "initial_sha256"), ("final_table", "final_sha256")):
            relative = item[key]
            path = ROOT / relative
            assert sha(path) == item[digest_key]
            tables[relative] = read_json(path)["payload"]
        assert item["refined"] == (item["initial_sha256"] != item["final_sha256"])
    for step in steps:
        assert sha(ROOT / step["table"]) == step["table_sha256"]
        tables[step["table"]] = read_json(ROOT / step["table"])["payload"]
        assert step["tolerance_met"] == "True"
        assert float(step["window_bound_J"]) <= float(step["requested_window_budget_J"])
        close(float(step["requested_window_budget_J"]), summary["initial_work_budget_J"] / 2 ** int(step["stage"]), 0.0)
    for relative, table in tables.items():
        specimen = table["metadata"]["provenance"]["specimen"]
        x, f = source_values[specimen]
        assert table["x"] == [x[i] for i in table["indices"]]
        assert table["force"] == [f[i] for i in table["indices"]]
        identity = hashlib.sha256(b"workcert-reference-float64-le-v1\0")
        identity.update(struct.pack("<Q", len(x)))
        identity.update(struct.pack("<%dd" % len(x), *x))
        identity.update(struct.pack("<%dd" % len(f), *f))
        assert identity.hexdigest() == table["certificate"]["reference_sha256"]
        wrapped = read_json(ROOT / relative)
        canonical = json.dumps(table, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf8")
        assert hashlib.sha256(canonical).hexdigest() == wrapped["payload_sha256"]
        expected = certificate(source_refs[specimen], table)
        for field, value in expected.items():
            close(table["certificate"][field], value, 1e-10 if field == "delta" else 1e-8)
    query_rows = csv_rows(OUT / "configuration_queries.csv")
    true_groups = {}
    for stroke in (10.0, 20.0, 30.0, 40.0):
        collected = defaultdict(list)
        for item in manifests:
            specimen = item["specimen"]
            group = "STWC" if specimen.startswith("STWC-") else "N-SCMC" if specimen.startswith("N-SCMC-") else specimen
            collected[group].append(float(source_refs[specimen].work(stroke)) / masses[specimen])
        true_groups[stroke] = {group: statistics.mean(values) for group, values in collected.items()}
    for row in query_rows:
        stroke = float(row["stroke_mm"])
        computed = group_records(initial if row["stage"] == "initial" else final, masses, tables, stroke)[row["configuration"]]
        for field in ("SEA_kJ_kg", "SEA_lower_kJ_kg", "SEA_upper_kJ_kg"):
            close(float(row[field]), computed[field], 1e-10)
        truth = true_groups[stroke][row["configuration"]]
        close(float(row["reference_SEA_kJ_kg"]), truth, 1e-10)
        assert float(row["SEA_lower_kJ_kg"]) - 1e-10 <= truth <= float(row["SEA_upper_kJ_kg"]) + 1e-10
    adjacent_total = separated = all_total = all_separated = 0
    for stroke in (10.0, 20.0, 30.0, 40.0):
        intervals = group_records(initial, masses, tables, stroke)
        ordered = sorted(intervals, key=lambda group: (true_groups[stroke][group], group))
        adjacent = [(lower, higher) for lower, higher in zip(ordered, ordered[1:])]
        count = sum(intervals[higher]["SEA_lower_kJ_kg"] > intervals[lower]["SEA_upper_kJ_kg"] for lower, higher in adjacent)
        count_all = sum(intervals[a]["SEA_lower_kJ_kg"] > intervals[b]["SEA_upper_kJ_kg"] or intervals[b]["SEA_lower_kJ_kg"] > intervals[a]["SEA_upper_kJ_kg"]
                        for i, a in enumerate(ordered) for b in ordered[i + 1:])
        report = next(v for v in summary["per_stroke_difficulty"] if v["stroke_mm"] == stroke)
        assert report["adjacent_separated"] == count and report["all_pairs_separated"] == count_all
        adjacent_total += len(adjacent)
        separated += count
        all_total += 861
        all_separated += count_all
    assert (adjacent_total, separated, all_total, all_separated) == (
        summary["initial_adjacent_pairs"], summary["initial_adjacent_separated"],
        summary["initial_all_pairs"], summary["initial_all_pairs_separated"])
    current = dict(initial)
    for stage in trace:
        configurations = stage["consumer_received_configurations"]
        calculated = group_records(current, masses, tables, stage["stroke_mm"])
        for row in configurations:
            for field in ("SEA_kJ_kg", "SEA_lower_kJ_kg", "SEA_upper_kJ_kg"):
                close(row[field], calculated[row["configuration"]][field], 1e-10)
        best = max(configurations, key=lambda row: (row["SEA_lower_kJ_kg"], row["configuration"]))
        contenders = sorted(row["configuration"] for row in configurations
                            if row["configuration"] != best["configuration"] and row["SEA_upper_kJ_kg"] >= best["SEA_lower_kJ_kg"])
        assert stage["leader"] == best["configuration"] and stage["challengers"] == contenders
        assert stage["winner_separated"] == (not contenders) and not stage["consumer_read_dense_references"]
        requests = sorted(set([best["configuration"]] + contenders)) if contenders else []
        assert stage["request_configurations"] == requests
        next_steps = [row for row in steps if int(row["stage"]) == stage["stage"] + 1]
        for row in next_steps:
            assert row["configuration"] in requests
            assert sha(ROOT / current[row["specimen"]]) == row["previous_table_sha256"]
            current[row["specimen"]] = row["table"]
    assert current == final and trace[-1]["winner_separated"]
    assert trace[-1]["leader"] == max(true_groups[20.0], key=true_groups[20.0].get)
    mass_rounding = read_json(OUT / "mass_rounding.json")
    assert mass_rounding["schema"] == "workcert.mass-rounding-sensitivity/1.0"
    assert mass_rounding["stroke_mm"] == 20.0
    assert mass_rounding["leader_at_reported_masses"] == "26" and mass_rounding["challenger"] == "35"
    close(mass_rounding["mass_half_width_g"], 0.05, 0.0)
    assert mass_rounding["source_workbook_sha256"] == sha(ROOT / "data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx")
    half_width = Decimal("0.05")
    rounded_leads = {}
    for stage in ("initial", "refined", "dense_reference"):
        stage_result = mass_rounding["stages"][stage]
        calculated_intervals = []
        assert [r["specimen"] for r in stage_result["records"]] == ["26", "35"]
        for record in stage_result["records"]:
            specimen = record["specimen"]
            item = next(v for v in manifests if v["specimen"] == specimen)
            assert mass_rounding["source_csv_sha256"][specimen] == sha(ROOT / item["source_csv"])
            mass = Decimal.from_float(masses[specimen])
            close(record["reported_mass_g"], mass, 0.0)
            for actual, expected in zip(record["mass_interval_g"], (mass - half_width, mass + half_width)):
                close(actual, expected, 1e-12)
            if stage == "dense_reference":
                work = source_refs[specimen].work(20.0)
                error = Decimal(0)
                points = len(source_refs[specimen].x)
            else:
                table = tables[(initial if stage == "initial" else final)[specimen]]
                work = Reference(table["x"], table["force"]).work(20.0)
                error = certificate(source_refs[specimen], table)["prefix"]
                points = len(table["x"])
            assert record["retained_points"] == points
            close(record["work_estimate_J"], work, 1e-10)
            close(record["prefix_bound_J"], error, 1e-10)
            work_interval = (work - error, work + error)
            reported_interval = tuple(v / mass for v in work_interval)
            rounded_interval = ((work - error) / (mass + half_width),
                                (work + error) / (mass - half_width))
            for field, expected in (("work_interval_J", work_interval),
                                    ("reported_mass_SEA_interval_kJ_kg", reported_interval),
                                    ("rounded_mass_SEA_interval_kJ_kg", rounded_interval)):
                for actual, value in zip(record[field], expected):
                    close(actual, value, 1e-10)
            calculated_intervals.append((reported_interval, rounded_interval))
        reported_lead = calculated_intervals[0][0][0] - calculated_intervals[1][0][1]
        rounded_lead = calculated_intervals[0][1][0] - calculated_intervals[1][1][1]
        close(stage_result["reported_mass_worst_lead_kJ_kg"], reported_lead, 1e-10)
        close(stage_result["rounded_mass_worst_lead_kJ_kg"], rounded_lead, 1e-10)
        assert stage_result["reported_mass_order_separated"] == (reported_lead > 0)
        assert stage_result["rounded_mass_order_separated"] == (rounded_lead > 0)
        rounded_leads[stage] = rounded_lead
    assert mass_rounding["stages"]["refined"]["reported_mass_order_separated"]
    assert all(value < 0 for value in rounded_leads.values())
    inverse = read_json(OUT / "energy_to_stroke.json")
    source = source_refs["STWC-1"]
    table = tables[final["STWC-1"]]
    reduced = Reference(table["x"], table["force"])
    for key, target in (("stroke_lower_mm", inverse["energy_target_J"] - table["certificate"]["prefix"]),
                        ("table_inverse_mm", inverse["energy_target_J"]),
                        ("stroke_upper_mm", inverse["energy_target_J"] + table["certificate"]["prefix"])):
        close(reduced.work(inverse[key]), target, 1e-10)
    assert source.work(inverse["stroke_lower_mm"]) <= Decimal.from_float(inverse["energy_target_J"])
    assert source.work(inverse["stroke_upper_mm"]) >= Decimal.from_float(inverse["energy_target_J"])
    close(source.work(inverse["reference_inverse_mm"]), inverse["energy_target_J"], 1e-10)
    lower, upper = inverse["loading_interval_mm"]
    retained_nodes = [lower] + [v for v in table["x"] if lower < v < upper] + [upper]
    source_nodes = [lower] + [v for v in source.x_float if lower < v < upper] + [upper]
    retained_minimum = min(reduced.force_at(v) for v in retained_nodes)
    source_minimum = min(source.force_at(v) for v in source_nodes)
    close(inverse["source_force_lower_bound_kN"], retained_minimum - Decimal.from_float(table["certificate"]["delta"]), 1e-10)
    close(inverse["reference_minimum_force_on_loading_interval_kN"], source_minimum, 1e-10)
    assert source_minimum > 0 and retained_minimum > 0 and inverse["source_force_lower_bound_kN"] > 0
    metric_source = ROOT / "validation/results_v02/selector_metrics.csv"
    dp_source = ROOT / "validation/results_v02/optimality_gaps.csv"
    sensitivity = read_json(OUT / "weighting_sensitivity.json")
    assert sensitivity["selector_metrics_sha256"] == sha(metric_source)
    assert sensitivity["optimality_gaps_sha256"] == sha(dp_source)
    metrics = [row for row in csv_rows(metric_source) if int(row["budget"]) == 33 and row["method"] != "work_only"]
    cohorts = Counter(row["dataset"] for row in metrics if row["method"] == "work")
    for row in csv_rows(OUT / "weighting_sensitivity.csv"):
        selected = [value for value in metrics if value["method"] == row["method"]]
        values = [float(value[row["metric"]]) for value in selected]
        weights = [weight(value, row["weighting"], cohorts) for value in selected]
        close(float(row["weighted_median_percent"]), weighted_median(values, weights), 1e-12)
    dp_rows = [row for row in csv_rows(dp_source) if int(row["budget"]) == 33]
    dp_cohorts = Counter(row["dataset"] for row in dp_rows if row["method"] == "work" and row["objective"] == "eta")
    for row in csv_rows(OUT / "dp_weighting_sensitivity.csv"):
        selected = [value for value in dp_rows if value["objective"] == row["objective"] and value["method"] == row["method"]]
        values = [float(value["ratio"]) for value in selected]
        close(float(row["weighted_median_ratio"]), weighted_median(values, [weight(value, row["weighting"], dp_cohorts) for value in selected]), 1e-12)
    for relative, digest in summary["supporting_inputs"].items():
        assert sha(ROOT / relative) == digest
    report = {"status": "PASS", "verification_script_sha256": sha(__file__),
              "workflow_core_sha256": summary["core_sha256"], "workcert_imported": False,
              "arithmetic": "Decimal, precision 80, initialized from exact binary64 coordinates, forces and masses",
              "unique_tables_reintegrated": len(tables), "certificate_fields_per_table": 9,
              "configuration_queries_checked": len(query_rows), "scalar_comparisons": CHECKS,
              "maximum_absolute_comparison_difference": MAXIMUM_DIFFERENCE,
              "adjacent_separation": [separated, adjacent_total], "all_pair_separation": [all_separated, all_total],
              "consumer_overlap_rule_verified": True, "reference_truth_used_in_request_rule": False,
              "energy_inverse_reference_covered": True,
              "mass_rounding_stages_independently_checked": 3,
              "mass_rounding_dense_reference_worst_lead_kJ_kg": float(rounded_leads["dense_reference"]),
              "source_or_result_files_rewritten": False}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    with localcontext() as context:
        context.prec = 80
        main()
