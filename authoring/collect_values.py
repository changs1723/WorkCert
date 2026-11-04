"""Collect article values from frozen results and a pinned publication snapshot."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "article_inputs"


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf8"))


def main():
    frozen = INPUTS / "scientific_fingerprints.json"
    if frozen.exists():
        for name, expected in json.loads(frozen.read_text(encoding="utf8"))["inputs"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, "Frozen article input changed: " + name
    snapshot = read("article_inputs/publication_snapshot.json")
    meta = snapshot.get("metadata", snapshot)
    assert meta["version"] == "0.3.0"
    fingerprints = snapshot.get("software_fingerprints", {})
    for name, expected in fingerprints.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    core_hash = hashlib.sha256((ROOT / "software/src/workcert/core.py").read_bytes()).hexdigest()
    comparison = read("validation/results_v02/comparative_summary.json")
    decisions = read("validation/decision_results/summary.json")
    mass_rounding = read("validation/decision_results/mass_rounding.json")
    numerical = read("validation/numerical_stability_results.json")
    headline = read("validation/results/scaling/headline_repeats.json")
    workflow = read("validation/workflow_results/summary_all.json")
    pla = read("validation/workflow_results_round2/summary.json")
    assert comparison["core_sha256"] == decisions["core_sha256"] == numerical["core_sha256"] == core_hash
    assert pla["core_sha256"] == core_hash
    for row in headline["measurements"]:
        if row["implementation"] == "v0_3_stable_incremental":
            assert row["core_sha256"] == core_hash
    for path, expected in decisions["supporting_inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    for filename, key in [("selector_metrics.csv", "selector_metrics_sha256"),
                          ("optimality_gaps.csv", "optimality_gaps_sha256")]:
        assert hashlib.sha256((ROOT / "validation/results_v02" / filename).read_bytes()).hexdigest() == decisions["weighting_sensitivity"][key]
    tests = snapshot["verification"]
    assert tests["status"] == "PASS" and tests["version"] == meta["version"]
    assert tests["core_sha256"] == core_hash
    new = headline["summary"]["v0_3_stable_incremental"]
    old = headline["summary"]["v0_1_full_scan"]
    current_runs = [r for r in headline["measurements"] if r["implementation"] == "v0_3_stable_incremental"]
    assert len(current_runs) == 3 and all(r["tolerance_met"] for r in current_runs)
    values = {"metadata": meta, "verification": tests,
              "article_date": snapshot.get("article_date", "3 November 2026"),
              "software_core_sha256": core_hash,
              "point_counts": {"initial": decisions["initial_total_retained_points"],
                               "final": decisions["best_candidate_query"]["final_total_retained_points"]},
              "timing": {"old": old, "new": new, "new_points": current_runs[0]["retained_points"],
                         "new_global_evaluations": current_runs[0]["global_error_evaluations"],
                         "old_global_evaluations": [r for r in headline["measurements"] if r["implementation"] == "v0_1_full_scan"][0]["global_error_evaluations"],
                         "hardware": headline["hardware"]},
              "cyclic": workflow["cyclic_path"], "decisions": decisions,
              "mass_rounding": mass_rounding,
              "numerical_probe": numerical,
              "stopping": comparison["ALL"]["stopping_1percent"]}
    INPUTS.mkdir(exist_ok=True)
    (INPUTS / "generated_values.json").write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    scientific = ["article_inputs/publication_snapshot.json", "validation/results_v02/comparative_summary.json",
                  "validation/results_v02/dp_summary.json", "validation/decision_results/summary.json",
                  "validation/decision_results/mass_rounding.json",
                  "validation/numerical_stability_results.json", "validation/results/scaling/headline_repeats.json",
                  "validation/workflow_results/summary_all.json", "validation/workflow_results_round2/summary.json",
                  "validation/connector_results/verification.json"]
    record = {"schema": "workcert.article-inputs/1", "software_version": meta["version"],
              "core_sha256": core_hash, "inputs": {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in scientific},
              "publication_state_source": "Pinned article_inputs/publication_snapshot.json; no live QA or network state is read"}
    (INPUTS / "input_fingerprints.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    print("Collected frozen WorkCert 0.3.0 article values.")


if __name__ == "__main__":
    main()
