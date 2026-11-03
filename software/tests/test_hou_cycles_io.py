"""Hou acceptance groups 4/5: independent chronological quadrature and I/O.

Expected numbers are derived in qa/hou_acceptance/CYCLES_IO_DERIVATIONS.txt.
Only the functions under test use WorkCert; the oracle uses Fraction arithmetic.
"""
from collections import Counter
from fractions import Fraction as Q
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

from workcert import ReducedResponse, from_indices, split_monotone_branches
from hou_support import AcceptanceCase


RESEARCH_ROOT = Path(os.environ.get("WORKCERT_RESEARCH_ROOT", Path(__file__).resolve().parents[2]))
PATH_X = [0, 1, 2, 3, 3, 2, 1, 0, 0, 1, 2]
PATH_F = [0, 2, -1, 0, 2, 4, -2, 2, -1, 0, -1]
SAVE_X = [0, 1, 2, 4]
SAVE_F = [1, 4, -2, 3]
SAVE_IDS = [0, 2, 3]


def exact_directed_work(x, force, q=None):
    """Integrate consecutive chronological edges, clipping the last at q.

    This helper is only used on one monotone chronological branch. Repeated x
    edges integrate to zero. It neither sorts coordinates nor calls WorkCert.
    """
    total = Q(0)
    if q is not None and Q(q) == Q(x[0]):
        return total
    for a, b, fa, fb in zip(x, x[1:], force, force[1:]):
        a, b, fa, fb = map(Q, (a, b, fa, fb))
        if a == b:
            continue
        end = b
        stops = q is not None and min(a, b) <= Q(q) <= max(a, b)
        if stops:
            end = Q(q)
        width = end - a
        total += fa * width + (fb - fa) * width * width / (2 * (b - a))
        if stops:
            return total
    return total


def load_composer():
    path = RESEARCH_ROOT / "examples" / "compose_branch_errors.py"
    spec = importlib.util.spec_from_file_location("hou_test_composer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compose_branch_errors


def source_records(series):
    """Convert returned branch certificates to the documented consumer input."""
    records = []
    for branch in series.branches:
        table = from_indices(branch.x, branch.force, [0, len(branch.x) - 1])
        c = table.certificate
        records.append({"kind": "branch", "direction": branch.direction,
                        "source_start": int(min(branch.source_indices)),
                        "source_end": int(max(branch.source_indices)),
                        "terminal": c.signed_terminal_error,
                        "minimum": c.min_cumulative_error,
                        "maximum": c.max_cumulative_error})
    for event in series.events:
        records.append({"kind": "zero_work_event", "direction": 0,
                        "source_start": event.source_start, "source_end": event.source_end,
                        "terminal": 0.0, "minimum": 0.0, "maximum": 0.0})
    return sorted(records, key=lambda row: row["source_start"])


class HouCyclesAndPersistence(AcceptanceCase):
    def test_cyclic_edges_are_covered_once(self):
        series = split_monotone_branches(PATH_X, PATH_F)
        self.check("cyclic.source_points", 11, series.source_points, atol=0)
        self.check("cyclic.branch_count", 3, len(series.branches), atol=0)
        self.check("cyclic.dwell_count", 2, len(series.events), atol=0)
        expected_ids = ([0, 1, 2, 3], [7, 6, 5, 4], [8, 9, 10])
        covered = []
        for i, (branch, ids) in enumerate(zip(series.branches, expected_ids)):
            actual_ids = list(map(int, branch.source_indices))
            self.check_true("cyclic.branch%d.source_indices" % i, actual_ids == ids,
                            expected=str(ids), actual=str(actual_ids))
            self.check("cyclic.branch%d.direction" % i, (1, -1, 1)[i], branch.direction, atol=0)
            self.check("cyclic.branch%d.start_x" % i, (0, 3, 0)[i], branch.start_x)
            self.check("cyclic.branch%d.end_x" % i, (3, 0, 2)[i], branch.end_x)
            chronological = actual_ids if branch.direction > 0 else actual_ids[::-1]
            covered.extend(zip(chronological, chronological[1:]))
        for i, event in enumerate(series.events):
            expected_pair = ((3, 4), (7, 8))[i]
            pair = (event.source_start, event.source_end)
            self.check_true("cyclic.event%d.source_pair" % i, pair == expected_pair,
                            expected=str(expected_pair), actual=str(pair))
            self.check("cyclic.event%d.displacement" % i, (3, 0)[i], event.displacement)
            self.check("cyclic.event%d.start_force" % i, (0, 2)[i], event.start_force)
            self.check("cyclic.event%d.end_force" % i, (2, -1)[i], event.end_force)
            covered.append(pair)
        counts = Counter(covered)
        for i in range(len(PATH_X) - 1):
            self.check("cyclic.edge_%d_%d.count" % (i, i + 1), 1, counts[(i, i + 1)], atol=0)
        self.check("cyclic.total_edge_count", 10, len(covered), atol=0)
        self.check("cyclic.reference_work", Q(-4), series.reference_work)

    def test_signed_branch_and_interior_work(self):
        series = split_monotone_branches(PATH_X, PATH_F)
        ranges = ((0, 3), (4, 7), (8, 10))
        queries = ((Q(0), Q(1, 2), Q(5, 3), Q(3)),
                   (Q(3), Q(5, 2), Q(5, 3), Q(0)),
                   (Q(0), Q(1, 2), Q(3, 2), Q(2)))
        reduced_total = 0.0
        for i, (branch, (first, last), qs) in enumerate(zip(series.branches, ranges, queries)):
            raw_x, raw_f = PATH_X[first:last + 1], PATH_F[first:last + 1]
            full = from_indices(branch.x, branch.force, list(range(len(branch.x))))
            reduced = from_indices(branch.x, branch.force, [0, len(branch.x) - 1])
            for q in qs:
                expected_full = exact_directed_work(raw_x, raw_f, q)
                expected_reduced = exact_directed_work([raw_x[0], raw_x[-1]],
                                                       [raw_f[0], raw_f[-1]], q)
                self.check("cyclic.branch%d.full_work@%s" % (i, q), expected_full,
                           branch.directed_work(full, float(q)))
                self.check("cyclic.branch%d.reduced_work@%s" % (i, q), expected_reduced,
                           branch.directed_work(reduced, float(q)))
            expected_end = exact_directed_work([raw_x[0], raw_x[-1]], [raw_f[0], raw_f[-1]])
            reduced_total += branch.directed_work(reduced)
            self.check("cyclic.branch%d.default_end_work" % i, expected_end,
                       branch.directed_work(reduced))
        self.check("cyclic.reduced_total", Q(-8), reduced_total)

    def test_descending_error_and_chronological_composition(self):
        series = split_monotone_branches(PATH_X, PATH_F)
        branch = series.branches[1]
        table = from_indices(branch.x, branch.force, [0, 3])
        c = table.certificate
        for field, expected in {"eta": Q(14, 3), "xi": Q(10, 3), "prefix": Q(10, 3),
                                "window": Q(10, 3), "delta": Q(4),
                                "signed_terminal_error": Q(-2), "min_cumulative_error": Q(-10, 3),
                                "max_cumulative_error": Q(0)}.items():
            self.check("descending.ascending_metadata." + field, expected, getattr(c, field))
        for q, expected in ((Q(3), Q(0)), (Q(5, 3), Q(-4, 3)), (Q(0), Q(2))):
            source_work = exact_directed_work(PATH_X[4:8], PATH_F[4:8], q)
            self.check("descending.directed_error@%s" % q, expected,
                       float(source_work) - branch.directed_work(table, float(q)))
        # This is the application consumer under test, not an oracle.
        actual = load_composer()(source_records(series), source_points=11)
        expected = {"signed_terminal_error": Q(4), "minimum_cumulative_error": Q(-1, 3),
                    "maximum_cumulative_error": Q(4), "prefix": Q(4), "window": Q(13, 3),
                    "branches": 3, "zero_work_events": 2}
        for field, value in expected.items():
            self.check("cyclic.composed." + field, value, actual[field])

    def test_composer_rejects_missing_duplicate_or_reordered_edges(self):
        compose = load_composer()
        records = source_records(split_monotone_branches(PATH_X, PATH_F))
        self.expect_rejected("cyclic.composition.missing_edge", lambda: compose(records[:1] + records[2:], source_points=11))
        self.expect_rejected("cyclic.composition.duplicate_edge", lambda: compose(records[:2] + records[1:], source_points=11))
        self.expect_rejected("cyclic.composition.reordered_edges", lambda: compose(records[::-1], source_points=11))

    def test_pure_dwell_and_strict_duplicate_policy(self):
        x, force = [7, 7, 7, 7], [-3, 5, -2, 9]
        series = split_monotone_branches(x, force)
        self.check("dwell.only.reference_work", 0, series.reference_work, atol=0)
        self.check("dwell.only.branches", 0, len(series.branches), atol=0)
        self.check("dwell.only.events", 3, len(series.events), atol=0)
        for i, event in enumerate(series.events):
            self.check("dwell.only.event%d.start" % i, i, event.source_start, atol=0)
            self.check("dwell.only.event%d.end" % i, i + 1, event.source_end, atol=0)
            self.check("dwell.only.event%d.start_force" % i, force[i], event.start_force, atol=0)
            self.check("dwell.only.event%d.end_force" % i, force[i + 1], event.end_force, atol=0)
        self.expect_rejected("dwell.strict_policy", lambda: split_monotone_branches(x, force, duplicate_policy="error"))

    def test_saved_response_roundtrip_against_analytic_values(self):
        original = from_indices(SAVE_X, SAVE_F, SAVE_IDS, x_unit="mm", force_unit="kN",
                                provenance={"acceptance": "Hou", "case": "signed nonuniform table"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "response.json"
            original.save(path)
            loaded = ReducedResponse.load(path)
            self.check_true("persistence.roundtrip_bytes", path.read_bytes() == loaded.to_bytes(),
                            expected="byte-identical", actual="byte-identical" if path.read_bytes() == loaded.to_bytes() else "different")
            self.check_true("persistence.roundtrip_metadata", loaded.metadata == original.metadata,
                            expected=str(original.metadata), actual=str(loaded.metadata))
            for i, expected in enumerate(SAVE_IDS):
                self.check("persistence.index%d" % i, expected, loaded.indices[i], atol=0)
                self.check("persistence.x%d" % i, SAVE_X[expected], loaded.x[i], atol=0)
                self.check("persistence.force%d" % i, SAVE_F[expected], loaded.force[i], atol=0)
            self.check_true("persistence.work_unit", loaded.work_unit == "J", expected="J", actual=loaded.work_unit)
            for q, expected in ((0, Q(0)), (1, Q(1, 4)), (2, Q(-1)), (3, Q(-7, 4)), (4, Q(0))):
                self.check("persistence.loaded_work@%s" % q, expected, loaded.work(q))
                self.check("persistence.original_work@%s" % q, expected, original.work(q))
            self.check("persistence.loaded_window[1,3]", Q(-2), loaded.window_work(1, 3))
            for field, expected in {"eta": Q(9, 2), "xi": Q(9, 2), "prefix": Q(9, 2),
                                    "window": Q(9, 2), "delta": Q(9, 2),
                                    "signed_terminal_error": Q(9, 2), "reference_work": Q(9, 2),
                                    "min_cumulative_error": Q(0), "max_cumulative_error": Q(9, 2)}.items():
                self.check("persistence.loaded_metadata." + field, expected, getattr(loaded.certificate, field))
            self.check_true("persistence.reference_verified", loaded.verify_reference(SAVE_X, SAVE_F))

    def test_source_mutation_at_discarded_point_is_rejected(self):
        original = from_indices(SAVE_X, SAVE_F, SAVE_IDS)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "response.json"
            original.save(path)
            loaded = ReducedResponse.load(path)
            changed = SAVE_F[:]
            changed[1] = 5  # Index 1 is explicitly absent from SAVE_IDS.
            self.check_true("source_mutation.retained_values_unchanged",
                            [changed[i] for i in SAVE_IDS] == [SAVE_F[i] for i in SAVE_IDS])
            self.expect_rejected("source_mutation.omitted_point", lambda: loaded.verify_reference(SAVE_X, changed))

    def test_saved_checksum_corruption_and_truncation_are_rejected(self):
        response = from_indices(SAVE_X, SAVE_F, SAVE_IDS)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            envelope = json.loads(response.to_bytes())
            envelope["payload"]["force"][0] += 1
            path.write_text(json.dumps(envelope), encoding="utf8")
            self.expect_rejected("corruption.payload_without_updated_digest", lambda: ReducedResponse.load(path))
            path.write_bytes(response.to_bytes()[:37])
            self.expect_rejected("corruption.truncated_json", lambda: ReducedResponse.load(path))

    def test_self_consistent_digest_does_not_allow_invalid_metadata(self):
        response = from_indices(SAVE_X, SAVE_F, SAVE_IDS)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad-invariant.json"
            envelope = json.loads(response.to_bytes())
            envelope["payload"]["certificate"]["prefix"] = -1
            canonical = json.dumps(envelope["payload"], sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False).encode("utf8")
            envelope["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
            path.write_text(json.dumps(envelope), encoding="utf8")
            self.expect_rejected("corruption.rehashed_negative_prefix", lambda: ReducedResponse.load(path))

    def test_illegal_source_arrays_and_indices_are_rejected(self):
        cases = (("duplicate_x", [0, 1, 1, 2], [0, 1, 2, 0], [0, 3]),
                 ("nan_x", [0, float("nan"), 2], [0, 1, 0], [0, 2]),
                 ("nan_force", [0, 1, 2], [0, float("nan"), 0], [0, 2]),
                 ("infinite_force", [0, 1, 2], [0, float("inf"), 0], [0, 2]),
                 ("duplicate_index", [0, 1, 2], [0, 1, 0], [0, 1, 1, 2]),
                 ("missing_endpoint", [0, 1, 2], [0, 1, 0], [0, 1]),
                 ("noninteger_index", [0, 1, 2], [0, 1, 0], [0.0, 2.0]))
        for label, x, force, ids in cases:
            self.expect_rejected("invalid_source." + label, lambda x=x, force=force, ids=ids: from_indices(x, force, ids))
        self.expect_rejected("invalid_path.nan_force", lambda: split_monotone_branches([0, 1, 0], [1, float("nan"), 2]))

    def test_out_of_domain_nonfinite_and_reversed_queries_are_rejected(self):
        response = from_indices(SAVE_X, SAVE_F, SAVE_IDS)
        for name in ("force_at", "work", "peak_force", "peak_bounds"):
            method = getattr(response, name)
            for label, q in (("below", -0.01), ("above", 4.01), ("nan", float("nan")), ("inf", float("inf"))):
                self.expect_rejected("invalid_query.%s.%s" % (name, label), lambda method=method, q=q: method(q))
        for label, a, b in (("below", -1, 2), ("above", 1, 5), ("nan_start", float("nan"), 2),
                            ("nan_end", 1, float("nan")), ("reversed", 3, 1)):
            self.expect_rejected("invalid_query.window." + label, lambda a=a, b=b: response.window_work(a, b))


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
