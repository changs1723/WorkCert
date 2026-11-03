"""Query-specific stopping, signed peaks, chronological branches and release checks."""
from pathlib import Path
import unittest
import numpy as np
from workcert import reduce_response, split_monotone_branches, ErrorMetadata, Certificate


class RevisionTests(unittest.TestCase):
    def test_selector_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError, "Choose method explicitly"):
            reduce_response([0, 1], [0, 1])
        self.assertIs(ErrorMetadata, Certificate)

    def test_sign_aware_peak_modes(self):
        x, f = np.arange(5.), [0, -10, 1, 4, 0]
        for mode, peak in [("absolute", 1), ("negative", 1), ("positive", 3)]:
            response = reduce_response(x, f, method="work", max_points=3, peak_mode=mode)
            self.assertIn(peak, response.indices)
            self.assertEqual(response.metadata["peak_mode"], mode)
        self.assertIn(1, reduce_response(x, f, method="vertical", max_points=3).indices)
        with self.assertRaises(ValueError):
            reduce_response(x, f, method="work", peak_mode="wrong")

    def test_units_are_unassigned_until_labelled(self):
        response = reduce_response([0, 1], [2, 2], method="work", max_points=2)
        self.assertEqual(response.x_unit, "unspecified")
        self.assertEqual(response.force_unit, "unspecified")
        self.assertEqual(response.work_unit, "unspecified*unspecified")
        self.assertEqual(response.work(1), 2.)

    def test_incremental_stops_at_first_verified_current_error(self):
        rng = np.random.default_rng(286)
        x = np.r_[0., np.cumsum(rng.uniform(.1, 2., 96))]
        f = rng.normal(2., 1., len(x))
        for method in ("work", "vertical"):
            hierarchy = [reduce_response(x, f, method=method, max_points=k) for k in range(3, 33)]
            for kind in ("eta", "xi", "prefix", "window"):
                tolerance = float(np.median([r.certificate.bound(kind) for r in hierarchy])) * .99
                eligible = [r for r in hierarchy if r.certificate.bound(kind) <= tolerance]
                result = reduce_response(x, f, method=method, max_points=32,
                                         tolerance=tolerance, certificate=kind)
                self.assertEqual(len(result.x), len(eligible[0].x))
                self.assertTrue(result.metadata["tolerance_met"])
                self.assertLessEqual(result.metadata["global_error_evaluations"], 2)
                self.assertTrue(result.verify_reference(x, f))

    def test_incremental_handles_cancellation_and_full_budget(self):
        rng = np.random.default_rng(93)
        for n in (17, 51, 103):
            x = np.cumsum(rng.uniform(.1, 1., n))
            f = rng.normal(size=n)
            for kind in ("eta", "xi", "prefix", "window"):
                r = reduce_response(x, f, method="work", max_points=n,
                                    tolerance=0., certificate=kind)
                self.assertTrue(r.metadata["tolerance_met"])
                self.assertEqual(r.certificate.eta, 0.)
                self.assertTrue(r.verify_reference(x, f))

    def test_closed_hysteresis_and_descending_queries(self):
        x, f = [0, 1, 2, 1, 0], [0, 2, 4, 1, 0]
        path = split_monotone_branches(x, f)
        self.assertEqual(len(path.branches), 2)
        self.assertEqual(path.branches[0].direction, 1)
        self.assertEqual(path.branches[1].direction, -1)
        work = 0.
        for branch in path.branches:
            self.assertTrue(np.all(np.diff(branch.x) > 0))
            r = reduce_response(branch.x, branch.force, method="work", max_points=len(branch.x))
            work += branch.directed_work(r)
            for array in (branch.x, branch.force, branch.source_indices):
                with self.assertRaises(ValueError):array.setflags(write=True)
        self.assertEqual(work, path.reference_work)
        self.assertEqual(work, 1.)
        branch = path.branches[1]
        r = reduce_response(branch.x, branch.force, method="work", max_points=3)
        self.assertLess(branch.directed_work(r, 1), 0.)

    def test_dwell_transitions_preserve_force_jump_and_work(self):
        x, f = [0, 1, 1, 1, 2, 1], [0, 2, 3, 4, 5, 0]
        path = split_monotone_branches(x, f)
        self.assertEqual(len(path.events), 2)
        self.assertEqual((path.events[0].start_force, path.events[0].end_force), (2., 3.))
        work = sum(b.directed_work(reduce_response(b.x, b.force, method="work", max_points=len(b.x)))
                   for b in path.branches)
        self.assertEqual(work, path.reference_work)
        with self.assertRaises(ValueError):
            split_monotone_branches(x, f, duplicate_policy="error")
        dwell = split_monotone_branches([2, 2, 2], [1, 2, 3])
        self.assertEqual(len(dwell.branches), 0)
        self.assertEqual(len(dwell.events), 2)
        self.assertEqual(dwell.reference_work, 0.)

    def test_loading_and_unloading_tables_cannot_be_confused(self):
        path=split_monotone_branches([0,1,2,1,0], [0,2,4,1,0])
        loading, unloading=path.branches
        response=reduce_response(loading.x,loading.force,method="work",max_points=3)
        with self.assertRaisesRegex(ValueError,"source"):
            unloading.directed_work(response)

    def test_branch_invalid_input_rejected(self):
        for x, f in [([0], [1]), ([0, np.inf], [1, 2]), ([0, 1], [1j, 2]), ([0, 1], [2])]:
            with self.assertRaises(ValueError):split_monotone_branches(x, f)
        with self.assertRaises(ValueError):split_monotone_branches([0, 1], [0, 2], duplicate_policy="drop")

    def test_required_license_alias_is_identical(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / "LICENSE").read_bytes(), (root / "Licence.txt").read_bytes())


if __name__ == "__main__":unittest.main()
