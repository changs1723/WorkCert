"""Data-linked article figures; no generated experimental imagery."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software/src"))
from workcert import ReducedResponse

OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
INPUTS = {}
OUTPUTS = []
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.labelsize": 9,
                     "legend.fontsize": 7.5, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42,
                     "axes.titlesize": 9.5, "axes.titleweight": "semibold"})
COL = {"work": "#0072b2", "vertical": "#009e73", "rdp": "#cc79a7", "vw": "#d55e00",
       "uniform_peak": "#777777", "uniform": "#b3b3b3"}
KEYS = list(COL)
LABEL = {"work": "Work", "vertical": "Vertical", "rdp": "RDP", "vw": "VW",
         "uniform_peak": "Uniform\n+ peak", "uniform": "Uniform"}


def register(relative):
    path = ROOT / relative
    INPUTS[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def read(relative):
    return json.loads(register(relative).read_text(encoding="utf8"))


def csv(relative):
    return pd.read_csv(register(relative), float_precision="round_trip")


def table(relative):
    return ReducedResponse.load(register(relative))


def export(fig, name):
    snapshot = read("article_inputs/publication_snapshot.json")
    epoch = int(snapshot.get("build_epoch", 1793664000))
    fixed = datetime.fromtimestamp(epoch, timezone.utc)
    for suffix in ("pdf", "png", "tiff"):
        path = OUT / (name + "." + suffix)
        options = {"bbox_inches": "tight", "pad_inches": .09}
        if suffix == "pdf":
            options["metadata"] = {"CreationDate": fixed, "ModDate": fixed,
                                   "Creator": "WorkCert data-linked figure builder"}
        elif suffix == "png":
            options["dpi"] = 180
        else:
            options.update(dpi=600, pil_kwargs={"compression": "tiff_lzw"})
        fig.savefig(path, **options)
        OUTPUTS.append({"file": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    plt.close(fig)


def numerics():
    data = read("validation/numerical_stability_results.json")
    constants, windows = data["constant_cases"], data["short_window_cases"]
    n = np.asarray([r["source_points"] for r in constants])
    ulps = np.asarray([np.spacing(r["expected_float64"]) for r in constants])
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.15), constrained_layout=True)
    a = axes[0]
    a.plot(n, np.asarray([r["legacy_absolute_error"] for r in constants]) / ulps,
           "o--", color="#d55e00", label="Serial cumsum formula", ms=4)
    a.plot(n, np.asarray([r["new_absolute_error"] for r in constants]) / ulps,
           "s-", color="#0072b2", label="Compensated integration", ms=4)
    a.set(xscale="log", yscale="symlog", xlabel="Source nodes", ylabel="Terminal-work error (ULPs)",
          title="(a) Constant-force integration", xticks=[1e3, 1e4, 1e5, 1e6],
          yticks=[0, 1, 100, 10000], ylim=(-.4, 16000))
    a.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: "%g" % v))
    a.legend(frameon=False, loc="upper left", fontsize=7)
    a = axes[1]
    x = [r["dominant_force"] for r in windows]
    a.axhline(.5, color="#a1a1a1", lw=4, alpha=.45, label="Exact local integral")
    a.plot(x, [r["legacy_prefix_subtraction"] for r in windows], "o--", color="#d55e00",
           ms=4, label="Global-prefix difference")
    a.plot(x, [r["new_direct_window"] for r in windows], "s-", color="#0072b2",
           ms=3, label="Direct window query")
    a.set(xscale="log", xlabel="Dominant preceding force", ylabel="Window work", title="(b) A small window after large work",
          xticks=[1, 1e8, 1e16], ylim=(-.035, .66), yticks=[0, .25, .5])
    a.legend(frameon=False, loc="lower left", fontsize=7)
    export(fig, "fig01_numerics")


def reference_work(x, f, value):
    j = np.searchsorted(x, value, side="left")
    xx = np.r_[x[:j], value]
    ff = np.r_[f[:j], np.interp(value, x, f)]
    return math.fsum((b - a) * (.5 * u + .5 * v) for a, b, u, v in zip(xx, xx[1:], ff, ff[1:]))


def decisions():
    summary = read("validation/decision_results/summary.json")
    raw = csv("data/prepared/PLA_STWC-1.csv")
    tab = table("validation/decision_results/tables/initial/STWC-1.json")
    configs = csv("validation/decision_results/configuration_queries.csv")
    refinement = csv("validation/decision_results/refinement_steps.csv")
    difficulty = csv("validation/decision_results/query_difficulty.csv")
    scatter = csv("validation/workflow_results_round2/repeat_scatter.csv").sort_values(["configuration", "stroke_mm"])
    fig, axes = plt.subplots(3, 2, figsize=(7, 7.15), constrained_layout=True)
    a = axes[0, 0]
    a.plot(raw.x_mm, raw.force_kN, color="#333333", lw=1.25, label="Reference")
    a.plot(tab.x, tab.force, "o--", color="#d55e00", ms=2.8, mfc="white", lw=.9, label="Exchanged table")
    a.set(xlabel="Travel (mm)", ylabel="Force (kN)", title="(a) STWC-1 loading response")
    a.legend(frameon=False, loc="upper right", fontsize=7)
    a = axes[0, 1]
    selected = configs[(configs.stroke_mm == 20.) & configs.configuration.isin(["26", "35"])]
    labels = []
    for i, (stage, config) in enumerate([("initial", "26"), ("initial", "35"), ("refinement_01", "26"), ("refinement_01", "35")]):
        rows = selected[(selected.configuration == config) & (selected.stage == stage)]
        # The public CSV uses the consumer stage labels recorded by the workflow.
        if rows.empty and stage != "initial":
            rows = selected[(selected.configuration == config) & (selected.stage != "initial")]
        r = rows.iloc[0]
        center = r.SEA_kJ_kg
        color = "#0072b2" if config == "26" else "#d55e00"
        a.errorbar(center, i, xerr=[[center - r.SEA_lower_kJ_kg], [r.SEA_upper_kJ_kg - center]],
                   fmt="o", capsize=3, color=color, ms=4)
        a.plot(r.reference_SEA_kJ_kg, i, "|", color="#252525", ms=11, mew=1)
        labels.append(config + (" / 1 J" if stage == "initial" else " / 0.5 J"))
    a.set(yticks=range(4), yticklabels=labels, xlabel="SEA at 20 mm (kJ/kg)", title="(b) Targeted best-candidate query")
    a.invert_yaxis()
    a = axes[1, 0]
    p = np.arange(len(difficulty))
    a.bar(p - .17, 100 * difficulty.all_pairs_separated / difficulty.all_pairs, .34,
          color="#b8d8eb", label="All pairs")
    a.bar(p + .17, 100 * difficulty.adjacent_separated / difficulty.adjacent_pairs, .34,
          color="#0072b2", label="Adjacent pairs")
    for i, r in enumerate(difficulty.itertuples()):
        a.text(i + .17, 100 * r.adjacent_separated / r.adjacent_pairs + 3,
               "%d/41" % r.adjacent_separated, ha="center", fontsize=7)
    a.set(xticks=p, xticklabels=["%g" % s for s in difficulty.stroke_mm], xlabel="Stroke (mm)",
          ylabel="Numerically separated (%)", title="(c) Comparison difficulty", ylim=(0, 115))
    a.legend(frameon=False, fontsize=7, loc="upper left")
    a = axes[1, 1]
    p = np.arange(len(refinement))
    a.bar(p - .17, refinement.previous_points, .34, color="#a4cde4", label="1 J")
    a.bar(p + .17, refinement.points, .34, color="#0072b2", label="0.5 J")
    for i, r in enumerate(refinement.itertuples()):
        a.text(i - .17, r.previous_points + 1, str(r.previous_points), ha="center", fontsize=8)
        a.text(i + .17, r.points + 1, str(r.points), ha="center", fontsize=8)
    a.set(xticks=p, xticklabels=[str(v) for v in refinement.specimen], xlabel="Requested source record",
          ylabel="Retained nodes", title="(d) Only two tables are replaced", ylim=(0, max(refinement.points) * 1.25))
    a.legend(frameon=False, fontsize=7, loc="upper left")
    a = axes[2, 0]
    inv = summary["energy_to_stroke"]
    q = np.linspace(20.8, 23.2, 220)
    xx, ff = raw.x_mm.to_numpy(), raw.force_kN.to_numpy()
    reference = np.asarray([reference_work(xx, ff, u) for u in q])
    work = tab.work(q)
    ep = inv["prefix_bound_J"]
    a.fill_between(q, work - ep, work + ep, color="#d9eaf5", label="Table work ± prefix bound")
    a.plot(q, reference, color="#333333", lw=1.1, label="Reference")
    a.plot(q, work, "--", color="#0072b2", lw=1)
    a.axhline(100, color="#d55e00", ls=":", lw=1)
    a.axvspan(inv["stroke_lower_mm"], inv["stroke_upper_mm"], color="#e9b986", alpha=.35)
    a.plot(inv["reference_inverse_mm"], 100, "o", color="#333333", ms=3)
    a.set(xlabel="Stroke (mm)", ylabel="Accumulated work (J)", title="(e) Inverting 100 J work capacity")
    a.legend(frameon=False, fontsize=6.5, loc="upper left")
    a = axes[2, 1]
    p = np.arange(len(scatter))
    a.bar(p - .16, scatter.EA_sample_SD_J, .32, color="#88b9d6", label="Sample SD (n=3)")
    a.bar(p + .16, scatter.maximum_prefix_bound_J, .32, color="#d55e00", label="Largest prefix bound")
    labels = [("N" if r.configuration == "N-SCMC" else "S") + str(int(r.stroke_mm)) for r in scatter.itertuples()]
    a.set(xticks=p, xticklabels=labels, ylabel="Energy (J)", title="(f) Reused triplicate controls",
          xlabel="N: nominal; S: STWC; stroke in mm")
    a.legend(frameon=False, fontsize=6.5, loc="upper left")
    export(fig, "fig02_decisions")


def cyclic():
    trace = np.load(register("validation/workflow_results/cyclic_path/chronological_path.npz"))
    info = read("validation/cyclic_round2_results/summary.json")
    branches = csv("validation/cyclic_round2_results/branch_diagnostics.csv")
    dead = csv("validation/cyclic_round2_results/deadband_sensitivity.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7, 4.55), constrained_layout=True)
    axes[0, 0].plot(trace["displacement_mm"], trace["reference_force_kN"], color="#406780", lw=.5)
    axes[0, 0].set(xlabel="Displacement (mm)", ylabel="Force (kN)", title="(a) Complete cyclic path")
    vals = np.sort(branches.source_points.to_numpy())
    pct = 100 * np.arange(1, len(vals) + 1) / len(vals)
    a = axes[0, 1]
    a.step(vals, pct, color="#0072b2", where="post")
    a.axvline(9, color="#d55e00", ls="--", lw=.8, label="Median: 9 source nodes")
    a.set(xscale="log", xlabel="Source nodes per branch", ylabel="Cumulative branches (%)", title="(b) Branch-size distribution", ylim=(0, 102))
    a.legend(frameon=False, fontsize=7)
    a = axes[1, 0]
    a.plot(dead.deadband_mm, dead.confirmed_reversals, "o-", ms=3, color="#0072b2")
    a.axhline(94, color="#d55e00", ls="--", lw=.8, label="94 extrema at 0.1–5 mm")
    a.set(xscale="log", xlabel="Diagnostic deadband (mm)", ylabel="Detected reversals", title="(c) Reversal-scale sensitivity")
    a.legend(frameon=False, fontsize=7)
    a = axes[1, 1]
    bound = info["sum_branch_window_errors_J"]
    a.axhspan(-bound, bound, color="#e4eff6")
    e = trace["cumulative_error_J"]
    a.plot(np.arange(len(e)) / 1000, e, color="#0072b2", lw=.8)
    a.axhline(0, color="#777777", lw=.5)
    a.set(xlabel=r"Chronological sample ($\times10^3$)", ylabel="Signed work error (J)", title="(d) Chronological integral")
    export(fig, "fig03_cyclic")


def selectors():
    summary = read("validation/results_v02/comparative_summary.json")
    gaps = csv("validation/results_v02/optimality_gaps.csv")
    weighted = csv("validation/decision_results/weighting_sensitivity.csv")
    cohorts = ["CX_steel", "EDAH", "PLA_plus"]
    matrix = np.asarray([[summary[c]["at33"][m]["window_error_percent"] for m in KEYS] for c in cohorts])
    fig = plt.figure(figsize=(7, 5.05), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=[.8, 1.1])
    a = fig.add_subplot(grid[0, :])
    im = a.imshow(matrix, cmap="Blues", norm=LogNorm(vmin=matrix.min() * .85, vmax=matrix.max() * 1.2), aspect="auto")
    for i in range(3):
        for j in range(6):
            a.text(j, i, "%.3f" % matrix[i, j], ha="center", va="center", fontsize=8.4,
                   color="white" if matrix[i, j] > np.sqrt(matrix.min() * matrix.max()) else "#102a3a")
    a.set(xticks=range(6), xticklabels=[LABEL[k] for k in KEYS], yticks=range(3),
          yticklabels=["CX steel (23)", "EDAH (1)", "PLA+ (46)"], title="(a) Cohort median window error (%)")
    cb = fig.colorbar(im, ax=a, fraction=.025, pad=.02)
    cb.set_ticks([.15, .3, .6, 1.2])
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: "%g" % v))
    cb.ax.minorticks_off()
    a = fig.add_subplot(grid[1, 0])
    positions = np.arange(6)
    for weighting, offset, label, color in [("equal_records", -.2, "Records", "#9ecae1"),
                                           ("equal_cohorts", 0, "Cohorts", "#2171b5"),
                                           ("equal_configurations", .2, "Configurations", "#d98b39")]:
        sub = weighted[(weighted.weighting == weighting) & (weighted.metric == "window_error_percent")].set_index("method")
        a.bar(positions + offset, [sub.loc[k, "weighted_median_percent"] for k in KEYS], .2, color=color, label=label)
    a.set(xticks=positions, xticklabels=[LABEL[k] for k in KEYS], ylabel="Weighted median window error (%)",
          title="(b) Weighting sensitivity", ylim=(0, .55))
    a.tick_params(axis="x", labelsize=7)
    a.legend(frameon=False, fontsize=6.3, loc="upper left")
    a = fig.add_subplot(grid[1, 1])
    method = "method" if "method" in gaps else "greedy_method"
    ratio = "cost_ratio" if "cost_ratio" in gaps else "ratio"
    subset = gaps[(gaps.budget == 33) & (gaps.objective == "eta")]
    data = [subset[subset[method] == k][ratio].to_numpy() for k in KEYS[:-1]]
    bp = a.boxplot(data, widths=.55, patch_artist=True, showfliers=True)
    for patch, key in zip(bp["boxes"], KEYS[:-1]):
        patch.set(facecolor=COL[key], alpha=.65)
    a.axhline(1, color="#555555", lw=.9, ls="--")
    a.set(xticks=range(1, 6), xticklabels=[LABEL[k] for k in KEYS[:-1]], ylabel=r"Area cost / exact optimum $\eta^*$",
          title="(c) Matched area objective (58)", ylim=(.8, max(max(d) for d in data) * 1.08))
    a.tick_params(axis="x", labelsize=7)
    export(fig, "fig04_selectors")


def scaling():
    stop = csv("validation/results_v02/stopping_metrics.csv")
    scale = read("validation/results/scaling/measurements.json")
    frame = pd.DataFrame(scale if isinstance(scale, list) else scale["measurements"])
    head = read("validation/results/scaling/headline_repeats.json")["summary"]
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.25), constrained_layout=True)
    a = axes[0]
    vals = [stop[(stop.method == m) & (stop.measure == c)].points.to_numpy()
            for m, c in [("work", "eta"), ("work", "window"), ("vertical", "eta"), ("vertical", "window")]]
    bp = a.boxplot(vals, widths=.55, patch_artist=True, showfliers=True)
    for patch, color in zip(bp["boxes"], ["#a6cce2", "#0072b2", "#a5d9c3", "#009e73"]):
        patch.set_facecolor(color)
    a.set(xticks=[1, 2, 3, 4], xticklabels=["Work\narea", "Work\ninterval", "Vertical\narea", "Vertical\ninterval"],
          ylabel="Nodes at a 1% interval-work requirement", title="(a) Matched stopping requirement")
    a = axes[1]
    for implementation, label, color in [("v0_1_full_scan", "Full scan (0.1)", "#555555"),
                                          ("v0_3_stable_incremental", "Stable incremental (0.3)", "#0072b2")]:
        d = frame[(frame.implementation == implementation) & np.isclose(frame.tolerance_fraction, .001)].sort_values("n")
        a.plot(d.n, d.seconds, "o-", color=color, label=label, ms=4)
        h = head[implementation]
        a.errorbar(1e6, h["median_seconds"], yerr=[[h["median_seconds"] - h["minimum_seconds"]],
                    [h["maximum_seconds"] - h["median_seconds"]]], fmt="s", color=color, capsize=3, ms=4)
    a.set(xscale="log", yscale="log", xlabel="Reference samples", ylabel="Construction time (s)",
          title="(b) 0.1% window-work tolerance", xticks=[1e3, 1e4, 1e5, 1e6])
    a.yaxis.set_major_formatter(FuncFormatter(lambda value, pos: "%g" % value))
    a.legend(frameon=False, loc="upper left", fontsize=7)
    export(fig, "fig05_scaling")


def main():
    frozen = ROOT / "article_inputs/scientific_fingerprints.json"
    if frozen.exists():
        for name, expected in json.loads(frozen.read_text(encoding="utf8"))["inputs"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, "Frozen article input changed: " + name
    numerics()
    decisions()
    cyclic()
    selectors()
    scaling()
    (OUT / "manifest.json").write_text(json.dumps(OUTPUTS, indent=2) + "\n", encoding="utf8")
    (OUT / "input_fingerprints.json").write_text(json.dumps(INPUTS, indent=2) + "\n", encoding="utf8")
    print("Exported five data-linked vector, PNG and 600 dpi TIFF figures.")


if __name__ == "__main__":
    main()
