"""Regression checks for the standalone directed-error metadata consumer.

Run from the source root with:
    python validation/test_branch_summary_validation.py

These example-consumer tests are separate from the installed WorkCert suite.
"""
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'workcert_branch_consumer', ROOT / 'examples/compose_branch_errors.py')
CONSUMER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONSUMER)
compose_branch_errors = CONSUMER.compose_branch_errors

SCALES = (1e-300, 1e-200, 1e-100, 1e-15, 1e-12,
          1e-3, 1., 1e3, 1e12, 1e100, 1e200, 1e300)


def branch(terminal, minimum, maximum, direction=1):
    return {'kind': 'branch', 'direction': direction, 'terminal': terminal,
            'minimum': minimum, 'maximum': maximum}


class BranchSummaryValidationTests(unittest.TestCase):
    def test_nonzero_terminal_requires_nonzero_containing_extremum(self):
        # The reviewed 1e-12 J / 1e-15 kJ pair is included in both signs.
        for scale in SCALES:
            for sign in (-1., 1.):
                with self.subTest(scale=scale, sign=sign):
                    with self.assertRaises(ValueError):
                        compose_branch_errors([branch(sign * scale, 0., 0.)])

    def test_extrema_must_contain_the_exact_initial_zero(self):
        for scale in SCALES:
            for record in (branch(2 * scale, scale, 3 * scale),
                           branch(-2 * scale, -3 * scale, -scale)):
                with self.subTest(scale=scale, record=record):
                    with self.assertRaises(ValueError):
                        compose_branch_errors([record])

    def test_one_ulp_endpoint_violation_is_rejected(self):
        # These are metadata invariants, rather than approximate comparisons.
        for scale in SCALES:
            outside = math.nextafter(scale, math.inf)
            for record in (branch(outside, 0., scale),
                           branch(-outside, -scale, 0.)):
                with self.subTest(scale=scale, record=record):
                    with self.assertRaises(ValueError):
                        compose_branch_errors([record])

    def test_unrelated_large_extremum_cannot_mask_a_small_violation(self):
        for record in (branch(1e-15, -1e100, 0.),
                       branch(-1e-15, 0., 1e100),
                       branch(1e100, 1e-15, 1e100),
                       branch(-1e100, -1e100, -1e-15)):
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    compose_branch_errors([record])

    def test_valid_summaries_across_work_unit_scales(self):
        for scale in SCALES:
            with self.subTest(scale=scale):
                actual = compose_branch_errors([branch(scale, -scale, 2 * scale)])
                self.assertEqual(actual['signed_terminal_error'], scale)
                self.assertEqual(actual['minimum_cumulative_error'], -scale)
                self.assertEqual(actual['maximum_cumulative_error'], 2 * scale)
                self.assertEqual(actual['prefix'], 2 * scale)
                self.assertEqual(actual['window'], 3 * scale)

    def test_descending_branches_use_the_terminal_shift(self):
        for scale in SCALES:
            with self.subTest(scale=scale):
                actual = compose_branch_errors(
                    [branch(2 * scale, -scale, 3 * scale, direction=-1)])
                self.assertEqual(actual['signed_terminal_error'], -2 * scale)
                self.assertEqual(actual['minimum_cumulative_error'], -scale - 2 * scale)
                self.assertEqual(actual['maximum_cumulative_error'], 3 * scale - 2 * scale)
                self.assertEqual(actual['window'],
                                 actual['maximum_cumulative_error'] -
                                 actual['minimum_cumulative_error'])

    def test_zero_and_subnormal_values(self):
        actual = compose_branch_errors([branch(-0., -0., 0.)])
        self.assertEqual(actual['prefix'], 0.)
        self.assertEqual(actual['window'], 0.)
        least = math.ulp(0.)
        for sign in (-1., 1.):
            with self.subTest(sign=sign):
                with self.assertRaises(ValueError):
                    compose_branch_errors([branch(sign * least, 0., 0.)])
        actual = compose_branch_errors([branch(least, 0., least)])
        self.assertEqual(actual['signed_terminal_error'], least)
        self.assertEqual(actual['window'], least)

    def test_overflow_is_rejected(self):
        cases = ([branch(1e308, 0., 1e308), branch(1e308, 0., 1e308)],
                 [branch(0., -1e308, 1e308)],
                 [branch(1e308, -1e308, 1e308, direction=-1)])
        for records in cases:
            with self.subTest(records=records):
                with self.assertRaises(ValueError):
                    compose_branch_errors(records)

    def test_nonfinite_and_boolean_values_are_rejected(self):
        for value in (float('inf'), -float('inf'), float('nan'), True):
            for field in ('terminal', 'minimum', 'maximum'):
                record = branch(0., 0., 0.)
                record[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        compose_branch_errors([record])

    def test_zero_work_events_and_coverage(self):
        records = [dict(branch(2., -1., 3.), source_start=0, source_end=1),
                   {'kind': 'zero_work_event', 'direction': 0, 'terminal': 0.,
                    'minimum': 0., 'maximum': 0., 'source_start': 1,
                    'source_end': 2}]
        actual = compose_branch_errors(records, source_points=3)
        self.assertEqual(actual['branches'], 1)
        self.assertEqual(actual['zero_work_events'], 1)
        with self.assertRaises(ValueError):
            compose_branch_errors(records[:1], source_points=3)

    def test_sequential_floating_point_composition_has_no_rounding_bound(self):
        terminals = (1e16, 1., -1e16)
        records = [branch(value, min(0., value), max(0., value))
                   for value in terminals]
        actual = compose_branch_errors(records)
        exact_terminal = sum((Fraction.from_float(value) for value in terminals),
                             Fraction(0))
        self.assertEqual(exact_terminal, 1)
        self.assertEqual(actual['signed_terminal_error'], 0.)
        self.assertNotEqual(Fraction(actual['signed_terminal_error']), exact_terminal)

    def test_all_archived_chronological_records_remain_valid(self):
        folder = ROOT / 'validation/cyclic_round2_results'
        manifest = json.loads((folder / 'branch_error_manifest.json').read_text(encoding='utf8'))
        actual = compose_branch_errors(manifest['records'],
                                       source_points=manifest['source_points'])
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf8'))
        expected = summary['composed_chronological_error_metadata']
        self.assertEqual(actual['branches'], 2971)
        self.assertEqual(actual['zero_work_events'], 1984)
        self.assertAlmostEqual(actual['prefix'], expected['prefix_error_J'], delta=1e-10)
        self.assertAlmostEqual(actual['window'], expected['window_error_J'], delta=1e-10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
