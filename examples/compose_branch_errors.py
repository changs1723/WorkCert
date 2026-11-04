"""Compose chronological work-error metadata without loading reference curves.

Each branch supplies the terminal value and extrema of its cumulative error
primitive in ascending displacement coordinates. Direction -1 starts at the
upper endpoint, so its chronological primitive is D(x)-D(U), not -D(x).
Zero-displacement events contribute zero work and remain explicit in coverage.

Example:
    python examples/compose_branch_errors.py validation/cyclic_round2_results/branch_error_manifest.json

The pure function uses the standard library only. It combines producer-supplied
errors; their validity relative to the reference is checked at construction.
The composition identities hold in real arithmetic. This example evaluates
them with sequential binary floating-point operations; the returned metadata
does not include a bound for arithmetic rounding.
"""
import argparse
import json
import math
from numbers import Real
from pathlib import Path


def compose_branch_errors(records, *, source_points=None):
    """Compute prefix/window errors from ordered, directed error summaries.

    Record fields are direction (+1/-1/0), terminal, minimum and maximum.
    A direction-zero record must have kind='zero_work_event' and zero errors.
    Optional source_start/source_end fields identify chronological vertex
    indices; if source_points is supplied, their complete edge coverage is
    required. All errors must use one common work unit. Each supplied interval
    must contain zero and its terminal error; these ordering conditions are
    checked directly, without a unit-dependent numerical tolerance.
    """
    d = lo = hi = 0.
    previous_end = 0
    branches = events = 0
    if source_points is not None and (isinstance(source_points, bool) or
            not isinstance(source_points, int) or source_points < 2):
        raise ValueError('source_points must be an integer of at least two')
    for record in records:
        direction = record['direction']
        if isinstance(direction, bool) or not isinstance(direction, int) or direction not in (-1, 0, 1):
            raise ValueError('Each direction must be -1, 0 or +1')
        values = [record[key] for key in ('terminal', 'minimum', 'maximum')]
        if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in values):
            raise ValueError('Error summaries must be finite real numbers')
        bd, bl, bh = map(float, values)
        if not bl <= min(0., bd) <= max(0., bd) <= bh:
            raise ValueError('Extrema must contain the initial and terminal error')
        if source_points is not None:
            first, last = record['source_start'], record['source_end']
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (first, last)):
                raise ValueError('Chronological source indices must be integers')
            if first != previous_end or not first < last < source_points:
                raise ValueError('Records must cover chronological edges exactly once in order')
            previous_end = last
        if direction == 0:
            if record.get('kind') != 'zero_work_event' or (bd, bl, bh) != (0., 0., 0.):
                raise ValueError('A zero-work event must have zero error metadata')
            if source_points is not None and last != first + 1:
                raise ValueError('Each zero-work event must cover one chronological edge')
            events += 1
        else:
            if direction == -1:bd, bl, bh = -bd, bl-bd, bh-bd
            lo, hi, d = min(lo, d+bl), max(hi, d+bh), d+bd
            if not all(math.isfinite(v) for v in (d, lo, hi)):
                raise ValueError('Combined errors exceed floating-point limits')
            branches += 1
    if source_points is not None and previous_end != source_points - 1:
        raise ValueError('The chronological record sequence is incomplete')
    window = hi-lo
    if not math.isfinite(window):
        raise ValueError('The combined window error exceeds floating-point limits')
    return {'signed_terminal_error': d, 'minimum_cumulative_error': lo,
            'maximum_cumulative_error': hi, 'prefix': max(abs(lo), abs(hi)),
            'window': window, 'branches': branches, 'zero_work_events': events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    if manifest.get('schema') != 'workcert.directed-error-sequence/1.0':
        raise ValueError('Unsupported directed error sequence')
    result = compose_branch_errors(manifest['records'], source_points=manifest['source_points'])
    result['work_unit'] = manifest['work_unit']
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':main()
