"""Analytical reconstruction error metadata for a supplied PL reference.

All calculations use NumPy float64. Bounds concern the supplied numerical
reference; they do not include measurement error or outward-rounded arithmetic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import heapq
import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

SCHEMA = "workcert.response/1.0"
VERSION = "0.2.0"
BOUND_NAMES = ("eta", "xi", "prefix", "window")


def _aligned(x, force):
    if np.iscomplexobj(x) or np.iscomplexobj(force):
        raise ValueError("x and force must be real-valued")
    try:
        x = np.asarray(x, dtype=np.float64)
        f = np.asarray(force, dtype=np.float64)
    except (ValueError, TypeError) as error:
        raise ValueError("x and force must be numeric arrays") from error
    if x.ndim != 1 or f.ndim != 1 or len(x) != len(f) or len(x) < 2:
        raise ValueError("x and force must be aligned one-dimensional arrays with at least two points")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(f)):
        raise ValueError("x and force must contain finite values")
    with np.errstate(over="ignore", invalid="ignore"):
        widths = np.diff(x)
    if not np.all(np.isfinite(widths)) or not np.all(widths > 0) or not np.isfinite(x[-1] - x[0]):
        raise ValueError("x must be strictly increasing with a finite domain span")
    return x.copy(), f.copy()


def _indices(indices, n):
    raw = np.asarray(indices)
    if raw.ndim != 1 or raw.dtype.kind not in "iu" or raw.dtype.kind == "b":
        raise ValueError("indices must be a one-dimensional integer array")
    result = raw.astype(np.int64)
    if len(result) < 2 or result[0] != 0 or result[-1] != n - 1:
        raise ValueError("indices must include both reference endpoints")
    if np.any(np.diff(result) <= 0) or np.any(result < 0) or np.any(result >= n):
        raise ValueError("indices must be unique, increasing and within the reference")
    return result


def _primitive_at_nodes(x, f):
    with np.errstate(over="raise", invalid="raise"):
        return np.r_[0.0, np.cumsum(np.diff(x) * (0.5 * f[:-1] + 0.5 * f[1:]))]


def _reference_hash(x, f):
    digest = hashlib.sha256()
    digest.update(b"workcert-reference-float64-le-v1\0")
    digest.update(np.asarray([len(x)], dtype="<u8").tobytes())
    digest.update(np.asarray(x, dtype="<f8").tobytes())
    digest.update(np.asarray(f, dtype="<f8").tobytes())
    return digest.hexdigest()


def _absolute_area(x, r):
    h = np.diff(x)
    a, b = np.abs(r[:-1]), np.abs(r[1:])
    area = h * (0.5 * a + 0.5 * b)
    crossing = (r[:-1] < 0) & (r[1:] > 0) | (r[:-1] > 0) & (r[1:] < 0)
    scale = np.maximum(a[crossing], b[crossing])
    aa, bb = a[crossing] / scale, b[crossing] / scale
    area[crossing] = h[crossing] * scale * 0.5 * (aa * aa + bb * bb) / (aa + bb)
    return float(np.sum(area))


_ZERO = (0.0, 0.0, 0.0, 0.0, 0.0)


def _summary(x, r):
    """Area, terminal primitive, minimum, maximum and force residual."""
    d = _primitive_at_nodes(x, r)
    lo, hi = float(np.min(d)), float(np.max(d))
    crosses = np.flatnonzero(((r[:-1] < 0) & (r[1:] > 0)) |
                            ((r[:-1] > 0) & (r[1:] < 0)))
    if len(crosses):
        t = -r[crosses] / (r[crosses + 1] - r[crosses])
        stationary = d[crosses] + (x[crosses + 1] - x[crosses]) * t * r[crosses] * 0.5
        lo, hi = min(lo, float(np.min(stationary))), max(hi, float(np.max(stationary)))
    return (_absolute_area(x, r), float(d[-1]), lo, hi, float(np.max(np.abs(r))))


def _concatenate(a, b):
    return (a[0] + b[0], a[1] + b[1], min(a[2], a[1] + b[2]),
            max(a[3], a[1] + b[3]), max(a[4], b[4]))


class _Node:
    __slots__ = ("key", "value", "left", "right", "height", "total")

    def __init__(self, key, value):
        self.key, self.value = key, value
        self.left = self.right = None
        self.height, self.total = 1, value


def _height(node):
    return node.height if node is not None else 0


def _refresh(node):
    node.height = 1 + max(_height(node.left), _height(node.right))
    node.total = _concatenate(_concatenate(node.left.total if node.left else _ZERO,
                                          node.value), node.right.total if node.right else _ZERO)
    return node


def _rotate(node, left):
    child = node.right if left else node.left
    if left:
        node.right, child.left = child.left, node
    else:
        node.left, child.right = child.right, node
    _refresh(node)
    return _refresh(child)


def _balance(node):
    _refresh(node)
    gap = _height(node.left) - _height(node.right)
    if gap > 1:
        if _height(node.left.left) < _height(node.left.right):
            node.left = _rotate(node.left, True)
        return _rotate(node, False)
    if gap < -1:
        if _height(node.right.right) < _height(node.right.left):
            node.right = _rotate(node.right, False)
        return _rotate(node, True)
    return node


def _put(node, key, value):
    if node is None:
        return _Node(key, value)
    if key < node.key:
        node.left = _put(node.left, key, value)
    elif key > node.key:
        node.right = _put(node.right, key, value)
    else:
        node.value = value
    return _balance(node)


def _delete(node, key):
    if node is None:
        raise RuntimeError("Missing active segment")
    if key < node.key:
        node.left = _delete(node.left, key)
    elif key > node.key:
        node.right = _delete(node.right, key)
    else:
        if node.left is None:
            return node.right
        if node.right is None:
            return node.left
        following = node.right
        while following.left is not None:
            following = following.left
        node.key, node.value = following.key, following.value
        node.right = _delete(node.right, following.key)
    return _balance(node)


def _certificate(summary, reference_work, n, digest):
    eta, terminal, lo, hi, delta = summary
    return Certificate(eta, (eta + abs(terminal)) * .5, max(abs(lo), abs(hi)),
                       hi - lo, delta, terminal, reference_work, lo, hi, n, digest)


@dataclass(frozen=True)
class Certificate:
    """Native-product-unit work bounds and force residual maximum.

    ``prefix`` is max(abs(D)); ``window`` is max(D)-min(D), where D is
    the reference minus reconstructed cumulative work. ``eta`` and ``xi``
    are absolute-area and sign-informed bounds. ``delta`` has force units.
    """
    eta: float
    xi: float
    prefix: float
    window: float
    delta: float
    signed_terminal_error: float
    reference_work: float
    min_cumulative_error: float
    max_cumulative_error: float
    reference_points: int
    reference_sha256: str

    def bound(self, kind="prefix", relative=False):
        if kind not in BOUND_NAMES:
            raise ValueError("certificate must be one of " + ", ".join(BOUND_NAMES))
        value = float(getattr(self, kind))
        if relative:
            if self.reference_work == 0:
                raise ValueError("Relative bounds require nonzero reference terminal work; use absolute units")
            value /= abs(self.reference_work)
        return value

    def to_dict(self):
        return asdict(self)


def certify(x, force, indices):
    """Evaluate analytic continuous-domain bounds for a vertex-subset PL curve.

    Signed forces are accepted. Indices must include both endpoints, be sorted
    and unique. Extrema include all residual zero crossings, not just nodes.
    """
    x, f = _aligned(x, force)
    ids = _indices(indices, len(x))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            r = f - np.interp(x, x[ids], f[ids])
            eta, terminal, lo, hi, delta = _summary(x, r)
            work = float(_primitive_at_nodes(x, f)[-1])
            values = [eta, (eta + abs(terminal)) * 0.5, max(abs(lo), abs(hi)),
                      hi - lo, delta, terminal, work, lo, hi]
    except FloatingPointError as error:
        raise ValueError("The response exceeds finite float64 calculation limits") from error
    if not np.all(np.isfinite(values)):
        raise ValueError("The response exceeds finite float64 calculation limits")
    return Certificate(*values, len(x), _reference_hash(x, f))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf8")


class ReducedResponse:
    """Retained response table, query primitives, provenance and certificates."""
    def __init__(self, x, force, indices, certificate, *, x_unit="unspecified", force_unit="unspecified", metadata=None):
        self._x, self._f = _aligned(x, force)
        if not isinstance(certificate, Certificate):
            raise ValueError("certificate must be a Certificate")
        self._indices = _indices(indices, certificate.reference_points)
        if len(self._indices) != len(self._x):
            raise ValueError("One reference index is required per retained point")
        self._certificate = certificate
        self._validate_certificate()
        for value in (x_unit, force_unit):
            if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
                raise ValueError("Unit labels must be nonempty single-line strings")
        self._x_unit, self._force_unit = x_unit, force_unit
        try:
            self._metadata = json.loads(_canonical(metadata or {}))
        except (TypeError, ValueError) as error:
            raise ValueError("metadata must contain finite JSON-serializable values") from error
        if not isinstance(self._metadata, dict):
            raise ValueError("metadata must be a JSON object")
        try:
            self._slope = np.diff(self._f) / np.diff(self._x)
            self._primitive = _primitive_at_nodes(self._x, self._f)
        except FloatingPointError as error:
            raise ValueError("The reduced table exceeds float64 limits") from error
        if not np.all(np.isfinite(self._slope)) or not np.all(np.isfinite(self._primitive)):
            raise ValueError("The reduced table exceeds float64 limits")
        # Cancellation can make terminal work tiny even when signed component
        # work is large. Scale this consistency check by the retained absolute
        # force quadrature as well as by the reported residual bounds.
        scale = max(1.0, abs(certificate.reference_work), certificate.eta,
                    abs(float(_primitive_at_nodes(self._x, np.abs(self._f))[-1])))
        if abs(certificate.reference_work - self._primitive[-1] - certificate.signed_terminal_error) > np.finfo(float).eps * scale * 256:
            raise ValueError("Retained terminal work is inconsistent with its certificate")
        # Bytes-backed arrays cannot be made writable again with setflags.
        # This keeps public coordinates and cached query primitives coherent.
        self._x = np.frombuffer(self._x.tobytes(), dtype=np.float64)
        self._f = np.frombuffer(self._f.tobytes(), dtype=np.float64)
        self._indices = np.frombuffer(self._indices.tobytes(), dtype=np.int64)

    def _validate_certificate(self):
        c = self._certificate
        numbers = [getattr(c, field) for field in ("eta", "xi", "prefix", "window", "delta",
                   "signed_terminal_error", "reference_work", "min_cumulative_error", "max_cumulative_error")]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) for v in numbers):
            raise ValueError("Certificate fields must be finite numbers")
        if any(getattr(c, name) < 0 for name in ("eta", "xi", "prefix", "window", "delta")):
            raise ValueError("Certificate bounds must be nonnegative")
        if not isinstance(c.reference_points, int) or isinstance(c.reference_points, bool) or c.reference_points < 2:
            raise ValueError("Invalid reference size")
        if not isinstance(c.reference_sha256, str) or len(c.reference_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in c.reference_sha256):
            raise ValueError("Invalid reference SHA-256")
        scale = max(1.0, c.eta, abs(c.reference_work))
        tol = np.finfo(float).eps * scale * 128
        if c.min_cumulative_error > tol or c.max_cumulative_error < -tol:
            raise ValueError("The cumulative-error range must contain zero")
        if (abs(c.xi - (c.eta + abs(c.signed_terminal_error)) * .5) > tol or
            abs(c.prefix - max(abs(c.min_cumulative_error), abs(c.max_cumulative_error))) > tol or
            abs(c.window - (c.max_cumulative_error - c.min_cumulative_error)) > tol or
            c.prefix > c.window + tol or c.window > c.xi + tol or c.xi > c.eta + tol or
            c.signed_terminal_error < c.min_cumulative_error - tol or
            c.signed_terminal_error > c.max_cumulative_error + tol):
            raise ValueError("Inconsistent certificate relationships")

    @property
    def x(self):
        return self._x

    @property
    def force(self):
        return self._f

    @property
    def indices(self):
        return self._indices

    @property
    def certificate(self):
        return self._certificate

    @property
    def metadata(self):
        return json.loads(_canonical(self._metadata))

    @property
    def x_unit(self):
        return self._x_unit

    @property
    def force_unit(self):
        return self._force_unit

    @property
    def work_unit(self):
        return {("mm", "kN"): "J", ("m", "N"): "J", ("m", "kN"): "kJ", ("mm", "N"): "mJ"}.get(
            (self.x_unit, self.force_unit), self.force_unit + "*" + self.x_unit)

    def _query(self, q):
        if np.iscomplexobj(q):
            raise ValueError("Queries must be real-valued")
        try:
            values = np.asarray(q, dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError("Queries must be numeric") from error
        if not np.all(np.isfinite(values)) or np.any(values < self._x[0]) or np.any(values > self._x[-1]):
            raise ValueError("Queries must be finite and lie inside the reference domain")
        return values

    def force_at(self, q):
        """Evaluate the retained PL force, with no extrapolation."""
        values = self._query(q)
        answer = np.interp(values.ravel(), self._x, self._f).reshape(values.shape)
        return float(answer) if answer.ndim == 0 else answer

    def work(self, q):
        """Integrate the retained PL force exactly from x[0] to q."""
        values = self._query(q)
        i = np.clip(np.searchsorted(self._x, values, side="right") - 1, 0, len(self._x) - 2)
        h = values - self._x[i]
        try:
            with np.errstate(over="raise", invalid="raise"):
                result = self._primitive[i] + h * (self._f[i] + .5 * self._slope[i] * h)
        except FloatingPointError as error:
            raise ValueError("The requested work exceeds finite float64 limits") from error
        return float(result) if result.ndim == 0 else result

    def window_work(self, a, b):
        """Integrate over broadcastable a <= b within the reference domain."""
        a, b = np.broadcast_arrays(self._query(a), self._query(b))
        if np.any(a > b):
            raise ValueError("Window start must not exceed window end")
        try:
            with np.errstate(over="raise", invalid="raise"):
                result = self.work(b) - self.work(a)
        except FloatingPointError as error:
            raise ValueError("The requested window work exceeds finite float64 limits") from error
        return float(result) if np.ndim(result) == 0 else result

    def _payload(self):
        return {"schema": SCHEMA, "software_version": VERSION,
                "x": self.x.tolist(), "force": self.force.tolist(), "indices": self.indices.tolist(),
                "units": {"displacement": self.x_unit, "force": self.force_unit, "work": self.work_unit},
                "certificate": self.certificate.to_dict(), "metadata": self.metadata}

    def to_bytes(self):
        """Return deterministic compact UTF-8 JSON with a payload checksum."""
        payload = self._payload()
        envelope = {"payload": payload, "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest()}
        return _canonical(envelope) + b"\n"

    def save(self, path):
        """Write a self-contained query table; the source reference is identified by hash."""
        Path(path).write_bytes(self.to_bytes())

    @classmethod
    def load(cls, path):
        """Read a query table and check its schema, checksum and internal invariants."""
        try:
            envelope = json.loads(Path(path).read_text(encoding="utf8"))
            if not isinstance(envelope, dict) or set(envelope) != {"payload", "payload_sha256"}:
                raise ValueError("Invalid response envelope")
            p = envelope["payload"]
            if hashlib.sha256(_canonical(p)).hexdigest() != envelope["payload_sha256"]:
                raise ValueError("Response payload checksum mismatch")
            if set(p) != {"schema", "software_version", "x", "force", "indices", "units", "certificate", "metadata"} or p["schema"] != SCHEMA:
                raise ValueError("Unsupported response schema")
            result = cls(p["x"], p["force"], p["indices"], Certificate(**p["certificate"]),
                         x_unit=p["units"]["displacement"], force_unit=p["units"]["force"], metadata=p["metadata"])
            if p["units"]["work"] != result.work_unit:
                raise ValueError("Inconsistent work-unit label")
            return result
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Malformed WorkCert response file") from error

    def verify_reference(self, x, force):
        """Recompute certificates against the supplied full source reference.

        A file checksum detects accidental changes. This method establishes
        consistency with the numerical reference available to the caller.
        """
        x, f = _aligned(x, force)
        if _reference_hash(x, f) != self.certificate.reference_sha256:
            raise ValueError("Reference checksum mismatch")
        if not np.array_equal(self.x, x[self.indices]) or not np.array_equal(self.force, f[self.indices]):
            raise ValueError("Retained coordinates do not match their reference indices")
        if certify(x, f, self.indices) != self.certificate:
            raise ValueError("Certificate does not match the supplied reference")
        return True


def _segment(x, f, a, b):
    if b - a < 2:
        return _ZERO, None
    r = f[a:b + 1] - np.interp(x[a:b + 1], [x[a], x[b]], [f[a], f[b]])
    split = a + 1 + int(np.argmax(np.abs(r[1:-1])))
    return _summary(x[a:b + 1], r), split


def _uniform(x, budget):
    grid = np.linspace(x[0], x[-1], budget)
    right = np.clip(np.searchsorted(x, grid), 0, len(x) - 1)
    left = np.maximum(right - 1, 0)
    selected = set(np.where(np.abs(x[left] - grid) < np.abs(x[right] - grid), left, right).tolist()) | {0, len(x) - 1}
    while len(selected) < budget:
        nodes = sorted(selected)
        _, a, b = max((x[b] - x[a], a, b) for a, b in zip(nodes[:-1], nodes[1:]) if b - a > 1)
        selected.add(a + 1 + int(np.argmin(np.abs(x[a + 1:b] - .5 * (x[a] + x[b])))))
    return selected


def reduce_response(x, force, *, max_points=33, tolerance=None, certificate="prefix", relative=False,
                    method=None, preserve_peak=True, peak_mode="absolute", x_unit="unspecified", force_unit="unspecified", provenance=None):
    """Construct an endpoint-preserving response table and evaluate work bounds.

    Adaptive ``work`` and ``vertical`` modes share the maximum vertical-residual
    split location but select intervals by absolute area or vertical deviation.
    Tolerance stopping evaluates the current representation at every step; the
    greedy sequence is not assumed monotone. An unmet tolerance is reported in
    metadata when the point limit is reached. Signed force values are retained.
    """
    x, f = _aligned(x, force)
    if isinstance(max_points, (bool, np.bool_)) or not isinstance(max_points, (int, np.integer)) or max_points < 2:
        raise ValueError("max_points must be an integer of at least two")
    if certificate not in BOUND_NAMES:
        raise ValueError("Unknown certificate")
    if method not in ("work", "vertical", "uniform", "uniform_peak"):
        raise ValueError("Choose method explicitly: work, vertical, uniform or uniform_peak")
    if peak_mode not in ("absolute", "positive", "negative"):
        raise ValueError("peak_mode must be absolute, positive or negative")
    if not isinstance(preserve_peak, (bool, np.bool_)) or not isinstance(relative, (bool, np.bool_)):
        raise ValueError("preserve_peak and relative must be boolean")
    if tolerance is not None:
        if isinstance(tolerance, (bool, np.bool_)) or not np.isscalar(tolerance) or np.iscomplexobj(tolerance):
            raise ValueError("tolerance must be a finite nonnegative real number")
        try:
            tolerance = float(tolerance)
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError("tolerance must be a finite nonnegative real number") from error
        if not np.isfinite(tolerance) or tolerance < 0:
            raise ValueError("tolerance must be a finite nonnegative real number")
    if provenance is not None and not isinstance(provenance, dict):
        raise ValueError("provenance must be a JSON object")
    if tolerance is not None and method in ("uniform", "uniform_peak"):
        raise ValueError("Tolerance stopping is available for adaptive work and vertical methods")
    limit = min(int(max_points), len(x))
    retain_peak = preserve_peak or method == "uniform_peak"
    selected = {0, len(x) - 1}
    peak = int(np.argmax(np.abs(f)) if peak_mode == "absolute" else
               np.argmax(f) if peak_mode == "positive" else np.argmin(f))
    if retain_peak:
        selected.add(peak)
    if len(selected) > limit:
        raise ValueError("The point budget cannot retain both endpoints and the interior peak")
    if relative and tolerance is not None and float(_primitive_at_nodes(x, f)[-1]) == 0:
        raise ValueError("Relative tolerance requires nonzero reference terminal work; use an absolute tolerance")
    if method in ("uniform", "uniform_peak"):
        selected = _uniform(x, limit)
        if retain_peak and peak not in selected:
            drop = min(selected - {0, len(x) - 1}, key=lambda j: (abs(x[j] - x[peak]), j))
            selected.remove(drop)
            selected.add(peak)
        cert = certify(x, f, np.asarray(sorted(selected)))
    else:
        heap, segments = [], {}
        tree = None
        reference_work = float(_primitive_at_nodes(x, f)[-1])
        digest = _reference_hash(x, f)
        global_evaluations = 0
        def add(a, b):
            nonlocal tree
            info = _segment(x, f, a, b)
            segments[a, b] = info
            tree = _put(tree, a, info[0])
            if info[1] is not None:
                score = info[0][0] if method == "work" else info[0][4]
                heapq.heappush(heap, (-score, a, b))
        initial = sorted(selected)
        for a, b in zip(initial[:-1], initial[1:]):
            add(a, b)
        while True:
            candidate = _certificate(tree.total, reference_work, len(x), digest)
            met = tolerance is not None and candidate.bound(certificate, relative) <= tolerance
            if met or len(selected) >= limit or not heap:
                cert = certify(x, f, np.asarray(sorted(selected)))
                global_evaluations += 1
                if tolerance is not None and cert.bound(certificate, relative) <= tolerance:
                    break
            if len(selected) >= limit or not heap:
                break
            _, a, b = heapq.heappop(heap)
            split = segments.pop((a, b))[1]
            tree = _delete(tree, a)
            selected.add(split)
            add(a, split)
            add(split, b)
    ids = np.asarray(sorted(selected), dtype=np.int64)
    metadata = {"selection_method": method, "preserve_peak": bool(retain_peak), "peak_mode": peak_mode,
                "error_evaluation": "incremental_segment_avl_then_global" if method in ("work", "vertical") else "global",
                "global_error_evaluations": global_evaluations if method in ("work", "vertical") else 1,
                "requested_max_points": int(max_points), "certificate_for_stopping": certificate,
                "requested_tolerance": None if tolerance is None else float(tolerance),
                "relative_tolerance": bool(relative),
                "tolerance_met": None if tolerance is None else cert.bound(certificate, relative) <= tolerance,
                "provenance": provenance or {}}
    return ReducedResponse(x[ids], f[ids], ids, cert, x_unit=x_unit, force_unit=force_unit, metadata=metadata)
