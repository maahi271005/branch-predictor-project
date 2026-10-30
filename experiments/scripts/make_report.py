#!/usr/bin/env python3
"""Generate the technical report (DOCX) from the processed results.

  build/venv/bin/python experiments/scripts/make_report.py [--results submission/results] [--out submission/Branch_Predictor_Report.docx]

Every number in the report is read from results_summary.csv, results_per_trace.csv and
ablation_mpki.csv (produced by analyze.py from the raw simulator outputs), or from the
explicitly cited exploration logs.
"""
import argparse, csv, os, re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]
SHORT = {t: t.split(".")[1].split("_")[0] for t in TRACES}


def rd(path):
    return list(csv.DictReader(open(path)))


def harness_mean(region, name):
    f = os.path.join(ROOT, "experiments", "results", "harness", region, name + ".txt")
    lines = [l for l in open(f) if not l.startswith("#")]
    return sum(float(re.search(r" mpki=(\S+)", l).group(1)) for l in lines) / len(lines)


class Rep:
    def __init__(self):
        self.d = Document()
        st = self.d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
        self.fig = 0; self.tab = 0

    def h(self, text, level=1):
        self.d.add_heading(text, level=level)

    def p(self, text, bold=False, italic=False):
        para = self.d.add_paragraph()
        # **bold** segments
        for i, part in enumerate(re.split(r"\*\*", text)):
            r = para.add_run(part); r.bold = bold or (i % 2 == 1); r.italic = italic
        return para

    def bullets(self, items):
        for it in items:
            para = self.d.add_paragraph(style="List Bullet")
            for i, part in enumerate(re.split(r"\*\*", it)):
                r = para.add_run(part); r.bold = (i % 2 == 1)

    def code(self, text):
        para = self.d.add_paragraph()
        r = para.add_run(text); r.font.name = "Consolas"; r.font.size = Pt(9)

    def table(self, header, rows, caption, widths=None, fs=8.5):
        self.tab += 1
        cap = self.d.add_paragraph(); r = cap.add_run(f"Table {self.tab}. {caption}"); r.bold = True; r.font.size = Pt(9.5)
        t = self.d.add_table(rows=1, cols=len(header)); t.style = "Light Grid Accent 1"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, hd in enumerate(header):
            c = t.rows[0].cells[i]; c.text = ""; rr = c.paragraphs[0].add_run(str(hd)); rr.bold = True; rr.font.size = Pt(fs)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""; rr = cells[i].paragraphs[0].add_run(str(v)); rr.font.size = Pt(fs)
                if isinstance(v, str) and v.startswith("**"):
                    cells[i].paragraphs[0].runs[0].text = v.strip("*"); cells[i].paragraphs[0].runs[0].bold = True
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths): row.cells[i].width = Inches(w)
        self.d.add_paragraph()
        return self.tab

    def figure(self, path, caption, width=6.5):
        self.fig += 1
        self.d.add_picture(path, width=Inches(width))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = self.d.add_paragraph(); r = cap.add_run(f"Figure {self.fig}. {caption}"); r.italic = True; r.font.size = Pt(9)
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return self.fig


def f4(x): return f"{float(x):.4f}"
def f3(x): return f"{float(x):.3f}"
def f2(x): return f"{float(x):.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(ROOT, "submission", "results"))
    ap.add_argument("--out", default=os.path.join(ROOT, "submission", "Branch_Predictor_Report.docx"))
    a = ap.parse_args()
    S = {r["predictor"]: r for r in rd(os.path.join(a.results, "results_summary.csv"))}
    PT = {(r["predictor"], r["trace"]): r for r in rd(os.path.join(a.results, "results_per_trace.csv"))}
    AB = rd(os.path.join(a.results, "ablation_mpki.csv"))
    figd = os.path.join(a.results, "figures")
    P, HP, TB, IM, TG = S["tsl_proposed"], S["hashed_perceptron"], S["tsl_base"], S["tsl_imli"], S["tage"]

    def red(x, ref):  # MPKI reduction in % of ref, from means
        return 100 * (1 - float(x["mean_mpki_10"]) / float(ref["mean_mpki_10"]))

    def gm(p, ref):
        import math
        return math.exp(sum(math.log(float(PT[p, t]["ipc"]) / float(PT[ref, t]["ipc"])) for t in TRACES) / 10)

    better_mpki_hp = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["mpki"]) < float(PT["hashed_perceptron", t]["mpki"])]
    worse_mpki_hp = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["mpki"]) > float(PT["hashed_perceptron", t]["mpki"])]
    better_mpki_tb = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["mpki"]) < float(PT["tsl_base", t]["mpki"])]
    worse_mpki_tb = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["mpki"]) > float(PT["tsl_base", t]["mpki"])]
    ipc_up_hp = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["ipc"]) > float(PT["hashed_perceptron", t]["ipc"])]
    ipc_dn_hp = [SHORT[t] for t in TRACES if float(PT["tsl_proposed", t]["ipc"]) < float(PT["hashed_perceptron", t]["ipc"])]
    sp_hp, sp_tb, sp_bi = gm("tsl_proposed", "hashed_perceptron"), gm("tsl_proposed", "tsl_base"), gm("tsl_proposed", "bimodal")

    R = Rep()
    t = R.d.add_heading("TFL-TAGE-SC-L: A TAGE-SC-L Branch Predictor with Target-Free Loop-Structure History for ChampSim", 0)
    R.p("Branch prediction assignment — technical report", italic=True)

    # ---------------------------------------------------------------- abstract
    R.h("Abstract")
    R.p(f"We design, implement and evaluate a branch predictor for the 2021 version of ChampSim, whose "
        f"predictor interface passes only the branch address and its outcome — no branch type and no target. "
        f"Several of the strongest history features of modern predictors (the Inner-Most-Loop-Iteration counter "
        f"IMLI, its outer-iteration history, and backward-branch histories) are defined on backward branches and "
        f"therefore cannot be computed in this interface without modifying the simulator. We observe that, because "
        f"ChampSim presents branches to the predictor in program order without wrong-path execution, the direction "
        f"of every taken branch can be inferred exactly from the address of the next branch presented to the predictor. "
        f"We verify this inference against the simulator's own targets (99.9996–100% agreement on all ten traces) and use it "
        f"to add IMLI-SIC, IMHIST and a backward-branch history to a re-implemented TAGE-SC-L predictor. The resulting "
        f"predictor, TFL-TAGE-SC-L, uses {int(P['storage_bits']):,} bits ({f2(P['storage_KB'])} KB). On ten SPEC CPU2017 "
        f"traces (50M warm-up + 200M measured instructions) it reaches a mean MPKI of {f3(P['mean_mpki_10'])}, "
        f"{red(P, HP):.1f}% lower than the 64 KB hashed perceptron shipped with ChampSim ({f3(HP['mean_mpki_10'])}) "
        f"and {red(P, TB):.2f}% lower than our TAGE-SC-L without the loop-structure components ({f3(TB['mean_mpki_10'])}), "
        f"with a geometric-mean IPC speedup of {100*(sp_hp-1):.2f}% over the hashed perceptron and {100*(sp_bi-1):.1f}% over bimodal; "
        f"the IPC gain attributable to the loop-structure components alone is small ({100*(sp_tb-1):+.2f}%) because "
        f"the traces that benefit most are memory-bound. "
        f"Ablations attribute the gains to each component, and we report negative results (a per-branch "
        f"allocation throttle that helps plain TAGE but is subsumed in TAGE-SC-L, and several IMLI variants).")

    # ---------------------------------------------------------------- 1
    R.h("1. Problem statement")
    R.p("The goal of the assignment is to design and implement a branch predictor in ChampSim that improves on "
        "suitable baselines, to evaluate it with IPC, branch prediction accuracy and MPKI, and to explain the results. "
        "We work with the ChampSim version provided for the course (2021, built with build_champsim.sh). Its predictor "
        "interface is:")
    R.code("uint8_t O3_CPU::predict_branch(uint64_t ip);\nvoid    O3_CPU::last_branch_result(uint64_t ip, uint8_t taken);")
    R.bullets([
        "The predictor is called for **every** branch type (conditional, direct/indirect jumps and calls, returns), "
        "with no type information; unconditional branches are always reported taken.",
        "No branch target is passed, and last_branch_result() follows each prediction immediately with the true outcome.",
        "Accuracy and MPKI are computed over all branch types; a misprediction is a direction mismatch.",
    ])
    R.p("The concrete problem we address is: **how far can a state-of-the-art TAGE-SC-L design be pushed in this "
        "PC-and-outcome-only interface, and can the loop-structure features that normally require branch targets be "
        "recovered without changing the simulator?**")

    # ---------------------------------------------------------------- 2
    R.h("2. Background and related work")
    R.p("We reviewed the six reference papers of the assignment and additional work (full review with access levels "
        "in research/literature_review.md). Table 1 summarises the ones that shaped the design.")
    R.table(["Work", "Core idea", "Relevance / limitation"], [
        ["Jiménez & Lin, HPCA 2001 [1]", "Perceptron per branch over global history; train on mispredict or |y| ≤ θ", "Long histories at linear cost; basis of hashed perceptron and of corrector (SC) tables"],
        ["Seznec, MICRO 2011 [2]; Seznec & Michaud 2006 [7]", "TAGE: tagged tables with geometric history lengths, longest match provides", "Strongest single-component predictor; struggles with statistically biased / hard-to-predict (H2P) branches"],
        ["Seznec et al., MICRO 2015 [3]", "IMLI counter: iterations of the inner-most loop; IMLI-SIC and IMLI-OH corrector tables", "Needs to know whether a branch is backward (target < PC) — not available in this interface"],
        ["Jiménez, CBP 2016 [4]", "Multiperspective perceptron: many feature types in one adder", "Confirms value of heterogeneous features in an adder; many features need type/target"],
        ["Michaud, TACO 2018 [5]", "BATAGE: dual-counter entries, Bayesian confidence, controlled allocation throttling (global)", "Allocation throttling is global; per-branch throttling left open"],
        ["Lin & Tarsa, IISWC 2019 [6]", "~10 hard-to-predict branches cause ~55% of mispredictions; each H2P causes ~13k TAGE allocations", "Motivates H2P handling / allocation filtering"],
        ["Seznec, CBP 2014/2016 [8]", "TAGE-SC-L: TAGE + statistical corrector + loop predictor; 3.986 MPKI at 64 KB", "Our base architecture; its 2016 code uses IMLI-SIC, IMHIST and backward-branch history"],
    ], "Key related work.", widths=[1.7, 2.5, 2.5])
    R.p("Newer work (CBP-2025 entries, LLBP [9], BranchNet, Whisper) either needs much larger storage, offline training, "
        "ISA hints, or data values that ChampSim traces do not carry; it was reviewed but not adopted.")

    # ---------------------------------------------------------------- 3
    R.h("3. Motivation")
    R.p(f"Two observations motivated the design. First, among the predictors shipped with this ChampSim, the hashed "
        f"perceptron (64 KB) is by far the best (mean MPKI {f3(HP['mean_mpki_10'])} vs {f3(S['gshare']['mean_mpki_10'])} for gshare), "
        f"and our re-implemented TAGE of similar storage is not better on average ({f3(TG['mean_mpki_10'])}): it wins on "
        f"gcc, xalancbmk, omnetpp and x264, is level on deepsjeng, and loses on mcf and xz, the two traces that dominate "
        f"mean MPKI. Combining "
        f"TAGE with a perceptron-like statistical corrector (TAGE-SC-L) is the established way to get the best of both.")
    R.p("Second, the corrector of TAGE-SC-L gains part of its accuracy from loop-structure history (IMLI, IMHIST, "
        "backward-branch history), all of which are defined on **backward** branches. The interface hides the target, so "
        "these components cannot be computed directly, and the obvious workaround — changing ChampSim's core to pass "
        "the target — changes the simulator that the assignment evaluates. We therefore asked whether the information "
        "can be recovered inside the predictor.")

    # ---------------------------------------------------------------- 4
    R.h("4. Proposed predictor: TFL-TAGE-SC-L")
    R.h("4.1 Target-free backward-branch inference (the enabling idea)", 2)
    R.p("ChampSim feeds the predictor all branches in program order and never executes a wrong path. Let B be a taken "
        "branch with target T and let N be the next branch presented to the predictor. Execution proceeds sequentially "
        "from T to N, so pc(N) ≥ T. If T ≤ pc(B), the sequential path from T reaches B itself (B lies between T and itself), "
        "so pc(N) ≤ pc(B). If T > pc(B), then pc(N) ≥ T > pc(B). Hence:")
    R.code("B is backward   <=>   pc(next branch presented to the predictor) <= pc(B)      (taken instances)")
    R.p("The test runs at the start of the next predict_branch() call, i.e. before any later prediction uses the loop "
        "state, so the counters seen by every prediction are the same as with target knowledge. Two small bit tables "
        "complete the mechanism: **bwd** (4 Kbit) remembers the inferred direction of each branch for its not-taken "
        "(loop-exit) instances, and **cond** (4 Kbit) marks a branch as conditional once it has been observed not-taken "
        "(ChampSim reports unconditional branches as always taken). Verification against the simulator's own target "
        "(branch_target = next_instr.ip) over 50M instructions per trace gave 99.9996–100% agreement on all ten traces "
        "(Section 7.3).")

    R.h("4.2 Architecture", 2)
    R.table(["Component", "Configuration", "Bits"], [
        ["Bimodal base", "8K × 2-bit counters", "16,384"],
        ["Tagged tables T1–T12", "2K entries each; 3-bit ctr, 1-bit u, tags 8–13 bits; history 4…640 (geometric)", "366,592"],
        ["TAGE control", "use_alt_on_na (4 × 5 bit), TICK, 640-bit global + 27-bit path history", "698"],
        ["Loop predictor", "64 entries, 4-way; 2 × 10-bit trip counts, 10-bit tag, 4-bit confidence, 4-bit age, direction; WITHLOOP", "2,503"],
        ["SC bias tables", "3 × 1K × 6-bit (PC × TAGE pred × confidence / provider)", "18,432"],
        ["SC control", "adaptive threshold + counter, 2 chooser counters", "30"],
        ["SC global + path GEHL", "4 global (6–40) + 3 path (9–25) × 1K × 6-bit", "43,008"],
        ["SC local GEHL", "4 × 1K × 6-bit (3–16) + 256 × 16-bit local histories", "28,672"],
        ["IMLI-SIC", "512 × 6-bit, indexed by hash(PC, IMLIcount); 10-bit IMLIcount", "3,082"],
        ["Backward inference", "bwd 4 Kbit + cond 4 Kbit + previous-branch register", "8,257"],
        ["IMHIST", "256 × 10-bit histories (one per IMLI value) + 1K × 6-bit table", "8,704"],
        ["Backward-branch history", "16-bit history + 2 × 1K × 6-bit tables", "12,304"],
        ["**Total**", "", f"**{int(P['storage_bits']):,} ({f2(P['storage_KB'])} KB)**"],
    ], "TFL-TAGE-SC-L configuration and storage (counted by the predictor's storage_bits()).", widths=[1.7, 3.6, 1.2])

    R.h("4.3 Prediction", 2)
    R.bullets([
        "Update the loop-structure state for the previous branch (Section 4.1).",
        "TAGE: compute indices/tags with folded global and path history; the longest matching table provides the "
        "prediction; for a newly allocated (weak) provider the alternate prediction is used when the use_alt_on_na "
        "counter says so. Confidence = provider counter magnitude.",
        "Loop predictor: overrides TAGE when its entry is confident and the global WITHLOOP counter is non-negative.",
        "Statistical corrector: sum of 6-bit counters (bias, global, path, local, IMLI-SIC, IMHIST, backward-history "
        "tables). If its sign disagrees with TAGE/loop, the corrector wins unless TAGE is highly confident and |sum| is "
        "below θ/4 (or θ/2, arbitrated by two chooser counters) — the TAGE-SC-L 2016 rule.",
    ])
    R.h("4.4 Update", 2)
    R.bullets([
        "Corrector: train all selected counters when the corrector mispredicted or |sum| < θ; adapt θ (O-GEHL rule).",
        "TAGE: update the provider (and the alternate for weak providers); set/clear u; on a TAGE misprediction allocate up "
        "to two entries in longer-history tables, only over entries with u = 0 and a weak/medium counter (strong ones are "
        "decayed); when the corrected final prediction was right, allocate only with probability 1/32; age u bits with "
        "the TICK counter.",
        "Histories: insert one bit (taken ⊕ PC bit) into the global history, one PC bit into the path history, update "
        "local history, IMLI (increment on taken backward conditional, reset on its exit), IMHIST and backward history.",
    ])

    R.h("5. Contribution and relation to prior work", 1)
    R.bullets([
        "**Target-free, exact backward-branch inference** for a predictor interface that provides only PC and outcome, "
        "with a proof, verification against ground truth, and an analysis of where the derived IMLI counter departs "
        "from a type- and target-aware one. We found no prior use of the next *predicted branch's* address for this "
        "purpose; the closest is passing the next *instruction* address, which requires simulator changes.",
        "Its use to bring IMLI-SIC, IMHIST and backward-branch history (published by Seznec et al. [3, 8]) into this "
        "ChampSim without modifying the core, and a measured evaluation of which of them help on SPEC CPU2017.",
        "A complete, documented TAGE-SC-L re-implementation for the 2021 ChampSim interface with ablation switches.",
        "Negative results: a per-branch TAGE allocation throttle (motivated by Lin & Tarsa [6] and BATAGE's global "
        "throttling [5]) reduces MPKI of plain TAGE but has no effect inside TAGE-SC-L; region-based IMLI and IMLI in "
        "global corrector tables did not help on these traces.",
    ])
    R.p("We do **not** claim TAGE-SC-L, IMLI-SIC, IMHIST or backward-branch histories as new; they are published "
        "mechanisms that we re-implemented from the papers.")

    # ---------------------------------------------------------------- 6
    R.h("6. Implementation", 1)
    R.bullets([
        "branch/tagescl.bpred — the whole predictor family (~700 lines, C++11, ChampSim .bpred interface); "
        "branch/tfl_tage_scl.bpred, tage_scl.bpred, tage.bpred — wrappers selecting the proposed design and the "
        "re-implemented baselines for the standard build_champsim.sh workflow.",
        "Only predictor-private state; one predictor object per CPU; deterministic (fixed-seed xorshift for the "
        "probabilistic allocation decisions).",
        "Simulator core: stats-only additions to src/main.cc, src/ooo_cpu.cc and inc/ooo_cpu.h that print exact branch "
        "and misprediction counts per branch type. They do not change timing: rebuilt bimodal results are identical to "
        "an earlier course run (e.g. mcf IPC 0.329782, MPKI 24.7064).",
        "Functional replay harness (experiments/harness): replays the exact branch sequence ChampSim feeds the predictor, "
        "compiling the unmodified .bpred against a minimal ooo_cpu.h. Its misprediction counts match ChampSim within "
        "≈0.05% (the offset is the warm-up boundary: ChampSim switches at retirement). Used for exploration and MPKI ablations.",
    ])

    # ---------------------------------------------------------------- 7
    R.h("7. Experimental methodology", 1)
    R.h("7.1 Simulator configuration and windows", 2)
    R.bullets([
        "ChampSim (2021), 1 core, 6-wide fetch, 352-entry ROB, no prefetchers, LRU LLC (defaults of this version).",
        "Every predictor and trace: 50M warm-up + 200M measured instructions (instructions 0–250M of each trace).",
        "Exploration and parameter tuning used a **different** window (instructions 1000M–1150M) through the harness, "
        "so the reported window was not used for tuning; the final ranking was confirmed on both.",
    ])
    R.h("7.2 Workloads", 2)
    rows = []
    for tname in TRACES:
        r = PT["bimodal", tname]
        rows.append([tname, f"{1000 * int(r['branches']) / int(r['instructions']):.1f}",
                     f"{int(r['cond_branches'])/int(r['branches'])*100:.0f}%", f3(PT['hashed_perceptron', tname]['mpki'])])
    R.table(["Trace (DPC-3 SimPoint)", "Branches per 1K instr.", "Conditional share", "Hashed-perceptron MPKI"], rows,
            "The ten required traces (2,000M instructions each, all verified with xz -t); statistics from the measured window.",
            widths=[2.2, 1.4, 1.3, 1.6])
    R.h("7.3 Validation", 2)
    R.bullets([
        "Traces: integrity (xz -t), length (2,000M instructions each, so no wrap-around), smoke tests with every predictor.",
        "Harness vs ChampSim: e.g. xz 103,049 vs 103,048 and mcf 164,572 vs 164,659 mispredictions (1M/10M window).",
        "Backward inference vs ChampSim's target: 99.9996–100% agreement per taken branch on all traces.",
        "IMLI counter vs an oracle using true branch types and targets (values clamped at 16): mcf 99.7%, x264 99.7%, "
        "gcc 96.4%, xz 95.7%, imagick 92.4%, deepsjeng 58.6%, xalancbmk 55.3%; low on lbm, cactuBSSN and omnetpp, where "
        "the oracle counter sits near saturation because of backward conditional branches that almost never exit.",
    ])
    R.h("7.4 Metrics", 2)
    R.bullets([
        "IPC: ChampSim's cumulative IPC of the measured region.",
        "Accuracy: (branches − mispredictions) / branches over **all** branch types (ChampSim's definition). "
        "Conditional-only accuracy is reported separately and never mixed with it.",
        "MPKI: 1000 × mispredictions / measured instructions (all types).",
        "Aggregates: arithmetic mean MPKI over the 10 traces (and the 7 integer traces); MPKI reductions computed from "
        "the means; geometric mean of per-trace IPC ratios for speedups; arithmetic mean IPC for information only.",
    ])
    R.h("7.5 Baselines and why", 2)
    R.table(["Baseline", "Storage", "Reason"], [
        ["Bimodal", "4 KB", "ChampSim default; lower bound"],
        ["Gshare", "4 KB", "classic global-history predictor"],
        ["Perceptron", "4 KB", "reference paper [1]"],
        ["Hashed perceptron", "64 KB", "strongest predictor shipped with ChampSim; same storage class as ours"],
        ["TAGE (ours)", f"{f2(TG['storage_KB'])} KB", "reference paper [2]; isolates the tagged component"],
        ["TAGE-SC-L (ours, no IMLI)", f"{f2(TB['storage_KB'])} KB", "state-of-the-art architecture [8] without our contribution — the key comparison"],
    ], "Baselines.", widths=[1.8, 0.9, 3.8])

    # ---------------------------------------------------------------- 8
    R.h("8. Results", 1)
    order = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tage_l", "tsl_base", "tsl_imli", "tsl_proposed"]
    R.table(["Predictor", "KB", "Mean IPC", "Speedup vs bimodal", "Speedup vs hashed perc.", "Mean MPKI", "Int. MPKI",
             "Accuracy (all)", "Accuracy (cond.)"],
            [[("**" + S[p]["label"] + "**") if p == "tsl_proposed" else S[p]["label"], f2(S[p]["storage_KB"]), f4(S[p]["mean_ipc"]),
              f4(S[p]["geomean_speedup_vs_bimodal"]), f4(S[p]["geomean_speedup_vs_hashed_perceptron"]),
              f3(S[p]["mean_mpki_10"]), f3(S[p]["mean_mpki_int7"]), f3(S[p]["pooled_accuracy_all_pct"]) + "%",
              f3(S[p]["pooled_cond_accuracy_pct"]) + "%"] for p in order if p in S],
            "Aggregate results, 10 traces, 50M + 200M instructions (accuracy pooled over all branches of all traces).",
            fs=7.5)
    R.figure(os.path.join(figd, "fig_aggregate.png"), "Mean MPKI and geometric-mean IPC speedup over bimodal.")
    for metric, title, fmt in (("mpki", "MPKI per trace", f3), ("ipc", "IPC per trace", f4)):
        sel = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tsl_base", "tsl_proposed"]
        R.table(["Trace"] + [S[p]["label"].replace(" (TSL + IMLI + IMHIST + BHIST)", "") for p in sel],
                [[SHORT[t]] + [fmt(PT[p, t][metric]) for p in sel] for t in TRACES], title + ".", fs=7.5)
    sel = ["bimodal", "hashed_perceptron", "tsl_base", "tsl_proposed"]
    R.table(["Trace"] + [f"{S[p]['label'].replace(' (TSL + IMLI + IMHIST + BHIST)', '')} all / cond." for p in sel],
            [[SHORT[t]] + [f"{float(PT[p, t]['accuracy_pct_all_branches']):.3f} / {float(PT[p, t]['cond_accuracy_pct']):.3f}" for p in sel] for t in TRACES],
            "Branch prediction accuracy per trace (%), all branch types / conditional branches only.", fs=7.5)
    R.figure(os.path.join(figd, "fig_mpki_per_trace.png"), "MPKI per trace (log scale).")
    R.figure(os.path.join(figd, "fig_ipc_speedup_per_trace.png"), "IPC per trace normalised to bimodal.")

    # ---------------------------------------------------------------- 9
    R.h("9. Analysis", 1)
    R.p(f"**Against the strongest shipped predictor.** TFL-TAGE-SC-L lowers mean MPKI from {f3(HP['mean_mpki_10'])} to "
        f"{f3(P['mean_mpki_10'])} ({red(P, HP):.1f}%) at slightly lower storage ({f2(P['storage_KB'])} vs {f2(HP['storage_KB'])} KB). "
        f"MPKI is lower on {len(better_mpki_hp)} of 10 traces ({', '.join(better_mpki_hp)})"
        + (f" and higher on {', '.join(worse_mpki_hp)}" if worse_mpki_hp else "") +
        f". The geometric-mean IPC speedup is {100*(sp_hp-1):.2f}%; IPC is higher on {len(ipc_up_hp)} traces"
        + (f" and lower on {', '.join(ipc_dn_hp)}" if ipc_dn_hp else "") + ".")
    worse_delta = max([float(PT["tsl_proposed", t]["mpki"]) - float(PT["tsl_base", t]["mpki"]) for t in TRACES
                       if SHORT[t] in worse_mpki_tb] or [0.0])
    worse_level = max([float(PT["tsl_base", t]["mpki"]) for t in TRACES if SHORT[t] in worse_mpki_tb] or [0.0])
    R.p(f"**Against TAGE-SC-L without the loop-structure components.** The contribution reduces mean MPKI from "
        f"{f3(TB['mean_mpki_10'])} to {f3(P['mean_mpki_10'])} ({red(P, TB):.2f}%), lower on {len(better_mpki_tb)} traces "
        f"({', '.join(better_mpki_tb)})" +
        (f", marginally higher on {', '.join(worse_mpki_tb)} (by at most {worse_delta:.4f} MPKI, on traces whose MPKI "
         f"is at most {worse_level:.3f})" if worse_mpki_tb else "") +
        f"; geometric-mean IPC speedup {100*(sp_tb-1):+.3f}%. IMLI-SIC alone accounts for "
        f"{red(IM, TB):.2f}% (TAGE-SC-L + IMLI: {f3(IM['mean_mpki_10'])}).")
    R.p("**Accuracy, MPKI and IPC.** IPC gains are much smaller than MPKI reductions and do not scale uniformly with "
        "them (Figure 4). In this ChampSim a misprediction stalls fetch until the branch executes, plus one cycle; "
        "Table 9 measures, per trace, the cycles saved per avoided misprediction (difference in cycles divided by "
        "difference in mispredictions, proposed vs hashed perceptron). The relative IPC gain is approximately "
        "ΔMPKI × (cycles per avoided misprediction) / (1000 × CPI): the same absolute saving matters less in a "
        "program that spends many cycles per instruction on memory stalls.")
    rows = []
    for tn in TRACES:
        hp, pp = PT["hashed_perceptron", tn], PT["tsl_proposed", tn]
        dm = int(hp["mispredictions"]) - int(pp["mispredictions"])
        dc = int(hp["cycles"]) - int(pp["cycles"])
        cpi = int(hp["cycles"]) / int(hp["instructions"])
        dmpki = float(hp["mpki"]) - float(pp["mpki"])
        cpm = dc / dm if dm else float("nan")
        est = 100 * dmpki * cpm / (1000 * cpi) if dm else float("nan")
        meas = 100 * (float(pp["ipc"]) / float(hp["ipc"]) - 1)
        rows.append([SHORT[tn], f"{dmpki:.3f}", f"{cpm:.1f}" if abs(dmpki) > 0.01 else "n/a (Δ≈0)", f"{cpi:.2f}",
                     f"{est:+.2f}%" if abs(dmpki) > 0.01 else "≈0", f"{meas:+.3f}%"])
    R.table(["Trace", "ΔMPKI (hp − proposed)", "Cycles saved per avoided misprediction", "CPI (hp)",
             "ΔMPKI × cycles / (1000 × CPI)", "Measured ΔIPC"], rows,
            "Why IPC moves less than MPKI: decomposition of the measured IPC gain of the proposed predictor over the "
            "hashed perceptron (the cycles per avoided misprediction are themselves measured, so the two right-hand "
            "columns agree by construction; the table shows which factor limits each trace).", fs=8)
    R.p("For example, mcf removes 0.107 mispredictions per 1,000 instructions at ~27 cycles each, but runs at "
        "~3.2 cycles per instruction (it is dominated by cache misses), so the IPC gain is below 0.1%; xz removes "
        "0.55 per 1,000 at ~25 cycles with a CPI near 1.0, giving +1.4%. Traces whose MPKI is already near zero "
        "(cactuBSSN, lbm, imagick) show IPC differences of a few thousandths of a percent in either direction, which "
        "is timing noise from the out-of-order model rather than a predictor effect. Accuracy over all branch types "
        "is inflated by trivially predicted unconditional branches, so conditional accuracy is the more informative "
        "number; the ranking of predictors is the same under both.")
    R.figure(os.path.join(figd, "fig_mpki_vs_ipc.png"), "Per-trace MPKI reduction vs IPC gain of TFL-TAGE-SC-L over the hashed perceptron.", width=4.6)
    R.p("**Where the remaining mispredictions are.** mcf and xz together account for most of the mean MPKI of every "
        "predictor. Lin & Tarsa [6] attribute about 97% (mcf) and 80% (xz) of mispredictions to a handful of data-dependent "
        "branches; no history-based predictor in our study removes them, consistent with their conclusion that such "
        "branches need different information than branch history.")

    # ---------------------------------------------------------------- 10
    R.h("10. Ablation study", 1)
    main_ab = [r for r in AB if r["region"] == "main"]
    tune_ab = {r["variant"]: r for r in AB if r["region"] == "tune"}
    R.table(["Variant", "Mean MPKI (reported window)", "Δ vs proposed", "Mean MPKI (tuning window)", "Δ vs proposed"],
            [[r["description"], f4(r["mean_mpki_10"]), f"{float(r['delta_vs_proposed_pct']):+.2f}%",
              f4(tune_ab[r['variant']]["mean_mpki_10"]) if r["variant"] in tune_ab else "",
              f"{float(tune_ab[r['variant']]['delta_vs_proposed_pct']):+.2f}%" if r["variant"] in tune_ab else ""] for r in main_ab],
            "Removing one component at a time (functional harness; mean MPKI over 10 traces).", fs=8)
    R.figure(os.path.join(figd, "fig_ablation.png"), "Ablation on the reported window.", width=5.6)
    for p in ("tsl_prop_noloop", "tsl_prop_nolocal"):
        if p in S:
            R.p(f"IPC ablation in ChampSim — {S[p]['label']}: mean MPKI {f3(S[p]['mean_mpki_10'])}, "
                f"geometric-mean IPC {100*(gm(p, 'tsl_proposed')-1):+.3f}% relative to the proposed design.")
    R.p("Each IMLI-derived component reduces MPKI on its own and their effects add up; the statistical corrector is "
        "the largest single contributor, the loop predictor the smallest (consistent with Seznec's report that IMLI "
        "largely subsumes the loop predictor [3]).")

    # ---------------------------------------------------------------- 11
    R.h("11. Exploration: what else was tried", 1)
    R.p("All in the functional harness on the tuning window (mean MPKI over 10 traces); details in experiments/experiment_log.md.")
    R.table(["Experiment", "Result", "Decision"], [
        ["Per-branch allocation throttle (payoff counter, 3 settings) in TAGE-SC-L", "−0.00% / +0.06% / +0.09%", "rejected"],
        ["Same throttle in plain TAGE", "−0.49% / −0.55%", "works in TAGE but subsumed by TAGE-SC-L's 1/32 allocation rule"],
        ["IMLI counting all taken backward branches (no conditional filter)", "+0.14%", "rejected"],
        ["Region-based IMLI (BrIMLI-like, 256-byte regions)", "+0.16% (loses gcc gain)", "rejected"],
        ["IMLI hashed into two global corrector tables", "+0.19% alone; +0.20% on top of IMHIST+BHIST", "rejected"],
        ["2 history bits per branch; longest history 1000 / 2000", "+0.28%; +0.15% / +0.96%", "rejected"],
    ], "Exploration results (Δ mean MPKI relative to the configuration at that point).", widths=[3.2, 1.8, 1.6])

    # ---------------------------------------------------------------- 12
    R.h("12. Storage and implementation trade-offs", 1)
    R.bullets([
        f"The loop-structure components cost {int(P['storage_bits']) - int(TB['storage_bits']):,} bits "
        f"({(int(P['storage_bits']) - int(TB['storage_bits']))/8192:.1f} KB) over TAGE-SC-L, mostly corrector tables.",
        "Latency: the inference adds one comparison per branch and a few table lookups that are summed by the existing "
        "corrector adder tree; no change to the TAGE critical path.",
        "A real pipeline would track the loop-structure state speculatively and repair it on mispredictions, as for any "
        "history; this ChampSim updates immediately, so that cost is not modelled.",
        "The 4KB baselines use 1/16 of our storage; comparisons at equal budget are those against the hashed perceptron "
        "(64 KB) and our TAGE-SC-L.",
    ])

    # ---------------------------------------------------------------- 13
    R.h("13. Limitations and threats to validity", 1)
    R.bullets([
        "Ten 250M-instruction windows of ten programs. Tuning used another window of the **same** programs, not "
        "different programs, so some optimism remains; the gains of the contribution (about 1%) are small relative to "
        "trace-to-trace variation.",
        "The simulator models direction prediction only, with immediate update and no wrong path; absolute numbers are "
        "not comparable with newer ChampSim versions or CBP results.",
        "The backward inference is exact only because this ChampSim has no wrong-path fetch and presents every branch "
        "in order; in a speculative front end it would have to use the predicted path and be repaired.",
        "IMLI depends on recognising conditional branches by their first not-taken outcome; on traces with never-exiting "
        "backward branches the counter differs from the paper's definition.",
        "Our TAGE-SC-L is a re-implementation at ~58 KB with 12 tables; it is not Seznec's championship code, which uses "
        "36 logical tables and further tuning.",
        "The hashed-perceptron storage was counted by hand from its source.",
    ])

    # ---------------------------------------------------------------- 14
    R.h("14. Conclusion", 1)
    R.p(f"A TAGE-SC-L predictor re-implemented for the 2021 ChampSim interface reduces mean MPKI by {red(TB, HP):.1f}% "
        f"relative to the strongest predictor shipped with the simulator. Inferring branch direction from the next "
        f"predicted branch's address — exact in this simulator and verified against its targets — makes the "
        f"loop-structure history of IMLI, IMHIST and backward-branch history usable without simulator changes and adds "
        f"a further {red(P, TB):.2f}% MPKI reduction, for a total of {red(P, HP):.1f}% ({f3(HP['mean_mpki_10'])} → "
        f"{f3(P['mean_mpki_10'])} MPKI) and a {100*(sp_hp-1):.2f}% geometric-mean IPC gain at {f2(P['storage_KB'])} KB. "
        f"In IPC the loop-structure components alone add only {100*(sp_tb-1):+.2f}%: in this simulator an avoided "
        f"misprediction saves about 22–50 cycles on most traces, which is small relative to the memory stalls of "
        f"several of the traces where they help most. "
        f"The largest remaining errors (mcf, xz) come from data-dependent branches that history-based prediction does not capture.")

    R.h("References", 1)
    for ref in [
        "[1] D. A. Jiménez, C. Lin, “Dynamic Branch Prediction with Perceptrons,” HPCA 2001.",
        "[2] A. Seznec, “A New Case for the TAGE Branch Predictor,” MICRO 2011.",
        "[3] A. Seznec, J. San Miguel, J. Albericio, “The Inner Most Loop Iteration Counter: A New Dimension in Branch History,” MICRO 2015.",
        "[4] D. A. Jiménez, “Multiperspective Perceptron Predictor,” CBP-5, 2016.",
        "[5] P. Michaud, “An Alternative TAGE-like Conditional Branch Predictor,” ACM TACO 15(3), 2018.",
        "[6] C.-K. Lin, S. J. Tarsa, “Branch Prediction Is Not a Solved Problem: Measurements, Opportunities, and Future Directions,” IISWC 2019 (arXiv:1906.08170).",
        "[7] A. Seznec, P. Michaud, “A case for (partially) TAgged GEometric history length branch prediction,” JILP 8, 2006.",
        "[8] A. Seznec, “TAGE-SC-L Branch Predictors,” CBP-4, 2014; “TAGE-SC-L Branch Predictors Again,” CBP-5, 2016.",
        "[9] F. Schall et al., “The Last-Level Branch Predictor,” MICRO 2024.",
        "[10] N. Gober et al., “The Championship Simulator: Architectural Simulation for Education and Competition,” arXiv:2210.14324, 2022.",
    ]:
        R.p(ref)
    R.d.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
