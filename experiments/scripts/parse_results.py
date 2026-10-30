#!/usr/bin/env python3
"""Parse ChampSim outputs of a stage into a per-run CSV.

  parse_results.py <stage> [--out file.csv]

Metrics (all over the measured region, after warmup):
  ipc            "CPU 0 cumulative IPC" from the final ROI statistics
  accuracy_pct   100 * (branches - mispredictions) / branches, ALL branch types
                 (this is ChampSim's own definition)
  mpki           1000 * mispredictions / measured instructions (ChampSim's own definition)
  cond_*         the same restricted to conditional branches (from BP_TYPE_MISSES)
"""
import argparse, csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES_DIR = os.path.join(ROOT, "experiments", "results")
TYPES = ["NOT_BRANCH", "BRANCH_DIRECT_JUMP", "BRANCH_INDIRECT", "BRANCH_CONDITIONAL",
         "BRANCH_DIRECT_CALL", "BRANCH_INDIRECT_CALL", "BRANCH_RETURN", "BRANCH_OTHER"]


def parse(path):
    txt = open(path).read()
    r = {"complete": "ChampSim completed" in txt}
    m = re.search(r"^# EXIT (\S+) WALL (\S+)s", txt, re.M)
    r["exit"] = m.group(1) if m else "?"
    r["wall_s"] = m.group(2) if m else ""
    m = re.search(r"^# RUN .*warm=(\d+)M sim=(\d+)M", txt, re.M)
    r["warm_M"], r["sim_M"] = (m.group(1), m.group(2)) if m else ("", "")
    roi = txt.split("Region of Interest Statistics")[-1]
    m = re.search(r"CPU 0 cumulative IPC: (\S+) instructions: (\d+) cycles: (\d+)", roi)
    if m:
        r["ipc"], r["instructions"], r["cycles"] = float(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"Branch Prediction Accuracy: (\S+)% MPKI: (\S+)", roi)
    if m:
        r["cs_accuracy_pct"], r["cs_mpki"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"BP_STATS num_branch: (\d+) mispredictions: (\d+) sim_instr: (\d+)", roi)
    if m:
        nb, mp, ni = map(int, m.groups())
        r.update(branches=nb, mispredictions=mp, mpki_instr=ni,
                 accuracy_pct=100.0 * (nb - mp) / nb, mpki=1000.0 * mp / ni)
    counts = {}
    for t in TYPES:
        m = re.search(r"^%s: (\d+)" % t, roi, re.M)
        counts[t] = int(m.group(1)) if m else 0
    m = re.search(r"BP_TYPE_MISSES((?: \d+){8})", roi)
    if m and "mpki_instr" in r:
        miss = list(map(int, m.group(1).split()))
        nc, mc = counts["BRANCH_CONDITIONAL"], miss[3]
        r.update(cond_branches=nc, cond_mispredictions=mc,
                 cond_accuracy_pct=100.0 * (nc - mc) / nc if nc else float("nan"),
                 cond_mpki=1000.0 * mc / r["mpki_instr"],
                 noncond_mispredictions=sum(miss) - mc)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("--out")
    a = ap.parse_args()
    base = os.path.join(RES_DIR, a.stage)
    rows = []
    for b in sorted(os.listdir(base)):
        d = os.path.join(base, b)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".txt"):
                r = parse(os.path.join(d, f))
                r.update(stage=a.stage, predictor=b, trace=f[:-4])
                rows.append(r)
    cols = ["stage", "predictor", "trace", "warm_M", "sim_M", "complete", "exit", "ipc", "accuracy_pct", "mpki",
            "branches", "mispredictions", "cond_accuracy_pct", "cond_mpki", "cond_branches", "cond_mispredictions",
            "noncond_mispredictions", "instructions", "cycles", "mpki_instr", "cs_accuracy_pct", "cs_mpki", "wall_s"]
    out = open(a.out, "w", newline="") if a.out else sys.stdout
    w = csv.DictWriter(out, cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)


if __name__ == "__main__":
    main()
