#!/usr/bin/env python3
"""Generate the data-dependent parts of the 50-trace LaTeX report from the CSVs.

  python3 experiments/scripts/make_report_50trace.py [--res results_50trace] [--rep report_50trace]

Writes <rep>/generated/values.tex   \\val{key} definitions for every number quoted in the text
       <rep>/generated/tab_*.tex    tables
       <rep>/generated/values.json  the same values, for verify_report_50trace.py
and copies the figures (PDF) to <rep>/figures/.
A \\val{key} with an unknown key stops LaTeX with an error, so the text cannot quote a
number that is not produced here.
"""
import argparse, csv, json, os, shutil, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROPOSED = "tsl_proposed"
SHORT = {"bimodal": "Bimodal", "gshare": "Gshare", "perceptron": "Perceptron",
         "hashed_perceptron": "Hashed perceptron", "tage": "TAGE", "tsl_base": "TAGE-SC-L",
         "tsl_proposed": "TFL-TAGE-SC-L"}
ABBR = {"bimodal": "Bim.", "gshare": "Gshare", "perceptron": "Perc.", "hashed_perceptron": "Hashed P.",
        "tage": "TAGE", "tsl_base": "TSL", "tsl_proposed": "Proposed"}
KEYNAME = {"bimodal": "bim", "gshare": "gsh", "perceptron": "perc", "hashed_perceptron": "hp",
           "tage": "tage", "tsl_base": "tsl", "tsl_proposed": "prop"}


def read(p):
    return list(csv.DictReader(open(p)))


def tex(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def f(x, nd):
    return f"{float(x):,.{nd}f}"


def sgn(x, nd):
    return f"{float(x):+.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default=os.path.join(ROOT, "results_50trace"))
    ap.add_argument("--rep", default=os.path.join(ROOT, "report_50trace"))
    a = ap.parse_args()
    gen = os.path.join(a.rep, "generated")
    os.makedirs(gen, exist_ok=True)
    os.makedirs(os.path.join(a.rep, "figures"), exist_ok=True)

    S = read(os.path.join(a.res, "summary.csv"))
    Sd = {s["predictor"]: s for s in S}
    P = read(os.path.join(a.res, "per_trace_results.csv"))
    Pok = [r for r in P if r["all_runs_ok"] == "True"]
    C = {r["baseline"]: r for r in read(os.path.join(a.res, "comparison_vs_baselines.csv"))}
    SUB = read(os.path.join(a.res, "subset_summary.csv"))
    RAW = read(os.path.join(a.res, "raw_results.csv"))
    MAN = read(os.path.join(a.res, "trace_manifest.csv"))
    cfg = json.load(open(os.path.join(a.res, "experiment_config.json")))
    preds = [s["predictor"] for s in S]
    others = [p for p in preds if p != PROPOSED]
    defaults = ["bimodal", "gshare", "perceptron", "hashed_perceptron"]

    V = {}

    def put(k, v):
        assert k not in V, k
        V[k] = v

    # experiment-level counts
    put("n_traces", str(len(P)))
    put("n_traces_agg", str(len(Pok)))
    put("n_orig", str(sum(r["group"] == "original10" for r in P)))
    put("n_add", str(sum(r["group"] == "additional40" for r in P)))
    put("n_int", str(sum(r["suite"] == "INT" for r in Pok)))
    put("n_fp", str(sum(r["suite"] == "FP" for r in Pok)))
    put("n_bench", str(len({r["trace"].split("_s-")[0] for r in P})))
    put("n_runs", str(len(RAW)))
    put("n_runs_ok", str(sum(r["status"] == "ok" for r in RAW)))
    put("n_runs_failed", str(sum(r["status"] != "ok" for r in RAW)))
    put("total_sim_hours", f(sum(float(s["total_sim_hours"]) for s in S), 1))
    put("trace_gb", f(sum(int(m["size_bytes"]) for m in MAN) / 1e9, 2))
    put("started", tex(cfg.get("started", "")[:16].replace("T", " ")))
    put("finished", tex(cfg.get("finished", "")[:16].replace("T", " ")))

    # per predictor
    for p in preds:
        k, s = KEYNAME[p], Sd[p]
        put(f"{k}_kb", f(s["storage_KB"], 2))
        put(f"{k}_bits", f"{int(s['storage_bits']):,}")
        put(f"{k}_mean_ipc", f(s["mean_ipc"], 4))
        put(f"{k}_gm_ipc", f(s["geomean_ipc"], 4))
        put(f"{k}_mpki", f(s["mean_mpki"], 3))
        put(f"{k}_median_mpki", f(s["median_mpki"], 3))
        put(f"{k}_acc", f(s["pooled_accuracy"], 3))
        put(f"{k}_cacc", f(s["pooled_cond_accuracy"], 3))
        put(f"{k}_speedup_bim", sgn(100 * (float(s["geomean_speedup_vs_bimodal"]) - 1), 2))
        put(f"{k}_hours", f(s["total_sim_hours"], 1))
        put(f"{k}_mean_wall_min", f(float(s["mean_wall_s"]) / 60, 1))
    d = int(Sd[PROPOSED]["storage_bits"]) - int(Sd["tsl_base"]["storage_bits"])
    put("prop_minus_tsl_bits", f"{d:,}")
    put("prop_minus_tsl_kb", f(d / 8192, 2))
    put("prop_minus_tsl_pct", f(100 * d / int(Sd["tsl_base"]["storage_bits"]), 1))
    d = int(Sd["hashed_perceptron"]["storage_bits"]) - int(Sd[PROPOSED]["storage_bits"])
    put("hp_minus_prop_bits", f"{d:,}")
    for key, rk in (("ipc", "rank_geomean_ipc"), ("mpki", "rank_mean_mpki"), ("acc", "rank_pooled_accuracy")):
        best = min(preds, key=lambda p: int(Sd[p][rk]))
        put(f"best_{key}", SHORT[best])
        put(f"prop_rank_{key}", Sd[PROPOSED][rk])
    best_mean_ipc = max(preds, key=lambda p: float(Sd[p]["mean_ipc"]))
    put("best_mean_ipc", SHORT[best_mean_ipc])
    best_base = max(others, key=lambda p: float(Sd[p]["geomean_ipc"]))
    best_def = max(defaults, key=lambda p: float(Sd[p]["geomean_ipc"]))
    put("best_base", SHORT[best_base])
    put("best_default", SHORT[best_def])

    # proposed vs each baseline
    for b in others:
        k, c = KEYNAME[b], C[b]
        put(f"vs_{k}_pct_mpki", f(c["pct_mpki_reduction"], 2))
        put(f"vs_{k}_abs_mpki", f(c["abs_mpki_reduction"], 4))
        put(f"vs_{k}_ipc", sgn(c["ipc_improvement_pct"], 3))
        put(f"vs_{k}_meanipc", sgn(c["mean_ipc_change_pct"], 3))
        put(f"vs_{k}_acc_pp", sgn(c["pooled_accuracy_change_pp"], 3))
        put(f"vs_{k}_mpki_win", c["traces_lower_mpki"])
        put(f"vs_{k}_mpki_tie", c["traces_equal_mpki"])
        put(f"vs_{k}_mpki_loss", c["traces_higher_mpki"])
        put(f"vs_{k}_ipc_win", c["traces_higher_ipc"])
        put(f"vs_{k}_ipc_tie", c["traces_equal_ipc"])
        put(f"vs_{k}_ipc_loss", c["traces_lower_ipc"])
        put(f"vs_{k}_ipc_win_half", c["traces_ipc_gain_ge_0.5pct"])
        put(f"vs_{k}_ipc_loss_half", c["traces_ipc_loss_ge_0.5pct"])
        put(f"vs_{k}_best_trace", tex(c["largest_ipc_gain_trace"]))
        put(f"vs_{k}_best_pct", sgn(c["largest_ipc_gain_pct"], 2))
        put(f"vs_{k}_worst_trace", tex(c["largest_ipc_loss_trace"]))
        put(f"vs_{k}_worst_pct", sgn(c["largest_ipc_loss_pct"], 2))
        put(f"vs_{k}_bestm_trace", tex(c["largest_mpki_reduction_trace"]))
        put(f"vs_{k}_bestm", f(c["largest_mpki_reduction"], 3))
        put(f"vs_{k}_worstm_trace", tex(c["largest_mpki_increase_trace"]))
        put(f"vs_{k}_worstm", f(c["largest_mpki_increase"], 4))
        # concentration of the gain: share of the mean-MPKI reduction from the single largest contributor,
        # and the reduction without that trace; spread of the per-trace IPC changes
        dm = sorted(Pok, key=lambda r: float(r["mpki_change_vs_" + b]))
        top, rest = dm[0], dm[1:]
        tot = sum(float(r["mpki_change_vs_" + b]) for r in Pok)
        put(f"vs_{k}_top_trace", tex(top["trace"]))
        put(f"vs_{k}_top_share", f(100 * float(top["mpki_change_vs_" + b]) / tot, 1) if tot < 0 else "--")
        mb = statistics.fmean(float(r["mpki_" + b]) for r in rest)
        mp_ = statistics.fmean(float(r["mpki_" + PROPOSED]) for r in rest)
        put(f"vs_{k}_pct_mpki_excl_top", f(100 * (1 - mp_ / mb), 2))
        dip = [float(r["ipc_change_pct_vs_" + b]) for r in Pok]
        put(f"vs_{k}_median_ipc", sgn(statistics.median(dip), 3))
        put(f"vs_{k}_n_ipc_flat", str(sum(abs(x) < 0.01 for x in dip)))
        put(f"vs_{k}_n_ipc_gt0p1", str(sum(x > 0.1 for x in dip)))
        put(f"vs_{k}_n_ipc_ltm0p1", str(sum(x < -0.1 for x in dip)))

    # subsets
    for r in SUB:
        sub, p = r["subset"], r["predictor"]
        k = f"{sub}_{KEYNAME[p]}"
        put(f"{k}_mpki", f(r["mean_mpki"], 3))
        put(f"{k}_gm_ipc", f(r["geomean_ipc"], 4))
        if p != PROPOSED:
            put(f"{k}_red", f(r["proposed_pct_mpki_reduction"], 2))
            put(f"{k}_ipcimp", sgn(r["proposed_ipc_speedup_pct"], 3))
    for sub in sorted({r["subset"] for r in SUB}):
        put(f"{sub}_n", next(r["n_traces"] for r in SUB if r["subset"] == sub))

    # per-trace extremes of MPKI
    mp = sorted(Pok, key=lambda r: float(r["mpki_" + PROPOSED]))
    put("prop_min_mpki_trace", tex(mp[0]["trace"])); put("prop_min_mpki", f(mp[0]["mpki_" + PROPOSED], 4))
    put("prop_max_mpki_trace", tex(mp[-1]["trace"])); put("prop_max_mpki", f(mp[-1]["mpki_" + PROPOSED], 3))
    put("n_prop_mpki_below_0p1", str(sum(float(r["mpki_" + PROPOSED]) < 0.1 for r in Pok)))
    put("n_prop_mpki_above_5", str(sum(float(r["mpki_" + PROPOSED]) > 5 for r in Pok)))
    # n_best_*: traces on which the predictor is best or tied for best; n_sole_*: best alone
    for p in [PROPOSED] + others:
        for m in ("mpki", "ipc"):
            best = [r["best_%s_predictor" % m].split("+") for r in Pok]
            put(f"n_best_{m}_{KEYNAME[p]}", str(sum(p in b for b in best)))
            put(f"n_sole_{m}_{KEYNAME[p]}", str(sum(b == [p] for b in best)))
    for m in ("mpki", "ipc"):
        put(f"n_tied_best_{m}", str(sum("+" in r["best_%s_predictor" % m] for r in Pok)))
    # share of the mean MPKI contributed by the 5 highest-MPKI traces (proposed)
    tot = sum(float(r["mpki_" + PROPOSED]) for r in Pok)
    top5 = sorted(Pok, key=lambda r: -float(r["mpki_" + PROPOSED]))[:5]
    put("top5_mpki_share", f(100 * sum(float(r["mpki_" + PROPOSED]) for r in top5) / tot, 1))
    put("top5_mpki_traces", ", ".join(tex(r["trace"]) for r in top5))

    # largest relative MPKI reduction vs TAGE-SC-L (traces where TAGE-SC-L has MPKI >= 0.05)
    rel = [(1 - float(r["mpki_" + PROPOSED]) / float(r["mpki_tsl_base"]), r) for r in Pok if float(r["mpki_tsl_base"]) >= 0.05]
    rel.sort(key=lambda x: -x[0])
    for i in range(2):
        put(f"tsl_rel{i + 1}_trace", tex(rel[i][1]["trace"])); put(f"tsl_rel{i + 1}_pct", f(100 * rel[i][0], 1))
        put(f"tsl_rel{i + 1}_from", f(rel[i][1]["mpki_tsl_base"], 3)); put(f"tsl_rel{i + 1}_to", f(rel[i][1]["mpki_" + PROPOSED], 3))
        put(f"tsl_rel{i + 1}_ipc", sgn(rel[i][1]["ipc_change_pct_vs_tsl_base"], 3))
        put(f"tsl_rel{i + 1}_prop_ipc", f(rel[i][1]["ipc_" + PROPOSED], 3))
    put("tsl_rel_median_pct", f(100 * statistics.median(x for x, _ in rel), 2))
    put("tsl_rel_n", str(len(rel)))
    # traces on which TAGE (or TAGE-SC-L) mispredicts more than the hashed perceptron
    R_ = {(r["predictor"], r["trace"]): r for r in RAW}
    for k in ("tage", "tsl_base", PROPOSED):
        put(f"n_{KEYNAME[k]}_worse_hp", str(sum(int(R_[k, r["trace"]]["mispredictions"]) > int(R_["hashed_perceptron", r["trace"]]["mispredictions"]) for r in Pok)))

    # validity checks (analyze_50trace.py)
    lines = [l.rstrip("\n") for l in open(os.path.join(a.res, "checks.txt")) if l.startswith(("PASS", "FAIL"))]
    put("checks_total", str(len(lines)))
    put("checks_failed", str(sum(l.startswith("FAIL") for l in lines)))
    orig = [l for l in lines if "original-10 runs identical" in l]
    if orig:
        detail = orig[0].split("[", 1)[1].rstrip("]")      # "<n> identical, <m> different"
        put("orig_identical", detail.split(" identical")[0])
        put("orig_different", detail.split(", ")[1].split(" ")[0])

    # ---- values.tex / values.json ----
    with open(os.path.join(gen, "values.tex"), "w") as fh:
        fh.write("% generated by experiments/scripts/make_report_50trace.py -- do not edit\n")
        fh.write("\\makeatletter\n\\newcommand{\\val}[1]{\\ifcsname val@#1\\endcsname\\csname val@#1\\endcsname"
                 "\\else\\errmessage{undefined report value #1}\\fi}\n")
        for k, v in V.items():
            fh.write(f"\\expandafter\\def\\csname val@{k}\\endcsname{{{v}}}\n")
        fh.write("\\makeatother\n")
    json.dump(V, open(os.path.join(gen, "values.json"), "w"), indent=1)

    def table(name, lines):
        with open(os.path.join(gen, name), "w") as fh:
            fh.write("% generated by experiments/scripts/make_report_50trace.py -- do not edit\n")
            fh.write("\n".join(lines) + "\n")

    # ---- main summary table ----
    L = [r"\begin{tabular}{lrrrrrrr}", r"\toprule",
         r"Predictor & Storage & Mean & Geomean & Speedup vs & Mean & Accuracy & Accuracy \\",
         r" & (KB) & IPC & IPC & Bimodal (\%) & MPKI & all (\%) & cond.\ (\%) \\", r"\midrule"]
    bi = max(preds, key=lambda p: float(Sd[p]["geomean_ipc"]))
    bm = min(preds, key=lambda p: float(Sd[p]["mean_mpki"]))
    ba = max(preds, key=lambda p: float(Sd[p]["pooled_accuracy"]))
    bmi = max(preds, key=lambda p: float(Sd[p]["mean_ipc"]))
    for p in preds:
        s = Sd[p]
        name = SHORT[p] + (" (proposed)" if p == PROPOSED else "")
        b = lambda cond, txt: r"\textbf{" + txt + "}" if cond else txt
        L.append(" & ".join([r"\textbf{" + name + "}" if p == PROPOSED else name, f(s["storage_KB"], 2),
                             b(p == bmi, f(s["mean_ipc"], 4)), b(p == bi, f(s["geomean_ipc"], 4)),
                             b(p == bi, sgn(100 * (float(s["geomean_speedup_vs_bimodal"]) - 1), 2)),
                             b(p == bm, f(s["mean_mpki"], 3)), b(p == ba, f(s["pooled_accuracy"], 3)),
                             f(s["pooled_cond_accuracy"], 3)]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    table("tab_summary.tex", L)

    # ---- proposed vs baselines ----
    L = [r"\begin{tabular}{lrrrrcc}", r"\toprule",
         r"Baseline & Baseline & MPKI & MPKI & Geomean IPC & Traces: lower / equal / & Traces: higher / equal / \\",
         r" & mean MPKI & reduction & reduction (\%) & improvement (\%) & higher MPKI & lower IPC \\", r"\midrule"]
    for b in others:
        c = C[b]
        L.append(" & ".join([SHORT[b], f(c["baseline_mean_mpki"], 3), f(c["abs_mpki_reduction"], 4),
                             f(c["pct_mpki_reduction"], 2), sgn(c["ipc_improvement_pct"], 3),
                             f"{c['traces_lower_mpki']} / {c['traces_equal_mpki']} / {c['traces_higher_mpki']}",
                             f"{c['traces_higher_ipc']} / {c['traces_equal_ipc']} / {c['traces_lower_ipc']}"]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    table("tab_comparison.tex", L)

    # ---- subsets ----
    subs = [s for s in ("all50", "original10", "additional40", "INT", "FP") if any(r["subset"] == s for r in SUB)]
    nice = {"all50": "All traces", "original10": "Original 10", "additional40": "Additional 40",
            "INT": "SPECint", "FP": "SPECfp"}
    L = [r"\begin{tabular}{lrrrrrrr}", r"\toprule",
         r"Subset & $n$ & \multicolumn{3}{c}{Mean MPKI} & \multicolumn{3}{c}{Proposed vs.\ baseline} \\",
         r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
         r" & & Hashed perc. & TAGE-SC-L & Proposed & MPKI red.\ vs HP & MPKI red.\ vs TSL & IPC vs TSL \\", r"\midrule"]
    for sub in subs:
        R = {r["predictor"]: r for r in SUB if r["subset"] == sub}
        L.append(" & ".join([nice[sub], R[PROPOSED]["n_traces"], f(R["hashed_perceptron"]["mean_mpki"], 3),
                             f(R["tsl_base"]["mean_mpki"], 3), f(R[PROPOSED]["mean_mpki"], 3),
                             f(R["hashed_perceptron"]["proposed_pct_mpki_reduction"], 2) + r"\%",
                             f(R["tsl_base"]["proposed_pct_mpki_reduction"], 2) + r"\%",
                             sgn(R["tsl_base"]["proposed_ipc_speedup_pct"], 3) + r"\%"]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    table("tab_subsets.tex", L)

    # ---- top gains / regressions vs best baseline and best default ----
    def topk(b, k=6):
        key = "ipc_change_pct_vs_" + b
        rows = sorted(Pok, key=lambda r: -float(r[key]))
        return rows[:k], rows[::-1][:k]
    L = [r"\begin{tabular}{llrrlrr}", r"\toprule",
         r" & \multicolumn{3}{c}{Largest IPC gains} & \multicolumn{3}{c}{Lowest IPC changes (losses, if any)} \\",
         r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
         r"Baseline & Trace & $\Delta$IPC (\%) & $\Delta$MPKI & Trace & $\Delta$IPC (\%) & $\Delta$MPKI \\", r"\midrule"]
    for b in dict.fromkeys([best_base, best_def]):
        g, l = topk(b)
        for i in range(len(g)):
            L.append(" & ".join([SHORT[b] if i == 0 else "", tex(g[i]["trace"]), sgn(g[i]["ipc_change_pct_vs_" + b], 3),
                                 sgn(g[i]["mpki_change_vs_" + b], 4), tex(l[i]["trace"]),
                                 sgn(l[i]["ipc_change_pct_vs_" + b], 3), sgn(l[i]["mpki_change_vs_" + b], 4)]) + r" \\")
        L.append(r"\midrule")
    L[-1] = r"\bottomrule"
    L.append(r"\end{tabular}")
    table("tab_extremes.tex", L)

    # ---- per-trace overview (longtable) ----
    L = [r"\begin{longtable}{llrrrrrrr}",
         r"\caption{Per-trace characteristics and results (measured window). Br/KI = branches per 1,000 instructions; "
         r"$\Delta$IPC relative to TAGE-SC-L and the hashed perceptron.}\label{tab:traces}\\", r"\toprule",
         r"Trace & Set & Br/KI & Cond. & MPKI & MPKI & MPKI & $\Delta$IPC (\%) & $\Delta$IPC (\%) \\",
         r" & & & share & HP & TSL & proposed & vs TSL & vs HP \\", r"\midrule", r"\endhead"]
    for r in sorted(P, key=lambda r: r["trace"]):
        if r["all_runs_ok"] != "True":
            L.append(tex(r["trace"]) + r" & \multicolumn{8}{l}{not all runs successful (see failure report)} \\")
            continue
        L.append(" & ".join([tex(r["trace"]), ("orig" if r["group"] == "original10" else "add") + "/" + r["suite"],
                             f(r["branches_per_kilo_instr"], 1), f(r["cond_share_pct"], 0) + r"\%",
                             f(r["mpki_hashed_perceptron"], 3), f(r["mpki_tsl_base"], 3), f(r["mpki_" + PROPOSED], 3),
                             sgn(r["ipc_change_pct_vs_tsl_base"], 3), sgn(r["ipc_change_pct_vs_hashed_perceptron"], 3)]) + r" \\")
    L += [r"\bottomrule", r"\end{longtable}"]
    table("tab_traces.tex", L)

    # ---- appendix: IPC and MPKI of all predictors ----
    for metric, nd, cap, lab in (("ipc", 4, "IPC of every predictor on every trace.", "tab:ipc_all"),
                                 ("mpki", 3, "MPKI of every predictor on every trace.", "tab:mpki_all"),
                                 ("accuracy", 3, "Branch prediction accuracy (\\%, all branch types) of every predictor on every trace.", "tab:acc_all")):
        L = [r"\begin{longtable}{l" + "r" * len(preds) + "}",
             r"\caption{" + cap + r" Bim.\ = bimodal, Perc.\ = perceptron, Hashed P.\ = hashed perceptron, "
             r"TSL = TAGE-SC-L, Proposed = TFL-TAGE-SC-L; bold = best on the trace.}\label{" + lab + r"}\\", r"\toprule",
             "Trace & " + " & ".join(ABBR[p] for p in preds) + r" \\",
             r"\midrule", r"\endhead"]
        for r in sorted(P, key=lambda r: r["trace"]):
            vals = [r[f"{metric}_{p}"] for p in preds]
            best = None
            if r["all_runs_ok"] == "True":
                best = (max if metric in ("ipc", "accuracy") else min)(range(len(preds)), key=lambda i: float(vals[i]))
            cells = []
            for i, x in enumerate(vals):
                c = f(x, nd) if x != "" else "--"
                cells.append(r"\textbf{" + c + "}" if i == best else c)
            L.append(tex(r["trace"]) + " & " + " & ".join(cells) + r" \\")
        L += [r"\bottomrule", r"\end{longtable}"]
        table(f"tab_all_{metric}.tex", L)

    # ---- storage ----
    L = [r"\begin{tabular}{lrrp{8.2cm}}", r"\toprule", r"Predictor & Bits & KB & Basis \\", r"\midrule"]
    for p in preds:
        s = Sd[p]
        L.append(" & ".join([SHORT[p], f"{int(s['storage_bits']):,}", f(s["storage_KB"], 2), tex(s["storage_basis"])]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    table("tab_storage.tex", L)

    # ---- runtime ----
    L = [r"\begin{tabular}{lrrrr}", r"\toprule",
         r"Predictor & Runs ok & Mean wall time (min) & Max wall time (min) & Total (CPU-h) \\", r"\midrule"]
    for p in preds:
        s = Sd[p]
        L.append(" & ".join([SHORT[p], f"{s['runs_ok']}/{int(s['runs_ok']) + int(s['runs_not_ok'])}",
                             f(float(s["mean_wall_s"]) / 60, 1), f(float(s["max_wall_s"]) / 60, 1),
                             f(s["total_sim_hours"], 1)]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    table("tab_runtime.tex", L)

    # ---- trace manifest (appendix) ----
    L = [r"\begin{longtable}{lllrl}", r"\caption{Trace manifest: the 50 SPEC CPU2017 traces (Zenodo record 10960004); "
         r"every file passed \texttt{xz -t} and matches Zenodo's size and MD5. Each trace holds 2,000M instructions.}"
         r"\label{tab:manifest}\\", r"\toprule", r"Trace & Set & Suite & Size (MB) & MD5 (first 12 hex) \\",
         r"\midrule", r"\endhead"]
    for m in sorted(MAN, key=lambda m: (m["group"] != "original10", m["trace"])):
        L.append(" & ".join([tex(m["trace"]), "original 10" if m["group"] == "original10" else "additional 40",
                             "INT" if m["trace"].split(".")[0] in {"600", "602", "605", "620", "623", "625", "631", "641", "648", "657"} else "FP",
                             f(int(m["size_bytes"]) / 1e6, 1), r"\texttt{" + m["md5"][:12] + "}"]) + r" \\")
    L += [r"\bottomrule", r"\end{longtable}"]
    table("tab_manifest.tex", L)

    # ---- RESULTS.md (markdown results-and-comparison file, same numbers) ----
    md = ["# TFL-TAGE-SC-L — results and comparison (50-trace evaluation)", "",
          f"Generated from the CSVs in this folder by `experiments/scripts/make_report_50trace.py`. "
          f"{V['n_runs_ok']} of {V['n_runs']} runs successful; aggregates over {V['n_traces_agg']} traces "
          f"({V['n_orig']} original + {V['n_add']} additional SPEC CPU2017 traces), 50M warm-up + 200M measured "
          "instructions each, ChampSim 2021 (1 core, no prefetchers, LRU LLC). The full analysis is in "
          "`report_50trace/TFL-TAGE-SC-L_50trace_Report.pdf`.", "",
          "## Overall", "",
          "| Predictor | Storage (KB) | Mean IPC | Geomean IPC | Speedup vs Bimodal | Mean MPKI | Accuracy all | Accuracy cond. |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for p in preds:
        s = Sd[p]
        md.append(f"| {SHORT[p]}{' (proposed)' if p == PROPOSED else ''} | {f(s['storage_KB'], 2)} | {f(s['mean_ipc'], 4)} | "
                  f"{f(s['geomean_ipc'], 4)} | {sgn(100 * (float(s['geomean_speedup_vs_bimodal']) - 1), 2)}% | "
                  f"{f(s['mean_mpki'], 3)} | {f(s['pooled_accuracy'], 3)}% | {f(s['pooled_cond_accuracy'], 3)}% |")
    md += ["", "Mean IPC = arithmetic mean of per-trace IPC; geomean IPC = geometric mean; speedup = geometric mean of "
           "per-trace IPC ratios; MPKI = arithmetic mean over traces (all branch types); accuracy pooled over all branches.",
           "", "## TFL-TAGE-SC-L relative to each baseline", "",
           "| Baseline | Baseline MPKI | MPKI reduction | Geomean IPC improvement | Traces lower/equal/higher MPKI | Traces higher/equal/lower IPC | Largest IPC gain | Largest IPC loss |",
           "|---|---:|---:|---:|---|---|---|---|"]
    for b in others:
        c = C[b]
        md.append(f"| {SHORT[b]} | {f(c['baseline_mean_mpki'], 3)} | {f(c['pct_mpki_reduction'], 2)}% | "
                  f"{sgn(c['ipc_improvement_pct'], 3)}% | {c['traces_lower_mpki']}/{c['traces_equal_mpki']}/{c['traces_higher_mpki']} | "
                  f"{c['traces_higher_ipc']}/{c['traces_equal_ipc']}/{c['traces_lower_ipc']} | "
                  f"{c['largest_ipc_gain_trace']} ({sgn(c['largest_ipc_gain_pct'], 2)}%) | "
                  f"{c['largest_ipc_loss_trace']} ({sgn(c['largest_ipc_loss_pct'], 2)}%) |")
    md += ["", "## Trace subsets", "",
           "| Subset | n | Mean MPKI HP | Mean MPKI TAGE-SC-L | Mean MPKI proposed | MPKI red. vs HP | MPKI red. vs TAGE-SC-L | IPC vs TAGE-SC-L |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for sub in subs:
        R = {r["predictor"]: r for r in SUB if r["subset"] == sub}
        md.append(f"| {nice[sub]} | {R[PROPOSED]['n_traces']} | {f(R['hashed_perceptron']['mean_mpki'], 3)} | "
                  f"{f(R['tsl_base']['mean_mpki'], 3)} | {f(R[PROPOSED]['mean_mpki'], 3)} | "
                  f"{f(R['hashed_perceptron']['proposed_pct_mpki_reduction'], 2)}% | "
                  f"{f(R['tsl_base']['proposed_pct_mpki_reduction'], 2)}% | {sgn(R['tsl_base']['proposed_ipc_speedup_pct'], 3)}% |")
    md += ["", "## Figures", ""]
    for fn in sorted(os.listdir(os.path.join(a.res, "figures")),
                     key=lambda s: int(s[3:].split("_")[0]) if s[3:].split("_")[0].isdigit() else 99):
        if fn.endswith(".png"):
            md.append(f"![{fn[:-4]}](figures/{fn})")
            md.append("")
    md += ["## Files", "",
           "| File | Contents |", "|---|---|",
           "| `raw_results.csv` | one row per predictor x trace run (350), with status, counters, metrics, log path |",
           "| `per_trace_results.csv` | one row per trace: IPC / MPKI / accuracy of all predictors, deltas of the proposed predictor |",
           "| `summary.csv` | one row per predictor: aggregates, storage, runtime |",
           "| `subset_summary.csv` | aggregates on trace subsets |",
           "| `comparison_vs_baselines.csv` | proposed vs each baseline |",
           "| `trace_manifest.csv` | the 50 traces, sizes, checksums |",
           "| `experiment_config.json` | exact settings, metric definitions, build information |",
           "| `run_status.csv`, `failure_report.md` | status of every run |",
           "| `checks.txt`, `report_verification.txt` | consistency checks of the results and of the report |",
           "| `TFL-TAGE-SC-L_50trace_Results.xlsx` | all of the above as a workbook, with the figures |"]
    open(os.path.join(a.res, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

    # ---- figures ----
    fig_src = os.path.join(a.res, "figures")
    for fn in sorted(os.listdir(fig_src)):
        if fn.endswith(".pdf"):
            shutil.copy(os.path.join(fig_src, fn), os.path.join(a.rep, "figures", fn))
    print(f"{len(V)} values, tables and figures written to {a.rep}")


if __name__ == "__main__":
    main()
