"""Hou acceptance group 6: independent paper spot checks (standard-library oracle).

This module does not import the existing workflow's integration or statistics.
Expected values come from the complete decimal CSV inputs and explicit PL
formulae below. The received JSON's indices define the fixed reconstruction.
The public client is invoked only as the system under test, never as an oracle.
"""
import bisect
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import unittest
import xml.etree.ElementTree as ET
import zipfile

from workcert import ReducedResponse
from hou_support import AcceptanceCase

ROOT = Path(os.environ.get("WORKCERT_RESEARCH_ROOT", Path(__file__).resolve().parents[2]))
RESULTS = ROOT / "validation/workflow_results_round2"
STROKES = (10.0, 20.0, 30.0, 40.0)
GROUPS = ("STWC", "N-SCMC")
# Absolute tolerances; no relative allowance and no rounding of the inputs.
WORK_ATOL = 1e-9
INDICATOR_ATOL = 1e-10
# Printed Table 2 is only a presentation check, separate from full-precision QA.
TABLE2 = {
    10.0: (50.823, 3.137, 5.082, .450, .444, .456),
    20.0: (92.904, 5.735, 4.645, .411, .408, .414),
    30.0: (138.290, 8.536, 4.610, .408, .406, .410),
    40.0: (183.262, 11.312, 4.582, .406, .404, .407),
}


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_curve(specimen):
    rows = csv_rows(ROOT / "data/prepared" / ("PLA_" + specimen + ".csv"))
    return [float(r["x_mm"]) for r in rows], [float(r["force_kN"]) for r in rows]


def scalar_force(x, f, q):
    """Direct linear interpolation with only Python scalar arithmetic."""
    if q < x[0] or q > x[-1]:
        raise ValueError("Independent oracle query outside input")
    if q == x[-1]:
        return f[-1]
    i = max(0, bisect.bisect_right(x, q) - 1)
    return f[i] + (f[i + 1] - f[i]) * (q - x[i]) / (x[i + 1] - x[i])


def scalar_integral(x, f, a, b):
    """Integral of each intersected line: f0*d + slope*d**2/2.

    This is deliberately not np.trapz/cumsum or any WorkCert helper.
    math.fsum limits error when combining many individual segment integrals.
    """
    if not x[0] <= a <= b <= x[-1]:
        raise ValueError("Independent oracle query outside input")
    terms = []
    for left, right, fl, fr in zip(x[:-1], x[1:], f[:-1], f[1:]):
        lo, hi = max(a, left), min(b, right)
        if hi <= lo:
            continue
        slope = (fr - fl) / (right - left)
        d0, d1 = lo - left, hi - left
        terms.append(fl * (d1 - d0) + slope * (d1 * d1 - d0 * d0) / 2)
    return math.fsum(terms)


def scalar_peak(x, f, q):
    return max([v for xx, v in zip(x, f) if xx <= q] + [scalar_force(x, f, q)])


def independent_prefix_error(x, f, kept):
    """Find extrema of integral(source - reduced), including residual zeros."""
    rx, rf = [x[i] for i in kept], [f[i] for i in kept]
    residual = [v - scalar_force(rx, rf, xx) for xx, v in zip(x, f)]
    cumulative, candidates = [], [0.0]
    for left, right, a, b in zip(x[:-1], x[1:], residual[:-1], residual[1:]):
        width = right - left
        start = math.fsum(cumulative)
        if a * b < 0:
            root_distance = -a * width / (b - a)
            candidates.append(start + a * root_distance / 2)
        cumulative.append((a + b) * width / 2)
        candidates.append(math.fsum(cumulative))
    return max(abs(v) for v in candidates)


def workbook_rows():
    """Read numeric XLSX cells as stored, using ZIP/XML rather than rounded CSV."""
    path = ROOT / "data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx"
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        strings = ["".join(item.itertext()) for item in
                   ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    records = {}
    for row in sheet.findall("s:sheetData/s:row", ns):
        cells = {}
        for cell in row.findall("s:c", ns):
            value = cell.find("s:v", ns)
            if value is None:
                continue
            column = "".join(c for c in cell.attrib["r"] if c.isalpha())
            cells[column] = strings[int(value.text)] if cell.get("t") == "s" else float(value.text)
        if isinstance(cells.get("B"), float):
            records[str(cells["A"])] = cells
    return records


def load_case(specimen):
    x, f = read_curve(specimen)
    path = RESULTS / "tables" / (specimen + ".json")
    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
    kept = payload["indices"]
    rx, rf = [x[i] for i in kept], [f[i] for i in kept]
    # All independent calculations are completed before invoking the receiver.
    ep = independent_prefix_error(x, f, kept)
    return x, f, kept, rx, rf, ep, ReducedResponse.load(path)


def client_query(table, mass, strokes):
    path = ROOT / "examples/query_exchange.py"
    spec = importlib.util.spec_from_file_location("hou_checked_consumer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.query_metrics(table, mass, strokes)


class HouPaperAcceptance(AcceptanceCase):
    """Four tests cover Table 2, specimen 05, all eight repeat/stroke cases."""

    def test_stwc1_table2_full_precision_and_printed(self):
        x, f, kept, rx, rf, ep, table = load_case("STWC-1")
        mass = workbook_rows()["STWC-1"]["B"]
        expected = {}
        for q in STROKES:
            w = scalar_integral(rx, rf, x[0], q)
            peak = scalar_peak(x, f, q)
            expected[q] = {"EA_J": w, "SEA_kJ_kg": w / mass,
                           "MCF_kN": w / q, "PCF_kN": peak, "CFE": w / q / peak,
                           "EA_lower_J": w - ep, "EA_upper_J": w + ep,
                           "SEA_lower_kJ_kg": (w - ep) / mass,
                           "SEA_upper_kJ_kg": (w + ep) / mass,
                           "MCF_lower_kN": (w - ep) / q,
                           "MCF_upper_kN": (w + ep) / q,
                           "PCF_lower_kN": peak, "PCF_upper_kN": peak,
                           "CFE_lower": (w - ep) / q / peak,
                           "CFE_upper": (w + ep) / q / peak}
        actual = {r["stroke_mm"]: r for r in client_query(table, mass, STROKES)}
        saved = {float(r["stroke_mm"]): r for r in csv_rows(RESULTS / "queries.csv")
                 if r["specimen"] == "STWC-1"}
        self.check_true("STWC-1 source verification", table.verify_reference(x, f))
        self.check("STWC-1 independent Ep", ep, table.certificate.prefix, atol=WORK_ATOL)
        self.check("STWC-1 measured mass g", 16.2, mass)
        for q in STROKES:
            with self.subTest(stroke=q):
                label = "STWC-1@%g" % q
                truth = scalar_integral(x, f, x[0], q)
                self.check(label + " dense EA archived", truth, float(saved[q]["reference_EA_J"]), atol=WORK_ATOL)
                for key, value in expected[q].items():
                    atol = WORK_ATOL if key.startswith("EA") else INDICATOR_ATOL
                    self.check(label + " client " + key, value, actual[q][key], atol=atol)
                    self.check(label + " archived " + key, value, float(saved[q][key]), atol=atol)
                self.check_true(label + " dense EA enclosed", actual[q]["EA_lower_J"] <= truth <= actual[q]["EA_upper_J"],
                                actual=[actual[q]["EA_lower_J"], truth, actual[q]["EA_upper_J"]])
                printed_keys = ("EA_J", "SEA_kJ_kg", "MCF_kN", "CFE", "CFE_lower", "CFE_upper")
                for key, printed in zip(printed_keys, TABLE2[q]):
                    self.check(label + " Table 2 rounded " + key, expected[q][key], printed, atol=.0005)
                for a, b in ((0.0, q), (q - 10.0, q)):
                    self.check(label + " window[%g,%g]" % (a, b), scalar_integral(rx, rf, a, b),
                               table.window_work(a, b), atol=WORK_ATOL)

    def test_specimen05_nominal_and_archived_endpoint(self):
        x, f, kept, rx, rf, ep, table = load_case("05")
        source = workbook_rows()["05"]
        nominal, endpoint = source["C"], x[-1]
        wn = scalar_integral(x, f, x[0], nominal)
        we = scalar_integral(x, f, x[0], endpoint)
        tail = scalar_integral(x, f, nominal, endpoint)
        published = source["E"] * 1000  # Workbook EA in kJ, native mm*kN = J.
        saved = next(r for r in csv_rows(RESULTS / "published_indicator_comparison.csv") if r["specimen"] == "05")
        self.check_true("05 source verification", table.verify_reference(x, f))
        self.check("05 nominal stroke mm", 50., nominal)
        self.check("05 archived endpoint mm", 50.009, endpoint)
        self.check("05 archived nominal EA", wn, float(saved["source_PL_EA_J"]), atol=WORK_ATOL)
        self.check("05 workbook EA equals endpoint integral", we, published, atol=WORK_ATOL)
        self.check("05 discrepancy equals last 0.009 mm work", tail, published - wn, atol=WORK_ATOL)
        self.check("05 endpoint minus nominal", tail, we - wn, atol=WORK_ATOL)
        self.check_true("05 nominal and endpoint genuinely differ", abs(published - wn) > .06,
                        actual=published - wn)
        self.check("05 printed nominal EA", wn, 290.800436, atol=5e-7)
        self.check("05 printed endpoint EA", we, 290.865173, atol=5e-7)
        self.check("05 independent Ep", ep, table.certificate.prefix, atol=WORK_ATOL)
        for q in (nominal, endpoint):
            expected = scalar_integral(rx, rf, x[0], q)
            self.check("05 reduced work@%.3f" % q, expected, table.work(q), atol=WORK_ATOL)
            self.check_true("05 reference covered@%.3f" % q,
                            abs(scalar_integral(x, f, x[0], q) - table.work(q)) <= ep + WORK_ATOL)

    def test_triplicate_arithmetic_means_and_sample_sd(self):
        masses = workbook_rows()
        scatter = {(r["configuration"], float(r["stroke_mm"])): r
                   for r in csv_rows(RESULTS / "repeat_scatter.csv")}
        configuration = {(r["configuration"], float(r["stroke_mm"])): r
                         for r in csv_rows(RESULTS / "configuration_queries.csv")}
        for group in GROUPS:
            cases = [(name, load_case(name)) for name in (group + "-" + str(i) for i in (1, 2, 3))]
            for q in STROKES:
                with self.subTest(group=group, stroke=q):
                    label = "%s@%g" % (group, q)
                    ea = [scalar_integral(c[0], c[1], c[0][0], q) for _, c in cases]
                    sea = [w / masses[name]["B"] for (name, _), w in zip(cases, ea)]
                    expected = {"EA_mean_J": statistics.mean(ea), "EA_sample_SD_J": statistics.stdev(ea),
                                "SEA_mean_kJ_kg": statistics.mean(sea), "SEA_sample_SD_kJ_kg": statistics.stdev(sea)}
                    for key, value in expected.items():
                        self.check(label + " " + key, value, float(scatter[group, q][key]), atol=WORK_ATOL)
                    self.check(label + " configuration SEA mean", statistics.mean(sea),
                               float(configuration[group, q]["reference_SEA_kJ_kg"]), atol=INDICATOR_ATOL)
                    self.check(label + " configuration SEA sample SD", statistics.stdev(sea),
                               float(configuration[group, q]["sample_SD_SEA_kJ_kg"]), atol=INDICATOR_ATOL)
                    self.check(label + " replicate count", 3, float(scatter[group, q]["n"]))
                    max_ep = max(c[5] for _, c in cases)
                    self.check(label + " maximum independent Ep", max_ep, float(scatter[group, q]["maximum_prefix_bound_J"]), atol=WORK_ATOL)
                    self.check_true(label + " reported Ep below observed sample SD", max_ep < statistics.stdev(ea),
                                    actual=[max_ep, statistics.stdev(ea)])

    def test_triplicate_mean_intervals_average_endpoints(self):
        masses = workbook_rows()
        rows = {(r["configuration"], float(r["stroke_mm"])): r
                for r in csv_rows(RESULTS / "configuration_queries.csv")}
        for group in GROUPS:
            cases = [(name, load_case(name)) for name in (group + "-" + str(i) for i in (1, 2, 3))]
            for q in STROKES:
                with self.subTest(group=group, stroke=q):
                    label = "%s@%g mean interval" % (group, q)
                    centers, lowers, uppers, truths = [], [], [], []
                    actual_lowers, actual_uppers = [], []
                    for name, (x, f, kept, rx, rf, ep, table) in cases:
                        mass = masses[name]["B"]
                        w = scalar_integral(rx, rf, x[0], q)
                        centers.append(w / mass)
                        lowers.append((w - ep) / mass)
                        uppers.append((w + ep) / mass)
                        truths.append(scalar_integral(x, f, x[0], q) / mass)
                        actual = client_query(table, mass, [q])[0]
                        actual_lowers.append(actual["SEA_lower_kJ_kg"])
                        actual_uppers.append(actual["SEA_upper_kJ_kg"])
                    lo, hi = statistics.mean(lowers), statistics.mean(uppers)
                    center = statistics.mean(centers)
                    actual = rows[group, q]
                    self.check(label + " reduced mean", center, float(actual["reduced_SEA_kJ_kg"]), atol=INDICATOR_ATOL)
                    self.check(label + " lower archived", lo, float(actual["SEA_lower_kJ_kg"]), atol=INDICATOR_ATOL)
                    self.check(label + " upper archived", hi, float(actual["SEA_upper_kJ_kg"]), atol=INDICATOR_ATOL)
                    self.check(label + " lower client", lo, statistics.mean(actual_lowers), atol=INDICATOR_ATOL)
                    self.check(label + " upper client", hi, statistics.mean(actual_uppers), atol=INDICATOR_ATOL)
                    self.check_true(label + " encloses dense mean", lo <= statistics.mean(truths) <= hi,
                                    actual=[lo, statistics.mean(truths), hi])
                    halfwidth = (hi - lo) / 2
                    recorded_halfwidth = (float(actual["SEA_upper_kJ_kg"]) - float(actual["SEA_lower_kJ_kg"])) / 2
                    self.check(label + " deterministic halfwidth", halfwidth, recorded_halfwidth, atol=INDICATOR_ATOL)
                    self.check_true(label + " does not divide error bound by sqrt(n)",
                                    abs(recorded_halfwidth - halfwidth / math.sqrt(3)) > 1e-4,
                                    actual=[recorded_halfwidth, halfwidth / math.sqrt(3)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
