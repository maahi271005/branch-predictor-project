#!/usr/bin/env python3
"""Reconcile the 50-trace target list with the trace directory and Zenodo.

  reconcile_traces.py --trace-dir DIR [--check LOG] [--download] [-j 4]

Inputs (experiments/traces/):
  target_traces.tsv      trace<TAB>group (original10 / additional40)
  zenodo_10960004.json   Zenodo API record "SPEC CPU 2017 ChampSim Traces"
                         (https://zenodo.org/records/10960004): sizes + md5
  LOG                    output of check_traces.sh (sha256, md5, xz -t)

A local file matches a target if it is named <trace>.champsimtrace.xz or
<trace>.champsimtrace.xz?download=1 (browser-mangled Zenodo download name).
A target is VALID when exactly one matching file passes xz -t and has
Zenodo's size and md5. Files are never renamed or deleted; the runner reaches
them through trace_map.tsv.

--download fetches targets that have no valid local file from Zenodo with
curl (resumable: partial data is kept in <name>.part and continued with -C -),
checks the md5 and only then moves <name>.part to <name>.

Outputs: trace_manifest.csv, trace_map.tsv, missing_traces.txt.
Run under Linux/WSL (uses curl, md5sum names with '?').
"""
import argparse, csv, hashlib, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TDIR = os.path.join(ROOT, "experiments", "traces")
SUFFIX = ".champsimtrace.xz"
ALT = SUFFIX + "?download=1"
ZURL = "https://zenodo.org/records/10960004/files/{}?download=1"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def download(job):
    name, size, want_md5, trace_dir = job
    dst = os.path.join(trace_dir, name)
    part = dst + ".part"
    for attempt in range(5):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have < size:
            # --speed-limit/--speed-time abort a stalled transfer (e.g. after a network
            # outage) so that the next attempt resumes it instead of hanging forever.
            subprocess.call(["curl", "-sS", "-L", "--retry", "5", "--retry-delay", "10",
                             "--speed-limit", "1024", "--speed-time", "60",
                             "-C", "-", "-o", part, ZURL.format(name)])
        if os.path.exists(part) and os.path.getsize(part) == size:
            if md5(part) == want_md5:
                os.replace(part, dst)
                return name, "downloaded"
            os.rename(part, part + ".badmd5")  # keep for inspection, restart cleanly
    return name, "FAILED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-dir", required=True)
    ap.add_argument("--check", help="check_traces.sh output")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("-j", type=int, default=4)
    a = ap.parse_args()

    targets = list(csv.DictReader(open(os.path.join(TDIR, "target_traces.tsv")), delimiter="\t"))
    assert len({t["trace"] for t in targets}) == len(targets), "duplicate trace in target list"
    zen = {f["key"]: (f["size"], f["checksum"].split(":", 1)[1])
           for f in json.load(open(os.path.join(TDIR, "zenodo_10960004.json")))["files"]}
    chk = {}
    if a.check:
        for line in open(a.check):
            p = line.rstrip("\n").split("|")
            chk[p[0]] = dict(size=int(p[1]), sha256=p[2], md5=p[3], xz_index=p[4],
                             uncompressed=p[5], xz_test=p[6])
    local = set(os.listdir(a.trace_dir))

    if a.download:
        jobs = []
        for t in targets:
            name = t["trace"] + SUFFIX
            if name not in zen:
                continue
            size, m = zen[name]
            ok = [f for f in (name, t["trace"] + ALT)
                  if f in local and os.path.getsize(os.path.join(a.trace_dir, f)) == size]
            if not ok:
                jobs.append((name, size, m, a.trace_dir))
        print(f"downloading {len(jobs)} files, {sum(j[1] for j in jobs)/1e9:.2f} GB", flush=True)
        with ThreadPoolExecutor(a.j) as ex:
            for name, st in ex.map(download, jobs):
                print(f"{st:10s} {name}", flush=True)
        return

    rows, tmap, missing = [], [], []
    for t in targets:
        name = t["trace"] + SUFFIX
        zsize, zmd5 = zen.get(name, (None, None))
        cands = [f for f in (name, t["trace"] + ALT) if f in local]
        good, notes = [], []
        for f in cands:
            c = chk.get(f)
            if c is None:
                notes.append(f"{f}: not in check log")
                continue
            reasons = []
            if c["xz_test"] != "OK":
                reasons.append("xz -t failed")
            if zsize is not None and c["size"] != zsize:
                reasons.append(f"size {c['size']} != zenodo {zsize}")
            if zmd5 is not None and c["md5"] != zmd5:
                reasons.append("md5 != zenodo")
            if reasons:
                notes.append(f"{f}: excluded ({'; '.join(reasons)})")
            else:
                good.append(f)
        if len(good) > 1:
            notes.append(f"duplicate copies {good}; using {good[0]}")
        use = good[0] if good else ""
        c = chk.get(use, {})
        unc = int(c["uncompressed"]) if c.get("uncompressed") else 0
        status = "VALID" if use else ("NOT_ON_ZENODO" if zsize is None else
                                       ("INVALID" if cands else "MISSING"))
        rows.append(dict(trace=t["trace"], group=t["group"], status=status, local_file=use,
                         size_bytes=c.get("size", ""), sha256=c.get("sha256", ""), md5=c.get("md5", ""),
                         zenodo_size=zsize or "", zenodo_md5=zmd5 or "",
                         xz_test=c.get("xz_test", ""), instructions=unc // 64 if unc else "",
                         notes=" | ".join(notes)))
        if use:
            p = os.path.abspath(os.path.join(a.trace_dir, use))
            if p.startswith(ROOT + os.sep):  # keep the map machine-independent
                p = os.path.relpath(p, ROOT)
            tmap.append((t["trace"], p))
        else:
            missing.append(f"{t['trace']}\t{t['group']}\t{status}")

    with open(os.path.join(TDIR, "trace_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(TDIR, "trace_map.tsv"), "w") as f:
        f.write("trace\tpath\n")
        for n, p in tmap:
            f.write(f"{n}\t{p}\n")
    with open(os.path.join(TDIR, "missing_traces.txt"), "w") as f:
        f.write("".join(m + "\n" for m in missing))

    extra = sorted(f for f in local if f.endswith((SUFFIX, ALT)) and
                   f.replace("?download=1", "")[:-len(SUFFIX)] not in {t["trace"] for t in targets})
    for g in ("original10", "additional40"):
        n = [r for r in rows if r["group"] == g]
        print(f"{g:13s} valid {sum(r['status'] == 'VALID' for r in n)}/{len(n)}")
    print(f"total valid unique: {len(tmap)}/{len(targets)}")
    for r in rows:
        if r["status"] != "VALID" or r["notes"]:
            print(f"  {r['status']:13s} {r['trace']:24s} {r['notes']}")
    if extra:
        print("local trace files not in the target list:", extra)


if __name__ == "__main__":
    main()
