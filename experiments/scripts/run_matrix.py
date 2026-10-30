#!/usr/bin/env python3
"""Run a (binary x trace) matrix of ChampSim simulations in parallel.

Resumable: a run is skipped when its output file already exists and contains
"ChampSim completed" and was produced with the same binary hash / settings
(recorded in the output header). Failed or partial outputs are re-run.

Example:
  run_matrix.py --stage B_baseline --bins bimodal,gshare --warm 50 --sim 100 -j 14
(warm / sim are in millions of instructions)
"""
import argparse, hashlib, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACE_DIR = os.path.join(ROOT, "champsim", "dpc3_traces")
BIN_DIR = os.path.join(ROOT, "build", "bin")
RES_DIR = os.path.join(ROOT, "experiments", "results")

TRACES = [
    "602.gcc_s-1850B", "605.mcf_s-1152B", "607.cactuBSSN_s-2421B", "619.lbm_s-2676B",
    "620.omnetpp_s-141B", "623.xalancbmk_s-10B", "625.x264_s-12B", "631.deepsjeng_s-928B",
    "638.imagick_s-824B", "657.xz_s-2302B",
]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def header_for(binary, trace, warm, sim, bin_hash):
    return f"# RUN binary={binary} bin_sha={bin_hash} trace={trace} warm={warm}M sim={sim}M\n"


def run_one(job):
    binary, trace, warm, sim, out, bin_hash = job
    hdr = header_for(binary, trace, warm, sim, bin_hash)
    if os.path.exists(out):
        with open(out) as f:
            txt = f.read()
        if txt.startswith(hdr) and "ChampSim completed" in txt:
            return (binary, trace, "skipped", 0.0)
    cmd = [os.path.join(BIN_DIR, binary),
           "-warmup_instructions", str(warm * 1000000),
           "-simulation_instructions", str(sim * 1000000),
           "-traces", os.path.join(TRACE_DIR, trace + ".champsimtrace.xz")]
    t0 = time.time()
    tmp = out + ".partial"
    with open(tmp, "w") as f:
        f.write(hdr)
        f.write("# CMD " + " ".join(cmd) + "\n")
        f.flush()
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
        f.write(f"# EXIT {rc} WALL {time.time()-t0:.1f}s\n")
    os.replace(tmp, out)
    return (binary, trace, "ok" if rc == 0 else f"rc={rc}", time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--bins", required=True, help="comma-separated binary names in build/bin")
    ap.add_argument("--traces", default="all", help="comma-separated trace prefixes or 'all'")
    ap.add_argument("--warm", type=int, required=True, help="warmup, millions of instructions")
    ap.add_argument("--sim", type=int, required=True, help="simulation, millions of instructions")
    ap.add_argument("-j", type=int, default=12)
    a = ap.parse_args()

    traces = TRACES if a.traces == "all" else [t for t in TRACES if any(t.startswith(p) for p in a.traces.split(","))]
    jobs = []
    for b in a.bins.split(","):
        bp = os.path.join(BIN_DIR, b)
        if not os.path.exists(bp):
            sys.exit(f"missing binary {bp}")
        h = sha(bp)
        d = os.path.join(RES_DIR, a.stage, b)
        os.makedirs(d, exist_ok=True)
        for t in traces:
            jobs.append((b, t, a.warm, a.sim, os.path.join(d, t + ".txt"), h))
    # longest-running traces first would be ideal; interleave binaries per trace
    jobs.sort(key=lambda j: (traces.index(j[1]), j[0]))
    print(f"{len(jobs)} runs, stage={a.stage}, warm={a.warm}M sim={a.sim}M, j={a.j}", flush=True)
    with ThreadPoolExecutor(a.j) as ex:
        for b, t, st, dt in ex.map(run_one, jobs):
            print(f"{st:8s} {dt:7.1f}s  {b:35s} {t}", flush=True)


if __name__ == "__main__":
    main()
