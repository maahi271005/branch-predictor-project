#!/usr/bin/env python3
"""Analysis of the 50-trace ChampSim evaluation (stage M50_50M_200M).

  python3 experiments/scripts/analyze_50trace.py [--stage M50_50M_200M] [--out results_50trace]

Standard library only, with its own parser (independent of parse_results.py).
Every expected (predictor, trace) combination gets a row, including failed or
missing runs, which are never dropped silently and never filled in.

Outputs (in --out):
  raw_results.csv           one row per predictor x trace (status, counters, metrics, log path)
  per_trace_results.csv     one row per trace: IPC / MPKI / accuracy of every predictor,
                            proposed-vs-baseline deltas
  summary.csv               one row per predictor: means, geomeans, pooled accuracy, storage, runtime
  subset_summary.csv        the same means for trace subsets (original 10, additional 40, INT, FP)
  comparison_vs_baselines.csv  proposed vs each other predictor (MPKI reduction, IPC speedup,
                            per-trace wins / losses / ties, largest gain / regression)
  run_status.csv, failure_report.md, checks.txt, trace_manifest.csv, experiment_config.json

Metric definitions (also in experiment_config.json):
  IPC        = ROI instructions / ROI cycles ("CPU 0 cumulative IPC" line of the ROI statistics)
  MPKI       = 1000 * mispredictions / ROI instructions, all branch types (ChampSim's definition)
  accuracy   = 100 * (branches - mispredictions) / branches, all branch types (ChampSim's definition);
               cond_accuracy / cond_mpki: conditional branches only (BP_TYPE_MISSES)
  mean IPC   = arithmetic mean of per-trace IPC;  geomean IPC = geometric mean of per-trace IPC
  speedup    = geometric mean over traces of IPC(pred) / IPC(ref)
  mean MPKI  = arithmetic mean of per-trace MPKI; % MPKI reduction is computed from the means
  pooled accuracy = sum over traces of correct predictions / sum of branches
"""
import argparse, csv, hashlib, json, math, os, re, shutil, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACES_DIR = os.path.join(ROOT, "experiments", "traces")

PREDICTORS = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tsl_base", "tsl_proposed"]
PROPOSED = "tsl_proposed"
LABEL = {"bimodal": "Bimodal", "gshare": "Gshare", "perceptron": "Perceptron",
         "hashed_perceptron": "Hashed Perceptron", "tage": "TAGE", "tsl_base": "TAGE-SC-L",
         "tsl_proposed": "TFL-TAGE-SC-L (proposed)"}
ORIGIN = {"bimodal": "ChampSim default", "gshare": "ChampSim default", "perceptron": "ChampSim default",
          "hashed_perceptron": "ChampSim default", "tage": "project reference (tagescl.bpred -DTSL_NO_SC -DTSL_NO_LOOP)",
          "tsl_base": "project reference (tagescl.bpred -DTSL_NO_IMLI)",
          "tsl_proposed": "proposed (tagescl.bpred -DTSL_IMHIST -DTSL_BHIST = tfl_tage_scl.bpred)"}
# Logical predictor state. TAGE-family values are printed by the predictor itself
# (storage_bits()) and are cross-checked against every log below; the four ChampSim
# predictors print nothing, so their bits are counted from the source code
# (same accounting as final_deliverables/audit/storage.csv).
STORAGE = {
    "bimodal": (32768, "16,384 x 2-bit counters (source count)"),
    "gshare": (32782, "16,384 x 2-bit counters + 14-bit global history (source count)"),
    "perceptron": (32624, "163 perceptrons x 25 x 8-bit weights + 24-bit history (source count)"),
    "hashed_perceptron": (524542, "16 x 4,096 x 8-bit weights + 240-bit history + 8-bit theta (assumed width) "
                                  "+ 6-bit training counter (source count)"),
    "tage": (383674, "storage_bits() printed by the predictor"),
    "tsl_base": (476319, "storage_bits() printed by the predictor"),
    "tsl_proposed": (508666, "storage_bits() printed by the predictor"),
}
TYPES = ["NOT_BRANCH", "BRANCH_DIRECT_JUMP", "BRANCH_INDIRECT", "BRANCH_CONDITIONAL",
         "BRANCH_DIRECT_CALL", "BRANCH_INDIRECT_CALL", "BRANCH_RETURN", "BRANCH_OTHER"]
# SPEC CPU2017 speed suite membership
INT_BENCH = {"600", "602", "605", "620", "623", "625", "631", "641", "648", "657"}


def suite(trace):
    return "INT" if trace.split(".")[0] in INT_BENCH else "FP"


def gmean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def parse_run(path, warm, sim):
    """Return a dict of metrics; status != 'ok' explains why a run is unusable."""
    r = {"status": "ok", "problem": ""}
    txt = open(path, errors="replace").read()

    def bad(msg):
        r["status"] = "failed"
        r["problem"] = (r["problem"] + "; " if r["problem"] else "") + msg

    m = re.match(r"# RUN binary=(\S+) bin_sha=(\S+) trace=(\S+) warm=(\d+)M sim=(\d+)M\n", txt)
    if not m:
        bad("missing run header")
        return r
    r["bin_sha16"] = m.group(2)
    if (int(m.group(4)), int(m.group(5))) != (warm, sim):
        bad(f"window {m.group(4)}M/{m.group(5)}M != {warm}M/{sim}M")
    m = re.search(r"^# EXIT (-?\d+) WALL ([\d.]+)s", txt, re.M)
    if m:
        r["exit"], r["wall_s"] = int(m.group(1)), float(m.group(2))
        if r["exit"] != 0:
            bad(f"exit code {r['exit']}")
    else:
        r["exit"], r["wall_s"] = "", ""
        bad("no exit record (run interrupted)")
    if "ChampSim completed all CPUs" not in txt:
        bad("ChampSim did not complete")
    r["wrapped"] = "Reached end of trace" in txt
    if r["wrapped"]:
        bad("trace wrapped around")
    m = re.search(r"^CPU 0 (.+) storage: (\d+) bits", txt, re.M)
    r["banner_storage_bits"] = int(m.group(2)) if m else ""
    m = re.search(r"Warmup complete CPU 0 instructions: (\d+) cycles: (\d+)", txt)
    r["warmup_instructions"] = int(m.group(1)) if m else ""
    if "Region of Interest Statistics" not in txt:
        bad("no ROI statistics")
        return r
    roi = txt[txt.index("Region of Interest Statistics"):]
    try:
        m = re.search(r"CPU 0 cumulative IPC: ([\d.]+) instructions: (\d+) cycles: (\d+)", roi)
        r["ipc_printed"], r["instructions"], r["cycles"] = float(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.search(r"Branch Prediction Accuracy: ([\d.]+(?:[eE][-+]?\d+)?)% MPKI: ([\d.]+(?:[eE][-+]?\d+)?)", roi)  # MPKI may be printed as e.g. 5.5e-05
        r["accuracy_printed"], r["mpki_printed"] = float(m.group(1)), float(m.group(2))
        m = re.search(r"BP_STATS num_branch: (\d+) mispredictions: (\d+) sim_instr: (\d+)", roi)
        r["branches"], r["mispredictions"], r["sim_instr_champsim"] = map(int, m.groups())
        m = re.search(r"BP_TYPE_MISSES((?: \d+){8})", roi)
        miss = list(map(int, m.group(1).split()))
        cnt = [int(re.search(r"^%s: (\d+)" % t, roi, re.M).group(1)) for t in TYPES]
    except (AttributeError, ValueError) as e:
        bad(f"unparseable statistics ({e})")
        return r
    r["cond_branches"], r["cond_mispredictions"] = cnt[3], miss[3]
    if r["instructions"] < sim * 1000000:
        bad("fewer measured instructions than requested")
    r["ipc"] = r["instructions"] / r["cycles"]
    r["mpki"] = 1000.0 * r["mispredictions"] / r["instructions"]
    r["accuracy"] = 100.0 * (r["branches"] - r["mispredictions"]) / r["branches"]
    r["cond_mpki"] = 1000.0 * r["cond_mispredictions"] / r["instructions"]
    r["cond_accuracy"] = 100.0 * (r["cond_branches"] - r["cond_mispredictions"]) / r["cond_branches"]
    r["branches_per_kilo_instr"] = 1000.0 * r["branches"] / r["instructions"]
    return r


class Checks:
    def __init__(self):
        self.lines, self.fail = [], 0

    def __call__(self, name, ok, detail=""):
        self.lines.append(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
        self.fail += not ok


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="M50_50M_200M")
    ap.add_argument("--warm", type=int, default=50)
    ap.add_argument("--sim", type=int, default=200)
    ap.add_argument("--out", default=os.path.join(ROOT, "results_50trace"))
    # testing options (e.g. re-analysing the earlier 10-trace logs)
    ap.add_argument("--manifest", default=os.path.join(TRACES_DIR, "trace_manifest.csv"))
    ap.add_argument("--stage-dir", help="results directory (default experiments/results/<stage>)")
    ap.add_argument("--no-bin-check", action="store_true", help="do not require logs to come from build/bin")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stage_dir = a.stage_dir or os.path.join(ROOT, "experiments", "results", a.stage)
    chk = Checks()

    manifest = list(csv.DictReader(open(a.manifest)))
    traces = [m["trace"] for m in manifest]
    group = {m["trace"]: m["group"] for m in manifest}
    chk("manifest has 50 unique traces", len(traces) == 50 == len(set(traces)), str(len(traces)))
    chk("all manifest traces VALID", all(m["status"] == "VALID" for m in manifest))
    chk("manifest md5 == Zenodo md5 for all traces", all(m["md5"] == m["zenodo_md5"] for m in manifest))

    bin_sha = {}
    for p in PREDICTORS:
        bp = os.path.join(ROOT, "build", "bin", p)
        bin_sha[p] = sha16(bp) if os.path.exists(bp) else ""

    # ---- raw results: every expected combination ------------------------------------
    raw = []
    R = {}
    for t in traces:
        for p in PREDICTORS:
            path = os.path.join(stage_dir, p, t + ".txt")
            if os.path.exists(path):
                r = parse_run(path, a.warm, a.sim)
            elif os.path.exists(path + ".partial"):
                r = {"status": "incomplete", "problem": "run in progress or interrupted (.partial only)"}
            else:
                r = {"status": "missing", "problem": "no output file"}
            r.update(predictor=p, label=LABEL[p], trace=t, group=group[t], suite=suite(t),
                     warm_M=a.warm, sim_M=a.sim, log=os.path.relpath(path, ROOT).replace(os.sep, "/"))
            if r["status"] == "ok" and bin_sha[p] and r.get("bin_sha16") != bin_sha[p] and not a.no_bin_check:
                r["status"], r["problem"] = "failed", f"binary hash {r.get('bin_sha16')} != current {bin_sha[p]}"
            raw.append(r)
            R[p, t] = r
    raw_cols = ["predictor", "label", "trace", "group", "suite", "status", "problem", "exit", "wall_s",
                "warm_M", "sim_M", "warmup_instructions", "instructions", "cycles", "ipc", "ipc_printed",
                "branches", "mispredictions", "mpki", "mpki_printed", "accuracy", "accuracy_printed",
                "cond_branches", "cond_mispredictions", "cond_mpki", "cond_accuracy",
                "branches_per_kilo_instr", "sim_instr_champsim", "banner_storage_bits", "wrapped",
                "bin_sha16", "log"]
    write_csv(os.path.join(a.out, "raw_results.csv"), raw, raw_cols)

    ok = [r for r in raw if r["status"] == "ok"]
    notok = [r for r in raw if r["status"] != "ok"]
    chk("expected runs = 7 x 50 = 350", len(raw) == 350, str(len(raw)))
    chk("all 350 runs successful", not notok, f"{len(ok)} ok, {len(notok)} not ok")
    for p in PREDICTORS:
        hs = {r.get("bin_sha16") for r in raw if r["predictor"] == p and r.get("bin_sha16")}
        chk(f"all runs of {p} produced by one binary", len(hs) <= 1, ", ".join(sorted(hs)))
    chk("binary hashes checked against build/bin" if all(bin_sha.values()) else
        "build/bin not present: binary hashes compared between runs only", True)
    for r in ok:
        tag = f"{r['predictor']}/{r['trace']}"
        if abs(r["ipc"] - r["ipc_printed"]) > 5e-6 * max(1, r["ipc"]) + 1e-6:
            chk(f"IPC arithmetic {tag}", False, f"{r['ipc']} vs printed {r['ipc_printed']}")
        mp_cs = 1000.0 * r["mispredictions"] / r["sim_instr_champsim"]
        if abs(mp_cs - r["mpki_printed"]) > 1e-4 * max(1, mp_cs):
            chk(f"MPKI arithmetic {tag}", False, f"{mp_cs} vs printed {r['mpki_printed']}")
        acc_cs = 100.0 * (r["branches"] - r["mispredictions"]) / r["branches"]
        if abs(acc_cs - r["accuracy_printed"]) > 1e-3:
            chk(f"accuracy arithmetic {tag}", False, f"{acc_cs} vs printed {r['accuracy_printed']}")
        if r["banner_storage_bits"] != "":
            if r["banner_storage_bits"] != STORAGE[r["predictor"]][0]:
                chk(f"storage banner {tag}", False, f"{r['banner_storage_bits']} != {STORAGE[r['predictor']][0]}")
    chk("IPC / MPKI / accuracy recomputed from counters agree with ChampSim's printed values (all ok runs)",
        not any(l.startswith("FAIL") and ("arithmetic" in l) for l in chk.lines))
    chk("printed storage_bits of TAGE-family runs match storage table",
        not any(l.startswith("FAIL  storage banner") for l in chk.lines))
    for t in traces:
        # every predictor sees the same trace window, hence the same branch stream
        nb = {R[p, t]["branches"] for p in PREDICTORS if R[p, t]["status"] == "ok"}
        if len(nb) > 1:
            spread = (max(nb) - min(nb)) / max(nb)
            if spread > 1e-4:
                chk(f"same branch count across predictors {t}", False, f"spread {spread:.2e}")
    chk("branch counts consistent across predictors on every trace (rel. spread <= 1e-4)",
        not any(l.startswith("FAIL  same branch count") for l in chk.lines))

    complete_traces = [t for t in traces if all(R[p, t]["status"] == "ok" for p in PREDICTORS)]
    chk("traces with all 7 predictors successful", len(complete_traces) == len(traces),
        f"{len(complete_traces)}/{len(traces)}")
    # Aggregates use only traces on which every predictor succeeded, so that all
    # predictors are averaged over the same set (reported in summary as n_traces).
    T = complete_traces
    if not T:
        write_csv(os.path.join(a.out, "run_status.csv"), raw,
                  ["predictor", "trace", "group", "status", "problem", "exit", "wall_s", "log"])
        print(f"{len(ok)}/{len(raw)} runs ok; no trace complete for all predictors yet")
        return

    def v(p, t, k):
        return R[p, t][k]

    # ---- per-trace table ---------------------------------------------------------
    per_trace = []
    for t in traces:
        row = {"trace": t, "group": group[t], "suite": suite(t), "all_runs_ok": t in T}
        any_ok = next((R[p, t] for p in PREDICTORS if R[p, t]["status"] == "ok"), None)
        row["branches_per_kilo_instr"] = any_ok["branches_per_kilo_instr"] if any_ok else ""
        row["cond_share_pct"] = 100.0 * any_ok["cond_branches"] / any_ok["branches"] if any_ok else ""
        for p in PREDICTORS:
            r = R[p, t]
            for k in ("ipc", "mpki", "accuracy", "cond_accuracy"):
                row[f"{k}_{p}"] = r.get(k, "") if r["status"] == "ok" else ""
        if t in T:
            # best = fewest cycles / mispredictions (as for wins and losses); ties list every predictor, joined by "+"
            for col, k in (("best_ipc_predictor", "cycles"), ("best_mpki_predictor", "mispredictions")):
                lo = min(R[p, t][k] for p in PREDICTORS)
                row[col] = "+".join(p for p in PREDICTORS if R[p, t][k] == lo)
            for b in PREDICTORS:
                if b == PROPOSED:
                    continue
                row[f"ipc_change_pct_vs_{b}"] = 100.0 * (v(PROPOSED, t, "ipc") / v(b, t, "ipc") - 1)
                row[f"mpki_change_vs_{b}"] = v(PROPOSED, t, "mpki") - v(b, t, "mpki")
        per_trace.append(row)
    pt_cols = ["trace", "group", "suite", "all_runs_ok", "branches_per_kilo_instr", "cond_share_pct"]
    for k in ("ipc", "mpki", "accuracy", "cond_accuracy"):
        pt_cols += [f"{k}_{p}" for p in PREDICTORS]
    pt_cols += ["best_ipc_predictor", "best_mpki_predictor"]
    pt_cols += [f"ipc_change_pct_vs_{b}" for b in PREDICTORS if b != PROPOSED]
    pt_cols += [f"mpki_change_vs_{b}" for b in PREDICTORS if b != PROPOSED]
    write_csv(os.path.join(a.out, "per_trace_results.csv"), per_trace, pt_cols)

    # ---- summaries -----------------------------------------------------------------
    def agg(p, ts):
        ipcs = [v(p, t, "ipc") for t in ts]
        mpkis = [v(p, t, "mpki") for t in ts]
        nb = sum(v(p, t, "branches") for t in ts)
        nm = sum(v(p, t, "mispredictions") for t in ts)
        cb = sum(v(p, t, "cond_branches") for t in ts)
        cm = sum(v(p, t, "cond_mispredictions") for t in ts)
        return {
            "n_traces": len(ts),
            "mean_ipc": statistics.fmean(ipcs), "geomean_ipc": gmean(ipcs),
            "min_ipc": min(ipcs), "max_ipc": max(ipcs),
            "mean_mpki": statistics.fmean(mpkis), "median_mpki": statistics.median(mpkis),
            "min_mpki": min(mpkis), "max_mpki": max(mpkis),
            "mean_cond_mpki": statistics.fmean(v(p, t, "cond_mpki") for t in ts),
            "pooled_accuracy": 100.0 * (nb - nm) / nb, "pooled_cond_accuracy": 100.0 * (cb - cm) / cb,
            "mean_accuracy": statistics.fmean(v(p, t, "accuracy") for t in ts),
            "mean_cond_accuracy": statistics.fmean(v(p, t, "cond_accuracy") for t in ts),
            "geomean_speedup_vs_bimodal": gmean([v(p, t, "ipc") / v("bimodal", t, "ipc") for t in ts]),
            "total_branches": nb, "total_mispredictions": nm,
        }

    summary = []
    S = {}
    for p in PREDICTORS:
        s = {"predictor": p, "label": LABEL[p], "origin": ORIGIN[p],
             "storage_bits": STORAGE[p][0], "storage_KB": STORAGE[p][0] / 8192.0, "storage_basis": STORAGE[p][1],
             "runs_ok": sum(R[p, t]["status"] == "ok" for t in traces),
             "runs_not_ok": sum(R[p, t]["status"] != "ok" for t in traces)}
        s.update(agg(p, T))
        walls = [R[p, t]["wall_s"] for t in traces if R[p, t]["status"] == "ok"]
        s["total_sim_hours"] = sum(walls) / 3600.0
        s["mean_wall_s"] = statistics.fmean(walls) if walls else ""
        s["max_wall_s"] = max(walls) if walls else ""
        summary.append(s)
        S[p] = s
    for k, rev in (("geomean_ipc", True), ("mean_mpki", False), ("pooled_accuracy", True)):
        for i, p in enumerate(sorted(PREDICTORS, key=lambda p: S[p][k], reverse=rev)):
            S[p][f"rank_{k}"] = i + 1
    sum_cols = ["predictor", "label", "origin", "storage_bits", "storage_KB", "storage_basis", "runs_ok",
                "runs_not_ok", "n_traces", "mean_ipc", "geomean_ipc", "min_ipc", "max_ipc",
                "geomean_speedup_vs_bimodal", "mean_mpki", "median_mpki", "min_mpki", "max_mpki",
                "mean_cond_mpki", "pooled_accuracy", "pooled_cond_accuracy", "mean_accuracy",
                "mean_cond_accuracy", "total_branches", "total_mispredictions", "rank_geomean_ipc",
                "rank_mean_mpki", "rank_pooled_accuracy", "total_sim_hours", "mean_wall_s", "max_wall_s"]
    write_csv(os.path.join(a.out, "summary.csv"), summary, sum_cols)

    subsets = {"all50": T,
               "original10": [t for t in T if group[t] == "original10"],
               "additional40": [t for t in T if group[t] == "additional40"],
               "INT": [t for t in T if suite(t) == "INT"],
               "FP": [t for t in T if suite(t) == "FP"]}
    sub_rows = []
    for name, ts in subsets.items():
        if not ts:
            continue
        for p in PREDICTORS:
            s = {"subset": name, "predictor": p, "label": LABEL[p]}
            s.update(agg(p, ts))
            if p != PROPOSED:
                s["proposed_pct_mpki_reduction"] = 100.0 * (1 - S_mean(PROPOSED, ts, v) / S_mean(p, ts, v))
                s["proposed_ipc_speedup_pct"] = 100.0 * (gmean([v(PROPOSED, t, "ipc") / v(p, t, "ipc") for t in ts]) - 1)
            sub_rows.append(s)
    write_csv(os.path.join(a.out, "subset_summary.csv"), sub_rows,
              ["subset", "predictor", "label", "n_traces", "mean_ipc", "geomean_ipc", "geomean_speedup_vs_bimodal",
               "mean_mpki", "median_mpki", "pooled_accuracy", "pooled_cond_accuracy", "proposed_pct_mpki_reduction",
               "proposed_ipc_speedup_pct"])

    # ---- proposed vs each baseline ------------------------------------------------
    comp = []
    for b in PREDICTORS:
        if b == PROPOSED:
            continue
        d_ipc = {t: 100.0 * (v(PROPOSED, t, "ipc") / v(b, t, "ipc") - 1) for t in T}
        d_mp = {t: v(PROPOSED, t, "mpki") - v(b, t, "mpki") for t in T}
        dm = {t: v(PROPOSED, t, "mispredictions") - v(b, t, "mispredictions") for t in T}
        dc = {t: v(PROPOSED, t, "cycles") - v(b, t, "cycles") for t in T}
        best_i = max(T, key=lambda t: d_ipc[t]); worst_i = min(T, key=lambda t: d_ipc[t])
        best_m = min(T, key=lambda t: d_mp[t]); worst_m = max(T, key=lambda t: d_mp[t])
        comp.append({
            "baseline": b, "baseline_label": LABEL[b], "n_traces": len(T),
            "baseline_mean_mpki": S[b]["mean_mpki"], "proposed_mean_mpki": S[PROPOSED]["mean_mpki"],
            "abs_mpki_reduction": S[b]["mean_mpki"] - S[PROPOSED]["mean_mpki"],
            "pct_mpki_reduction": 100.0 * (1 - S[PROPOSED]["mean_mpki"] / S[b]["mean_mpki"]),
            "baseline_geomean_ipc": S[b]["geomean_ipc"], "proposed_geomean_ipc": S[PROPOSED]["geomean_ipc"],
            "geomean_ipc_speedup": gmean([v(PROPOSED, t, "ipc") / v(b, t, "ipc") for t in T]),
            "ipc_improvement_pct": 100.0 * (gmean([v(PROPOSED, t, "ipc") / v(b, t, "ipc") for t in T]) - 1),
            "mean_ipc_change_pct": 100.0 * (S[PROPOSED]["mean_ipc"] / S[b]["mean_ipc"] - 1),
            "pooled_accuracy_change_pp": S[PROPOSED]["pooled_accuracy"] - S[b]["pooled_accuracy"],
            "traces_lower_mpki": sum(dm[t] < 0 for t in T), "traces_equal_mpki": sum(dm[t] == 0 for t in T),
            "traces_higher_mpki": sum(dm[t] > 0 for t in T),
            "traces_higher_ipc": sum(dc[t] < 0 for t in T), "traces_equal_ipc": sum(dc[t] == 0 for t in T),
            "traces_lower_ipc": sum(dc[t] > 0 for t in T),
            "traces_ipc_gain_ge_0.5pct": sum(d_ipc[t] >= 0.5 for t in T),
            "traces_ipc_loss_ge_0.5pct": sum(d_ipc[t] <= -0.5 for t in T),
            "largest_ipc_gain_trace": best_i, "largest_ipc_gain_pct": d_ipc[best_i],
            "largest_ipc_loss_trace": worst_i, "largest_ipc_loss_pct": d_ipc[worst_i],
            "largest_mpki_reduction_trace": best_m, "largest_mpki_reduction": -d_mp[best_m],
            "largest_mpki_increase_trace": worst_m, "largest_mpki_increase": d_mp[worst_m],
        })
    write_csv(os.path.join(a.out, "comparison_vs_baselines.csv"), comp, list(comp[0]))

    # ---- reconciliation: summary values recomputed from raw_results.csv -------------
    back = list(csv.DictReader(open(os.path.join(a.out, "raw_results.csv"))))
    for p in PREDICTORS:
        rows = [r for r in back if r["predictor"] == p and r["status"] == "ok" and r["trace"] in T]
        ipcs = [int(r["instructions"]) / int(r["cycles"]) for r in rows]
        mp = [1000.0 * int(r["mispredictions"]) / int(r["instructions"]) for r in rows]
        chk(f"summary reconciles with raw_results.csv: {p}",
            abs(statistics.fmean(ipcs) - S[p]["mean_ipc"]) < 1e-12 and abs(gmean(ipcs) - S[p]["geomean_ipc"]) < 1e-12
            and abs(statistics.fmean(mp) - S[p]["mean_mpki"]) < 1e-12,
            f"mean IPC {statistics.fmean(ipcs):.6f}, geomean IPC {gmean(ipcs):.6f}, mean MPKI {statistics.fmean(mp):.6f}")
    # original-10 subset vs the earlier 10-trace study (same traces, window, binaries' source)
    prev = os.path.join(ROOT, "archive", "10trace_study", "final_deliverables", "audit", "per_run.csv")
    if os.path.exists(prev):
        old = {(r["binary"], r["trace"]): r for r in csv.DictReader(open(prev))}
        same = diff = 0
        for p in PREDICTORS:
            for t in subsets["original10"]:
                o = old.get((p, t))
                if o:
                    eq = int(o["cycles"]) == v(p, t, "cycles") and int(o["mispredictions"]) == v(p, t, "mispredictions")
                    same += eq; diff += not eq
        chk("original-10 runs identical to the earlier 10-trace study (cycles and mispredictions)",
            diff == 0, f"{same} identical, {diff} different")

    # ---- status / failure report ----------------------------------------------------
    write_csv(os.path.join(a.out, "run_status.csv"), raw,
              ["predictor", "trace", "group", "status", "problem", "exit", "wall_s", "log"])
    with open(os.path.join(a.out, "failure_report.md"), "w") as f:
        f.write(f"# Run status — stage {a.stage}\n\n")
        f.write(f"Expected runs: {len(raw)} (7 predictors x {len(traces)} traces)  \n")
        f.write(f"Successful: {len(ok)}  \nNot successful: {len(notok)}\n\n")
        if notok:
            f.write("| Predictor | Trace | Status | Problem | Log |\n|---|---|---|---|---|\n")
            for r in notok:
                f.write(f"| {r['predictor']} | {r['trace']} | {r['status']} | {r['problem']} | {r['log']} |\n")
            f.write(f"\nAggregates use the {len(T)} traces on which all seven predictors succeeded.\n")
        else:
            f.write("All runs completed with exit code 0, the full requested window, no trace "
                    "wrap-around, and parseable statistics.\n")

    shutil.copy(a.manifest, os.path.join(a.out, "trace_manifest.csv"))

    builds = {}
    for p in PREDICTORS:
        bi = os.path.join(ROOT, "build", "bin", p + ".buildinfo")
        if os.path.exists(bi):
            builds[p] = dict(l.rstrip("\n").split(": ", 1) for l in open(bi) if ": " in l)
            builds[p]["binary_sha256_16"] = bin_sha[p]
    started = os.path.join(ROOT, "experiments", "results", a.stage + ".started")
    finished = os.path.join(ROOT, "experiments", "results", a.stage + ".finished")
    cfg = {
        "stage": a.stage,
        "results_directory": f"experiments/results/{a.stage}/<predictor>/<trace>.txt",
        "simulator": "ChampSim (2021 build_champsim.sh version) in champsim/, stats-only core additions (BP_STATS, BP_TYPE_MISSES)",
        "configuration": {"cores": 1, "l1i_prefetcher": "no", "l1d_prefetcher": "no", "l2c_prefetcher": "no",
                          "llc_prefetcher": "no", "llc_replacement": "lru",
                          "equivalent_build": "./build_champsim.sh <predictor> no no no no lru 1",
                          "branch_mispredict_penalty_cycles": 1, "rob_entries": 352, "fetch_width": 6},
        "warmup_instructions": a.warm * 1000000,
        "simulation_instructions": a.sim * 1000000,
        "window": "instructions 0 - 250M of each trace (no trace shorter than 2,000M instructions)",
        "traces": {"count": len(traces), "original10": sum(group[t] == "original10" for t in traces),
                   "additional40": sum(group[t] == "additional40" for t in traces),
                   "source": "SPEC CPU 2017 ChampSim Traces, Zenodo record 10960004 (CC-BY-4.0), md5-verified",
                   "manifest": "trace_manifest.csv"},
        "predictors": {p: {"label": LABEL[p], "origin": ORIGIN[p], "storage_bits": STORAGE[p][0],
                           "build": builds.get(p, {})} for p in PREDICTORS},
        "parallel_jobs": 14,
        "host": "Windows 11 + WSL2 Ubuntu 26.04, 16 logical CPUs, 7.8 GB RAM for WSL",
        "started": open(started).read().strip() if os.path.exists(started) else "",
        "finished": open(finished).read().strip() if os.path.exists(finished) else "",
        "metrics": {
            "ipc": "ROI instructions / ROI cycles (ChampSim 'CPU 0 cumulative IPC')",
            "mpki": "1000 x mispredictions / ROI instructions, all branch types",
            "accuracy": "100 x (branches - mispredictions) / branches, all branch types (ChampSim's definition)",
            "cond_accuracy": "same, conditional branches only",
            "mean_ipc": "arithmetic mean of per-trace IPC",
            "geomean_ipc": "geometric mean of per-trace IPC",
            "speedup": "geometric mean of per-trace IPC ratios",
            "mean_mpki": "arithmetic mean of per-trace MPKI; % reductions computed from the means",
            "pooled_accuracy": "sum of correct predictions / sum of branches over all traces",
            "storage": "logical predictor state in bits (see summary.csv storage_basis)",
        },
        "aggregation_trace_set": f"{len(T)} traces on which all 7 predictors succeeded",
    }
    json.dump(cfg, open(os.path.join(a.out, "experiment_config.json"), "w"), indent=2)

    with open(os.path.join(a.out, "checks.txt"), "w") as f:
        f.write("\n".join(chk.lines) + f"\n\n{len(chk.lines)} checks, {chk.fail} failed\n")
    print(f"{len(ok)}/{len(raw)} runs ok; aggregates over {len(T)} traces; {len(chk.lines)} checks, {chk.fail} failed")
    for s in summary:
        print(f"  {s['label']:28s} meanIPC {s['mean_ipc']:.4f} gmIPC {s['geomean_ipc']:.4f} "
              f"MPKI {s['mean_mpki']:.4f} acc {s['pooled_accuracy']:.3f}%")


def S_mean(p, ts, v):
    return statistics.fmean(v(p, t, "mpki") for t in ts)


if __name__ == "__main__":
    main()
