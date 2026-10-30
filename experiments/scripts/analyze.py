#!/usr/bin/env python3
"""Build the results/comparison files and figures from raw ChampSim outputs.

  build/venv/bin/python experiments/scripts/analyze.py [--out submission/results]

Inputs  : experiments/results/B_baseline_50M_200M/*/*.txt and G_final_50M_200M/*/*.txt (ChampSim),
          experiments/results/harness/{main,tune}/*.txt (MPKI ablations from the replay harness)
Outputs : results_per_trace.csv, results_summary.csv, ablation_mpki.csv,
          Branch_Predictor_Results.xlsx, figures/*.png

Aggregates
  mean IPC              arithmetic mean over the 10 traces (information only)
  geomean speedup       geometric mean over traces of IPC(pred)/IPC(reference)
  mean MPKI             arithmetic mean over the 10 traces (and over the 7 integer traces)
  MPKI reduction        1 - meanMPKI(pred)/meanMPKI(reference), computed on the means
  accuracy              ChampSim definition, all branch types; conditional-only reported separately
"""
import argparse, csv, math, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "experiments", "results")
sys.path.insert(0, os.path.join(ROOT, "experiments", "scripts"))
from parse_results import parse  # noqa: E402

TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]
SHORT = {t: t.split(".")[1].split("_")[0] for t in TRACES}
INT = {"602", "605", "620", "623", "625", "631", "657"}

# predictor -> (stage, label, storage bits, role)
PRED = {
    "bimodal":           ("B_baseline_50M_200M", "Bimodal", 32768, "baseline (repo)"),
    "gshare":            ("B_baseline_50M_200M", "Gshare", 32782, "baseline (repo)"),
    "perceptron":        ("B_baseline_50M_200M", "Perceptron", 32648, "baseline (repo)"),
    "hashed_perceptron": ("B_baseline_50M_200M", "Hashed perceptron", 524542, "baseline (repo, 64 KB)"),
    "tage":              ("G_final_50M_200M", "TAGE", 383674, "baseline (re-implemented)"),
    "tage_l":            ("G_final_50M_200M", "TAGE + loop", 386177, "baseline (re-implemented)"),
    "tsl_base":          ("G_final_50M_200M", "TAGE-SC-L", 476319, "baseline (re-implemented, no IMLI)"),
    "tsl_imli":          ("G_final_50M_200M", "TAGE-SC-L + IMLI", 487658, "intermediate"),
    "tsl_proposed":      ("G_final_50M_200M", "Proposed (TSL + IMLI + IMHIST + BHIST)", 508666, "proposed"),
    "tsl_prop_noloop":   ("G_final_50M_200M", "Proposed - loop", 506163, "ablation"),
    "tsl_prop_nolocal":  ("G_final_50M_200M", "Proposed - local", 479994, "ablation"),
}
MAIN = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tsl_base", "tsl_imli", "tsl_proposed"]


def load():
    data, missing = {}, []
    for p, (stage, *_rest) in PRED.items():
        for t in TRACES:
            f = os.path.join(RES, stage, p, t + ".txt")
            if not os.path.exists(f):
                missing.append((p, t)); continue
            r = parse(f)
            if not r.get("complete") or r.get("exit") != "0" or "ipc" not in r:
                missing.append((p, t)); continue
            r["file"] = os.path.relpath(f, ROOT)
            data[p, t] = r
    return data, missing


def gmean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def harness_table(region):
    d = os.path.join(RES, "harness", region)
    out = {}
    for name in ("prop", "prop_noimhist", "prop_nobhist", "prop_noimli", "prop_noloop", "prop_nolocal", "prop_nosc", "tage"):
        f = os.path.join(d, name + ".txt")
        if not os.path.exists(f):
            continue
        lines = [l for l in open(f) if not l.startswith("#")]
        out[name] = {l.split(".br")[0]: float(re.search(r" mpki=(\S+)", l).group(1)) for l in lines}
    return out


ABL_LABEL = {
    "prop": "Proposed (all components)",
    "prop_noimhist": "- IMHIST",
    "prop_nobhist": "- backward-branch history",
    "prop_noimli": "- all IMLI-derived components (= TAGE-SC-L)",
    "prop_noloop": "- loop predictor",
    "prop_nolocal": "- local-history SC tables",
    "prop_nosc": "- statistical corrector (= TAGE + loop)",
    "tage": "TAGE only",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "submission", "results"))
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "figures"), exist_ok=True)
    data, missing = load()
    if missing:
        print("WARNING: missing/incomplete runs:", missing)
    preds = [p for p in PRED if all((p, t) in data for t in TRACES)]

    # ------------------------------------------------------------ per-trace CSV
    per_trace = []
    for p in preds:
        for t in TRACES:
            r = data[p, t]
            per_trace.append({
                "predictor": p, "label": PRED[p][1], "role": PRED[p][3], "storage_bits": PRED[p][2],
                "storage_KB": round(PRED[p][2] / 8192, 2), "trace": t,
                "warmup_M": r["warm_M"], "measured_M": r["sim_M"],
                "ipc": r["ipc"], "instructions": r["instructions"], "cycles": r["cycles"],
                "branches": r["branches"], "mispredictions": r["mispredictions"],
                "accuracy_pct_all_branches": round(r["accuracy_pct"], 4), "mpki": round(r["mpki"], 4),
                "cond_branches": r["cond_branches"], "cond_mispredictions": r["cond_mispredictions"],
                "cond_accuracy_pct": round(r["cond_accuracy_pct"], 4), "cond_mpki": round(r["cond_mpki"], 4),
                "ipc_speedup_vs_bimodal": round(r["ipc"] / data["bimodal", t]["ipc"], 5),
                "ipc_speedup_vs_hashed_perceptron": round(r["ipc"] / data["hashed_perceptron", t]["ipc"], 5),
                "raw_output": r["file"],
            })
    with open(os.path.join(a.out, "results_per_trace.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(per_trace[0])); w.writeheader(); w.writerows(per_trace)

    # ------------------------------------------------------------ summary
    summ = []
    hp_mpki = sum(data["hashed_perceptron", t]["mpki"] for t in TRACES) / 10
    base_mpki = sum(data["tsl_base", t]["mpki"] for t in TRACES) / 10 if "tsl_base" in preds else float("nan")
    for p in preds:
        ipc = [data[p, t]["ipc"] for t in TRACES]
        mp = [data[p, t]["mpki"] for t in TRACES]
        mp_int = [data[p, t]["mpki"] for t in TRACES if t[:3] in INT]
        mis = sum(data[p, t]["mispredictions"] for t in TRACES)
        br = sum(data[p, t]["branches"] for t in TRACES)
        cmis = sum(data[p, t]["cond_mispredictions"] for t in TRACES)
        cbr = sum(data[p, t]["cond_branches"] for t in TRACES)
        row = {
            "predictor": p, "label": PRED[p][1], "role": PRED[p][3],
            "storage_bits": PRED[p][2], "storage_KB": round(PRED[p][2] / 8192, 2),
            "mean_ipc": round(sum(ipc) / 10, 5),
            "geomean_speedup_vs_bimodal": round(gmean([data[p, t]["ipc"] / data["bimodal", t]["ipc"] for t in TRACES]), 5),
            "geomean_speedup_vs_hashed_perceptron": round(gmean([data[p, t]["ipc"] / data["hashed_perceptron", t]["ipc"] for t in TRACES]), 5),
            "geomean_speedup_vs_tage_sc_l": round(gmean([data[p, t]["ipc"] / data["tsl_base", t]["ipc"] for t in TRACES]), 5) if "tsl_base" in preds else "",
            "mean_mpki_10": round(sum(mp) / 10, 4), "mean_mpki_int7": round(sum(mp_int) / 7, 4),
            "mpki_reduction_vs_hashed_perceptron_pct": round(100 * (1 - (sum(mp) / 10) / hp_mpki), 2),
            "mpki_reduction_vs_tage_sc_l_pct": round(100 * (1 - (sum(mp) / 10) / base_mpki), 2) if "tsl_base" in preds else "",
            "pooled_accuracy_all_pct": round(100 * (br - mis) / br, 4),
            "pooled_cond_accuracy_pct": round(100 * (cbr - cmis) / cbr, 4),
            "mean_accuracy_all_pct": round(sum(data[p, t]["accuracy_pct"] for t in TRACES) / 10, 4),
            "total_mispredictions": mis,
        }
        summ.append(row)
    with open(os.path.join(a.out, "results_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(summ[0])); w.writeheader(); w.writerows(summ)

    # ------------------------------------------------------------ ablation (harness MPKI)
    abl_rows = []
    for region in ("main", "tune"):
        tab = harness_table(region)
        if "prop" not in tab:
            continue
        ref = sum(tab["prop"].values()) / 10
        for name, vals in tab.items():
            m = sum(vals.values()) / 10
            row = {"region": region, "variant": name, "description": ABL_LABEL[name], "mean_mpki_10": round(m, 4),
                   "delta_vs_proposed_pct": round(100 * (m - ref) / ref, 2)}
            row.update({SHORT[t]: round(vals[t], 4) for t in TRACES})
            abl_rows.append(row)
    if abl_rows:
        with open(os.path.join(a.out, "ablation_mpki.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, list(abl_rows[0])); w.writeheader(); w.writerows(abl_rows)

    figures(a.out, data, preds, abl_rows)
    workbook(a.out, per_trace, summ, abl_rows, data, preds)
    for s in summ:
        print(f"{s['label'][:40]:40s} IPC={s['mean_ipc']:.4f} gm/hp={s['geomean_speedup_vs_hashed_perceptron']:.4f} "
              f"MPKI={s['mean_mpki_10']:.4f} red/hp={s['mpki_reduction_vs_hashed_perceptron_pct']:6.2f}% acc={s['pooled_accuracy_all_pct']:.3f}")


def figures(out, data, preds, abl_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir = os.path.join(out, "figures")
    show = [p for p in MAIN if p in preds]
    colors = ["#9e9e9e", "#bdbdbd", "#8c96c6", "#6a51a3", "#fdae6b", "#e6550d", "#31a354", "#006d2c"]
    x = range(len(TRACES))
    wbar = 0.8 / len(show)

    def grouped(metric, ylabel, fname, log=False, ref=None):
        fig, ax = plt.subplots(figsize=(12, 4.6))
        for i, p in enumerate(show):
            vals = [data[p, t][metric] / (data[ref, t][metric] if ref else 1) for t in TRACES]
            ax.bar([k + (i - len(show) / 2 + 0.5) * wbar for k in x], vals, wbar, label=PRED[p][1], color=colors[i % len(colors)])
        ax.set_xticks(list(x)); ax.set_xticklabels([SHORT[t] for t in TRACES])
        ax.set_ylabel(ylabel)
        if log: ax.set_yscale("log")
        if ref: ax.axhline(1.0, color="black", lw=0.8)
        ax.legend(fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(fig_dir, fname), dpi=160); plt.close(fig)

    grouped("mpki", "MPKI (log scale)", "fig_mpki_per_trace.png", log=True)
    grouped("ipc", "IPC normalised to bimodal", "fig_ipc_speedup_per_trace.png", ref="bimodal")
    grouped("accuracy_pct", "Accuracy % (all branch types)", "fig_accuracy_per_trace.png")

    # aggregate bars
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2))
    labels = [PRED[p][1].replace(" (TSL + IMLI + IMHIST + BHIST)", "") for p in show]
    mp = [sum(data[p, t]["mpki"] for t in TRACES) / 10 for p in show]
    sp = [gmean([data[p, t]["ipc"] / data["bimodal", t]["ipc"] for t in TRACES]) for p in show]
    axs[0].barh(labels, mp, color=colors[:len(show)]); axs[0].set_xlabel("mean MPKI (10 traces)"); axs[0].invert_yaxis()
    for i, v in enumerate(mp): axs[0].text(v, i, f" {v:.3f}", va="center", fontsize=8)
    axs[1].barh(labels, sp, color=colors[:len(show)]); axs[1].set_xlabel("geomean IPC speedup vs bimodal"); axs[1].invert_yaxis()
    axs[1].set_xlim(min(sp) - 0.02, max(sp) + 0.03)
    for i, v in enumerate(sp): axs[1].text(v, i, f" {v:.4f}", va="center", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(fig_dir, "fig_aggregate.png"), dpi=160); plt.close(fig)

    # MPKI reduction vs IPC gain, per trace, proposed vs hashed perceptron
    if "tsl_proposed" in preds:
        fig, ax = plt.subplots(figsize=(6.4, 4.6))
        for t in TRACES:
            dm = data["hashed_perceptron", t]["mpki"] - data["tsl_proposed", t]["mpki"]
            di = 100 * (data["tsl_proposed", t]["ipc"] / data["hashed_perceptron", t]["ipc"] - 1)
            ax.scatter(dm, di, color="#006d2c"); ax.annotate(SHORT[t], (dm, di), fontsize=8, xytext=(3, 3), textcoords="offset points")
        ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6)
        ax.set_xlabel("MPKI reduction vs hashed perceptron (absolute)"); ax.set_ylabel("IPC gain vs hashed perceptron (%)")
        ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(os.path.join(fig_dir, "fig_mpki_vs_ipc.png"), dpi=160); plt.close(fig)

    # ablation
    rows = [r for r in abl_rows if r["region"] == "main"]
    if rows:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh([r["description"] for r in rows], [r["mean_mpki_10"] for r in rows],
                color=["#006d2c"] + ["#74c476"] * (len(rows) - 1))
        for i, r in enumerate(rows): ax.text(r["mean_mpki_10"], i, f" {r['mean_mpki_10']:.4f} ({r['delta_vs_proposed_pct']:+.2f}%)", va="center", fontsize=8)
        ax.invert_yaxis(); ax.set_xlabel("mean MPKI, 10 traces (reported window, harness) — axis does not start at 0")
        ax.set_xlim(min(r["mean_mpki_10"] for r in rows) * 0.97, max(r["mean_mpki_10"] for r in rows) * 1.06)
        fig.tight_layout(); fig.savefig(os.path.join(fig_dir, "fig_ablation.png"), dpi=160); plt.close(fig)


def workbook(out, per_trace, summ, abl_rows, data, preds):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active; ws.title = "Summary"
    ws.append(["Branch predictor comparison — ChampSim (2021), 1 core, no prefetchers, LRU LLC; "
               "10 DPC-3 SPEC CPU2017 traces; 50M warmup + 200M measured instructions"])
    ws.append([]); ws.append(list(summ[0])); [setattr(c, "font", Font(bold=True)) for c in ws[3]]
    for s in summ: ws.append(list(s.values()))
    ws.append([])
    notes = [
        "Accuracy (all) = (branches - mispredictions)/branches over ALL branch types, ChampSim's definition; the old ChampSim interface predicts the direction of every branch type.",
        "Conditional accuracy restricts the same ratio to conditional branches (from the per-type misprediction counters added to main.cc).",
        "MPKI = 1000 * mispredictions / measured instructions. Mean MPKI is the arithmetic mean over traces; reductions are computed from the means.",
        "Speedups are geometric means of per-trace IPC ratios. Mean IPC is shown for information only.",
        "Storage counts all predictor state in bits (tables, histories, counters); repo baselines counted by hand from their source.",
    ]
    for n in notes: ws.append([n])

    for title, tab in (("Per-trace", per_trace),):
        w2 = wb.create_sheet(title); w2.append(list(tab[0])); [setattr(c, "font", Font(bold=True)) for c in w2[1]]
        for r in tab: w2.append(list(r.values()))

    for metric, title in (("ipc", "IPC"), ("mpki", "MPKI"), ("accuracy_pct", "Accuracy(all)"), ("cond_accuracy_pct", "Accuracy(cond)")):
        w3 = wb.create_sheet(title)
        w3.append(["trace"] + [PRED[p][1] for p in preds]); [setattr(c, "font", Font(bold=True)) for c in w3[1]]
        for t in TRACES: w3.append([t] + [round(data[p, t][metric], 5) for p in preds])

    if abl_rows:
        w4 = wb.create_sheet("Ablation (MPKI)")
        w4.append(list(abl_rows[0])); [setattr(c, "font", Font(bold=True)) for c in w4[1]]
        for r in abl_rows: w4.append(list(r.values()))

    wf = wb.create_sheet("Graphs")
    row = 1
    for fimg in ("fig_aggregate.png", "fig_mpki_per_trace.png", "fig_ipc_speedup_per_trace.png", "fig_mpki_vs_ipc.png", "fig_ablation.png"):
        pth = os.path.join(out, "figures", fimg)
        if os.path.exists(pth):
            img = Image(pth); img.width, img.height = img.width * 0.45, img.height * 0.45
            wf.add_image(img, f"A{row}"); row += int(img.height / 20) + 2
    wb.save(os.path.join(out, "Branch_Predictor_Results.xlsx"))


if __name__ == "__main__":
    main()
