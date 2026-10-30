#!/usr/bin/env python3
"""Independent audit: recompute every reported metric from the raw ChampSim outputs.

  python3 final_deliverables/scripts/recompute_metrics.py

Uses only the Python standard library and its own parsing code (it does not reuse
experiments/scripts/parse_results.py), so it is an independent check of the original pipeline.

Writes final_deliverables/audit/:
  per_run.csv            one row per ChampSim run, raw counters + derived metrics + checks
  summary.csv            aggregates per predictor
  relative.csv           requested relative comparisons (MPKI reductions, IPC improvements)
  harness_vs_champsim.csv  replay-harness MPKI vs ChampSim MPKI for identical configurations
  ablation.csv           harness ablation, recomputed from the harness output files
  checks.txt             every consistency check with PASS/FAIL
  audit.json             everything above in one file

Definitions (as requested for the audit)
  MPKI          = 1000 * mispredictions / retired instructions of the measured region
                  (retired instructions = the 'instructions' field of the ROI IPC line, 200,000,000)
  ChampSim MPKI = 1000 * mispredictions / (num_retired - warmup_instructions), as printed by ChampSim
  IPC           = instructions / cycles of the measured region
  geomean speedup = exp(mean(log(IPC_p / IPC_ref))) over the 10 traces
  % MPKI reduction = (MPKI_ref - MPKI_p) / MPKI_ref * 100, on mean MPKI
  IPC improvement  = (geomean speedup - 1) * 100
"""
import csv, hashlib, json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "experiments", "results")
OUT = os.path.join(ROOT, "final_deliverables", "audit")
TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]
INT7 = [t for t in TRACES if t[:3] in ("602", "605", "620", "623", "625", "631", "657")]
STAGES = {"bimodal": "B_baseline_50M_200M", "gshare": "B_baseline_50M_200M", "perceptron": "B_baseline_50M_200M",
          "hashed_perceptron": "B_baseline_50M_200M", "tage": "G_final_50M_200M", "tage_l": "G_final_50M_200M",
          "tsl_base": "G_final_50M_200M", "tsl_imli": "G_final_50M_200M", "tsl_proposed": "G_final_50M_200M",
          "tsl_prop_noloop": "G_final_50M_200M", "tsl_prop_nolocal": "G_final_50M_200M"}
TYPES = ["NOT_BRANCH", "BRANCH_DIRECT_JUMP", "BRANCH_INDIRECT", "BRANCH_CONDITIONAL", "BRANCH_DIRECT_CALL",
         "BRANCH_INDIRECT_CALL", "BRANCH_RETURN", "BRANCH_OTHER"]
checks = []


def check(name, ok, detail=""):
    checks.append(("PASS" if ok else "FAIL", name, detail))
    return ok


def sha256(path, n=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:n] if n else h.hexdigest()


def parse_run(path):
    txt = open(path).read()
    r = {"path": os.path.relpath(path, ROOT)}
    m = re.match(r"# RUN binary=(\S+) bin_sha=(\S+) trace=(\S+) warm=(\d+)M sim=(\d+)M\n", txt)
    r["binary"], r["bin_sha16"], r["trace"], r["warm_M"], r["sim_M"] = m.group(1), m.group(2), m.group(3), int(m.group(4)), int(m.group(5))
    m = re.search(r"^# EXIT (-?\d+) WALL ([\d.]+)s", txt, re.M)
    r["exit"], r["wall_s"] = int(m.group(1)), float(m.group(2))
    r["completed"] = "ChampSim completed all CPUs" in txt
    r["wrapped"] = "Reached end of trace" in txt
    m = re.search(r"^CPU 0 (.+) storage: (\d+) bits", txt, re.M)
    r["predictor_banner"] = m.group(1) if m else ""
    r["banner_storage_bits"] = int(m.group(2)) if m else None
    m = re.search(r"Warmup complete CPU 0 instructions: (\d+) cycles: (\d+)", txt)
    r["warmup_instr"], r["warmup_cycles"] = int(m.group(1)), int(m.group(2))
    roi = txt[txt.index("Region of Interest Statistics"):]
    m = re.search(r"CPU 0 cumulative IPC: ([\d.]+) instructions: (\d+) cycles: (\d+)", roi)
    r["ipc_printed"], r["instructions"], r["cycles"] = float(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"Branch Prediction Accuracy: ([\d.]+)% MPKI: ([\d.]+)", roi)
    r["acc_printed"], r["mpki_printed"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"BP_STATS num_branch: (\d+) mispredictions: (\d+) sim_instr: (\d+)", roi)
    r["branches"], r["mispredictions"], r["sim_instr_champsim"] = map(int, m.groups())
    m = re.search(r"BP_TYPE_MISSES((?: \d+){8})", roi)
    miss = list(map(int, m.group(1).split()))
    cnt = [int(re.search(r"^%s: (\d+)" % t, roi, re.M).group(1)) for t in TYPES]
    r["type_counts"], r["type_misses"] = cnt, miss
    r["cond_branches"], r["cond_mispredictions"] = cnt[3], miss[3]
    # derived, full precision
    r["ipc"] = r["instructions"] / r["cycles"]
    r["mpki"] = 1000.0 * r["mispredictions"] / r["instructions"]
    r["mpki_champsim_def"] = 1000.0 * r["mispredictions"] / r["sim_instr_champsim"]
    r["cond_mpki"] = 1000.0 * r["cond_mispredictions"] / r["instructions"]
    r["accuracy_all"] = 100.0 * (r["branches"] - r["mispredictions"]) / r["branches"]
    r["accuracy_cond"] = 100.0 * (r["cond_branches"] - r["cond_mispredictions"]) / r["cond_branches"]
    return r


def gmean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def main():
    os.makedirs(OUT, exist_ok=True)
    runs = {}
    for p, st in STAGES.items():
        for t in TRACES:
            f = os.path.join(RES, st, p, t + ".txt")
            if not check(f"run exists: {p}/{t}", os.path.exists(f)):
                continue
            runs[p, t] = parse_run(f)

    # ---------------------------------------------------------------- per-run checks
    buildinfo = {}
    for p in STAGES:
        bi = os.path.join(ROOT, "build", "bin", p + ".buildinfo")
        binp = os.path.join(ROOT, "build", "bin", p)
        info = dict(l.split(": ", 1) for l in open(bi).read().splitlines() if ": " in l) if os.path.exists(bi) else {}
        info["binary_sha16_now"] = sha256(binp, 16) if os.path.exists(binp) else None
        buildinfo[p] = info
    cur_src = sha256(os.path.join(ROOT, "champsim", "branch", "tagescl.bpred"))
    for (p, t), r in runs.items():
        check(f"exit 0: {p}/{t}", r["exit"] == 0, str(r["exit"]))
        check(f"completed: {p}/{t}", r["completed"])
        check(f"no trace wrap: {p}/{t}", not r["wrapped"])
        check(f"window 50M+200M: {p}/{t}", (r["warm_M"], r["sim_M"]) == (50, 200), f"{r['warm_M']}+{r['sim_M']}")
        # ChampSim retires up to RETIRE_WIDTH=4 instructions per cycle and stops at the end of the cycle that
        # reaches the target, so the measured region is 200,000,000..200,000,003 instructions.
        check(f"measured instructions in [200M, 200M+4): {p}/{t}", 200_000_000 <= r["instructions"] < 200_000_004, str(r["instructions"]))
        check(f"printed IPC = instructions/cycles: {p}/{t}", abs(r["ipc"] - r["ipc_printed"]) < 5e-6 * r["ipc"],
              f"{r['ipc_printed']} vs {r['ipc']:.6f}")
        check(f"printed MPKI = ChampSim definition: {p}/{t}", abs(r["mpki_printed"] - r["mpki_champsim_def"]) < 1e-4 * max(1, r["mpki_printed"]),
              f"{r['mpki_printed']} vs {r['mpki_champsim_def']:.6f}")
        check(f"result produced by the binary present in build/bin: {p}/{t}",
              buildinfo[p].get("binary_sha16_now") == r["bin_sha16"], f"{r['bin_sha16']} vs {buildinfo[p].get('binary_sha16_now')}")
        if buildinfo[p].get("predictor") == "branch/tagescl.bpred":
            check(f"binary built from current (frozen) tagescl.bpred: {p}",
                  buildinfo[p].get("predictor_sha256") == cur_src, buildinfo[p].get("predictor_sha256", "")[:12])
    # suspicious duplicates: identical cycles and mispredictions for different predictors on a trace
    for t in TRACES:
        seen = {}
        for p in STAGES:
            if (p, t) in runs:
                k = (runs[p, t]["cycles"], runs[p, t]["mispredictions"])
                if k in seen:
                    checks.append(("NOTE", f"identical cycles+mispredictions: {seen[k]} and {p} on {t}", str(k)))
                seen[k] = p
    # the same trace must present the same number of branches to every predictor (fetch order differs only at
    # the warm-up boundary); report the spread
    for t in TRACES:
        nb = [runs[p, t]["branches"] for p in STAGES if (p, t) in runs]
        spread = max(nb) - min(nb)
        check(f"branch count consistent across predictors (spread < 0.01%): {t}", spread < 1e-4 * max(nb), f"spread {spread} of {max(nb)}")

    # ---------------------------------------------------------------- aggregates
    preds = [p for p in STAGES if all((p, t) in runs for t in TRACES)]
    S = {}
    for p in preds:
        rs = [runs[p, t] for t in TRACES]
        S[p] = {
            "mean_mpki": sum(r["mpki"] for r in rs) / 10,
            "mean_mpki_champsim_def": sum(r["mpki_champsim_def"] for r in rs) / 10,
            "mean_mpki_int7": sum(runs[p, t]["mpki"] for t in INT7) / 7,
            "mean_cond_mpki": sum(r["cond_mpki"] for r in rs) / 10,
            "mean_ipc": sum(r["ipc"] for r in rs) / 10,
            "pooled_accuracy_all": 100.0 * (1 - sum(r["mispredictions"] for r in rs) / sum(r["branches"] for r in rs)),
            "pooled_accuracy_cond": 100.0 * (1 - sum(r["cond_mispredictions"] for r in rs) / sum(r["cond_branches"] for r in rs)),
            "mean_accuracy_all": sum(r["accuracy_all"] for r in rs) / 10,
            "mean_accuracy_cond": sum(r["accuracy_cond"] for r in rs) / 10,
            "total_mispredictions": sum(r["mispredictions"] for r in rs),
            "banner_storage_bits": rs[0]["banner_storage_bits"],
        }
        for ref in ("bimodal", "hashed_perceptron", "tage", "tsl_base", "tsl_imli"):
            if ref in preds:
                S[p][f"gm_speedup_vs_{ref}"] = gmean([runs[p, t]["ipc"] / runs[ref, t]["ipc"] for t in TRACES])
        S[p]["ratio_of_mean_ipc_vs_bimodal"] = S[p]["mean_ipc"] / sum(runs["bimodal", t]["ipc"] for t in TRACES) * 10
        S[p]["arith_mean_of_speedups_vs_bimodal"] = sum(runs[p, t]["ipc"] / runs["bimodal", t]["ipc"] for t in TRACES) / 10

    rel = []
    P = "tsl_proposed"
    for ref in ("hashed_perceptron", "tage", "tsl_base", "tsl_imli", "bimodal"):
        a, b = S[ref]["mean_mpki"], S[P]["mean_mpki"]
        rel.append({"proposed_vs": ref, "baseline_mean_mpki": a, "proposed_mean_mpki": b,
                    "abs_mpki_reduction": a - b, "pct_mpki_reduction": 100 * (a - b) / a,
                    "gm_ipc_speedup": S[P][f"gm_speedup_vs_{ref}"], "ipc_improvement_pct": 100 * (S[P][f"gm_speedup_vs_{ref}"] - 1),
                    "traces_lower_mpki": sum(runs[P, t]["mpki"] < runs[ref, t]["mpki"] for t in TRACES),
                    "traces_higher_mpki": sum(runs[P, t]["mpki"] > runs[ref, t]["mpki"] for t in TRACES),
                    "traces_higher_ipc": sum(runs[P, t]["ipc"] > runs[ref, t]["ipc"] for t in TRACES),
                    "traces_lower_ipc": sum(runs[P, t]["ipc"] < runs[ref, t]["ipc"] for t in TRACES)})

    # ---------------------------------------------------------------- compare with the original pipeline
    orig_summary = {r["predictor"]: r for r in csv.DictReader(open(os.path.join(ROOT, "submission", "results", "results_summary.csv")))}
    orig_pt = {(r["predictor"], r["trace"]): r for r in csv.DictReader(open(os.path.join(ROOT, "submission", "results", "results_per_trace.csv")))}
    for p in preds:
        o = orig_summary[p]
        check(f"original mean MPKI matches recomputation: {p}", abs(float(o["mean_mpki_10"]) - S[p]["mean_mpki_champsim_def"]) < 6e-5,
              f"orig {o['mean_mpki_10']} recomputed(ChampSim def) {S[p]['mean_mpki_champsim_def']:.6f} (retired-instr def {S[p]['mean_mpki']:.6f})")
        check(f"original geomean speedup vs bimodal matches: {p}", abs(float(o["geomean_speedup_vs_bimodal"]) - S[p]["gm_speedup_vs_bimodal"]) < 6e-5,
              f"orig {o['geomean_speedup_vs_bimodal']} recomputed {S[p]['gm_speedup_vs_bimodal']:.6f}")
        check(f"original geomean speedup vs hashed perceptron matches: {p}", abs(float(o["geomean_speedup_vs_hashed_perceptron"]) - S[p]["gm_speedup_vs_hashed_perceptron"]) < 6e-5)
        check(f"original pooled accuracy matches: {p}", abs(float(o["pooled_accuracy_all_pct"]) - S[p]["pooled_accuracy_all"]) < 6e-5)
        check(f"original storage equals predictor-reported storage: {p}",
              S[p]["banner_storage_bits"] is None or int(o["storage_bits"]) == S[p]["banner_storage_bits"],
              f"orig {o['storage_bits']} banner {S[p]['banner_storage_bits']}")
        for t in TRACES:
            ot, r = orig_pt[p, t], runs[p, t]
            ok = (int(ot["mispredictions"]) == r["mispredictions"] and int(ot["cycles"]) == r["cycles"]
                  and abs(float(ot["ipc"]) - r["ipc_printed"]) < 1e-9)
            check(f"original per-trace counters match raw output: {p}/{t}", ok)

    # ---------------------------------------------------------------- harness vs ChampSim
    hmap = {"tsl_proposed": "prop", "tsl_prop_noloop": "prop_noloop", "tsl_prop_nolocal": "prop_nolocal",
            "tsl_base": "prop_noimli", "tage_l": "prop_nosc", "tage": "tage", "hashed_perceptron": "hashed_perceptron"}
    hvc = []
    for p, h in hmap.items():
        f = os.path.join(RES, "harness", "main", h + ".txt")
        if not os.path.exists(f) or p not in preds:
            continue
        lines = [l for l in open(f) if not l.startswith("#")]
        hm = {l.split(".br")[0]: (int(re.search(r" mispredictions=(\d+)", l).group(1)), float(re.search(r" mpki=(\S+)", l).group(1))) for l in lines}
        for t in TRACES:
            cm = runs[p, t]["mispredictions"]
            hvc.append({"champsim_predictor": p, "harness_variant": h, "trace": t, "champsim_mispredictions": cm,
                        "harness_mispredictions": hm[t][0], "rel_diff_pct": 100 * (hm[t][0] - cm) / cm if cm else 0.0,
                        "champsim_mpki": runs[p, t]["mpki_champsim_def"], "harness_mpki": hm[t][1]})
        mh, mc = sum(v[1] for v in hm.values()) / 10, S[p]["mean_mpki_champsim_def"]
        check(f"harness mean MPKI within 0.1% of ChampSim: {p} vs harness {h}", abs(mh - mc) / mc < 1e-3, f"harness {mh:.4f} ChampSim {mc:.4f}")

    # ---------------------------------------------------------------- harness provenance + ablation recomputation
    src = open(os.path.join(ROOT, "champsim", "branch", "tagescl.bpred")).read()
    rep = open(os.path.join(ROOT, "experiments", "harness", "replay.cc")).read()
    abl = []
    labels = {"prop": "Proposed (all components)", "prop_noimhist": "without IMHIST", "prop_nobhist": "without backward-branch history",
              "prop_noimli": "without all IMLI-derived components (= TAGE-SC-L)", "prop_noloop": "without loop predictor",
              "prop_nolocal": "without local-history SC tables", "prop_nosc": "without statistical corrector (= TAGE + loop)",
              "tage": "TAGE only"}
    for region in ("main", "tune"):
        base = None
        for name in labels:
            f = os.path.join(RES, "harness", region, name + ".txt")
            hdr = open(f).readline()
            flags = re.search(r"flags=(.*) key=", hdr).group(1)
            key = re.search(r"key=(\S+)", hdr).group(1)
            exp_key = hashlib.sha256((src + rep + flags).encode()).hexdigest()[:16]
            check(f"harness result {region}/{name} produced from the frozen source (key)", key == exp_key, f"flags='{flags}'")
            lines = [l for l in open(f) if not l.startswith("#")]
            vals = {l.split(".br")[0]: float(re.search(r" mpki=(\S+)", l).group(1)) for l in lines}
            m = sum(vals.values()) / len(vals)
            if name == "prop":
                base = m
            row = {"region": region, "variant": name, "description": labels[name], "flags": flags, "mean_mpki": m,
                   "delta_vs_proposed_pct": 100 * (m - base) / base}
            row.update({t: vals[t] for t in TRACES})
            abl.append(row)

    # ---------------------------------------------------------------- write
    with open(os.path.join(OUT, "per_run.csv"), "w", newline="") as f:
        cols = ["binary", "trace", "warm_M", "sim_M", "exit", "completed", "wrapped", "instructions", "cycles", "ipc", "ipc_printed",
                "branches", "mispredictions", "mpki", "mpki_champsim_def", "mpki_printed", "cond_branches", "cond_mispredictions",
                "cond_mpki", "accuracy_all", "accuracy_cond", "acc_printed", "sim_instr_champsim", "warmup_instr",
                "banner_storage_bits", "predictor_banner", "bin_sha16", "wall_s", "path"]
        w = csv.DictWriter(f, cols, extrasaction="ignore"); w.writeheader()
        for k in sorted(runs):
            w.writerow(runs[k])
    with open(os.path.join(OUT, "summary.csv"), "w", newline="") as f:
        cols = ["predictor"] + list(next(iter(S.values())))
        w = csv.DictWriter(f, cols); w.writeheader()
        for p in preds:
            w.writerow({"predictor": p, **S[p]})
    for name, rows in (("relative.csv", rel), ("harness_vs_champsim.csv", hvc), ("ablation.csv", abl)):
        with open(os.path.join(OUT, name), "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, "checks.txt"), "w") as f:
        for s, n, d in checks:
            f.write(f"{s}\t{n}\t{d}\n")
    json.dump({"summary": S, "relative": rel, "ablation": abl, "checks": checks}, open(os.path.join(OUT, "audit.json"), "w"), indent=1)

    nf = sum(1 for c in checks if c[0] == "FAIL")
    print(f"{len(runs)} runs parsed; {len(checks)} checks; {nf} FAIL; {sum(1 for c in checks if c[0]=='NOTE')} NOTE")
    for c in checks:
        if c[0] != "PASS":
            print("  ", *c)
    print(f"\n{'predictor':18s} {'meanMPKI':>9s} {'(CS def)':>9s} {'gm/bimodal':>10s} {'gm/hp':>8s} {'gm/tsl':>8s} {'meanIPC':>8s} {'accAll':>7s} {'accCond':>7s}")
    for p in preds:
        s = S[p]
        print(f"{p:18s} {s['mean_mpki']:9.5f} {s['mean_mpki_champsim_def']:9.5f} {s['gm_speedup_vs_bimodal']:10.6f} "
              f"{s['gm_speedup_vs_hashed_perceptron']:8.6f} {s['gm_speedup_vs_tsl_base']:8.6f} {s['mean_ipc']:8.5f} "
              f"{s['pooled_accuracy_all']:7.3f} {s['pooled_accuracy_cond']:7.3f}")
    print()
    for r in rel:
        print(f"proposed vs {r['proposed_vs']:18s} MPKI {r['baseline_mean_mpki']:.5f} -> {r['proposed_mean_mpki']:.5f} "
              f"abs {r['abs_mpki_reduction']:.5f} ({r['pct_mpki_reduction']:.3f}%)  IPC {r['ipc_improvement_pct']:+.4f}%  "
              f"MPKI lower/higher on {r['traces_lower_mpki']}/{r['traces_higher_mpki']} traces, IPC higher/lower on {r['traces_higher_ipc']}/{r['traces_lower_ipc']}")


if __name__ == "__main__":
    main()
