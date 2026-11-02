"""Independent rational controls and checks of the cyclic diagnostic outputs."""
from fractions import Fraction
from pathlib import Path
import importlib.util
import json

import numpy as np
import pandas as pd

from cyclic_round2 import ROOT, OUT, exact_residual_summary, extrema_with_deadband, append_directed_summary


def rational_extrema(x, r):
    accumulated = Fraction(0)
    values = [accumulated]
    for a, b, left, right in zip(x[:-1], x[1:], r[:-1], r[1:]):
        width = Fraction(int(b) - int(a))
        left, right = Fraction(int(left)), Fraction(int(right))
        if left * right < 0:
            t = -left / (right - left)
            values.append(accumulated + width * (left*t + (right-left)*t*t/2))
        accumulated += width * (left + right)/2
        values.append(accumulated)
    return float(accumulated), float(min(values)), float(max(values))


def main():
    spec = importlib.util.spec_from_file_location('metadata_consumer', ROOT/'examples/compose_branch_errors.py')
    consumer = importlib.util.module_from_spec(spec);spec.loader.exec_module(consumer)
    rng = np.random.default_rng(20261102)
    max_delta = 0.
    for i in range(256):
        n = int(rng.integers(3, 32))
        # Signed, reversing and dwelling paths exercise chronological integration.
        x = rng.integers(-20, 21, n)
        r = rng.integers(-30, 31, n)
        expected = rational_extrema(x, r)
        d, lo, hi = exact_residual_summary(x.astype(float), r.astype(float))
        actual = (float(d[-1]), lo, hi)
        max_delta = max(max_delta, *[abs(a-b) for a, b in zip(expected, actual)])
        assert np.allclose(actual, expected, rtol=0., atol=5e-11)
    # Hand-checkable extrema: a 0.02 downward tick is below the 0.2 deadband.
    path = np.array([0., 1., 2., 1.98, 2.01, 2., 1., 0., -1., -.9, -.5, .1])
    assert np.array_equal(extrema_with_deadband(path, .2), [4, 8])
    assert np.array_equal(extrema_with_deadband(-path, .2), [4, 8])
    for x in (np.zeros(20), np.arange(20.), -np.arange(20.)):
        assert len(extrema_with_deadband(x, .1)) == 0
    for threshold in (0., -1., float('nan'), float('inf')):
        try:extrema_with_deadband(path, threshold)
        except ValueError:pass
        else:raise AssertionError('Invalid threshold accepted')
    max_fold_delta = 0.
    for _ in range(128):
        aggregate = (0., 0., 0.)
        path_x, path_r = [0], [0]
        records = []
        for _ in range(6):
            x = np.r_[0, np.cumsum(rng.integers(1, 8, int(rng.integers(2, 8))))]
            r = rng.integers(-20, 21, len(x));r[0]=r[-1]=0
            direction = int(rng.choice([-1,1]))
            terminal, lo, hi = rational_extrema(x, r)
            aggregate = append_directed_summary(aggregate, (terminal, lo, hi), direction)
            chronological_x = x if direction == 1 else x[::-1]
            chronological_r = r if direction == 1 else r[::-1]
            chronological_x = chronological_x - chronological_x[0] + path_x[-1]
            first = len(path_x)-1
            path_x.extend(chronological_x[1:].tolist());path_r.extend(chronological_r[1:].tolist())
            records.append({'kind':'branch', 'direction':direction, 'terminal':terminal,
                'minimum':lo, 'maximum':hi, 'source_start':first, 'source_end':len(path_x)-1})
            if bool(rng.integers(2)):
                first = len(path_x)-1;path_x.append(path_x[-1]);path_r.append(path_r[-1])
                records.append({'kind':'zero_work_event','direction':0,'terminal':0.,'minimum':0.,'maximum':0.,
                    'source_start':first,'source_end':first+1})
        expected = rational_extrema(path_x, path_r)
        max_fold_delta = max(max_fold_delta, *[abs(a-b) for a,b in zip(aggregate, expected)])
        assert np.allclose(aggregate, expected, rtol=0., atol=5e-11)
        public = consumer.compose_branch_errors(records, source_points=len(path_x))
        assert np.allclose((public['signed_terminal_error'],public['minimum_cumulative_error'],
                            public['maximum_cumulative_error']), expected, rtol=0., atol=5e-11)

    summary = json.loads((OUT/'summary.json').read_text(encoding='utf8'))
    old = json.loads((ROOT/'validation/workflow_results/cyclic_path/summary.json').read_text(encoding='utf8'))
    branch = pd.read_csv(OUT/'branch_diagnostics.csv', float_precision='round_trip')
    diagnostic = pd.read_csv(OUT/'deadband_sensitivity.csv')
    indices = pd.read_csv(OUT/'deadband_extrema.csv')
    assert len(branch) == summary['exact_monotone_branches'] == old['branches']
    assert len(branch) == 2971 and summary['exact_zero_displacement_events'] == 1984
    assert np.isclose(branch.independent_window_error_J.sum(), summary['sum_branch_window_errors_J'], atol=1e-10)
    assert np.isclose(branch.terminal_error_J.sum(), summary['signed_terminal_reference_minus_reconstruction_J'], atol=1e-9)
    assert np.isclose(summary['reference_signed_path_work_J'], old['reference_signed_path_work_J'], atol=1e-9)
    assert np.isclose(summary['maximum_continuous_chronological_error_J'], old['maximum_continuous_chronological_work_error_J'], atol=1e-9)
    assert np.isclose(summary['sum_branch_window_errors_J'], old['sum_branch_window_bounds_J'], atol=1e-9)
    assert summary['monotonicity']['chronological_error_is_monotone'] is False
    assert summary['monotonicity']['negative_error_increments'] > 0
    assert summary['monotonicity']['positive_error_increments'] > 0
    stable = diagnostic[(diagnostic.deadband_mm >= .1) & (diagnostic.deadband_mm <= 5.)]
    assert len(stable) == 6 and np.all(stable.confirmed_reversals == 94)
    baseline = indices[indices.deadband_mm == .1].source_index.to_numpy()
    for t in stable.deadband_mm:
        assert np.array_equal(baseline, indices[indices.deadband_mm == t].source_index.to_numpy())
    assert not diagnostic.data_modified.any() and not diagnostic.used_for_reconstruction.any()
    assert summary['deadband_diagnostic']['reconstruction_threshold_mm'] is None
    assert summary['protocol_context']['S1_L1_failure_cycle_table_3'] * 2 == len(baseline)
    composed = summary['composed_chronological_error_metadata']
    assert not composed['reads_reference_values']
    assert np.isclose(composed['prefix_error_J'], summary['maximum_continuous_chronological_error_J'], atol=1e-8)
    manifest = json.loads((OUT/'branch_error_manifest.json').read_text(encoding='utf8'))
    public = consumer.compose_branch_errors(manifest['records'],source_points=manifest['source_points'])
    assert public['branches'] == 2971 and public['zero_work_events'] == 1984
    assert np.isclose(public['prefix'], composed['prefix_error_J'], rtol=0., atol=1e-10)
    # Complete-coverage validation rejects a dropped event or reversed manifest.
    for records in (manifest['records'][1:], list(reversed(manifest['records']))):
        try:consumer.compose_branch_errors(records,source_points=manifest['source_points'])
        except ValueError:pass
        else:raise AssertionError('Invalid chronological coverage accepted')
    invalid = [{'kind':'branch','direction':True,'terminal':0.,'minimum':0.,'maximum':0.},
               {'kind':'branch','direction':1,'terminal':0.,'minimum':1.,'maximum':2.},
               {'kind':'zero_work_event','direction':0,'terminal':1.,'minimum':0.,'maximum':1.},
               {'kind':'branch','direction':1,'terminal':1e308,'minimum':-1e308,'maximum':1e308}]
    for record in invalid:
        try:consumer.compose_branch_errors([record])
        except ValueError:pass
        else:raise AssertionError('Invalid metadata accepted')
    report = {'status': 'PASS', 'rational_signed_path_cases': 256,
              'maximum_rational_oracle_difference_J': max_delta,
              'deadband_hand_cases': 5, 'invalid_deadband_controls': 4,
              'all_branch_errors_match_frozen_reference': True,
              'stable_deadband_runs': len(stable), 'stable_extrema': len(baseline),
              'rational_directed_metadata_fold_cases': 128,
              'maximum_rational_directed_fold_difference_J': max_fold_delta,
              'standalone_consumer_rational_directed_cases':128,
              'standalone_consumer_full_source_edges':manifest['source_points']-1,
              'invalid_consumer_metadata_or_coverage_controls':6,
              'scale_diagnostic_does_not_modify_or_reconstruct_the_path': True,
              'physical_event_assignment_claimed': False}
    (OUT/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':main()
