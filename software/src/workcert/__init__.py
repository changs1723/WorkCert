"""Reconstruction error metadata and reusable piecewise-linear work queries."""
from .core import Certificate, ReducedResponse, certify, reduce_response
from .preprocessing import BranchSeries, MonotoneBranch, ZeroDisplacementEvent, split_monotone_branches
from .interop import from_indices, indices_from_coordinates

ErrorMetadata = Certificate
__version__ = "0.3.0"
__all__ = ["Certificate", "ErrorMetadata", "ReducedResponse", "certify", "reduce_response",
           "BranchSeries", "MonotoneBranch", "ZeroDisplacementEvent", "split_monotone_branches", "from_indices", "indices_from_coordinates", "__version__"]

