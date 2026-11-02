"""Check revised core against frozen references and selector controls."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'software/src'))
sys.path.insert(0, str(ROOT / 'validation'))
from workcert import ReducedResponse, indices_from_coordinates, reduce_response
from baselines import vw_indices


def main():
    vw_cases = unchanged_cases = peak_queries = 0
    for path in sorted((ROOT / 'data/prepared').glob('*.csv')):
        values = np.genfromtxt(path, delimiter=',', skip_header=1)
        x, f = values[:, 0], values[:, 1]
        peak = int(np.argmax(np.abs(f)))
        for budget in (9, 17, 33, 65, 129):
            current = reduce_response(x, f, method='vw', max_points=budget)
            expected = vw_indices(x, f, budget, anchors=[peak])
            np.testing.assert_array_equal(current.indices, expected)
            np.testing.assert_array_equal(indices_from_coordinates(x, f, np.column_stack([current.x, current.force])), expected)
            assert current.verify_reference(x, f)
            vw_cases += 1
        for method in ('work', 'vertical'):
            for budget in (9, 33, 129):
                current = reduce_response(x, f, method=method, max_points=budget)
                frozen = ReducedResponse.load(ROOT / 'validation/results_v02/tables/fixed' /
                    (path.stem + '__' + method + '__' + str(budget) + '.json'))
                np.testing.assert_array_equal(current.indices, frozen.indices)
                assert current.certificate == frozen.certificate
                assert frozen.verify_reference(x, f)
                # Test complete continuous-domain peak extrema through all
                # reference nodes plus every original cell midpoint.
                q = np.sort(np.r_[x, (x[:-1]+x[1:])/2])
                actual = np.maximum(np.maximum.accumulate(f)[np.searchsorted(x, q, side='right')-1], np.interp(q, x, f))
                lower, upper = current.peak_bounds(q)
                assert np.all(lower <= actual + 1e-10) and np.all(upper >= actual - 1e-10)
                peak_queries += len(q)
                unchanged_cases += 1
    old_files = sorted((ROOT / 'validation/compatibility/v01').glob('*.json'))[:15]
    for path in old_files:
        response = ReducedResponse.load(path)
        assert response.metadata.get('retained_global_maximum') is None
        lo, hi = response.peak_bounds(response.x[-1])
        assert lo <= hi
    report = {'status': 'PASS', 'core_sha256': hashlib.sha256((ROOT / 'software/src/workcert/core.py').read_bytes()).hexdigest(),
              'vw_reference_budget_cases_matching_benchmark': vw_cases,
              'coordinate_adapter_exact_roundtrip_cases': vw_cases,
              'work_vertical_frozen_selection_and_error_cases': unchanged_cases,
              'signed_prefix_peak_bound_queries': peak_queries,
              'old_v01_JSON_files_loaded': len(old_files),
              'compatibility_fixture_directory': 'validation/compatibility/v01',
              'note': 'No random measurement uncertainty, author manual review or remote CI is inferred from these automated controls.'}
    assert vw_cases == 350 and unchanged_cases == 420 and len(old_files) == 15
    (ROOT / 'validation/results_v02/core_round2_verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':main()
