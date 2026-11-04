#!/usr/bin/env python3
"""Figures for the 50-trace evaluation, generated only from the CSV files
written by analyze_50trace.py (no hand-entered values).

  build/venv/Scripts/python experiments/scripts/make_figures_50trace.py [--res results_50trace]

Writes <res>/figures/figN_*.png (300 dpi) and .pdf (vector, used by the report).
Needs matplotlib (tested with 3.11.2).
"""
import argparse, csv, math, os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROPOSED = "tsl_proposed"

# Palette (validated: dataviz reference palette, light surface)
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C_DEFAULT, C_REF, C_PROP = "#b4b2a8", "#6f6d66", "#2a78d6"   # ChampSim default / project reference / proposed
C_GAIN, C_LOSS, C_NEUTRAL = "#2a78d6", "#e34948", "#c3c2b7"   # diverging: blue = better, red = worse
C_S1, C_S2 = "#2a78d6", "#eb6834"                           # two-series slots
SEQ = LinearSegmentedColormap.from_list("blue_seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.dpi": 300, "savefig.bbox": "tight", "figure.facecolor": "white",
})


def read(path):
    return list(csv.DictReader(open(path)))


def color_of(p):
    return C_PROP if p == PROPOSED else (C_DEFAULT if p in ("bimodal", "gshare", "perceptron", "hashed_perceptron") else C_REF)


def short(label):
    return label.replace(" (proposed)", "*").replace("Hashed Perceptron", "Hashed\nPerceptron").replace("TFL-TAGE-SC-L*", "TFL-TAGE-\nSC-L (ours)")


def group_legend(fig):
    """One legend row under the panels (never over the bars)."""
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.legend(handles=[Patch(color=C_DEFAULT, label="ChampSim default"),
                        Patch(color=C_REF, label="Project reference (re-implemented)"),
                        Patch(color=C_PROP, label="TFL-TAGE-SC-L (proposed)")],
               loc="lower center", ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, 0.0))


def save(fig, out, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"))
    plt.close(fig)
    print("wrote", name)


def bars(ax, S, key, fmt, ylabel, title, ylim=None):
    xs = range(len(S))
    vals = [float(s[key]) for s in S]
    b = ax.bar(xs, vals, color=[color_of(s["predictor"]) for s in S], width=0.68, edgecolor="white", linewidth=1)
    ax.set_xticks(list(xs), [short(s["label"]) for s in S])
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", color=INK)
    ax.grid(axis="x", visible=False)
    if ylim:
        ax.set_ylim(*ylim)
    lo = ax.get_ylim()[0]
    for rect, v in zip(b, vals):
        ax.annotate(fmt.format(v), (rect.get_x() + rect.get_width() / 2, v), xytext=(0, 2),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7.5, color=INK)
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default=os.path.join(ROOT, "results_50trace"))
    a = ap.parse_args()
    out = os.path.join(a.res, "figures")
    os.makedirs(out, exist_ok=True)
    S = read(os.path.join(a.res, "summary.csv"))
    P = [r for r in read(os.path.join(a.res, "per_trace_results.csv")) if r["all_runs_ok"] == "True"]
    C = {r["baseline"]: r for r in read(os.path.join(a.res, "comparison_vs_baselines.csv"))}
    SUB = read(os.path.join(a.res, "subset_summary.csv"))
    n = int(S[0]["n_traces"])
    lab = {s["predictor"]: s["label"] for s in S}
    others = [s for s in S if s["predictor"] != PROPOSED]
    best_base = max(others, key=lambda s: float(s["geomean_ipc"]))["predictor"]
    best_default = max([s for s in others if color_of(s["predictor"]) == C_DEFAULT],
                       key=lambda s: float(s["geomean_ipc"]))["predictor"]
    refs = [best_base] + ([best_default] if best_default != best_base else [])

    # 1 — IPC: arithmetic and geometric mean
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    top = max(float(s["mean_ipc"]) for s in S)
    bars(axs[0], S, "mean_ipc", "{:.4f}", "IPC", f"(a) Arithmetic mean IPC over {n} traces", (0, top * 1.12))
    bars(axs[1], S, "geomean_ipc", "{:.4f}", "IPC", f"(b) Geometric mean IPC over {n} traces", (0, top * 1.12))
    group_legend(fig)
    save(fig, out, "fig1_ipc_comparison")

    # 2 — accuracy (all branches = ChampSim definition; conditional only)
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    lo = math.floor(min(float(s["pooled_cond_accuracy"]) for s in S)) - 1
    bars(axs[0], S, "pooled_accuracy", "{:.3f}", "Accuracy (%)", "(a) All branch types (ChampSim definition)", (lo, 100))
    bars(axs[1], S, "pooled_cond_accuracy", "{:.3f}", "Accuracy (%)", "(b) Conditional branches only", (lo, 100))
    for ax in axs:
        ax.set_xlabel(f"pooled over {n} traces; y-axis starts at {lo}%", fontsize=7, color=MUTED)
    group_legend(fig)
    save(fig, out, "fig2_accuracy_comparison")

    # 3 — MPKI: all, INT, FP
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, sub, title in zip(axs, ("all50", "INT", "FP"), ("(a) All traces", "(b) SPECint traces", "(c) SPECfp traces")):
        rows = [r for r in SUB if r["subset"] == sub]
        if not rows:
            continue
        bars(ax, rows, "mean_mpki", "{:.3f}", "Mean MPKI", f"{title} (n = {rows[0]['n_traces']})",
             (0, max(float(r["mean_mpki"]) for r in rows) * 1.15))
        ax.tick_params(axis="x", labelsize=6.5)
    group_legend(fig)
    save(fig, out, "fig3_mpki_comparison")

    # 4 — geometric-mean IPC speedup over bimodal
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for s in S:
        s["_sp"] = 100 * (float(s["geomean_speedup_vs_bimodal"]) - 1)
    bars(ax, S, "_sp", "{:+.2f}%", "Geomean IPC speedup over Bimodal (%)",
         f"Geometric-mean IPC speedup over Bimodal ({n} traces)", (0, max(s["_sp"] for s in S) * 1.15))
    group_legend(fig)
    save(fig, out, "fig4_geomean_ipc_speedup")

    # 5 / 6 — per-trace IPC change and MPKI change vs the best baseline(s)
    for fig_no, key, ylab, fname in ((5, "ipc_change_pct_vs_", "IPC change (%)", "fig5_per_trace_ipc_vs_best_baselines"),
                                     (6, "mpki_change_vs_", "MPKI change (proposed − baseline)", "fig6_per_trace_mpki_change")):
        fig, axs = plt.subplots(len(refs), 1, figsize=(12, 3.4 * len(refs)), squeeze=False)
        for ax, b in zip(axs[:, 0], refs):
            rows = sorted(P, key=lambda r: float(r[key + b]), reverse=(fig_no == 5))
            vals = [float(r[key + b]) for r in rows]
            good = [(v > 0) if fig_no == 5 else (v < 0) for v in vals]
            cols = [C_NEUTRAL if v == 0 else (C_GAIN if g else C_LOSS) for v, g in zip(vals, good)]
            ax.bar(range(len(rows)), vals, color=cols, width=0.75)
            ax.axhline(0, color=AXIS, linewidth=0.8)
            ax.set_xticks(range(len(rows)), [r["trace"] for r in rows], rotation=90, fontsize=6.5)
            ax.set_xlim(-0.7, len(rows) - 0.3)
            ax.grid(axis="x", visible=False)
            ax.set_ylabel(ylab)
            nb = sum(good); nw = sum((not g) and v != 0 for v, g in zip(vals, good))
            what = "higher IPC" if fig_no == 5 else "lower MPKI"
            ax.set_title(f"TFL-TAGE-SC-L vs {lab[b]}: {what} on {nb} of {len(rows)} traces, worse on {nw}",
                         loc="left", color=INK)
            if fig_no == 6:
                ax.set_yscale("symlog", linthresh=0.01)
                ax.set_ylabel(ylab + "\n(symmetric log scale)")
        axs[0, 0].legend(handles=[Patch(color=C_GAIN, label="proposed better"), Patch(color=C_LOSS, label="proposed worse")],
                         loc="upper right", fontsize=7.5)
        fig.tight_layout()
        save(fig, out, fname)

    # 7 — MPKI heatmap, trace x predictor
    preds = [s["predictor"] for s in S]
    rows = sorted(P, key=lambda r: (r["suite"], r["trace"]))
    M = [[max(float(r["mpki_" + p]), 1e-3) for p in preds] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 13))
    im = ax.imshow(M, aspect="auto", cmap=SEQ, norm=LogNorm(vmin=1e-3, vmax=max(max(m) for m in M)))
    ax.set_xticks(range(len(preds)), [short(lab[p]).replace("\n", " ") for p in preds], rotation=30, ha="right")
    ax.set_yticks(range(len(rows)), [f"{r['trace']} ({r['suite']})" for r in rows], fontsize=7)
    ax.grid(False)
    for i, m in enumerate(M):
        for j, val in enumerate(m):
            raw = float(rows[i]["mpki_" + preds[j]])
            ax.text(j, i, f"{raw:.3f}" if raw < 10 else f"{raw:.2f}", ha="center", va="center", fontsize=6,
                    color="white" if val > 0.5 else INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("MPKI (log scale)")
    ax.set_title(f"MPKI per trace and predictor ({len(rows)} traces)", loc="left", color=INK)
    fig.tight_layout()
    save(fig, out, "fig7_mpki_heatmap")

    # 8 - storage vs mean MPKI: all predictors (log x) and a zoom on the 45-65 KB class
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    big = [s for s in S if float(s["storage_KB"]) > 16]
    for ax, rows, zoom in ((axs[0], S, False), (axs[1], big, True)):
        ys = sorted(float(s["mean_mpki"]) for s in rows)
        for s in rows:
            x, y = float(s["storage_KB"]), float(s["mean_mpki"])
            ax.scatter([x], [y], s=60, color=color_of(s["predictor"]), edgecolor="white", linewidth=1.5, zorder=3)
            if zoom or float(s["storage_KB"]) < 16:
                # in the zoom, alternate label sides by MPKI rank so neighbours do not collide
                k = ys.index(y)
                dx, ha = ((8, "left") if k % 2 == 0 else (-8, "right")) if zoom else (8, "left")
                ax.annotate(s["label"].replace(" (proposed)", " (ours)") + (f"\n{y:.3f} MPKI, {x:.1f} KB" if zoom else ""),
                            (x, y), xytext=(dx, 0), textcoords="offset points", ha=ha, va="center", fontsize=7.5, color=INK)
        ax.set_ylabel(f"Mean MPKI ({n} traces)")
    axs[0].set_xscale("log")
    axs[0].set_xlim(3, 120)
    axs[0].set_xlabel("Predictor storage (KB, log scale)")
    axs[0].set_title("(a) All predictors", loc="left", color=INK)
    if big:
        lo = min(float(s["mean_mpki"]) for s in big); hi = max(float(s["mean_mpki"]) for s in big)
        xl = min(float(s["storage_KB"]) for s in big); xh = max(float(s["storage_KB"]) for s in big)
        axs[1].set_ylim(lo - 0.25 * (hi - lo), hi + 0.25 * (hi - lo))
        axs[1].set_xlim(xl - 0.35 * (xh - xl), xh + 0.35 * (xh - xl))
        axs[0].add_patch(plt.Rectangle((xl * 0.93, lo - 0.25 * (hi - lo)), xh * 1.07 - xl * 0.93, 1.5 * (hi - lo),
                                       fill=False, edgecolor=MUTED, linewidth=0.8, linestyle="--"))
    axs[1].set_xlabel("Predictor storage (KB)")
    axs[1].set_title("(b) Zoom: 45-65 KB predictors (axes do not start at zero)", loc="left", color=INK)
    fig.tight_layout()
    save(fig, out, "fig8_storage_vs_mpki")

    # 9 — per-trace MPKI reduction vs IPC gain relative to the best baseline
    fig, axs = plt.subplots(1, len(refs), figsize=(6 * len(refs), 4), squeeze=False)
    for ax, b in zip(axs[0], refs):
        for suite_name, col in (("INT", C_S1), ("FP", C_S2)):
            rr = [r for r in P if r["suite"] == suite_name]
            ax.scatter([-float(r["mpki_change_vs_" + b]) for r in rr], [float(r["ipc_change_pct_vs_" + b]) for r in rr],
                       s=28, color=col, edgecolor="white", linewidth=1, label=f"SPEC{suite_name.lower()} ({len(rr)})", zorder=3)
        # label the four largest IPC changes, skipping a label whose point is too close to one already labelled
        pts = [(-float(r["mpki_change_vs_" + b]), float(r["ipc_change_pct_vs_" + b])) for r in P]
        xr = (max(x for x, _ in pts) - min(x for x, _ in pts)) or 1
        yr = (max(y for _, y in pts) - min(y for _, y in pts)) or 1
        done = []
        for r in sorted(P, key=lambda r: abs(float(r["ipc_change_pct_vs_" + b])), reverse=True)[:4]:
            x, y = -float(r["mpki_change_vs_" + b]), float(r["ipc_change_pct_vs_" + b])
            if any(abs(x - u) / xr < 0.25 and abs(y - v) / yr < 0.06 for u, v in done):
                continue
            done.append((x, y))
            ax.annotate(r["trace"], (x, y), xytext=(4, 3), textcoords="offset points", fontsize=6.5, color=INK2)
        ax.axhline(0, color=AXIS, linewidth=0.8); ax.axvline(0, color=AXIS, linewidth=0.8)
        ax.set_xlabel(f"MPKI reduction vs {lab[b]}")
        ax.set_ylabel("IPC change (%)")
        ax.set_title(f"Per-trace effect vs {lab[b]}", loc="left", color=INK)
        ax.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout()
    save(fig, out, "fig9_mpki_reduction_vs_ipc_gain")

    # 10 — generalisation: original 10 vs additional 40
    bases = [s["predictor"] for s in others]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, key, ylab, title in ((axs[0], "proposed_pct_mpki_reduction", "MPKI reduction (%)", "(a) MPKI reduction of TFL-TAGE-SC-L"),
                                 (axs[1], "proposed_ipc_speedup_pct", "Geomean IPC improvement (%)", "(b) IPC improvement of TFL-TAGE-SC-L")):
        w = 0.38
        for k, (sub, col) in enumerate((("original10", C_S1), ("additional40", C_S2))):
            rows = {r["predictor"]: r for r in SUB if r["subset"] == sub}
            if not rows:
                continue
            vals = [float(rows[b][key]) for b in bases]
            ax.bar([i + (k - 0.5) * w for i in range(len(bases))], vals, width=w - 0.04, color=col,
                   label=f"{'original 10' if sub == 'original10' else 'additional 40'} traces (n = {rows[bases[0]]['n_traces']})")
        ax.set_xticks(range(len(bases)), [short(lab[b]) for b in bases], fontsize=7)
        ax.axhline(0, color=AXIS, linewidth=0.8)
        ax.grid(axis="x", visible=False)
        ax.set_ylabel(ylab)
        for c in ax.containers:
            ax.bar_label(c, fmt="%.2f", fontsize=6.5, padding=2, color=INK)
        ax.margins(y=0.12)
        ax.set_title(title + " vs each baseline", loc="left", color=INK)
        ax.legend(loc="upper right", fontsize=7.5)
    fig.tight_layout()
    save(fig, out, "fig10_generalisation_original_vs_additional")


if __name__ == "__main__":
    main()
