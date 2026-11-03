"""Export and independently read a point-budgeted nonlinear connector table.

This is an input-data round trip on the monotone loading domain, not a finite
element analysis or an unloading constitutive model. The 33-point budget is
selected by this example; it is not an Abaqus point limit.
"""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'software/src'))
from workcert import reduce_response


def primitive(x, f, q):
    """Independent piecewise-linear primitive used by the table consumer."""
    prefix = np.r_[0., np.cumsum(np.diff(x) * (f[:-1] + f[1:]) / 2)]
    j = np.minimum(np.searchsorted(x, q, side='right') - 1, len(x) - 2)
    h = q - x[j]
    return prefix[j] + f[j] * h + (f[j+1] - f[j]) / np.diff(x)[j] * h*h / 2


def reference_errors(reference, x, f):
    """Evaluate residual extrema from exported columns, without WorkCert queries."""
    rx, rf = reference.T
    residual = rf - np.interp(rx, x, f)
    critical = list(rx)
    for a, b, u, v in zip(rx[:-1], rx[1:], residual[:-1], residual[1:]):
        if u * v < 0:
            critical.append(a - u * (b - a) / (v - u))
    critical = np.sort(np.asarray(critical))
    difference = primitive(rx, rf, critical) - primitive(x, f, critical)
    return dict(delta=float(np.max(np.abs(residual))),
                prefix=float(np.max(np.abs(difference))),
                window=float(np.max(difference) - np.min(difference)))


def main():
    out = ROOT / 'validation/connector_results'
    out.mkdir(exist_ok=True)
    data = np.loadtxt(ROOT / 'data/prepared/PLA_STWC-1.csv', delimiter=',', skiprows=1)
    tab = reduce_response(data[:, 0], data[:, 1], method='vertical', max_points=33,
                          x_unit='mm', force_unit='kN')
    text = ('** WorkCert loading-branch data exchange; force kN, displacement mm\n'
            '** Application-selected point budget: 33; original source retained\n'
            '*CONNECTOR BEHAVIOR, NAME=WORKCERT_STWC1\n'
            '*CONNECTOR ELASTICITY, COMPONENT=1, NONLINEAR\n')
    text += ''.join('%.17g, %.17g\n' % (f, x) for x, f in zip(tab.x, tab.force))
    path = out / 'STWC1_connector.inp'
    path.write_text(text, encoding='ascii')
    # Read the consumer format without using WorkCert's JSON loader or queries.
    values = np.asarray([[float(t) for t in line.split(',')]
                         for line in path.read_text().splitlines() if not line.startswith('*')])
    f, x = values[:, 0], values[:, 1]
    assert np.array_equal(x, tab.x) and np.array_equal(f, tab.force)
    q = np.array([10., 20., 30., 40.])
    ea = primitive(x, f, q)
    dense = primitive(data[:, 0], data[:, 1], q)
    assert np.all(np.abs(ea - dense) <= tab.certificate.prefix + 1e-12)
    assert np.allclose(ea, tab.work(q), rtol=0., atol=1e-12)
    independent = reference_errors(data, x, f)
    for name, expected in independent.items():
        assert np.isclose(getattr(tab.certificate, name), expected, rtol=0., atol=1e-10)
    tab.save(out / 'STWC1_table.json')
    result = {'status': 'PASS', 'source_nodes': len(data), 'point_budget': 33,
              'selector': 'vertical',
              'retained_points': len(x), 'strokes_mm': q.tolist(),
              'consumer_EA_J': ea.tolist(), 'actual_EA_errors_J': (ea-dense).tolist(),
              'stored_prefix_bound_J': tab.certificate.prefix,
              'stored_window_bound_J': tab.certificate.window,
              'maximum_force_error_kN': tab.certificate.delta,
              'independent_export_checks': independent,
              'domain_mm': [float(x[0]), float(x[-1])],
              'scope': 'Independent write/read check of a 33-point force-displacement input table over the measured monotone loading branch. The domain is the source displacement interval, not an unloading law or a solver-specific point limit.',
              'format_documentation': 'https://help.3ds.com/2025/English/DSSIMULIA_Established/SIMACAEELMRefMap/simaelm-c-connelastbehav.htm'}
    (out / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':main()
