"""Chronological branch extraction without folding a cyclic response."""
from dataclasses import dataclass
import numpy as np
from .core import _reference_hash


def _immutable(values, dtype=float):
    array = np.asarray(values, dtype=dtype)
    return np.frombuffer(array.tobytes(), dtype=array.dtype)


@dataclass(frozen=True)
class ZeroDisplacementEvent:
    source_start: int
    source_end: int
    displacement: float
    start_force: float
    end_force: float


@dataclass(frozen=True)
class MonotoneBranch:
    """Ascending query coordinates, with the original chronological direction."""
    x: np.ndarray
    force: np.ndarray
    source_indices: np.ndarray
    direction: int
    start_x: float
    end_x: float
    reference_sha256: str

    def directed_work(self, response, q=None):
        """Physical F dx from chronological start to q (default: branch end)."""
        if response.x[0] != self.x[0] or response.x[-1] != self.x[-1]:
            raise ValueError("The response domain does not match this branch")
        if response.certificate.reference_sha256 != self.reference_sha256:
            raise ValueError("The response source does not match this branch")
        return response.work(self.end_x if q is None else q) - response.work(self.start_x)


@dataclass(frozen=True)
class BranchSeries:
    branches: tuple
    events: tuple
    reference_work: float
    source_points: int


def split_monotone_branches(displacement, force, *, duplicate_policy="split"):
    """Partition a finite chronological path at every reversal or exact dwell.

    Reversal nodes belong to both adjacent branches. Equal-coordinate pairs
    remain explicit zero-work events, including force changes at a dwell.
    No noise threshold, smoothing or contact detection is applied. Use an
    explicitly documented preparation before this function when needed.
    """
    if duplicate_policy not in ("split", "error"):
        raise ValueError("duplicate_policy must be split or error")
    if np.iscomplexobj(displacement) or np.iscomplexobj(force):
        raise ValueError("Inputs must be real-valued")
    try:
        x, f = np.asarray(displacement, dtype=float), np.asarray(force, dtype=float)
    except (ValueError, TypeError) as error:
        raise ValueError("Inputs must be numeric") from error
    if x.ndim != 1 or f.ndim != 1 or len(x) != len(f) or len(x) < 2:
        raise ValueError("Inputs must be aligned one-dimensional arrays with at least two points")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(f)):
        raise ValueError("Inputs must be finite")
    with np.errstate(over="raise", invalid="raise"):
        try:
            dx = np.diff(x)
            reference_work = float(np.sum(dx * (0.5 * f[:-1] + 0.5 * f[1:])))
        except FloatingPointError as error:
            raise ValueError("The path exceeds float64 limits") from error
    if duplicate_policy == "error" and np.any(dx == 0):
        raise ValueError("Equal displacement samples require duplicate_policy='split'")
    branches, events = [], []
    def append(first, last):
        if last <= first:
            return
        direction = 1 if x[last] > x[first] else -1
        ids = np.arange(first, last + 1) if direction > 0 else np.arange(last, first - 1, -1)
        branches.append(MonotoneBranch(_immutable(x[ids]), _immutable(f[ids]),
                        _immutable(ids, np.int64), direction, float(x[first]), float(x[last]),
                        _reference_hash(x[ids], f[ids])))
    first, direction = 0, 0
    for i, delta in enumerate(dx):
        sign = int(np.sign(delta))
        if sign == 0:
            append(first, i)
            events.append(ZeroDisplacementEvent(i, i + 1, float(x[i]), float(f[i]), float(f[i + 1])))
            first, direction = i + 1, 0
        elif direction and sign != direction:
            append(first, i)
            first, direction = i, sign
        else:
            direction = sign
    append(first, len(x) - 1)
    return BranchSeries(tuple(branches), tuple(events), reference_work, len(x))
