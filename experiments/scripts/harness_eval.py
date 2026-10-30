#!/usr/bin/env python3
"""Functional (MPKI-only) evaluation of predictor variants with the replay harness.

  harness_eval.py --region main|tune NAME[=FLAGS] ... [-j N]

Each NAME is built from branch/<predictor>.bpred (default tagescl) with the
given -D flags, e.g.  tage="-DTSL_NO_SC -DTSL_NO_LOOP"  or  hashed_perceptron@hashed_perceptron
(NAME@PREDICTOR selects another .bpred).  Results are cached in
experiments/results/harness/<region>/<NAME>.txt together with the flags and
the predictor source hash; a cached result is reused only if both match.

Regions (instruction windows of each trace, in millions):
  main : 50M warmup + 200M measured, instructions 0-250M   (the reported window)
  tune : 50M warmup + 100M measured, instructions 1000M-1150M (parameter tuning)
"""
import argparse, hashlib, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CS = os.path.join(ROOT, "champsim")
HB = os.path.join(ROOT, "build", "harness")
REGIONS = {"main": ("branchstreams", 50, 200), "tune": ("branchstreams_tune", 50, 100)}
TRACES = ["602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
          "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
          "638.imagick_s-824B", "657.xz_s-2302B"]
INT = {"602", "605", "620", "623", "625", "631", "657"}


def build(name, bp, flags):
    src = os.path.join(CS, "branch", bp + ".bpred")
    key = hashlib.sha256((open(src).read() + open(os.path.join(ROOT, "experiments/harness/replay.cc")).read()
                          + flags).encode()).hexdigest()[:16]
    exe = os.path.join(HB, f"rp_{name}")
    stamp = exe + ".key"
    if not (os.path.exists(exe) and os.path.exists(stamp) and open(stamp).read() == key):
        cmd = (f"g++ -O3 -std=c++11 -I{ROOT}/experiments/harness/shim {flags} -x c++ {src} "
               f"-x c++ {ROOT}/experiments/harness/replay.cc -o {exe}")
        subprocess.check_call(cmd, shell=True)
        open(stamp, "w").write(key)
    return exe, key


def run(exe, region, trace):
    d, w, s = REGIONS[region]
    out = subprocess.check_output([exe, str(w), str(s), os.path.join(ROOT, "build", d, trace + ".br")], text=True)
    return [l for l in out.splitlines() if l.startswith(trace)][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="tune", choices=REGIONS)
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("variants", nargs="+")
    a = ap.parse_args()
    resdir = os.path.join(ROOT, "experiments", "results", "harness", a.region)
    os.makedirs(resdir, exist_ok=True)

    table = {}
    for v in a.variants:
        name, _, flags = v.partition("=")
        name, _, bp = name.partition("@")
        bp = bp or "tagescl"
        exe, key = build(name, bp, flags)
        path = os.path.join(resdir, name + ".txt")
        hdr = f"# predictor={bp} flags={flags} key={key}\n"
        if os.path.exists(path) and open(path).read().startswith(hdr):
            lines = open(path).read().splitlines()[1:]
        else:
            with ThreadPoolExecutor(a.j) as ex:
                lines = list(ex.map(lambda t: run(exe, a.region, t), TRACES))
            open(path, "w").write(hdr + "\n".join(lines) + "\n")
        table[name] = {l.split(".br")[0]: float(re.search(r" mpki=(\S+)", l).group(1)) for l in lines}

    names = list(table)
    print(f"region={a.region}  MPKI (all branch types)")
    print(f"{'trace':24s}" + "".join(f"{n[:16]:>17s}" for n in names))
    for t in TRACES:
        print(f"{t:24s}" + "".join(f"{table[n][t]:17.4f}" for n in names))
    for label, sel in (("mean(10)", TRACES), ("mean(int7)", [t for t in TRACES if t[:3] in INT])):
        print(f"{label:24s}" + "".join(f"{sum(table[n][t] for t in sel) / len(sel):17.4f}" for n in names))
    if len(names) > 1:
        ref = sum(table[names[0]].values()) / len(TRACES)
        print(f"{'vs first (mean10)':24s}" + "".join(
            f"{100 * (sum(table[n].values()) / len(TRACES) - ref) / ref:16.2f}%" for n in names))


if __name__ == "__main__":
    main()
