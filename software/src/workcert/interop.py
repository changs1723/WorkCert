"""Attach query/error metadata to indices selected by another algorithm."""
import numpy as np
from .core import ReducedResponse, certify


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
                           metadata={"selection_method": "external_indices", "provenance": provenance or {}})
