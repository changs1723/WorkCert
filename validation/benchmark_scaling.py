"""Reproducible algorithm-cost comparison on explicitly synthetic compression data."""
from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software/src"))


def hardware_environment():
    """Record timing-relevant hardware without host or user identifiers."""
    cpu = platform.processor()
    memory_bytes = None
    memory_source = None
    if sys.platform == "win32":
        import ctypes
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total_physical", ctypes.c_ulonglong),
                        ("available_physical", ctypes.c_ulonglong),
                        ("total_pagefile", ctypes.c_ulonglong),
                        ("available_pagefile", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong),
                        ("available_virtual", ctypes.c_ulonglong),
                        ("available_extended_virtual", ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed while recording timing hardware")
        memory_bytes = status.total_physical
        memory_source = "Windows GlobalMemoryStatusEx: total physical memory available to OS"
    elif sys.platform == "darwin":
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"],
                                      text=True).strip()
        memory_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"],
                                                  text=True).strip())
        memory_source = "macOS sysctl hw.memsize"
    else:
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.is_file():
            for line in cpuinfo.read_text().splitlines():
                if line.lower().startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        if hasattr(os, "sysconf"):
            memory_bytes = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            memory_source = "POSIX sysconf physical pages times page size"
    return {"captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cpu_model": cpu, "logical_processors": os.cpu_count(),
            "physical_memory_bytes": memory_bytes,
            "physical_memory_GiB": None if memory_bytes is None else memory_bytes / 2**30,
            "memory_source": memory_source, "platform": platform.platform(),
            "python": sys.version, "numpy": np.__version__}


def one(implementation, n, tolerance):
    if implementation == "v0_1_full_scan":
        path = ROOT / "validation/scaling/legacy_core_v0_1.py"
        spec = importlib.util.spec_from_file_location("legacy_workcert_core", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        reducer = module.reduce_response
    else:
        from workcert import reduce_response
        reducer = reduce_response
        path = ROOT / "software/src/workcert/core.py"
    x = np.linspace(0., 1., n)
    force = (1 - np.exp(-40*x))*(1 + .15*np.sin(40*np.pi*x) + .08*np.sin(113*np.pi*x)) + .8*x**8
    # Warm-up uses a separate small signal and is excluded from the measurement.
    reducer(x[:min(n, 200)], force[:min(n, 200)], method="work", max_points=33,
            x_unit="mm", force_unit="kN")
    before = time.perf_counter()
    response = reducer(x, force, method="work", max_points=1025, tolerance=tolerance,
                       certificate="window", relative=True, x_unit="mm", force_unit="kN")
    seconds = time.perf_counter() - before
    return {"implementation": implementation, "n": n, "tolerance_fraction": tolerance,
            "tolerance_kind": "window", "max_points": 1025, "seconds": seconds,
            "retained_points": len(response.x), "tolerance_met": response.metadata["tolerance_met"],
            "actual_window_relative": response.certificate.bound("window", True),
            "global_error_evaluations": response.metadata.get("global_error_evaluations",
                                                        len(response.x)-len({0,n-1,int(np.argmax(force))})+1),
            "reference_sha256": response.certificate.reference_sha256,
            "core_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "PASS"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--one", choices=("v0_1_full_scan", "v0_3_stable_incremental"))
    parser.add_argument("--n", type=int)
    parser.add_argument("--tolerance", type=float)
    parser.add_argument("--timeout", type=float, default=120.)
    parser.add_argument("--headline", action="store_true", help="Three independent paired repeats at one million points and 0.1% window error")
    args = parser.parse_args()
    if args.one:
        print(json.dumps(one(args.one, args.n, args.tolerance)))
        return
    out = ROOT / "validation/results/scaling"
    out.mkdir(parents=True, exist_ok=True)
    hardware = hardware_environment()
    (out / "hardware.json").write_text(json.dumps(hardware, indent=2) + "\n", encoding="utf8")
    if args.headline:
        rows=[]
        for repeat in range(3):
            order=("v0_1_full_scan","v0_3_stable_incremental") if repeat%2==0 else ("v0_3_stable_incremental","v0_1_full_scan")
            for implementation in order:
                p=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--one",implementation,
                                  "--n","1000000","--tolerance","0.001"],capture_output=True,text=True,timeout=args.timeout)
                if p.returncode:raise RuntimeError(p.stdout+p.stderr)
                row=json.loads(p.stdout);row['repeat']=repeat+1;rows.append(row)
                print(json.dumps(row),flush=True)
        summary={}
        for implementation in ("v0_1_full_scan","v0_3_stable_incremental"):
            values=[r['seconds'] for r in rows if r['implementation']==implementation]
            summary[implementation]={'median_seconds':float(np.median(values)),
                                     'minimum_seconds':min(values),'maximum_seconds':max(values)}
        assert len({r['retained_points'] for r in rows})==1 and all(r['tolerance_met'] for r in rows)
        report={'signal':'synthetic analytic compression-like function; not experimental observations',
                'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
                'hardware':hardware,'hardware_record':'hardware.json',
                'method':'three independent process pairs; alternating implementation order; separate small warm-up; all construction/hash/final global check included',
                'measurements':rows,'summary':summary,
                'median_speed_ratio':summary['v0_1_full_scan']['median_seconds']/summary['v0_3_stable_incremental']['median_seconds']}
        (out/'headline_repeats.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(summary),flush=True)
        return
    records=[]
    for tolerance in (.01, .001, .0001):
        for n in (1000,10000,100000,1000000):
            for implementation in ("v0_1_full_scan","v0_3_stable_incremental"):
                command=[sys.executable,str(Path(__file__).resolve()),"--one",implementation,
                         "--n",str(n),"--tolerance",str(tolerance)]
                try:
                    p=subprocess.run(command,capture_output=True,text=True,timeout=args.timeout)
                    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
                    record=json.loads(p.stdout)
                except subprocess.TimeoutExpired:
                    record={"implementation":implementation,"n":n,"tolerance_fraction":tolerance,
                            "status":"CENSORED_TIMEOUT","timeout_seconds":args.timeout}
                records.append(record)
                print(json.dumps(record),flush=True)
                (out/"measurements.json").write_text(json.dumps(records,indent=2),encoding="utf8")
    paired=[]
    for tolerance in (.01,.001,.0001):
        for n in (1000,10000,100000,1000000):
            rows=[r for r in records if r['n']==n and r['tolerance_fraction']==tolerance]
            a,b=rows
            item={"n":n,"tolerance_fraction":tolerance,"old_status":a['status'],"new_status":b['status']}
            if a['status']==b['status']=='PASS':
                item.update(speed_ratio=a['seconds']/b['seconds'],same_reference=a['reference_sha256']==b['reference_sha256'],
                            old_points=a['retained_points'],new_points=b['retained_points'])
                assert item['same_reference'] and a['tolerance_met']==b['tolerance_met']
            paired.append(item)
    report={"signal":"synthetic analytic compression-like function; not experimental observations",
            "python":sys.version,"numpy":np.__version__,"platform":platform.platform(),
            "hardware":hardware,"hardware_record":"hardware.json",
            "timing":"one measured construction after a separate small warm-up per independent process; native allocations/hash/final global evaluation included",
            "point_cap":1025,"timeout_seconds_per_case":args.timeout,"pairs":paired,
            "worst_case_complexity":"Segment rescanning can still cost O(nK); AVL summary updates cost O(log K) and use O(K) nodes. The incremental implementation removes full-reference certificate scans at each insertion."}
    (out/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf8")


if __name__=="__main__":main()
