"""Regression tests for the example's acceptance gate, independent of datasets."""
import copy
import unittest

from checked_cyclic_path import compose_checked_path, PathToleranceError


def branch(**changes):
    record = dict(kind='branch', branch_id=7, source_start=0, source_end=2,
                  direction=1, terminal=.25, minimum=-.25, maximum=.5,
                  work_unit='J', bounds={'window':.75, 'prefix':.5, 'eta':1., 'xi':.75},
                  reference_work=10., certificate_for_stopping='window',
                  requested_tolerance=1., relative_tolerance=False, tolerance_met=True)
    record.update(changes)
    return record


def checked(records, **kwargs):
    return compose_checked_path(records, source_points=3, work_unit='J', **kwargs)


class CheckedPathTests(unittest.TestCase):
    def test_accepts_verified_budget(self):
        report = checked([branch()])
        self.assertTrue(report['valid_for_downstream_use'])
        self.assertEqual(report['failed_branch_ids'], [])
        self.assertEqual(report['error_summary']['window'], .75)

    def test_exact_budget_equality_passes(self):
        self.assertTrue(checked([branch(requested_tolerance=.75)])['tolerance_met'])

    def test_actual_error_rejects_even_if_flag_true(self):
        with self.assertRaises(PathToleranceError) as error:
            checked([branch(requested_tolerance=.5)])
        self.assertEqual(error.exception.report['failed_branch_ids'], [7])

    def test_flag_false_rejects_even_when_error_within_budget(self):
        with self.assertRaises(PathToleranceError):
            checked([branch(tolerance_met=False)])

    def test_missing_flag_rejects(self):
        record = branch(); del record['tolerance_met']
        with self.assertRaises(PathToleranceError):checked([record])

    def test_none_flag_rejects(self):
        with self.assertRaises(PathToleranceError):checked([branch(tolerance_met=None)])

    def test_string_flag_is_not_truthy_success(self):
        with self.assertRaises(PathToleranceError):checked([branch(tolerance_met='True')])

    def test_missing_tolerance_rejects(self):
        record = branch(); del record['requested_tolerance']
        with self.assertRaises(PathToleranceError):checked([record])

    def test_missing_relative_flag_rejects(self):
        record = branch(); del record['relative_tolerance']
        with self.assertRaises(PathToleranceError):checked([record])

    def test_invalid_stopping_measure_rejects(self):
        for value in (None, [], {}, 'unknown'):
            with self.subTest(value=value), self.assertRaises(PathToleranceError):
                checked([branch(certificate_for_stopping=value)])

    def test_nonfinite_or_negative_budget_rejects(self):
        for value in (-1., float('nan'), float('inf'), True):
            with self.subTest(value=value), self.assertRaises(PathToleranceError):
                checked([branch(requested_tolerance=value)])

    def test_relative_metric_computed_from_reference(self):
        report = checked([branch(requested_tolerance=.08, relative_tolerance=True)])
        self.assertEqual(report['branch_status'][0]['observed_error'], .075)
        with self.assertRaises(PathToleranceError):
            checked([branch(requested_tolerance=.07, relative_tolerance=True)])

    def test_zero_reference_requires_absolute_policy(self):
        with self.assertRaises(PathToleranceError):
            checked([branch(reference_work=0., relative_tolerance=True)])
        self.assertTrue(checked([branch(reference_work=0.)])['tolerance_met'])

    def test_diagnostic_status_propagates_failure(self):
        report = checked([branch(tolerance_met=False)], strict=False)
        self.assertFalse(report['valid_for_downstream_use'])
        self.assertFalse(report['tolerance_met'])
        self.assertEqual(report['failed_branch_ids'], [7])
        self.assertEqual(report['error_summary']['branches'], 1)

    def test_descending_summary_preserves_chronological_extrema(self):
        summary = checked([branch(direction=-1)])['error_summary']
        self.assertEqual(summary['signed_terminal_error'], -.25)
        self.assertEqual(summary['minimum_cumulative_error'], -.5)
        self.assertEqual(summary['maximum_cumulative_error'], .25)

    def test_zero_work_event_keeps_coverage(self):
        b = branch(source_end=1)
        event = dict(kind='zero_work_event', direction=0, source_start=1, source_end=2,
                     terminal=0., minimum=0., maximum=0., work_unit='J')
        report = checked([b, event])
        self.assertEqual(report['error_summary']['zero_work_events'], 1)

    def test_missing_branch_cannot_be_silently_skipped(self):
        with self.assertRaises(ValueError):checked([branch(source_start=1)])

    def test_unit_mismatch_rejects(self):
        with self.assertRaises(ValueError):checked([branch(work_unit='kJ')])

    def test_metric_must_match_extrema(self):
        record = branch();record['bounds']['window'] = 0.
        with self.assertRaises(PathToleranceError):checked([record])

    def test_eta_cannot_understate_known_window_error(self):
        record=branch(certificate_for_stopping='eta',requested_tolerance=.1)
        record['bounds']['eta']=0.
        with self.assertRaises(PathToleranceError):checked([record])
        self.assertTrue(checked([branch(certificate_for_stopping='eta')])['tolerance_met'])

    def test_xi_cannot_understate_known_window_error(self):
        record=branch(certificate_for_stopping='xi',requested_tolerance=.1)
        record['bounds']['xi']=0.
        with self.assertRaises(PathToleranceError):checked([record])
        self.assertTrue(checked([branch(certificate_for_stopping='xi')])['tolerance_met'])

    def test_near_zero_nonzero_error_does_not_get_a_floor(self):
        for scale in (1e-12,1e-15):
            record = branch(terminal=scale,minimum=0.,maximum=scale,
                bounds={'window':scale},requested_tolerance=0.)
            with self.subTest(scale=scale), self.assertRaises(PathToleranceError):
                checked([record])

    def test_zero_budget_exact_representation_passes(self):
        record = branch(terminal=0.,minimum=0.,maximum=0.,bounds={'window':0.},
                        requested_tolerance=0.)
        self.assertTrue(checked([record])['tolerance_met'])

    def test_sequential_float_semantics_are_not_claimed_exact(self):
        records=[]
        for i, value in enumerate((1e16,1.,-1e16)):
            records.append(branch(branch_id=i,source_start=i,source_end=i+1,
                terminal=value,minimum=min(0.,value),maximum=max(0.,value),
                bounds={'window':abs(value)},requested_tolerance=abs(value)))
        report=compose_checked_path(records,source_points=4,work_unit='J')
        self.assertEqual(report['error_summary']['signed_terminal_error'],0.)
        self.assertFalse(report['arithmetic_rounding_enclosed'])

    def test_input_not_modified(self):
        records=[branch()];before=copy.deepcopy(records)
        checked(records)
        self.assertEqual(records,before)


if __name__ == '__main__':unittest.main(verbosity=2)
