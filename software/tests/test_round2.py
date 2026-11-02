"""Reference-peak bounds and geometric interoperability controls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from workcert import ReducedResponse, from_indices, indices_from_coordinates, reduce_response


def source_prefix_peak(x, force, query):
    return max(float(np.max(force[x <= query])), float(np.interp(query, x, force)))


class QueryPeakTests(unittest.TestCase):
    def test_preserved_peak_makes_late_CFE_denominator_exact(self):
        x = np.arange(8.)
        force = np.array([0., 2., 5., 10., 6., 7., 4., 3.])
        table = reduce_response(x, force, method='work', max_points=3)
        self.assertGreater(table.certificate.delta, 0)
        np.testing.assert_array_equal(table.peak_bounds([3., 3.5, 7.]), ([10., 10., 10.], [10., 10., 10.]))
        q = 6.
        low, high = table.peak_bounds(q)
        self.assertEqual(low, high)
        tight_width = 2 * table.certificate.prefix / (q * low)
        generic_low, generic_high = 10-table.certificate.delta, 10+table.certificate.delta
        old_width = ((table.work(q)+table.certificate.prefix)/(q*generic_low) -
                     (table.work(q)-table.certificate.prefix)/(q*generic_high))
        self.assertLess(tight_width, old_width)

    def test_peak_bounds_cover_signed_reference_before_and_after_peak(self):
        rng = np.random.default_rng(30211)
        for _ in range(40):
            x = np.r_[0., np.cumsum(rng.uniform(.1, 2., 19))]
            f = rng.normal(0, 3, len(x))
            table = reduce_response(x, f, method='vertical', max_points=7)
            q = np.r_[x, rng.uniform(x[0], x[-1], 80)]
            lo, hi = table.peak_bounds(q)
            actual = np.array([source_prefix_peak(x, f, v) for v in q])
            self.assertTrue(np.all(lo <= actual + 1e-12))
            self.assertTrue(np.all(hi >= actual - 1e-12))
            full = from_indices(x, f, np.arange(len(x)))
            np.testing.assert_allclose(full.peak_force(q), actual, atol=1e-12)

    def test_new_peak_summary_roundtrip_and_old_missing_summary(self):
        x = np.arange(6.)
        f = np.array([0., 8., 1., 4., 2., 0.])
        current = reduce_response(x, f, method='work', max_points=3)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'response.json'
            current.save(path)
            loaded = ReducedResponse.load(path)
            self.assertEqual(loaded.peak_bounds(5.), (8., 8.))
            self.assertTrue(loaded.verify_reference(x, f))
        old = ReducedResponse(current.x, current.force, current.indices, current.certificate,
                              metadata={'selection_method': 'old_payload'})
        lo, hi = old.peak_bounds(5.)
        self.assertLessEqual(lo, 8.)
        self.assertGreater(hi, 8.)
        self.assertTrue(old.verify_reference(x, f))

    def test_peak_summary_validation_and_source_recheck(self):
        x = np.arange(5.)
        f = np.array([0., 1., 6., 2., 0.])
        external = from_indices(x, f, [0, 3, 4])
        self.assertIsNone(external.metadata['retained_global_maximum'])
        # A retained-node-consistent but false producer claim cannot be
        # authenticated without the full source; verify_reference rejects it.
        forged = ReducedResponse(external.x, external.force, external.indices, external.certificate,
            metadata={'retained_global_maximum': {'reference_index': 3, 'x': 3., 'force': 2.}})
        with self.assertRaises(ValueError):
            forged.verify_reference(x, f)
        for claim in [{'reference_index': 2, 'x': 2., 'force': 6.},
                      {'reference_index': 3, 'x': 3.1, 'force': 2.},
                      {'reference_index': True, 'x': 3., 'force': 2.}]:
            with self.assertRaises(ValueError):
                ReducedResponse(external.x, external.force, external.indices, external.certificate,
                                metadata={'retained_global_maximum': claim})


class GeometricSelectorTests(unittest.TestCase):
    @staticmethod
    def brute_vw(x, f, budget, anchors):
        # A small-reference, quadratic oracle uses a fresh list of all
        # surviving triangles at every removal; no heap/linked-list code.
        xx = (x-x[0])/(x[-1]-x[0])
        yy = (f-min(f))/(np.ptp(f) or 1.)
        active = list(range(len(x)))
        while len(active) > budget:
            triangles = []
            for pos in range(1, len(active)-1):
                a, i, b = active[pos-1:pos+2]
                if i in anchors:continue
                area = abs(np.linalg.det(np.array([[xx[i]-xx[a], yy[i]-yy[a]],
                                                   [xx[b]-xx[a], yy[b]-yy[a]]]))) / 2
                triangles.append((area, i, pos))
            active.pop(min(triangles)[2])
        return np.array(active)

    def test_vw_matches_independent_exhaustive_triangle_removal(self):
        rng = np.random.default_rng(44513)
        for _ in range(35):
            x = np.r_[0., np.cumsum(rng.uniform(.1, 1., 22))]
            f = rng.normal(size=len(x))
            peak = int(np.argmax(np.abs(f)))
            for budget in (3, 7, 13):
                table = reduce_response(x, f, method='vw', max_points=budget)
                np.testing.assert_array_equal(table.indices, self.brute_vw(x, f, budget, {0, len(x)-1, peak}))
                self.assertEqual(len(table.x), budget)
                self.assertTrue(table.verify_reference(x, f))

    def test_vw_anchor_modes_and_fixed_budget_only(self):
        x = np.arange(9.)
        f = np.array([0., -10., 4., 0., 2., -1., 3., 1., 0.])
        for mode, expected in [('absolute', 1), ('negative', 1), ('positive', 2)]:
            table = reduce_response(x, f, method='vw', peak_mode=mode, max_points=3)
            self.assertEqual(table.indices.tolist(), [0, expected, 8])
        with self.assertRaises(ValueError):
            reduce_response(x, f, method='vw', tolerance=.1)
        full = reduce_response(x, f, method='vw', max_points=100)
        self.assertEqual(full.certificate.eta, 0)

    def test_exact_coordinate_adapter_accepts_vertices_and_rejects_projection(self):
        x = np.array([0., .3, 1., 2., 5.])
        f = np.array([0., 2., 4., 1., 0.])
        coordinates = np.column_stack([x, f])[[0, 2, 4]]
        ids = indices_from_coordinates(x, f, coordinates)
        np.testing.assert_array_equal(ids, [0, 2, 4])
        self.assertTrue(from_indices(x, f, ids).verify_reference(x, f))
        changed_x, changed_f = coordinates.copy(), coordinates.copy()
        changed_x[1, 0] = np.nextafter(changed_x[1, 0], np.inf)
        changed_f[1, 1] = np.nextafter(changed_f[1, 1], np.inf)
        for bad in (changed_x, changed_f, coordinates[::-1], coordinates[:-1],
                    coordinates[[0, 1, 1, 2]], [[0, 0], [np.nan, 1]]):
            with self.assertRaises(ValueError):indices_from_coordinates(x, f, bad)

    def test_vw_is_available_from_CLI(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'force.csv'
            source.write_text('stroke_mm,force_kN\n0,0\n1,5\n2,1\n3,4\n4,0\n', encoding='utf8')
            target = Path(folder)/'table.json'
            completed = subprocess.run([sys.executable, '-m', 'workcert', 'reduce', str(source), str(target),
                '--method', 'vw', '--max-points', '3'], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['points'], 3)
            self.assertEqual(ReducedResponse.load(target).indices.tolist(), [0, 1, 4])


if __name__ == '__main__':unittest.main()
