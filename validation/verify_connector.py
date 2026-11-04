"""Check a frozen connector export without rebuilding or replacing any files."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software/src"))
from workcert import ReducedResponse
from connector_exchange import primitive, reference_errors


def main():
    out = ROOT / "validation/connector_results"
    table = ReducedResponse.load(out / "STWC1_table.json")
    reference = np.loadtxt(ROOT / "data/prepared/PLA_STWC-1.csv", delimiter=",", skiprows=1)
    assert table.verify_reference(reference[:, 0], reference[:, 1])
    rows = [line for line in (out / "STWC1_connector.inp").read_text().splitlines() if not line.startswith("*")]
    force, x = np.asarray([[float(v) for v in row.split(",")] for row in rows]).T
    np.testing.assert_array_equal(x, table.x)
    np.testing.assert_array_equal(force, table.force)
    report = json.loads((out / "verification.json").read_text())
    for key, actual in reference_errors(reference, x, force).items():
        assert np.isclose(actual, getattr(table.certificate, key), rtol=0., atol=1e-10)
    queries = np.asarray(report["strokes_mm"])
    np.testing.assert_allclose(primitive(x, force, queries), table.work(queries), rtol=0., atol=1e-10)
    np.testing.assert_allclose(report["consumer_EA_J"], table.work(queries), rtol=0., atol=1e-10)
    print(json.dumps({"status": "PASS", "retained_rows": len(x), "queries": len(queries),
                      "writes_source_files": False}))


if __name__ == "__main__":
    main()
