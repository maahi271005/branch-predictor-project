#!/usr/bin/env python3
"""Build the corrected figures and results workbook from the independent audit data.

  build/venv/bin/python final_deliverables/scripts/build_results.py

Inputs : final_deliverables/audit/{per_run,summary,relative,ablation,harness_vs_champsim,seed_sensitivity}.csv
         (produced by recompute_metrics.py and seed_sensitivity.py from the raw outputs)
Outputs: final_deliverables/figures/*.png, final_deliverables/TFL-TAGE-SC-L_Results.xlsx,
         final_deliverables/audit/storage.csv
"""
import csv, math, os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FD = os.path.join(ROOT, "final_deliverables")
AUD, FIG = os.path.join(FD, "audit"), os.path.join(FD, "figures")
TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]
SHORT = {t: t.split(".")[1].split("_")[0] for t in TRACES}
LABEL = {"bimodal": "Bimodal", "gshare": "Gshare", "perceptron": "Perceptron", "hashed_perceptron": "Hashed perceptron",
         "tage": "TAGE", "tage_l": "TAGE + loop", "tsl_base": "TAGE-SC-L", "tsl_imli": "TAGE-SC-L + IMLI",
         "tsl_proposed": "TFL-TAGE-SC-L (proposed)", "tsl_prop_noloop": "Proposed without loop",
         "tsl_prop_nolocal": "Proposed without local SC"}
MAIN = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tsl_base", "tsl_imli", "tsl_proposed"]
COL = {"bimodal": "#9e9e9e", "gshare": "#c7c7c7", "perceptron": "#9ecae1", "hashed_perceptron": "#3182bd",
       "tage": "#fdae6b", "tage_l": "#fd8d3c", "tsl_base": "#e6550d", "tsl_imli": "#74c476", "tsl_proposed": "#006d2c",
       "tsl_prop_noloop": "#a1d99b", "tsl_prop_nolocal": "#c7e9c0"}

# Storage (bits) — see storage.csv for the derivation of every entry.
STORAGE = {
    "bimodal": (32768, "16,384 x 2-bit counters (16,381 used: index = PC mod 16381)"),
    "gshare": (32782, "16,384 x 2-bit counters + 14-bit global history"),
    "perceptron": (32624, "163 perceptrons x 25 weights x 8 bit + 24-bit history (speculative copy not counted: identical under immediate update)"),
    "hashed_perceptron": (524542, "16 x 4,096 x 8-bit weights (524,288) + 240-bit history + theta (8 bit, assumed) + training counter (6 bit)"),
    "tage": (383674, "predictor-reported storage_bits(); see TFL breakdown"),
    "tage_l": (386177, "TAGE + 2,503-bit loop predictor"),
    "tsl_base": (476319, "TAGE + loop + statistical corrector without IMLI components"),
    "tsl_imli": (487658, "+ IMLI-SIC (3,082) + backward-inference tables (8,257)"),
    "tsl_proposed": (508666, "+ IMHIST (8,704) + backward-branch history (12,304)"),
    "tsl_prop_noloop": (506163, "proposed - loop predictor"),
    "tsl_prop_nolocal": (479994, "proposed - local-history SC tables and local histories"),
}
TFL_BREAKDOWN = [
    ("Bimodal base", "8K x 2-bit counters", 16384),
    ("Tagged tables T1-T12", "12 x 2,048 entries x (3-bit ctr + 1-bit u + 8..13-bit tag)", 366592),
    ("TAGE control and histories", "use_alt_on_na 4 x 5 bit, TICK 11 bit, 640-bit global + 27-bit path history", 698),
    ("Loop predictor", "64 x (2 x 10-bit counts, 10-bit tag, 4-bit conf, 4-bit age, 1-bit dir) + 7-bit WITHLOOP", 2503),
    ("SC bias tables", "3 x 1,024 x 6 bit", 18432),
    ("SC global + path GEHL", "7 x 1,024 x 6 bit", 43008),
    ("SC control", "threshold 9 bit, threshold counter 7 bit, 2 choosers x 7 bit", 30),
    ("SC local GEHL + local histories", "4 x 1,024 x 6 bit + 256 x 16-bit histories", 28672),
    ("IMLI-SIC", "512 x 6 bit + 10-bit IMLI counter", 3082),
    ("Backward-branch inference", "bwd 4,096 bit + cond 4,096 bit + previous PC 64 bit + previous outcome 1 bit", 8257),
    ("IMHIST", "256 x 10-bit histories + 1,024 x 6-bit table", 8704),
    ("Backward-branch history", "16-bit history + 2 x 1,024 x 6-bit tables", 12304),
]
NOT_COUNTED = [("Folded-history registers (index/tag/GEHL folding)", 422, "recomputable from the global history; excluded, as in TAGE storage reports"),
               ("Pseudo-random generator state", 64, "any cheap LFSR would do; excluded"),
               ("Per-prediction scratch values (indices, sums)", 0, "pipeline latches, not storage")]


def rd(name):
    return list(csv.DictReader(open(os.path.join(AUD, name))))


def main():
    os.makedirs(FIG, exist_ok=True)
    runs = {(r["binary"], r["trace"]): r for r in rd("per_run.csv")}
    S = {r["predictor"]: r for r in rd("summary.csv")}
    REL = rd("relative.csv")
    AB = rd("ablation.csv")
    HVC = rd("harness_vs_champsim.csv")
    SEED = rd("seed_sensitivity.csv") if os.path.exists(os.path.join(AUD, "seed_sensitivity.csv")) else []
    f = lambda p, t, k: float(runs[p, t][k])
    assert sum(b for _, _, b in TFL_BREAKDOWN) == STORAGE["tsl_proposed"][0] == int(S["tsl_proposed"]["banner_storage_bits"])
    for p in ("tage", "tage_l", "tsl_base", "tsl_imli", "tsl_proposed", "tsl_prop_noloop", "tsl_prop_nolocal"):
        assert STORAGE[p][0] == int(S[p]["banner_storage_bits"]), p

    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8})
    xs = range(len(TRACES))

    # ---- Fig 1: overall summary (mean MPKI; geomean IPC speedup vs bimodal)
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    lab = [LABEL[p] for p in MAIN]
    mp = [float(S[p]["mean_mpki"]) for p in MAIN]
    sp = [100 * (float(S[p]["gm_speedup_vs_bimodal"]) - 1) for p in MAIN]
    axs[0].barh(lab, mp, color=[COL[p] for p in MAIN]); axs[0].invert_yaxis()
    axs[0].set_xlabel("Arithmetic-mean MPKI over 10 traces (lower is better)")
    for i, v in enumerate(mp): axs[0].text(v, i, f" {v:.3f}", va="center", fontsize=8)
    axs[0].set_xlim(0, max(mp) * 1.15)
    axs[1].barh(lab, sp, color=[COL[p] for p in MAIN]); axs[1].invert_yaxis()
    axs[1].set_xlabel("Geometric-mean IPC speedup over bimodal (%)")
    for i, v in enumerate(sp): axs[1].text(v, i, f" {v:.2f}%", va="center", fontsize=8)
    axs[1].set_xlim(0, max(sp) * 1.15)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig1_overall_summary.png"), dpi=170); plt.close(fig)

    # ---- Fig 2: MPKI per trace (log)
    fig, ax = plt.subplots(figsize=(11.5, 4.4))
    w = 0.8 / len(MAIN)
    for i, p in enumerate(MAIN):
        ax.bar([k + (i - len(MAIN) / 2 + 0.5) * w for k in xs], [f(p, t, "mpki") for t in TRACES], w, label=LABEL[p], color=COL[p])
    ax.set_yscale("log"); ax.set_ylabel("MPKI (log scale; all branch types)")
    ax.set_xticks(list(xs)); ax.set_xticklabels([SHORT[t] for t in TRACES])
    ax.grid(axis="y", which="both", alpha=0.25)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig2_mpki_per_trace.png"), dpi=170); plt.close(fig)

    # ---- Fig 3: IPC normalised to bimodal, per trace, shown as % change
    fig, ax = plt.subplots(figsize=(11.5, 4.4))
    sel = [p for p in MAIN if p != "bimodal"]
    w = 0.8 / len(sel)
    for i, p in enumerate(sel):
        ax.bar([k + (i - len(sel) / 2 + 0.5) * w for k in xs],
               [100 * (f(p, t, "ipc") / f("bimodal", t, "ipc") - 1) for t in TRACES], w, label=LABEL[p], color=COL[p])
    ax.axhline(0, color="black", lw=0.7)
    ax.set_ylabel("IPC normalised to bimodal, as % change\n100 x (IPC / IPC_bimodal - 1)")
    ax.set_xticks(list(xs)); ax.set_xticklabels([SHORT[t] for t in TRACES]); ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig3_ipc_vs_bimodal_per_trace.png"), dpi=170); plt.close(fig)

    # ---- Fig 4: MPKI reduction vs IPC gain (two panels)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, ref, title in ((axs[0], "hashed_perceptron", "vs hashed perceptron"),
                           (axs[1], "tsl_base", "vs TAGE-SC-L (isolates the loop-structure components)")):
        pts = []
        for t in TRACES:
            dx = f(ref, t, "mpki") - f("tsl_proposed", t, "mpki")
            dy = 100 * (f("tsl_proposed", t, "ipc") / f(ref, t, "ipc") - 1)
            pts.append((SHORT[t], dx, dy))
        xr = max(p[1] for p in pts) - min(0, min(p[1] for p in pts))
        yr = max(p[2] for p in pts) - min(0, min(p[2] for p in pts))
        near = [p for p in pts if abs(p[1]) < 0.06 * xr and abs(p[2]) < 0.06 * yr]
        for name, dx, dy in pts:
            ax.scatter(dx, dy, color="#006d2c", s=22, zorder=3)
            if (name, dx, dy) not in near:
                ax.annotate(name, (dx, dy), xytext=(5, -3), textcoords="offset points", fontsize=7.5)
        if near:
            txt = "near (0, 0):\n" + "\n".join(f"{n}: {dx:+.4f} MPKI, {dy:+.3f}%" for n, dx, dy in sorted(near, key=lambda q: q[1]))
            ax.text(0.98, 0.04, txt, transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
                    bbox=dict(boxstyle="round", fc="white", ec="0.7"))
        lo_y = min(0, min(p[2] for p in pts)); hi_y = max(p[2] for p in pts)
        ax.set_ylim(lo_y - 0.08 * yr, hi_y + 0.12 * yr)
        ax.set_xlim(min(0, min(p[1] for p in pts)) - 0.05 * xr, max(p[1] for p in pts) + 0.18 * xr)
        ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6); ax.grid(alpha=0.25)
        ax.set_xlabel(f"Absolute MPKI reduction {title.split(' (')[0]}  (MPKI_ref - MPKI_proposed)")
        ax.set_ylabel("IPC gain (%) = 100 x (IPC_proposed / IPC_ref - 1)")
        ax.set_title(f"Proposed {title}")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig4_mpki_reduction_vs_ipc_gain.png"), dpi=170); plt.close(fig)

    # ---- Fig 5: branch prediction accuracy (dot plot, two definitions)
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    for ax, key, title in ((axs[0], "accuracy_all", "All branch types (ChampSim definition)"),
                           (axs[1], "accuracy_cond", "Conditional branches only")):
        for i, p in enumerate(MAIN):
            ax.plot([k + (i - len(MAIN) / 2 + 0.5) * 0.09 for k in xs], [f(p, t, key) for t in TRACES], "o", ms=4,
                    color=COL[p], label=LABEL[p], markeredgecolor="black", markeredgewidth=0.3)
        ax.set_xticks(list(xs)); ax.set_xticklabels([SHORT[t] for t in TRACES], rotation=40, ha="right")
        ax.set_ylim(80, 100.5); ax.grid(alpha=0.25); ax.set_title(title)
    axs[0].set_ylabel("Prediction accuracy (%) — axis starts at 80%")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=4, loc="upper center", frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.88)); fig.savefig(os.path.join(FIG, "fig5_accuracy_per_trace.png"), dpi=170); plt.close(fig)

    # ---- Fig 6: ablation (harness), with ChampSim cross-check and seed noise
    main_ab = [r for r in AB if r["region"] == "main"]
    cs_of = {"prop": "tsl_proposed", "prop_noloop": "tsl_prop_noloop", "prop_nolocal": "tsl_prop_nolocal",
             "prop_noimli": "tsl_base", "prop_nosc": "tage_l", "tage": "tage"}
    fig, ax = plt.subplots(figsize=(9, 4.2))
    names = [r["description"] for r in main_ab]
    vals = [float(r["mean_mpki"]) for r in main_ab]
    ax.barh(names, vals, color=["#006d2c"] + ["#a1d99b"] * (len(vals) - 1), label="functional harness (reported window)")
    for i, r in enumerate(main_ab):
        ax.text(vals[i], i, f" {vals[i]:.4f} ({float(r['delta_vs_proposed_pct']):+.2f}%)", va="center", fontsize=7.5)
        if r["variant"] in cs_of:
            ax.plot(float(S[cs_of[r["variant"]]]["mean_mpki"]), i, "k|", ms=14, mew=2, label="ChampSim run" if i == 0 else None)
    if SEED:
        seed_of = {"prop": "proposed", "prop_noimhist": "no_imhist", "prop_nobhist": "no_bhist",
                   "prop_noimli": "tsl_base", "prop_noloop": "no_loop"}
        first = True
        for i, r in enumerate(main_ab):
            if r["variant"] in seed_of:
                ps = [float(x["mean_mpki"]) for x in SEED if x["config"] == seed_of[r["variant"]]]
                ax.plot([min(ps), max(ps)], [i + 0.3, i + 0.3], color="#d95f0e", lw=2.5, solid_capstyle="butt",
                        label="min-max over 4 RNG seeds (harness)" if first else None)
                first = False
    ax.invert_yaxis(); ax.set_xlim(min(vals) * 0.985, max(vals) * 1.06)
    ax.set_xlabel("Mean MPKI over 10 traces — axis does not start at 0")
    ax.legend(loc="upper right", fontsize=7.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig6_ablation.png"), dpi=170); plt.close(fig)

    # ---- Fig 7: storage vs accuracy trade-off (full range + zoom on the 64 KB class)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.25]})
    pts = [(p, STORAGE[p][0] / 8192, float(S[p]["mean_mpki"])) for p in MAIN + ["tage_l"]]
    for p, x, y in pts:
        axs[0].scatter(x, y, color=COL[p], s=40, edgecolor="black", lw=0.4, zorder=3)
        if x < 10:
            axs[0].annotate(LABEL[p], (x, y), xytext=(6, -3), textcoords="offset points", fontsize=7.5)
    axs[0].annotate("64 KB class\n(see right)", (60, 3.2), xytext=(25, 6.5), fontsize=7.5, arrowprops=dict(arrowstyle="->", lw=0.6))
    axs[0].set_xlabel("Storage (KB)"); axs[0].set_ylabel("Mean MPKI (10 traces)"); axs[0].grid(alpha=0.25)
    axs[0].set_xlim(0, 70)
    place = {"tage": (8, 3, "left"), "tage_l": (8, -9, "left"), "tsl_base": (-8, -3, "right"),
             "tsl_imli": (0, 9, "center"), "tsl_proposed": (-8, -3, "right"), "hashed_perceptron": (-8, -3, "right")}
    for p, x, y in pts:
        if x >= 10:
            axs[1].scatter(x, y, color=COL[p], s=46, edgecolor="black", lw=0.4, zorder=3)
            dx, dy, ha = place[p]
            axs[1].annotate(LABEL[p], (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7.5, ha=ha, va="center")
    axs[1].set_ylim(3.02, 3.32)
    axs[1].set_xlabel("Storage (KB)"); axs[1].set_ylabel("Mean MPKI (10 traces)"); axs[1].grid(alpha=0.25)
    axs[1].set_xlim(44, 66.5); axs[1].set_title("Zoom: 45-65 KB predictors (axes do not start at 0)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig7_storage_vs_mpki.png"), dpi=170); plt.close(fig)

    # ---- storage table with increments
    st_rows = []
    chain = [("bimodal", None), ("gshare", "bimodal"), ("perceptron", "bimodal"), ("hashed_perceptron", "bimodal"),
             ("tage", "hashed_perceptron"), ("tage_l", "tage"), ("tsl_base", "tage_l"), ("tsl_imli", "tsl_base"),
             ("tsl_proposed", "tsl_imli")]
    for p, prev in chain:
        bits = STORAGE[p][0]
        row = {"predictor": p, "label": LABEL[p], "storage_bits": bits, "storage_KB": bits / 8192,
               "mean_mpki": float(S[p]["mean_mpki"]), "gm_speedup_vs_bimodal": float(S[p]["gm_speedup_vs_bimodal"]),
               "compared_with": prev or "", "incremental_bits": bits - STORAGE[prev][0] if prev else "",
               "incremental_mpki_change": float(S[p]["mean_mpki"]) - float(S[prev]["mean_mpki"]) if prev else "",
               "incremental_mpki_change_pct": 100 * (float(S[p]["mean_mpki"]) / float(S[prev]["mean_mpki"]) - 1) if prev else "",
               "incremental_ipc_pct": 100 * (float(S[p]["gm_speedup_vs_bimodal"]) / float(S[prev]["gm_speedup_vs_bimodal"]) - 1) if prev else "",
               "basis": STORAGE[p][1]}
        st_rows.append(row)
    with open(os.path.join(AUD, "storage.csv"), "w", newline="") as fo:
        wr = csv.DictWriter(fo, list(st_rows[0])); wr.writeheader(); wr.writerows(st_rows)

    # ---- workbook
    wb = Workbook()
    hdr = Font(bold=True); fill = PatternFill("solid", fgColor="DDEBF7")

    def sheet(title, header, rows, widths=None, first=False):
        ws = wb.active if first else wb.create_sheet(title)
        ws.title = title
        ws.append(header)
        for c in ws[1]: c.font = hdr; c.fill = fill; c.alignment = Alignment(wrap_text=True, vertical="top")
        for r in rows: ws.append(r)
        for i, wdt in enumerate(widths or []):
            ws.column_dimensions[chr(65 + i) if i < 26 else "A" + chr(65 + i - 26)].width = wdt
        ws.freeze_panes = "B2"
        return ws

    ws = sheet("README", ["Item", "Description"], [
        ["What", "Corrected results of the branch-predictor project (TFL-TAGE-SC-L). All values recomputed independently from the raw ChampSim outputs by final_deliverables/scripts/recompute_metrics.py."],
        ["Simulator", "ChampSim 2021 (build_champsim.sh version), 1 core, no prefetchers, LRU LLC."],
        ["Workloads", "10 DPC-3 SPEC CPU2017 traces; every run 50M warm-up + 200M measured instructions (instructions 0-250M)."],
        ["MPKI", "1000 x mispredictions / retired instructions of the measured region (200,000,000-200,000,003). Identical to ChampSim's printed MPKI to 5 decimals."],
        ["IPC", "measured instructions / measured cycles."],
        ["Accuracy (all)", "(branches - mispredictions)/branches over ALL branch types (ChampSim's definition: the 2021 interface predicts the direction of every branch type; unconditional branches are always taken)."],
        ["Accuracy (cond.)", "same ratio restricted to conditional branches (per-type counters added to ChampSim; stats only)."],
        ["Mean MPKI", "arithmetic mean over the 10 traces. % reductions are computed from the means: (MPKI_ref - MPKI_p)/MPKI_ref x 100."],
        ["Speedup", "geometric mean over traces of IPC_p / IPC_ref. IPC improvement % = (speedup - 1) x 100. Arithmetic mean IPC shown for information only."],
        ["Pooled accuracy", "sum over traces of correct predictions / sum of branches (weights traces by branch count)."],
        ["Harness", "Ablation and noise-floor sheets use the functional replay harness (MPKI only, no IPC). They are labelled as such and are not ChampSim results."],
        ["Storage", "logical state in bits, from the predictors' source code; not physical area. See Storage sheet for assumptions."],
    ], widths=[18, 140], first=True)

    preds = list(S)
    sheet("Summary (ChampSim)", ["Predictor", "Storage bits", "Storage KB", "Mean MPKI", "Mean MPKI (7 int)", "Mean cond. MPKI",
                                 "Geomean speedup vs bimodal", "Geomean speedup vs hashed perceptron", "Geomean speedup vs TAGE-SC-L",
                                 "Mean IPC (info)", "Pooled accuracy all %", "Pooled accuracy cond. %", "Mean accuracy all %", "Total mispredictions"],
          [[LABEL[p], STORAGE[p][0], STORAGE[p][0] / 8192, float(S[p]["mean_mpki"]), float(S[p]["mean_mpki_int7"]), float(S[p]["mean_cond_mpki"]),
            float(S[p]["gm_speedup_vs_bimodal"]), float(S[p]["gm_speedup_vs_hashed_perceptron"]), float(S[p]["gm_speedup_vs_tsl_base"]),
            float(S[p]["mean_ipc"]), float(S[p]["pooled_accuracy_all"]), float(S[p]["pooled_accuracy_cond"]),
            float(S[p]["mean_accuracy_all"]), int(S[p]["total_mispredictions"])] for p in preds],
          widths=[26] + [14] * 13)
    sheet("Proposed vs baselines", ["Baseline", "Baseline mean MPKI", "Proposed mean MPKI", "Absolute MPKI reduction", "% MPKI reduction",
                                    "Geomean IPC speedup", "IPC improvement %", "Traces with lower MPKI", "Traces with higher MPKI",
                                    "Traces with higher IPC", "Traces with lower IPC"],
          [[LABEL[r["proposed_vs"]], float(r["baseline_mean_mpki"]), float(r["proposed_mean_mpki"]), float(r["abs_mpki_reduction"]),
            float(r["pct_mpki_reduction"]), float(r["gm_ipc_speedup"]), float(r["ipc_improvement_pct"]), int(r["traces_lower_mpki"]),
            int(r["traces_higher_mpki"]), int(r["traces_higher_ipc"]), int(r["traces_lower_ipc"])] for r in REL], widths=[22] + [14] * 10)
    for key, title in (("ipc", "IPC per trace"), ("mpki", "MPKI per trace"), ("accuracy_all", "Accuracy all per trace"),
                       ("accuracy_cond", "Accuracy cond per trace"), ("mispredictions", "Mispredictions per trace")):
        sheet(title, ["Trace"] + [LABEL[p] for p in preds], [[SHORT[t]] + [f(p, t, key) for p in preds] for t in TRACES], widths=[12] + [14] * len(preds))
    sheet("Raw counters", ["Predictor", "Trace", "Warm-up M", "Measured M", "Exit", "Completed", "Trace wrapped", "Instructions", "Cycles",
                           "Branches", "Mispredictions", "Cond. branches", "Cond. mispredictions", "IPC", "MPKI", "ChampSim printed MPKI",
                           "Binary sha (16)", "Raw output file"],
          [[r["binary"], r["trace"], int(r["warm_M"]), int(r["sim_M"]), int(r["exit"]), r["completed"], r["wrapped"], int(r["instructions"]),
            int(r["cycles"]), int(r["branches"]), int(r["mispredictions"]), int(r["cond_branches"]), int(r["cond_mispredictions"]),
            float(r["ipc"]), float(r["mpki"]), float(r["mpki_printed"]), r["bin_sha16"], r["path"]] for r in runs.values()],
          widths=[18, 22] + [11] * 15 + [60])
    ws = sheet("Storage", ["Predictor", "Bits", "KB", "Mean MPKI", "Geomean speedup vs bimodal", "Compared with", "Incremental bits",
                           "Incremental MPKI change", "Incremental MPKI change %", "Incremental IPC %", "Basis"],
               [[r["label"], r["storage_bits"], r["storage_KB"], r["mean_mpki"], r["gm_speedup_vs_bimodal"], LABEL.get(r["compared_with"], ""),
                 r["incremental_bits"], r["incremental_mpki_change"], r["incremental_mpki_change_pct"], r["incremental_ipc_pct"], r["basis"]] for r in st_rows],
               widths=[24, 10, 8, 10, 12, 18, 12, 12, 12, 12, 90])
    ws.append([]); ws.append(["TFL-TAGE-SC-L breakdown", "Bits", "", "", "", "", "", "", "", "", "Structure"])
    for n, d, b in TFL_BREAKDOWN: ws.append([n, b, b / 8192] + [""] * 7 + [d])
    ws.append(["Total", sum(b for _, _, b in TFL_BREAKDOWN), sum(b for _, _, b in TFL_BREAKDOWN) / 8192])
    ws.append([]); ws.append(["Not counted (assumption)", "Bits", "", "", "", "", "", "", "", "", "Reason"])
    for n, b, why in NOT_COUNTED: ws.append([n, b] + [""] * 8 + [why])
    sheet("Ablation (harness)", ["Region", "Variant", "Description", "Flags", "Mean MPKI", "Delta vs proposed %"] + [SHORT[t] for t in TRACES],
          [[r["region"], r["variant"], r["description"], r["flags"], float(r["mean_mpki"]), float(r["delta_vs_proposed_pct"])] +
           [float(r[t]) for t in TRACES] for r in AB], widths=[8, 14, 44, 40, 11, 11] + [9] * 10)
    sheet("Harness vs ChampSim", ["ChampSim predictor", "Harness variant", "Trace", "ChampSim mispredictions", "Harness mispredictions",
                                  "Difference %", "ChampSim MPKI", "Harness MPKI"],
          [[r["champsim_predictor"], r["harness_variant"], r["trace"], int(r["champsim_mispredictions"]), int(r["harness_mispredictions"]),
            float(r["rel_diff_pct"]), float(r["champsim_mpki"]), float(r["harness_mpki"])] for r in HVC], widths=[18, 16, 22, 14, 14, 11, 12, 12])
    if SEED:
        sheet("Noise floor (harness seeds)", ["Config", "Seed", "Mean MPKI"] + [SHORT[t] for t in TRACES],
              [[s["config"], int(s["seed"]), float(s["mean_mpki"])] + [float(s[t]) for t in TRACES] for s in SEED], widths=[12, 6, 11] + [9] * 10)
    wsg = wb.create_sheet("Graphs")
    row = 1
    for fn in sorted(os.listdir(FIG)):
        img = Image(os.path.join(FIG, fn)); sc = 640 / img.width
        img.width, img.height = img.width * sc, img.height * sc
        wsg.cell(row=row, column=1, value=fn).font = hdr
        wsg.add_image(img, f"A{row + 1}"); row += int(img.height / 19) + 4
    wb.save(os.path.join(FD, "TFL-TAGE-SC-L_Results.xlsx"))
    print("figures:", sorted(os.listdir(FIG)))
    print("wrote", os.path.join(FD, "TFL-TAGE-SC-L_Results.xlsx"))


if __name__ == "__main__":
    main()
