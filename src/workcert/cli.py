"""WorkCert's CSV-to-certified-table command line interface."""
import argparse
import csv
import json
import sys

import numpy as np

from .core import BOUND_NAMES, ReducedResponse, reduce_response


def _read_csv(path, x_column, force_column):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or x_column not in rows[0] or force_column not in rows[0]:
        raise ValueError("CSV must contain the requested x and force columns")
    try:
        return [float(row[x_column]) for row in rows], [float(row[force_column]) for row in rows]
    except (TypeError, ValueError, KeyError) as error:
        raise ValueError("CSV coordinates and forces must be numeric") from error


def main(argv=None):
    parser = argparse.ArgumentParser(prog="workcert", description="Reduce and query certified force-displacement tables.")
    parser.add_argument("--version", action="version", version="WorkCert 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    reduce = commands.add_parser("reduce", help="Reduce a CSV with a header row")
    reduce.add_argument("csv")
    reduce.add_argument("output")
    reduce.add_argument("--x-column", default="stroke_mm")
    reduce.add_argument("--force-column", default="force_kN")
    reduce.add_argument("--max-points", type=int, default=33)
    reduce.add_argument("--method", choices=("work", "vertical", "uniform", "uniform_peak"), default="work")
    reduce.add_argument("--no-peak", action="store_true")
    reduce.add_argument("--tolerance", type=float)
    reduce.add_argument("--relative", action="store_true")
    reduce.add_argument("--certificate", choices=BOUND_NAMES, default="prefix")
    reduce.add_argument("--x-unit", default="mm")
    reduce.add_argument("--force-unit", default="kN")
    query = commands.add_parser("query", help="Query force, prefix work or window work")
    query.add_argument("table")
    query.add_argument("--at", type=float, nargs="+")
    query.add_argument("--window", type=float, nargs=2, metavar=("START", "END"))
    inspect = commands.add_parser("inspect", help="Show provenance, bounds and retained-point count")
    inspect.add_argument("table")
    verify = commands.add_parser("verify", help="Verify against the full reference CSV")
    verify.add_argument("table")
    verify.add_argument("csv")
    verify.add_argument("--x-column", default="stroke_mm")
    verify.add_argument("--force-column", default="force_kN")
    args = parser.parse_args(argv)
    try:
        if args.command == "reduce":
            x, f = _read_csv(args.csv, args.x_column, args.force_column)
            table = reduce_response(x, f, max_points=args.max_points, tolerance=args.tolerance,
                                    certificate=args.certificate, relative=args.relative, method=args.method,
                                    preserve_peak=not args.no_peak, x_unit=args.x_unit, force_unit=args.force_unit,
                                    provenance={"input_file": args.csv})
            table.save(args.output)
            output = {"output": args.output, "points": len(table.x), "work_unit": table.work_unit,
                      "certificate": table.certificate.to_dict(), "metadata": table.metadata}
        else:
            table = ReducedResponse.load(args.table)
            if args.command == "inspect":
                output = {"points": len(table.x), "domain": [float(table.x[0]), float(table.x[-1])],
                          "units": {"displacement": table.x_unit, "force": table.force_unit, "work": table.work_unit},
                          "certificate": table.certificate.to_dict(), "metadata": table.metadata}
            elif args.command == "verify":
                x, f = _read_csv(args.csv, args.x_column, args.force_column)
                output = {"verified": table.verify_reference(x, f)}
            else:
                if (args.at is None) == (args.window is None):
                    raise ValueError("Specify exactly one of --at or --window")
                if args.window is not None:
                    output = {"window": args.window, "work": table.window_work(*args.window), "work_unit": table.work_unit}
                else:
                    output = {"at": args.at, "force": table.force_at(args.at).tolist(),
                              "work": table.work(args.at).tolist(), "force_unit": table.force_unit,
                              "work_unit": table.work_unit}
        print(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (ValueError, OSError, OverflowError) as error:
        print("workcert: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

