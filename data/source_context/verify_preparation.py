"""Audit source bytes and re-extract the 24 fixed steel/EDAH references."""
from pathlib import Path
import csv
import hashlib
import json

import numpy as np

ROOT = Path(__file__).resolve().parent


def numeric_csv(path, encoding="utf-8-sig", skiprows=0):
    lines = path.read_text(encoding=encoding).splitlines()[skiprows:]
    lines = [line for line in lines if line.strip() and not line.startswith("#")]
    delimiter = ";" if ";" in lines[0] else ","
    return np.asarray([[float(v) for v in row[:3]]
                       for row in csv.reader(lines, delimiter=delimiter)], dtype=float)


def prepared_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return np.asarray([[float(r["stroke_mm"]), float(r["force_kN"])]
                           for r in csv.DictReader(stream)], dtype=float)


def main():
    manifest = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf8"))
    for record in manifest["files"]:
        blob = (ROOT / record["file"]).read_bytes()
        assert len(blob) == record["bytes"]
        assert hashlib.sha256(blob).hexdigest() == record["sha256"]
        if "expected_repository_sha256" in record:
            assert hashlib.sha256(blob).hexdigest() == record["expected_repository_sha256"]
        if "expected_repository_md5" in record:
            assert hashlib.md5(blob).hexdigest() == record["expected_repository_md5"]
    inventory = json.loads((ROOT / "preparation_inventory.json").read_text(encoding="utf8"))
    maxima = {"displacement_mm": 0., "force_kN": 0.}
    nodes = 0
    for record in inventory["records"]:
        if not record["included"]:
            continue
        source = ROOT / record["source_file"]
        target = ROOT / record["reference_input"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == record["reference_input_sha256"]
        if record["dataset_doi"].startswith("10.17632"):
            raw = numeric_csv(source)
            force, travel = -raw[:, 0], -raw[:, 1]
            end = int(np.argmax(travel))
            assert end == record["loading_end_row_zero_based"]
            good = force[:end + 1] >= record["contact_threshold_kN"]
            start = int(np.flatnonzero(good[:-2] & good[1:-1] & good[2:])[0])
            assert start == record["contact_row_zero_based"]
            x0, f0 = travel[start:end + 1] - travel[start], force[start:end + 1]
            selected = [0]
            maximum = x0[0]
            for i in range(1, len(x0)):
                if x0[i] > maximum + record["record_high_tolerance_mm"]:
                    selected.append(i)
                    maximum = x0[i]
            x, f = x0[selected], f0[selected]
            assert np.count_nonzero(f < 0) == record["negative_clipped_loading_nodes"] == 0
            endpoint = record["endpoint_mm"]
            last = int(np.searchsorted(x, endpoint))
            x, f = np.r_[x[:last], endpoint], np.r_[f[:last], np.interp(endpoint, x, f)]
        else:
            raw = numeric_csv(source, encoding=record["encoding"], skiprows=3)
            x, f = raw[:, 2] - raw[0, 2], raw[:, 1] / 1000.
            assert np.count_nonzero(f < 0) == 60
        archived = prepared_csv(target)
        assert len(x) == len(archived)
        values = np.column_stack((x, f))
        scale = max(1., float(np.max(np.abs(archived))))
        allowed = 512 * np.finfo(float).eps * scale
        assert np.max(np.abs(values - archived)) <= allowed, record["source_file"]
        maxima["displacement_mm"] = max(maxima["displacement_mm"], float(np.max(np.abs(x - archived[:, 0]))))
        maxima["force_kN"] = max(maxima["force_kN"], float(np.max(np.abs(f - archived[:, 1]))))
        nodes += len(x)
    return {"status": "PASS", "source_and_metadata_files_hashed": len(manifest["files"]),
            "steel_reference_windows_reextracted": 23, "EDAH_records_reextracted": 1,
            "reextracted_nodes": nodes, "maximum_absolute_difference": maxima,
            "comparison_tolerance": "512 * float64 epsilon * max(1, maximum absolute reference value)",
            "output_policy": "Read-only audit; no benchmark reference or table overwritten"}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
