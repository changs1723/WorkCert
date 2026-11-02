"""Attach query/error metadata to indices selected by another algorithm."""
import numpy as np
from .core import ReducedResponse, certify, _aligned, _retained_global_maximum


def from_indices(x, force, indices, *, x_unit="unspecified", force_unit="unspecified", provenance=None):
    """Construct a response from any valid endpoint-preserving vertex subset.

    This lets external simplifiers choose the nodes while WorkCert evaluates
    their reconstruction errors and provides work queries and persistence.
    """
    if provenance is not None and not isinstance(provenance, dict):
        raise ValueError("provenance must be a JSON object")
    error = certify(x, force, indices)
    ids = np.asarray(indices, dtype=np.int64)
    xx, ff = np.asarray(x, dtype=float), np.asarray(force, dtype=float)
    return ReducedResponse(xx[ids], ff[ids], ids, error, x_unit=x_unit, force_unit=force_unit,
                           metadata={"selection_method": "external_indices", "provenance": provenance or {},
                                     "retained_global_maximum": _retained_global_maximum(xx, ff, ids)})


def indices_from_coordinates(x, force, coordinates):
    """Map unchanged (x, force) vertices returned by an external simplifier.

    Every coordinate must exactly match a source vertex. Endpoints, increasing
    order and distinct vertices are required; no rounding, nearest-neighbor
    snapping, interpolation or reordering is implicit.
    """
    xx, ff = _aligned(x, force)
    if np.iscomplexobj(coordinates):
        raise ValueError("coordinates must be real-valued source vertices")
    try:
        points = np.asarray(coordinates, dtype=float)
    except (ValueError, TypeError) as error:
        raise ValueError("coordinates must be numeric (x, force) pairs") from error
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 2 or not np.all(np.isfinite(points)):
        raise ValueError("coordinates must be finite (x, force) pairs")
    ids = np.searchsorted(xx, points[:, 0])
    if np.any(ids >= len(xx)):
        raise ValueError("Every coordinate must exactly match a source vertex")
    if (not np.array_equal(xx[ids], points[:, 0]) or
            not np.array_equal(ff[ids], points[:, 1])):
        raise ValueError("Every coordinate must exactly match a source vertex")
    if ids[0] != 0 or ids[-1] != len(xx) - 1 or np.any(np.diff(ids) <= 0):
        raise ValueError("Returned coordinates must include endpoints in increasing source order")
    return ids.astype(np.int64)
