"""Prepare hash-linked benchmark inputs from the included reference archive."""
from pathlib import Path
import hashlib
import json
import re
import shutil

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs = ROOT / "data/reference_inputs"
    prepared = ROOT / "data/prepared"
    inputs.mkdir(parents=True, exist_ok=True)
    prepared.mkdir(exist_ok=True)
    records = []
    originals = sorted(inputs.glob("*.csv"), key=lambda p:
                       "external_EDAH" if p.stem == "EDAH" else p.stem.replace("metal_", "", 1))
    assert len(originals) == 24, "The 24 archived steel/EDAH reference inputs are required"
    for p in originals:
        name = "EDAH" if p.stem in ("external_EDAH", "EDAH") else p.stem if p.stem.startswith("metal_") else "metal_" + p.stem
        q = inputs / (name + ".csv")
        if p.resolve() != q.resolve():
            shutil.copy2(p, q)
        data = pd.read_csv(q, float_precision="round_trip")
        x, f = data.stroke_mm.to_numpy(), data.force_kN.to_numpy()
        records.append((name, "EDAH" if name == "EDAH" else "CX_steel", x, f,
                        q, {"prepared_source_csv_sha256": sha(p),
                            "preparation": "Existing archived prepared reference, unchanged; see source attribution",
                            "doi": "10.5281/zenodo.16399749" if name == "EDAH" else "10.17632/8bxkdw4nfw.1"}))
    manifest = json.loads((ROOT / "data/metadata/pla_download_manifest.json").read_text())
    for record in manifest["downloaded"]:
        p = ROOT / record["local_path"]
        assert sha(p) == record["sha256"]
        if not (re.fullmatch(r"\d{2}", p.stem) or p.stem.startswith(("N-SCMC-", "STWC-"))):
            continue
        workbook = openpyxl.load_workbook(p, read_only=True, data_only=True)
        assert len(workbook.worksheets) == 1
        sheet = workbook.active
        values = list(sheet.values)
        assert tuple(values[0]) == ("Displacement (mm)", "Force (kN)"), p.name
        data = np.asarray(values[1:], dtype=float)
        assert data.shape == (1000, 2)
        assert np.all(np.isfinite(data)) and np.all(np.diff(data[:, 0]) > 0)
        workbook.close()
        records.append(("PLA_" + p.stem, "PLA_plus", data[:, 0] - data[0, 0], data[:, 1],
                        p, {"doi": "10.17632/v7p6y654ft.4", "sheet": sheet.title,
                            "header": list(values[0]), "preparation": "Entire 1000-point archived curve; initial displacement subtracted; signed forces unchanged"}))
    audit = []
    for name, dataset, x, f, source, details in records:
        assert len(x) == len(f) >= 2 and np.all(np.isfinite(x)) and np.all(np.isfinite(f))
        assert np.all(np.diff(x) > 0)
        path = prepared / (name + ".csv")
        pd.DataFrame({"x_mm": x, "force_kN": f}).to_csv(path, index=False, float_format="%.17g")
        audit.append({"curve": name, "dataset": dataset, "points": len(x),
                      "start_mm": float(x[0]), "end_mm": float(x[-1]),
                      "negative_force_observations": int(np.count_nonzero(f < 0)),
                      "min_force_kN": float(np.min(f)), "peak_force_kN": float(np.max(f)),
                      "reference_work_J": float(np.trapz(f, x)),
                      "source": source.relative_to(ROOT).as_posix(), "source_sha256": sha(source),
                      "prepared": path.relative_to(ROOT).as_posix(), "prepared_sha256": sha(path),
                      "numeric_csv_parsing": "pandas float_precision=round_trip; CSV exports use 17 significant digits", **details})
    assert len(audit) == 70
    out = {"curves": audit, "total_curves": len(audit), "reference_nodes": sum(r["points"] for r in audit),
           "datasets": {d: sum(r["dataset"] == d for r in audit) for d in sorted({r["dataset"] for r in audit})},
           "new_pla_workbooks_verified": len(manifest["downloaded"]),
           "new_pla_compression_curves": 46, "pla_records_excluded": [],
           "excluded_auxiliary_workbooks": [r["filename"] for r in manifest["downloaded"]
                                             if not (re.fullmatch(r"\d{2}", Path(r["filename"]).stem)
                                                     or Path(r["filename"]).stem.startswith(("N-SCMC-", "STWC-")))],
           "interpretation": "Archived tabulated numerical references, not independent time-sample specimens; dataset summaries are descriptive"}
    (ROOT / "data/metadata/reference_audit.json").write_text(json.dumps(out, indent=2), encoding="utf8")
    pd.DataFrame(audit).drop(columns=["header"], errors="ignore").to_csv(ROOT / "data/metadata/reference_inventory.csv", index=False)
    print(json.dumps({k: out[k] for k in ("total_curves", "reference_nodes", "datasets", "new_pla_compression_curves")}, indent=2))


if __name__ == "__main__":
    main()
