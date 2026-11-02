"""Diagnose exact cyclic branches, directional bias and reversal scale.

The deadband sweep labels extrema only. It does not alter measured coordinates,
merge monotone tables, or assign a reconstruction guarantee to a smoothed path.
All errors below are independently integrated from the archived reference and
the saved vertex-subset tables without importing WorkCert.
"""
from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/cyclic_round2_results'
THRESHOLDS = (.001, .01, .0158, .025, .05, .1, .25, .5, 1., 2., 5.)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8')


def raw_source():
    path = ROOT / 'data/extended/cyclic_RHS_10829958/cyclic_RHS.xlsx'
    expected = '26065e56a3923add82c988876037fa5e50991eecc5c2e8c2ad636b3e2b430673'
    assert sha(path) == expected
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = [(r[1], r[2]) for r in book['S1_L1'].iter_rows(min_row=4, values_only=True)
            if isinstance(r[1], (int, float)) and isinstance(r[2], (int, float))]
    book.close()
    data = np.asarray(rows, dtype=float)
    assert data.shape == (125157, 2) and np.all(np.isfinite(data))
    return path, data[:, 0], data[:, 1]


def source_hash(x, f):
    h = hashlib.sha256(b'workcert-reference-float64-le-v1\0')
    for a in (np.asarray([len(x)], dtype='<u8'), np.asarray(x, dtype='<f8'), np.asarray(f, dtype='<f8')):
        h.update(a.tobytes())
    return h.hexdigest()


def extrema_with_deadband(x, threshold):
    """Running-extremum directional-change detector; return confirmed extrema.

    A reversal is confirmed after moving threshold away from the running extreme.
    The last unconfirmed endpoint is not counted as a reversal. The first motion
    is established from the running initial range. Equal extrema keep their first
    source index. This returns annotations, not monotone intervals for F(x).
    """
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError('The diagnostic deadband must be positive and finite')
    direction = 0
    lo = hi = 0
    extreme = 0
    result = []
    for i, value in enumerate(x):
        if direction == 0:
            if value < x[lo]:lo = i
            if value > x[hi]:hi = i
            if value - x[lo] >= threshold:
                direction, extreme = 1, i
            elif x[hi] - value >= threshold:
                direction, extreme = -1, i
        elif direction > 0:
            if value > x[extreme]:extreme = i
            elif x[extreme] - value >= threshold:
                result.append(extreme)
                direction, extreme = -1, i
        else:
            if value < x[extreme]:extreme = i
            elif value - x[extreme] >= threshold:
                result.append(extreme)
                direction, extreme = 1, i
    return np.asarray(result, dtype=np.int64)


def exact_residual_summary(x, residual):
    """Integrate a piecewise-linear residual including every interior extremum."""
    h = np.diff(x)
    increments = h * (residual[:-1] + residual[1:]) * .5
    d = np.r_[0., np.cumsum(increments)]
    cross = np.flatnonzero(residual[:-1] * residual[1:] < 0)
    t = -residual[cross] / (residual[cross + 1] - residual[cross])
    interior = d[cross] + .5 * h[cross] * t * residual[cross]
    lo = min(float(np.min(d)), float(np.min(interior)) if len(interior) else 0.)
    hi = max(float(np.max(d)), float(np.max(interior)) if len(interior) else 0.)
    return d, lo, hi


def append_directed_summary(aggregate, source_summary, direction):
    """Compose stored source errors in chronological order, without source data."""
    d, lo, hi = source_summary
    if direction == -1:
        # Chronological start is the upper x endpoint: D(x) - D(U).
        d, lo, hi = -d, lo - d, hi - d
    elif direction != 1:
        raise ValueError('Branch direction must be +1 or -1')
    accumulated, minimum, maximum = aggregate
    return accumulated + d, min(minimum, accumulated + lo), max(maximum, accumulated + hi)


def quantify(workflow_directory):
    source, x, f = raw_source()
    metrics_file = workflow_directory / 'branch_metrics.csv'
    rows = pd.read_csv(metrics_file, float_precision='round_trip')
    approximation = f.copy()
    coverage = np.zeros(len(x) - 1, dtype=np.int16)
    per_branch = []
    max_difference = 0.
    aggregate = (0., 0., 0.)
    ordered_metadata = []
    for row in rows.itertuples():
        path = workflow_directory / 'tables' / Path(row.table).name
        assert sha(path) == row.sha256
        envelope = json.loads(path.read_text(encoding='utf8'))
        p = envelope['payload']
        canonical = json.dumps(p, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
        assert hashlib.sha256(canonical).hexdigest() == envelope['payload_sha256']
        cert = p['certificate']
        aggregate = append_directed_summary(aggregate,
            (cert['signed_terminal_error'], cert['min_cumulative_error'], cert['max_cumulative_error']),
            int(row.direction))
        a, b = int(row.source_first), int(row.source_last)
        ordered_metadata.append({'kind': 'branch', 'source_start': a, 'source_end': b,
            'direction': int(row.direction), 'terminal': cert['signed_terminal_error'],
            'minimum': cert['min_cumulative_error'], 'maximum': cert['max_cumulative_error']})
        ids = np.arange(a, b + 1) if row.direction > 0 else np.arange(b, a - 1, -1)
        bx, bf = x[ids], f[ids]
        assert np.all(np.diff(bx) > 0)
        assert p['certificate']['reference_sha256'] == source_hash(bx, bf)
        retained = np.asarray(p['indices'], dtype=int)
        assert np.array_equal(np.asarray(p['x']), bx[retained])
        assert np.array_equal(np.asarray(p['force']), bf[retained])
        af = np.interp(bx, p['x'], p['force'])
        approximation[ids] = af
        coverage[a:b] += 1
        d, lo, hi = exact_residual_summary(bx, bf - af)
        prefix, window = max(abs(lo), abs(hi)), hi - lo
        max_difference = max(max_difference, abs(window - p['certificate']['window']),
                             abs(prefix - p['certificate']['prefix']))
        assert np.isclose(window, p['certificate']['window'], rtol=1e-9, atol=1e-9)
        directed_error = int(row.direction) * float(d[-1])
        assert np.isclose(directed_error, row.reference_directed_work_J - row.reduced_directed_work_J,
                          rtol=1e-9, atol=1e-8)
        per_branch.append({'branch': int(row.branch), 'source_first': a, 'source_last': b,
            'source_points': len(bx), 'retained_points': len(retained), 'direction': int(row.direction),
            'excursion_mm': float(bx[-1] - bx[0]),
            'reference_signed_work_J': float(row.reference_directed_work_J),
            'terminal_error_J': directed_error, 'independent_window_error_J': window,
            'independent_prefix_error_J': prefix, 'tolerance_met': bool(row.tolerance_met)})
    dx = np.diff(x)
    dwells = dx == 0
    assert np.all(coverage[~dwells] == 1) and np.all(coverage[dwells] == 0)
    ordered_metadata.extend({'kind': 'zero_work_event', 'source_start': int(i), 'source_end': int(i+1),
            'direction': 0, 'terminal': 0., 'minimum': 0., 'maximum': 0.}
        for i in np.flatnonzero(dwells))
    ordered_metadata.sort(key=lambda v: v['source_start'])
    write_json(OUT / 'branch_error_manifest.json', {'schema': 'workcert.directed-error-sequence/1.0',
        'source_doi': '10.5281/zenodo.10829958', 'source_xlsx_sha256': sha(source),
        'source_points': len(x), 'work_unit': 'J', 'records': ordered_metadata})
    d, lo, hi = exact_residual_summary(x, f - approximation)
    full_work = float(np.sum(dx * (f[:-1] + f[1:]) * .5))
    reduced_work = float(np.sum(dx * (approximation[:-1] + approximation[1:]) * .5))
    bound = float(sum(r['independent_window_error_J'] for r in per_branch))
    max_error = max(abs(lo), abs(hi))
    assert np.allclose(aggregate, (float(d[-1]), lo, hi), rtol=0., atol=1e-8)
    assert abs(full_work - reduced_work - d[-1]) < 1e-8
    assert max_error <= bound + 1e-8
    npz = np.load(workflow_directory / 'chronological_path.npz')
    assert np.array_equal(x, npz['displacement_mm']) and np.array_equal(f, npz['reference_force_kN'])
    assert np.array_equal(approximation, npz['reconstructed_force_kN'])
    assert np.allclose(d, npz['cumulative_error_J'], rtol=0., atol=1e-10)
    branch = pd.DataFrame(per_branch)
    branch.to_csv(OUT / 'branch_diagnostics.csv', index=False, float_format='%.17g')
    sizes = branch.source_points.to_numpy()
    excursions = branch.excursion_mm.to_numpy()
    ab_work = np.abs(branch.reference_signed_work_J.to_numpy())
    abs_total = float(ab_work.sum())
    length_rows = []
    for upper in (2, 5, 10, 20, 50, 100, 500, 1000, int(max(sizes))):
        selected = sizes <= upper
        length_rows.append({'maximum_source_points': upper, 'branches': int(selected.sum()),
            'branch_fraction': float(selected.mean()),
            'sum_retained_nodes': int(branch.loc[selected, 'retained_points'].sum()),
            'sum_abs_branch_work_J': float(ab_work[selected].sum()),
            'fraction_sum_abs_branch_work': float(ab_work[selected].sum() / abs_total)})
    pd.DataFrame(length_rows).to_csv(OUT / 'branch_length_distribution.csv', index=False)
    excursion_rows = []
    for upper in (.0158, .0316, .05, .1, .25, .5, 1., 5., 10.):
        selected = excursions <= upper + 1e-10
        excursion_rows.append({'maximum_excursion_mm': upper, 'branches': int(selected.sum()),
            'branch_fraction': float(selected.mean()),
            'sum_abs_branch_work_J': float(ab_work[selected].sum()),
            'fraction_sum_abs_branch_work': float(ab_work[selected].sum() / abs_total),
            'sum_window_error_J': float(branch.loc[selected, 'independent_window_error_J'].sum())})
    pd.DataFrame(excursion_rows).to_csv(OUT / 'branch_excursion_distribution.csv', index=False)
    sensitivity, confirmed = [], []
    indices = {}
    for threshold in THRESHOLDS:
        ids = extrema_with_deadband(x, threshold)
        indices[threshold] = ids
        sensitivity.append({'deadband_mm': threshold, 'confirmed_reversals': len(ids),
                            'data_modified': False, 'used_for_reconstruction': False})
        confirmed += [{'deadband_mm': threshold, 'reversal_number': j,
                       'source_index': int(i), 'displacement_mm': float(x[i])}
                      for j, i in enumerate(ids)]
    pd.DataFrame(sensitivity).to_csv(OUT / 'deadband_sensitivity.csv', index=False)
    pd.DataFrame(confirmed).to_csv(OUT / 'deadband_extrema.csv', index=False)
    increments = np.diff(d)
    eps = 1e-12
    nonzero_ids = np.flatnonzero(dx != 0)
    nz = np.sign(dx[nonzero_ids])
    run_cuts = np.r_[0, np.flatnonzero(nz[:-1] != nz[1:]) + 1, len(nz)]
    run_rows = []
    for j, (a, b) in enumerate(zip(run_cuts[:-1], run_cuts[1:])):
        edges = nonzero_ids[a:b]
        first, last = int(edges[0]), int(edges[-1] + 1)
        run_rows.append({'direction_run': j, 'direction': int(nz[a]),
            'source_first': first, 'source_last': last,
            'nonzero_edges': len(edges), 'zero_steps_within_run': int(np.sum(dx[first:last] == 0)),
            'excursion_mm': abs(float(x[last] - x[first])),
            'first_step_magnitude_mm': abs(float(dx[first])),
            'reference_signed_work_J': float(np.sum(dx[edges] * (f[edges] + f[edges+1]) * .5)),
            'terminal_error_J': float(d[last] - d[first])})
    runs = pd.DataFrame(run_rows)
    runs.to_csv(OUT / 'direction_run_diagnostics.csv', index=False, float_format='%.17g')
    reversal_rows = []
    for j in range(1, len(run_cuts)-1):
        before, after = int(nonzero_ids[run_cuts[j]-1]), int(nonzero_ids[run_cuts[j]])
        reversal_rows.append({'reversal': j-1, 'previous_nonzero_edge': before,
            'next_nonzero_edge': after, 'intervening_zero_steps': after-before-1,
            'incoming_step_magnitude_mm': abs(float(dx[before])),
            'outgoing_step_magnitude_mm': abs(float(dx[after])),
            'following_direction_run_excursion_mm': run_rows[j]['excursion_mm']})
    pd.DataFrame(reversal_rows).to_csv(OUT / 'reversal_diagnostics.csv', index=False, float_format='%.17g')
    quantiles = (0, .25, .5, .75, .9, .95, .99, 1.)
    quantitative = {}
    for name, values in [('source_points', sizes), ('retained_points', branch.retained_points.to_numpy()),
                         ('excursion_mm', excursions), ('absolute_nonzero_step_mm', np.abs(dx[dx != 0]))]:
        quantitative[name] = {str(q): float(v) for q, v in zip(quantiles, np.quantile(values, quantiles))}
    sample = np.unique(np.r_[np.arange(0, len(x), 25), len(x)-1])
    pd.DataFrame({'source_index': sample, 'reference_displacement_mm': x[sample],
                  'cumulative_error_J': d[sample]}).to_csv(OUT / 'cumulative_error_samples.csv', index=False)
    summary = {'source_doi': '10.5281/zenodo.10829958', 'source_xlsx_sha256': sha(source),
        'workflow_branch_metrics_sha256': sha(metrics_file), 'source_points': len(x),
        'exact_monotone_branches': len(branch), 'exact_zero_displacement_events': int(dwells.sum()),
        'adjacent_nonzero_step_sign_changes': int(np.sum(dx[:-1] * dx[1:] < 0)),
        'direction_changes_after_omitting_zero_steps': int(np.sum(nz[:-1] != nz[1:])),
        'source_point_quantiles': quantitative['source_points'], 'all_quantiles': quantitative,
        'direction_runs_ignoring_zero_steps': {'count': len(runs),
            'excursion_quantiles_mm': {str(q): float(v) for q, v in zip(quantiles, np.quantile(runs.excursion_mm, quantiles))},
            'runs_with_excursion_at_most_0_1_mm': int(np.sum(runs.excursion_mm <= .1)),
            'fraction_with_excursion_at_most_0_1_mm': float(np.mean(runs.excursion_mm <= .1)),
            'sum_absolute_work_of_runs_at_most_0_1_mm_J': float(np.abs(runs.loc[runs.excursion_mm <= .1, 'reference_signed_work_J']).sum()),
            'interpretation': 'Runs ignore zero steps for diagnostic counting; they are not replacements for strict F(x) branches.'},
        'sum_retained_branch_nodes': int(branch.retained_points.sum()),
        'reference_signed_path_work_J': full_work, 'reconstructed_signed_path_work_J': reduced_work,
        'signed_terminal_reference_minus_reconstruction_J': float(d[-1]),
        'maximum_continuous_chronological_error_J': max_error,
        'sum_branch_window_errors_J': bound,
        'composed_chronological_error_metadata': {
            'signed_terminal_error_J': aggregate[0], 'minimum_error_J': aggregate[1],
            'maximum_error_J': aggregate[2], 'prefix_error_J': max(abs(aggregate[1]), abs(aggregate[2])),
            'window_error_J': aggregate[2]-aggregate[1], 'reads_reference_values': False,
            'source_fields': ['signed_terminal_error', 'min_cumulative_error', 'max_cumulative_error'],
            'direction_transform': 'ascending: (d,l,h); descending: (-d,l-d,h-d)',
            'composition': '(dA+dB,min(lA,dA+lB),max(hA,dA+hB))',
            'zero_displacement_events': 'zero-work contribution',
            'independently_matches_full_reference_residual_extrema': True},
        'terminal_error_percent_of_absolute_net_reference_work': float(100*d[-1]/abs(full_work)),
        'maximum_error_percent_of_absolute_net_reference_work': float(100*max_error/abs(full_work)),
        'bound_percent_of_absolute_net_reference_work': float(100*bound/abs(full_work)),
        'sum_absolute_directed_reference_branch_work_J': abs_total,
        'allocated_sum_branch_tolerances_J': .001*abs_total,
        'branches_unmet_tolerance_at_cap': int((~branch.tolerance_met).sum()),
        'monotonicity': {'tolerance_J': eps, 'positive_error_increments': int(np.sum(increments > eps)),
            'negative_error_increments': int(np.sum(increments < -eps)),
            'near_zero_error_increments': int(np.sum(np.abs(increments) <= eps)),
            'sum_positive_increments_J': float(increments[increments > 0].sum()),
            'sum_negative_increments_J': float(increments[increments < 0].sum()),
            'positive_terminal_branch_errors': int(np.sum(branch.terminal_error_J > 1e-10)),
            'negative_terminal_branch_errors': int(np.sum(branch.terminal_error_J < -1e-10)),
            'chronological_error_is_monotone': bool(np.all(increments >= -eps) or np.all(increments <= eps))},
        'deadband_diagnostic': {'thresholds_mm': THRESHOLDS,
            'stable_extrema_range_mm': [.1, 5.],
            'stable_extrema_count': int(len(indices[.1])),
            'stable_extrema_indices_identical': all(np.array_equal(indices[.1], indices[t]) for t in (.25, .5, 1., 2., 5.)),
            'data_modified': False, 'reconstruction_threshold_mm': None,
            'purpose': 'Scale diagnostic only; no branch merging or coordinate/force filtering is applied.',
            'not_a_sensor_uncertainty_estimate': True},
        'protocol_context': {'source_paper_doi': '10.1016/j.tws.2022.109969',
            'loading_protocol_section': '2.4; adapted ANSI/AISC 341 stepped cyclic displacement protocol',
            'S1_L1_corner_crack_cycle_table_3': 43, 'S1_L1_failure_cycle_table_3': 47,
            'reported_cycle_count_twice': 94,
            'interpretation': 'The stable count of 94 detected extrema is consistent with 47 reported cycles; command histories are not provided, so individual extrema are not assigned ground-truth loading events.'},
        'independent_checks': {'source_table_node_identity_checks': len(branch),
            'source_hash_checks': len(branch), 'saved_payload_checks': len(branch),
            'every_nonzero_chronological_edge_covered_once': True,
            'all_zero_steps_remain_zero_work_events': True,
            'max_independent_prefix_window_difference_J': max_difference,
            'archived_chronological_arrays_reproduced': True},
        'interpretation': 'A signed reference-relative F dx path integral. The positive net reconstruction deficit is observed in this record, not asserted for every curve or interpreted as measurement uncertainty.'}
    write_json(OUT / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow-directory', type=Path,
                        default=ROOT / 'validation/workflow_results/cyclic_path')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = quantify(args.workflow_directory.resolve())
    print(json.dumps({k: summary[k] for k in ['source_points', 'exact_monotone_branches',
          'reference_signed_path_work_J', 'signed_terminal_reference_minus_reconstruction_J',
          'maximum_error_percent_of_absolute_net_reference_work', 'deadband_diagnostic']}, indent=2))


if __name__ == '__main__':main()
