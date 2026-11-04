"""Run every installed-package test once, with separate historical and 0.3 phases.

The Hou tests retain their recorded authorship and per-check oracles. Newly
added tests are not represented as independently performed human review.
"""
from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import unittest

from run_hou_acceptance import AuditResult, BASELINE

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("Choose a new, empty test-output directory")
    out.mkdir(parents=True, exist_ok=True)
    import numpy
    import workcert
    import_path = Path(workcert.__file__).resolve()
    source_hashes = {p.name: {"workspace": sha(p), "installed": sha(import_path.with_name(p.name))}
                     for p in (ROOT / "software/src/workcert").glob("*.py")}
    if "site-packages" not in str(import_path) or any(v["workspace"] != v["installed"] for v in source_hashes.values()):
        raise RuntimeError("Tests must import the installed distribution matching every current runtime module")
    test_files = sorted(p.name for p in (ROOT / "software/tests").glob("test_*.py"))
    phases = {"baseline": [name for name in test_files if name in BASELINE],
              "hou_acceptance": [name for name in test_files if name.startswith("test_hou_")],
              "revision_03": [name for name in test_files if name not in BASELINE and not name.startswith("test_hou_")]}
    assert sorted(name for names in phases.values() for name in names) == test_files
    environment = {"timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "python": sys.version, "numpy": numpy.__version__, "workcert": workcert.__version__,
                   "distribution_version": importlib.metadata.version("workcert"),
                   "import_path": str(import_path), "platform": platform.platform(),
                   "source_hashes": source_hashes,
                   "test_hashes": {name: sha(ROOT / "software/tests" / name) for name in test_files}}
    (out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf8")
    os.environ["WORKCERT_RESEARCH_ROOT"] = str(ROOT)
    os.environ["HOU_RESULTS_JSONL"] = str(out / "results.jsonl")
    summary = {"status": "PASS", "tests_run": 0, "total_checks": 0, "failed_checks": 0,
               "discovery": "Every test_*.py file exactly once", "phases": {},
               "human_review_inferred": False}
    cases = []
    for phase, patterns in phases.items():
        suite = unittest.TestSuite()
        for pattern in patterns:
            suite.addTests(unittest.TestLoader().discover(str(ROOT / "software/tests"), pattern=pattern))
        if not suite.countTestCases():
            raise RuntimeError("Missing tests for phase " + phase)
        with (out / (phase + ".log")).open("w", encoding="utf8") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=AuditResult).run(suite)
        passed = result.wasSuccessful() and not result.skipped
        summary["phases"][phase] = {"tests_run": result.testsRun, "failures": len(result.failures),
                                     "errors": len(result.errors), "skipped": len(result.skipped),
                                     "status": "PASS" if passed else "FAIL"}
        summary["tests_run"] += result.testsRun
        if not passed:
            summary["status"] = "FAIL"
            for case in result.cases:
                if case["status"] != "PASS":
                    print(case["status"] + ": " + case["test"] + "\n" + case["detail"], flush=True)
        cases.extend({"phase": phase, **case} for case in result.cases)
        print(phase + ": " + json.dumps(summary["phases"][phase]), flush=True)
    with (out / "cases.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["phase", "test", "status", "detail"])
        writer.writeheader()
        writer.writerows(cases)
    if (out / "results.jsonl").exists():
        rows = [json.loads(row) for row in (out / "results.jsonl").read_text(encoding="utf8").splitlines()]
        summary["total_checks"] = len(rows)
        summary["failed_checks"] = sum(row["status"] != "PASS" for row in rows)
        if summary["failed_checks"]:
            summary["status"] = "FAIL"
        with (out / "results.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
