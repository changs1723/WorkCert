"""Independent acceptance arithmetic and audit rows; no WorkCert imports.

Authorship: Codex, assigned the Hou acceptance role on 2026-11-03.
Human authorship/review is deliberately not asserted.
"""
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import unittest

ROWS = []


def rational(value):
    return value if isinstance(value, Fraction) else Fraction(str(value))


def pl_value(x, f, q):
    x, f, q = list(map(rational, x)), list(map(rational, f)), rational(q)
    if not x[0] <= q <= x[-1]:
        raise ValueError('outside independent reference')
    for a, b, u, v in zip(x, x[1:], f, f[1:]):
        if a <= q <= b:
            return u + (v-u)*(q-a)/(b-a)
    raise AssertionError('no segment')


def pl_integral(x, f, a, b):
    """Clip each line to [a,b], then sum exact rational trapezoids."""
    x, f, a, b = list(map(rational, x)), list(map(rational, f)), rational(a), rational(b)
    if b < a:
        return -pl_integral(x, f, b, a)
    if not x[0] <= a <= b <= x[-1]:
        raise ValueError('outside independent reference')
    total = Fraction(0)
    for left, right, u, v in zip(x, x[1:], f, f[1:]):
        lo, hi = max(left, a), min(right, b)
        if hi > lo:
            slope = (v-u)/(right-left)
            total += (hi-lo)*(2*u+slope*(lo+hi-2*left))/2
    return total


def exact_errors(x, f, indices):
    """Integrate residual lobes split at rational zeros, retaining all extrema.

    This is an independent mathematical oracle, never calling the package.
    """
    x, f = list(map(rational, x)), list(map(rational, f))
    rx, rf = [x[i] for i in indices], [f[i] for i in indices]
    residual = [y-pl_value(rx, rf, t) for t, y in zip(x, f)]
    cuts = set(x)
    for a, b, u, v in zip(x, x[1:], residual, residual[1:]):
        if u*v < 0:
            cuts.add(a-u*(b-a)/(v-u))
    cuts = sorted(cuts)
    lobes = [pl_integral(x, residual, a, b) for a, b in zip(cuts, cuts[1:])]
    cumulative = [Fraction(0)]
    for area in lobes:
        cumulative.append(cumulative[-1]+area)
    eta, terminal = sum(map(abs, lobes)), cumulative[-1]
    low, high = min(cumulative), max(cumulative)
    return dict(eta=eta, xi=(eta+abs(terminal))/2, prefix=max(abs(low),abs(high)),
                window=high-low, delta=max(map(abs,residual)),
                signed_terminal_error=terminal, min_cumulative_error=low,
                max_cumulative_error=high, reference_work=pl_integral(x,f,x[0],x[-1])), dict(zip(cuts,cumulative))


def prefix_peak(x, f, q):
    return max([rational(v) for t,v in zip(x,f) if rational(t) <= rational(q)] + [pl_value(x,f,q)])


def record(row):
    ROWS.append(row)
    path = os.environ.get('HOU_RESULTS_JSONL')
    if path:
        with Path(path).open('a',encoding='utf8') as stream:
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')


class AcceptanceCase(unittest.TestCase):
    def check(self, label, expected, actual, atol=1e-12, rtol=0):
        e, a = float(expected), float(actual)
        difference = a-e
        tolerance = atol+rtol*abs(e)
        passed = math.isfinite(a) and math.isfinite(e) and abs(difference) <= tolerance
        record(dict(test=self.id(),check=label,expected=str(expected),actual=str(actual),
                    difference=str(difference),atol=atol,rtol=rtol,tolerance=tolerance,
                    status='PASS' if passed else 'FAIL'))
        self.assertTrue(passed, '%s: expected %s, got %s, difference %s, tolerance %s' % (label,expected,actual,difference,tolerance))

    def check_true(self, label, condition, expected='True', actual=None):
        passed = bool(condition)
        record(dict(test=self.id(),check=label,expected=str(expected),actual=str(condition if actual is None else actual),
                    difference='' if passed else 'mismatch',atol=0,rtol=0,tolerance=0,status='PASS' if passed else 'FAIL'))
        self.assertTrue(passed,label)

    def expect_rejected(self, label, operation, exception=ValueError):
        try:
            operation()
        except exception as error:
            self.check_true(label,True,expected=exception.__name__,actual=type(error).__name__+': '+str(error))
        except Exception as error:
            self.check_true(label,False,expected=exception.__name__,actual=type(error).__name__+': '+str(error))
        else:
            self.check_true(label,False,expected=exception.__name__,actual='accepted')
