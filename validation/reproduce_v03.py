"""Verify a frozen WorkCert source tree, or explicitly rebuild its scientific results.

Verification runs legacy validators in a separate working copy. It never runs
result generators before inspecting the saved results, and never writes into
the source tree. Reports and the working copy are retained in the output folder.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TREES = ("software", "data", "validation", "examples", "references", "authoring", "release_evidence",
         "article", "article_inputs", "figures")
OMIT = {".git", "__pycache__", ".venv", ".baseline_env", ".validation", "env", "build", "dist", "pip_cache"}
OMIT_SUFFIXES = {".pyc", ".pyo", ".nbc", ".nbi"}
VERIFIERS = (
    "data/source_context/verify_preparation.py",
    "validation/verify_extended_benchmark.py",
    "validation/independent_archive_arithmetic.py",
    "validation/verify_exact_errors.py",
    "validation/verify_workflow.py",
    "validation/review_round2_verify_workflow.py",
    "validation/core_round2_verify.py",
    "validation/verify_cyclic_round2.py",
    "validation/verify_connector.py",
    "validation/test_branch_summary_validation.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    """Scientific files and root documentation; exclude caches and private work areas."""
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix not in OMIT_SUFFIXES:
            yield path
    for name in TREES:
        source = root / name
        if not source.is_dir():
            continue
        for directory, dirs, names in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in OMIT and not d.endswith(".egg-info"))
            for name in sorted(names):
                path = Path(directory) / name
                if path.suffix not in OMIT_SUFFIXES:
                    yield path


def snapshot(root):
    result = {path.relative_to(root).as_posix(): sha(path) for path in files(root)}
    # A published tree may also contain a frozen article or publication evidence.
    # Copy and protect all manifest-listed payloads, even outside the core trees.
    manifest = root / "MANIFEST.sha256"
    if manifest.exists():
        for _, name in manifest_rows(manifest):
            path = root / name
            if path.is_file():
                result[name] = sha(path)
    return result


def manifest_rows(manifest):
    seen = set()
    for number, row in enumerate(manifest.read_text(encoding="utf8").splitlines(), 1):
        digest, name = row.split("  ", 1)
        relative = Path(name)
        if (relative.is_absolute() or relative.drive or ".." in relative.parts or
                name in seen or len(digest) != 64 or "\\" in name or ":" in name):
            raise ValueError("Invalid or duplicate manifest entry at row " + str(number))
        seen.add(name)
        yield digest, name


def manifest_check(root):
    manifest = root / "MANIFEST.sha256"
    if not manifest.exists():
        return {"status": "NOT_PRESENT", "scope": "Canonical development tree; numerical table and source manifests are checked by the full validators"}
    seen = set()
    for digest, name in manifest_rows(manifest):
        seen.add(name)
        path = root / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError("Manifest mismatch: " + name)
    unlisted = {path.relative_to(root).as_posix() for path in files(root)} - seen - {"MANIFEST.sha256"}
    if unlisted:
        raise ValueError("Unlisted source files: " + ", ".join(sorted(unlisted)[:20]))
    return {"status": "PASS", "payload_files": len(seen)}


def changed(before, after):
    return [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def output_folder(root, requested):
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="workcert-verification-"))
    out = requested.expanduser().resolve()
    # An explicit qa/ folder is allowed, but data/code/frozen-output trees are not.
    if out == root or any(out == root / name or root / name in out.parents for name in TREES):
        raise ValueError("The verification output must be outside the frozen source/data/result directories")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new, empty verification output directory")
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_verify(root, out, checks):
    before = snapshot(root)
    report = {"mode": "verify-only", "checks": checks, "source_root": str(root),
              "output_directory": str(out), "source_files_before": len(before),
              "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "validators": [], "status": "FAIL"}
    (out / "source_before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf8")
    returncode = 1
    try:
        report["public_manifest"] = manifest_check(root)
        if checks == "integrity":
            if report["public_manifest"]["status"] != "PASS":
                raise ValueError("Integrity-only checks require a supplied MANIFEST.sha256")
        else:
            work = out / "working_copy"
            work.mkdir()
            for relative, digest in before.items():
                target = work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / relative, target)
                if sha(target) != digest:
                    raise ValueError("Source changed while making the verification copy: " + relative)
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["NUMBA_CACHE_DIR"] = str(out / "numba_cache")
            env["WORKCERT_RESEARCH_ROOT"] = str(work)
            # Validators explicitly import the copied source. External package paths
            # must not accidentally substitute an earlier installed WorkCert.
            env["PYTHONPATH"] = str(work / "software/src")
            env["MPLCONFIGDIR"] = str(out / "matplotlib_cache")
            scripts = list(VERIFIERS)
            if (work / "validation/decision_verify.py").exists():
                scripts.append("validation/decision_verify.py")
            for index, relative in enumerate(scripts):
                if not (work / relative).is_file():
                    raise ValueError("Missing validator: " + relative)
                log = out / ("%02d_" % index + Path(relative).stem + ".log")
                with log.open("w", encoding="utf8") as stream:
                    process = subprocess.run([sys.executable, str(work / relative)], cwd=work,
                                             env=env, stdout=stream, stderr=subprocess.STDOUT)
                report["validators"].append({"script": relative, "exit_code": process.returncode,
                                             "log": log.name})
                print(relative + ": " + str(process.returncode), flush=True)
                if process.returncode:
                    raise RuntimeError("Verification failed: " + relative + "; see " + str(log))
        report["status"] = "PASS"
        returncode = 0
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        print(report["error"], file=sys.stderr, flush=True)
    finally:
        after = snapshot(root)
        report["source_files_after"] = len(after)
        report["changed_source_files"] = changed(before, after)
        report["source_unchanged"] = not report["changed_source_files"]
        if not report["source_unchanged"]:
            report["status"] = "FAIL"
            returncode = 1
        (out / "source_after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf8")
        (out / "verification_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2), flush=True)
    return returncode


def run_recompute(root, scaling, figures):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = [
        ("validation/acquire_pla_data.py",), ("validation/prepare_data.py",),
        ("validation/check_baselines.py",), ("validation/extended_benchmark.py",),
        ("validation/optimal_dp.py",), ("validation/extended_benchmark.py", "--finish-dp"),
        ("validation/user_workflow.py", "--case", "all"),
        ("validation/review_round2_workflow.py",), ("validation/cyclic_round2.py",),
        ("validation/connector_exchange.py",),
    ]
    if (root / "validation/decision_workflow.py").exists():
        commands.append(("validation/decision_workflow.py",))
    if scaling:
        commands += [("validation/benchmark_scaling.py",), ("validation/benchmark_scaling.py", "--headline")]
    if figures:
        script = "authoring/build_figures.py" if (root / "authoring/build_figures.py").exists() else "authoring/build_v02_figures.py"
        commands.append((script,))
    for command in commands:
        print("Rebuilding " + " ".join(command), flush=True)
        subprocess.run([sys.executable, str(root / command[0]), *command[1:]], cwd=root, env=env, check=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true", help="Verify frozen files in an isolated copy; source files are unchanged (default)")
    mode.add_argument("--recompute", action="store_true", help="Explicitly overwrite derived scientific results in this source tree")
    parser.add_argument("--output-dir", type=Path, help="New folder for reports and the verification copy; default is a new system temporary folder")
    parser.add_argument("--checks", choices=("full", "integrity"), default="full", help="Full numerical verification or manifest-only integrity verification")
    parser.add_argument("--include-scaling", action="store_true")
    parser.add_argument("--figures", action="store_true")
    parser.add_argument("--source-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.source_root.resolve()
    if not root.is_dir():
        parser.error("The source root must exist")
    if (args.include_scaling or args.figures) and not args.recompute:
        parser.error("--include-scaling and --figures require --recompute")
    if args.recompute:
        if args.output_dir is not None or args.checks != "full":
            parser.error("--output-dir and --checks apply to --verify-only")
        return run_recompute(root, args.include_scaling, args.figures)
    try:
        out = output_folder(root, args.output_dir)
    except ValueError as error:
        parser.error(str(error))
    return run_verify(root, out, args.checks)


if __name__ == "__main__":
    sys.exit(main())
