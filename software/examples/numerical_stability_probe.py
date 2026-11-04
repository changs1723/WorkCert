"""Reproduce constant-load, cancellation and consistency examples as JSON.

Run with an installed WorkCert:
  python software/examples/numerical_stability_probe.py --output stability.json

The reference values use exact Fraction arithmetic on binary64 inputs. The
legacy column reproduces the documented serial-cumsum expression; it does not
pretend to execute an older package or measure independent physical data.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import workcert
from workcert import ReducedResponse, certify, from_indices, reduce_response
from workcert import split_monotone_branches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    constants = []
    for n in (1001, 10001, 100001, 1000001):
        x = np.arange(n, dtype=float) * 1e-4
        force = np.full(n, .1)
        exact = Fraction(.1) * (Fraction(float(x[-1])) - Fraction(float(x[0])))
        expected = float(exact)
        legacy = float(np.cumsum(np.diff(x) * (.5 * force[:-1] + .5 * force[1:]))[-1])
        response = from_indices(x, force, [0, n - 1])
        c = response.certificate
        assert all(getattr(c, key) == 0. for key in
                   ("eta", "xi", "prefix", "window", "delta", "signed_terminal_error"))
        assert abs(c.reference_work - expected) <= 2 * math.ulp(expected)
        assert abs(response.work(x[-1]) - expected) <= 2 * math.ulp(expected)
        constants.append({"source_points": n, "x_step": 1e-4, "constant_force": .1,
                          "exact_binary_input_integral": str(exact), "expected_float64": expected,
                          "legacy_serial_reference_work": legacy,
                          "legacy_absolute_error": abs(legacy - expected),
                          "new_reference_work": c.reference_work,
                          "new_absolute_error": abs(c.reference_work - expected),
                          "retained_points": len(response.x), "all_reconstruction_errors_zero": True})
    windows = []
    for exponent in (0, 4, 8, 12, 15, 16):
        base = float(10**exponent)
        x, force = np.array([0., 1., 2.]), np.array([base, 0., 1.])
        legacy = np.r_[0., np.cumsum(np.diff(x) * (.5 * force[:-1] + .5 * force[1:]))]
        response = from_indices(x, force, [0, 1, 2])
        answer = response.window_work(1., 2.)
        assert answer == .5
        windows.append({"dominant_force": base, "exponent": exponent, "query": [1., 2.],
                        "exact_binary_input_integral": "1/2", "expected_float64": .5,
                        "legacy_prefix_subtraction": float(legacy[2] - legacy[1]),
                        "new_direct_window": answer,
                        "new_prefix_subtraction": response.work(2.) - response.work(1.),
                        "window_reconstruction_error": response.certificate.window})
    x, force = [0., 1., 2.], [1e12, 1e12 + .01, 1e12]
    table = from_indices(x, force, [0, 2])
    zero_fields = {key: 0. for key in ("eta", "xi", "prefix", "window", "delta",
                  "signed_terminal_error", "min_cumulative_error", "max_cumulative_error")}
    altered = replace(table.certificate, **zero_fields)
    try:
        ReducedResponse(table.x, table.force, table.indices, altered, metadata=table.metadata)
        raise AssertionError("The zero-error forgery passed construction")
    except ValueError as error:
        constructor_message = str(error)
    altered = replace(altered, reference_work=table.work(2.))
    forged = ReducedResponse(table.x, table.force, table.indices, altered, metadata=table.metadata)
    try:
        forged.verify_reference(x, force)
        raise AssertionError("The self-consistent zero-error forgery passed reference verification")
    except ValueError as error:
        verification_message = str(error)
    overflow = []
    for method in ("work", "vertical", "uniform", "uniform_peak", "vw"):
        try:
            reduce_response([0, 1, 2], [1e308] * 3, method=method, max_points=2)
            raise AssertionError("An unrepresentable integral was accepted")
        except ValueError as error:
            overflow.append({"method": method, "exception": type(error).__name__, "message": str(error)})
    multiscale_x = np.arange(11.)
    multiscale_force = [0., 2e100, 0., 2., 0., 2e-100, 0., -2e100, 0., -2., 0.]
    multiscale = from_indices(multiscale_x, multiscale_force, np.arange(11))
    multiscale_expected = float(2 * Fraction(float(1e-100)))
    multiscale_actual = multiscale.window_work(0., 10.)
    assert multiscale_actual == multiscale_expected
    path = split_monotone_branches([0., 1., 2., 3., 4.], [0., 1e16, 1., -1e16, 0.])
    assert path.reference_work == 1.
    package = Path(workcert.__file__).parent
    result = {"status": "PASS", "run_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "numpy": np.__version__, "workcert": workcert.__version__,
              "core_sha256": hashlib.sha256((package / "core.py").read_bytes()).hexdigest(),
              "oracle": "Exact Fraction integral of binary64 constants and local triangle; no measurements",
              "legacy_comparison": "Documented NumPy serial-cumsum formula, not an old-package execution",
              "constant_cases": constants, "short_window_cases": windows,
              "verification_case": {"actual_prefix_error": table.certificate.prefix,
                  "unaltered_reference_verified": table.verify_reference(x, force),
                  "zero_forgery_rejected_at_construction": True, "construction_message": constructor_message,
                  "self_consistent_zero_forgery_rejected_by_verification": True,
                  "verification_message": verification_message},
              "overflow_api_cases": overflow,
              "multiscale_window_case": {"x": multiscale_x.tolist(), "force": multiscale_force,
                  "expected_float64": multiscale_expected, "actual_window": multiscale_actual,
                  "actual_prefix": multiscale.work(10.),
                  "fallback_condition": "abs(net) <= eps64 * sum(abs(original area components))",
                  "fallback_method": "math.fsum over original queried leaf components and endpoint pieces",
                  "query_complexity": "O(log K) normally; O(m) for a cancellation-triggered query spanning m segments"},
              "path_component_consistency_case": {"force": [0., 1e16, 1., -1e16, 0.],
                  "exact_input_integral": "1", "path_reference_work": path.reference_work},
              "arithmetic_scope": "Reconstruction metadata do not enclose floating-point query error. Direct windows avoid subtracting large global primitives; multiplication and output rounding remain binary64."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": result["status"], "core_sha256": result["core_sha256"],
                      "constant_cases": len(constants), "short_window_cases": len(windows),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
