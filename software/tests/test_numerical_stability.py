"""AI-assisted strict-review regressions; independent analytical/Fraction oracles.

These tests were added after the authors' v0.2.0 test confirmation. Their
creation and execution do not constitute an additional human verification.
"""
from dataclasses import replace
from fractions import Fraction
import math
import itertools
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from workcert import ReducedResponse, certify, from_indices, reduce_response, split_monotone_branches


ERROR_FIELDS = ("eta", "xi", "prefix", "window", "delta", "signed_terminal_error",
                "min_cumulative_error", "max_cumulative_error")


def fraction_area(x, f, a, b):
    """Integrate binary64 input PL segments using exact rational arithmetic."""
    xx, ff = [Fraction(float(v)) for v in x], [Fraction(float(v)) for v in f]
    a, b = Fraction(float(a)), Fraction(float(b))
    result = Fraction(0)
    for left, right, fa, fb in zip(xx[:-1], xx[1:], ff[:-1], ff[1:]):
        lo, hi = max(a, left), min(b, right)
        if lo < hi:
            slope = (fb - fa) / (right - left)
            flo, fhi = fa + slope * (lo - left), fa + slope * (hi - left)
            result += (hi - lo) * (flo + fhi) / 2
    return float(result)


class NumericalStabilityTests(unittest.TestCase):
    def assert_zero_reconstruction(self, response):
        for field in ERROR_FIELDS:
            self.assertEqual(getattr(response.certificate, field), 0., field)

    def test_review_long_constant_all_constructors_and_roundtrip(self):
        x = np.arange(100001, dtype=float) * 1e-4
        force = np.full(len(x), .1)
        expected = float(Fraction(.1) * (Fraction(float(x[-1])) - Fraction(float(x[0]))))
        constructors = [("external", lambda: from_indices(x, force, [0, len(x) - 1]))]
        constructors += [(method, lambda method=method: reduce_response(
            x, force, method=method, max_points=2))
            for method in ("work", "vertical", "uniform", "uniform_peak", "vw")]
        constructors += [("zero tolerance", lambda: reduce_response(
            x, force, method="work", tolerance=0., max_points=129)),
            ("full nodes", lambda: from_indices(x, force, np.arange(len(x))))]
        with tempfile.TemporaryDirectory() as folder:
            for label, construct in constructors:
                with self.subTest(constructor=label):
                    response = construct()
                    self.assert_zero_reconstruction(response)
                    self.assertEqual(response.certificate.reference_work, expected)
                    self.assertEqual(response.work(x[-1]), expected)
                    self.assertEqual(response.window_work(x[0], x[-1]), expected)
                    path = Path(folder) / "constant.json"
                    response.save(path)
                    loaded = ReducedResponse.load(path)
                    self.assertTrue(loaded.verify_reference(x, force))
                    self.assertEqual(loaded.to_bytes(), response.to_bytes())

    def test_constant_family_sizes_force_coordinate_scales_and_shift(self):
        for n in (3, 257, 1001, 10001, 100001):
            for x_scale in (2.**-20, 1., 2.**20):
                for force_scale in (2.**-20, 1., 2.**20):
                    with self.subTest(n=n, x_scale=x_scale, force_scale=force_scale):
                        x = (np.arange(n) * 1e-4 + 3.) * x_scale
                        force = np.full(n, -.1 * force_scale)
                        response = from_indices(x, force, [0, n - 1])
                        expected = float(Fraction(float(force[0])) *
                            (Fraction(float(x[-1])) - Fraction(float(x[0]))))
                        self.assert_zero_reconstruction(response)
                        self.assertLessEqual(abs(response.work(x[-1]) - expected), 2 * math.ulp(expected))
                        self.assertTrue(response.verify_reference(x, force))

    def test_exact_dyadic_affine_family_has_zero_error(self):
        for n in (3, 257, 10001, 100001):
            for scale in (2.**-12, 1., 2.**12):
                with self.subTest(n=n, scale=scale):
                    x = np.arange(n, dtype=float) / 256. - 2.
                    force = (3 * x - 7) * scale
                    response = from_indices(x, force, [0, n - 1])
                    self.assert_zero_reconstruction(response)
                    expected = fraction_area([x[0], x[-1]], [force[0], force[-1]], x[0], x[-1])
                    self.assertEqual(response.work(x[-1]), expected)
                    q = x[0] + (x[-1] - x[0]) * .375
                    self.assertEqual(response.window_work(x[0], q),
                                     fraction_area(x[[0, -1]], force[[0, -1]], x[0], q))

    def test_nondyadic_affine_samples_use_actual_binary_inputs(self):
        # These binary64 samples are not assumed to lie on one exact affine PL law.
        x = np.arange(37.) * .001 + .003
        force = 1e8 + 3.1 * x
        response = from_indices(x, force, [0, len(x) - 1])
        expected_work = fraction_area(x, force, x[0], x[-1])
        self.assertLessEqual(abs(response.certificate.reference_work - expected_work),
                             2 * math.ulp(expected_work))
        slope = (Fraction(float(force[-1])) - Fraction(float(force[0]))) / (
            Fraction(float(x[-1])) - Fraction(float(x[0])))
        delta = max(abs(Fraction(float(fi)) - Fraction(float(force[0])) - slope *
                        (Fraction(float(xi)) - Fraction(float(x[0])))) for xi, fi in zip(x, force))
        self.assertAlmostEqual(response.certificate.delta, float(delta), delta=1e-16)

    def test_review_large_prefix_short_window_and_broadcast(self):
        response = from_indices([0., 1., 2.], [1e16, 0., 1.], [0, 1, 2])
        self.assertEqual(response.certificate.window, 0.)
        self.assertEqual(response.window_work(1., 2.), .5)
        np.testing.assert_array_equal(response.window_work([1., 1.5, 2.], 2.), [.5, .375, 0.])

    def test_compensated_full_window_keeps_small_signed_component(self):
        # Exact segment areas: 1e16, 1, -1e16. The small term survives local sums.
        x, f = [0., 1., 2., 3.], [2e16, 0., 2., -2e16 - 2.]
        response = from_indices(x, f, [0, 1, 2, 3])
        expected = fraction_area(x, f, 0., 3.)
        self.assertEqual(response.window_work(0., 3.), expected)
        self.assertEqual(response.work(3.), expected)
        for a, b in ((1., 2.), (.5, 2.5), (1.5, 3.)):
            self.assertLessEqual(abs(response.window_work(a, b) - fraction_area(x, f, a, b)),
                                 2 * math.ulp(fraction_area(x, f, a, b)))

    def test_random_local_windows_against_fraction_oracle(self):
        rng = np.random.default_rng(20261103)
        for trial in range(30):
            x = np.arange(9., dtype=float)
            f = rng.integers(-50, 51, len(x)).astype(float)
            response = from_indices(x, f, np.arange(len(x)))
            for _ in range(8):
                a, b = sorted(rng.integers(0, 33, 2) / 4.)
                expected = fraction_area(x, f, a, b)
                self.assertLessEqual(abs(response.window_work(a, b) - expected),
                                     4 * math.ulp(expected) if expected else 0., (trial, a, b))

    def test_three_scale_cancellation_all_permutations_and_interior_windows(self):
        amplitudes = [1e100, 1., 1e-100, -1e100, -1.]
        for order in itertools.permutations(amplitudes):
            force = np.array([0.] + [value for amplitude in order for value in (2 * amplitude, 0.)])
            x = np.arange(len(force), dtype=float)
            expected = fraction_area(x, force, x[0], x[-1])
            response = from_indices(x, force, np.arange(len(x)))
            with self.subTest(order=order, window="complete"):
                self.assertEqual(response.work(x[-1]), expected)
                self.assertEqual(response.window_work(x[0], x[-1]), expected)
            # Large endpoint contributions outside this window must neither
            # pollute its condition estimate nor replace its local leaf terms.
            xx = np.r_[x[0] - 2., x[0] - 1., x, x[-1] + 1., x[-1] + 2.]
            ff = np.r_[0., 2e120, force, -2e120, 0.]
            padded = from_indices(xx, ff, np.arange(len(xx)))
            with self.subTest(order=order, window="interior"):
                self.assertEqual(padded.window_work(x[0], x[-1]), expected)
            # Include a non-node endpoint in a zero-force padding segment.
            xx = np.r_[x[0] - 2., x[0] - 1., x, x[-1] + 1.]
            ff = np.r_[0., 0., force, 0.]
            padded = from_indices(xx, ff, np.arange(len(xx)))
            with self.subTest(order=order, window="fractional start"):
                self.assertEqual(padded.window_work(x[0] - .5, x[-1]), expected)
                self.assertEqual(padded.work(x[-1]), expected)

    def test_source_baseline_cannot_excuse_zeroed_nonzero_error(self):
        x, f = [0., 1., 2.], [1e12, 1e12 + .01, 1e12]
        response = from_indices(x, f, [0, 2])
        self.assertEqual(response.certificate.prefix, .010009765625)
        forged = replace(response.certificate, **{name: 0. for name in ERROR_FIELDS})
        with self.assertRaisesRegex(ValueError, "Retained terminal work"):
            ReducedResponse(response.x, response.force, response.indices, forged, metadata=response.metadata)
        # Even a forger who changes the terminal reference work to make that
        # identity self-consistent cannot replace the actual residual by zero.
        forged = replace(forged, reference_work=response.work(x[-1]))
        changed = ReducedResponse(response.x, response.force, response.indices, forged, metadata=response.metadata)
        with self.assertRaisesRegex(ValueError, "Certificate field"):
            changed.verify_reference(x, f)

    def test_local_ulp_verification_accepts_last_bits_rejects_material_change(self):
        response = from_indices([0, 1, 2], [0, 2, 0], [0, 2])
        one = replace(response.certificate, delta=np.nextafter(response.certificate.delta, np.inf))
        changed = ReducedResponse(response.x, response.force, response.indices, one)
        self.assertTrue(changed.verify_reference([0, 1, 2], [0, 2, 0]))
        far = replace(response.certificate, delta=response.certificate.delta + 100 * math.ulp(response.certificate.delta))
        changed = ReducedResponse(response.x, response.force, response.indices, far)
        with self.assertRaisesRegex(ValueError, "Certificate field 'delta'"):
            changed.verify_reference([0, 1, 2], [0, 2, 0])

    def test_internal_checks_have_no_unit_sized_floor(self):
        response = from_indices([0., 1e-12, 2e-12], [0., 2e-12, 0.], [0, 2])
        for changed in (replace(response.certificate, reference_work=response.certificate.reference_work + 1e-28),
                        replace(response.certificate, window=response.certificate.window / 2)):
            with self.assertRaises(ValueError):
                ReducedResponse(response.x, response.force, response.indices, changed)

    def test_directed_branch_uses_local_window(self):
        series = split_monotone_branches([2., 1., 0.], [1., 0., 1e16])
        branch = series.branches[0]
        response = from_indices(branch.x, branch.force, [0, 1, 2])
        self.assertEqual(branch.directed_work(response, 1.), -.5)

    def test_branch_reference_retains_endpoint_mean_corrections(self):
        x, force = np.arange(5.), np.array([0., 1e16, 1., -1e16, 0.])
        expected = fraction_area(x, force, x[0], x[-1])
        self.assertEqual(expected, 1.)
        for xx, ff, direction in ((x, force, 1), (x[::-1], force[::-1], -1)):
            series = split_monotone_branches(xx, ff)
            self.assertEqual(series.reference_work, direction * expected)
            branch = series.branches[0]
            response = from_indices(branch.x, branch.force, np.arange(len(x)))
            self.assertEqual(branch.directed_work(response), direction * expected)

    def test_overflow_api_exception_and_cli_exit_protocol(self):
        for method in ("work", "vertical", "uniform", "uniform_peak", "vw"):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    reduce_response([0, 1, 2], [1e308] * 3, method=method, max_points=2)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "overflow.csv"
            target = Path(folder) / "table.json"
            source.write_text("stroke_mm,force_kN\n0,1e308\n1,1e308\n2,1e308\n", encoding="utf8")
            for method in ("work", "vertical", "uniform", "uniform_peak", "vw"):
                result = subprocess.run([sys.executable, "-m", "workcert", "reduce", str(source),
                    str(target), "--method", method, "--max-points", "2"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(result.stderr.startswith("workcert:"))
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
