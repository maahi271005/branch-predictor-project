#!/usr/bin/env python3
"""Noise-floor estimate: rerun predictor configurations with different pseudo-random seeds.

  python3 final_deliverables/scripts/seed_sensitivity.py [-j N]

The TAGE-SC-L family uses a fixed-seed xorshift generator for probabilistic allocation decisions.
Changing only the seed gives statistically equivalent predictors; the spread of their mean MPKI is
the run-to-run noise against which small differences between configurations must be judged.

The predictor source is NOT modified: a copy of branch/tagescl.bpred with a different seed literal
is written to build/seed_copies/ and compiled into the functional replay harness. Runs use the
reported window (50M warmup + 200M measured, build/branchstreams/). Seed 0 means the original seed.
Output: final_deliverables/audit/seed_sensitivity.csv
"""
import argparse, csv, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "champsim", "branch", "tagescl.bpred")
ORIG_SEED = "0x2545F4914F6CDD1DULL"
SEEDS = {0: ORIG_SEED, 1: "0x9E3779B97F4A7C15ULL", 2: "0xD1B54A32D192ED03ULL", 3: "0x8CB92BA72F3D8DD7ULL"}
CONFIGS = {
    "proposed": "-DTSL_IMHIST -DTSL_BHIST",
    "tsl_imli": "",
    "tsl_base": "-DTSL_NO_IMLI",
    "no_imhist": "-DTSL_BHIST",
    "no_bhist": "-DTSL_IMHIST",
    "no_loop": "-DTSL_IMHIST -DTSL_BHIST -DTSL_NO_LOOP",
}
TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]


def build(cfg, seed):
    d = os.path.join(ROOT, "build", "seed_copies"); os.makedirs(d, exist_ok=True)
    src = open(SRC).read()
    assert src.count(ORIG_SEED) == 1
    copy = os.path.join(d, f"tagescl_seed{seed}.bpred")
    open(copy, "w").write(src.replace(ORIG_SEED, SEEDS[seed]))
    exe = os.path.join(d, f"rp_{cfg}_seed{seed}")
    subprocess.check_call(f"g++ -O3 -std=c++11 -I{ROOT}/experiments/harness/shim {CONFIGS[cfg]} -x c++ {copy} "
                          f"-x c++ {ROOT}/experiments/harness/replay.cc -o {exe}", shell=True)
    return exe


def run(job):
    cfg, seed, exe, t = job
    out = subprocess.check_output([exe, "50", "200", os.path.join(ROOT, "build", "branchstreams", t + ".br")], text=True)
    line = [l for l in out.splitlines() if l.startswith(t)][0]
    return cfg, seed, t, float(re.search(r" mpki=(\S+)", line).group(1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("-j", type=int, default=16); a = ap.parse_args()
    jobs = []
    for cfg in CONFIGS:
        for seed in SEEDS:
            exe = build(cfg, seed)
            jobs += [(cfg, seed, exe, t) for t in TRACES]
    with ThreadPoolExecutor(a.j) as ex:
        res = list(ex.map(run, jobs))
    rows = {}
    for cfg, seed, t, m in res:
        rows.setdefault((cfg, seed), {})[t] = m
    out = os.path.join(ROOT, "final_deliverables", "audit", "seed_sensitivity.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["config", "seed", "mean_mpki"] + TRACES)
        for (cfg, seed), v in sorted(rows.items()):
            w.writerow([cfg, seed, sum(v.values()) / 10] + [v[t] for t in TRACES])
    for cfg in CONFIGS:
        ms = [sum(rows[cfg, s].values()) / 10 for s in SEEDS]
        mean = sum(ms) / len(ms)
        print(f"{cfg:10s} seeds: " + " ".join(f"{m:.5f}" for m in ms) + f"  mean {mean:.5f}  range {max(ms)-min(ms):.5f} ({100*(max(ms)-min(ms))/mean:.3f}%)")


if __name__ == "__main__":
    main()
