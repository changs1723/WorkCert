"""Reject cyclic-path use when any branch has an unmet or unknown tolerance.

This application example wraps WorkCert 0.3.0 without changing its runtime.
The branch composer combines reconstruction errors in sequential float64;
neither its summaries nor this acceptance policy enclose arithmetic error.
"""
from __future__ import annotations

import importlib.util
import math
from numbers import Real
from pathlib import Path

_COMPOSER = Path(__file__).resolve().parents[1] / 'examples/compose_branch_errors.py'
_spec = importlib.util.spec_from_file_location('_workcert_branch_composer', _COMPOSER)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class PathToleranceError(ValueError):
    """The requested branch tolerances are not all established."""

    def __init__(self, report):
        self.report = report
        super().__init__('Path rejected: unmet or unknown branch tolerances: ' +
                         ', '.join(map(str, report['failed_branch_ids'])))


def _nonnegative(value):
    return (isinstance(value, Real) and not isinstance(value, bool) and
            math.isfinite(value) and value >= 0.)


def _branch_status(record):
    reasons = []
    if record.get('tolerance_met') is not True:
        reasons.append('tolerance_met is not explicitly True')
    kind = record.get('certificate_for_stopping')
    request = record.get('requested_tolerance')
    relative = record.get('relative_tolerance')
    bounds = record.get('bounds')
    observed = None
    valid_kind = isinstance(kind, str) and kind in ('eta', 'xi', 'prefix', 'window')
    if not valid_kind:
        reasons.append('missing or invalid stopping measure')
    if not _nonnegative(request):
        reasons.append('missing or invalid requested tolerance')
    if not isinstance(relative, bool):
        reasons.append('missing or invalid relative_tolerance flag')
    if not valid_kind or not isinstance(bounds, dict) or not _nonnegative(bounds.get(kind)):
        reasons.append('missing or invalid observed reconstruction error')
    else:
        observed = float(bounds[kind])
        # Stored primitive extrema must agree with their derived error measure.
        if kind == 'window' and observed != record['maximum'] - record['minimum']:
            reasons.append('window error disagrees with primitive extrema')
        if kind == 'prefix' and observed != max(abs(record['minimum']), abs(record['maximum'])):
            reasons.append('prefix error disagrees with primitive extrema')
        if kind in ('eta', 'xi') and observed < record['maximum'] - record['minimum']:
            reasons.append('area bound is smaller than the primitive range')
    if relative is True:
        reference = record.get('reference_work')
        if (not isinstance(reference, Real) or isinstance(reference, bool) or
                not math.isfinite(reference) or reference == 0.):
            reasons.append('relative tolerance requires finite nonzero reference work')
            observed = None
        elif observed is not None:
            observed /= abs(reference)
    if observed is not None and _nonnegative(request) and observed > request:
        reasons.append('observed error exceeds requested tolerance')
    return {'branch_id': record['branch_id'], 'tolerance_met': not reasons,
            'stopping_measure': kind, 'relative_tolerance': relative,
            'requested_tolerance': request, 'observed_error': observed,
            'reasons': reasons}


def compose_checked_path(records, *, source_points, work_unit, strict=True):
    """Compose an ordered path and require every prescribed branch tolerance.

    Branch records contain the original directed-error summary plus branch_id,
    work_unit, bounds, reference_work, certificate_for_stopping,
    requested_tolerance, relative_tolerance, and tolerance_met. The latter four
    are copied from the serialized table metadata, never inferred from a cap.
    Explicit zero-work events retain source-edge coverage but need no tolerance.

    By default any failed/unknown branch raises PathToleranceError before the
    caller receives a usable combined summary. strict=False is for diagnostic
    reporting only; it preserves failed IDs and valid_for_downstream_use=False.
    The reported tolerance_met means all local budgets were met, not that a
    user-specified global relative path error has been met.
    """
    if not isinstance(strict, bool):
        raise ValueError('strict must be boolean')
    if not isinstance(work_unit, str) or not work_unit.strip():
        raise ValueError('work_unit must be a nonempty string')
    records = list(records)
    if any(record.get('work_unit') != work_unit for record in records):
        raise ValueError('Every record must use the same explicit work unit')
    # Structural validation and complete chronological edge coverage happen
    # even in diagnostic mode. It is never permissible to skip a failed branch.
    errors = _module.compose_branch_errors(records, source_points=source_points)
    statuses, seen = [], set()
    for record in records:
        if record['direction'] == 0:
            continue
        branch = record.get('branch_id')
        if isinstance(branch, bool) or not isinstance(branch, int) or branch < 0 or branch in seen:
            raise ValueError('Every branch must have a unique nonnegative integer ID')
        seen.add(branch)
        statuses.append(_branch_status(record))
    failed = [status['branch_id'] for status in statuses if not status['tolerance_met']]
    report = {'schema': 'workcert.checked-cyclic-path/1.0', 'work_unit': work_unit,
              'tolerance_met': not failed, 'valid_for_downstream_use': not failed,
              'failed_branch_ids': failed, 'branch_status': statuses,
              'error_summary': errors,
              'acceptance_scope': 'all prescribed local branch budgets',
              'arithmetic_rounding_enclosed': False}
    if strict and failed:
        raise PathToleranceError(report)
    return report
