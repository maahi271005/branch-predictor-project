#!/usr/bin/env python3
"""Verify the 50-trace report against the result CSVs.

  build/venv/Scripts/python experiments/scripts/verify_report_50trace.py [--pdf report_50trace/TFL-TAGE-SC-L_50trace_Report.pdf]

1. Recomputes the headline values directly from raw_results.csv (not from summary.csv) and
   compares them with the values the report prints (report_50trace/generated/values.json).
2. Checks that every \\val{key} used in the LaTeX sources is defined.
3. Checks the PDF (PyMuPDF): opens, page count, every required section heading present,
   the trace count stated, figures embedded, no aggregate value of the earlier 10-trace report
   appearing in the main text (before the section on the earlier study).
4. Checks every figure file exists and is non-empty.
Writes results_50trace/report_verification.txt; exit status 1 on any failure.
"""
import argparse, csv, glob, json, math, os, re, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREDS = ["bimodal", "gshare", "perceptron", "hashed_perceptron", "tage", "tsl_base", "tsl_proposed"]
KEY = {"bimodal": "bim", "gshare": "gsh", "perceptron": "perc", "hashed_perceptron": "hp",
       "tage": "tage", "tsl_base": "tsl", "tsl_proposed": "prop"}
# Aggregate values of the earlier 10-trace report (archive/10trace_study) that must not reappear
# as results in the new main text.
OLD_AGGREGATES = ["9.884", "6.153", "5.384", "3.247", "3.295", "3.293", "3.072", "3.065", "3.046",
                  "+10.078", "+0.433", "+0.058", "6.22%", "0.85%", "69.19%", "97.932", "97.795"]
SECTIONS = ["Abstract", "Introduction and objective", "Background and related work", "Predictor implementation",
            "Experimental methodology", "Hardware and storage accounting", "Benchmark trace description",
            "Results", "Discussion", "Relation to the earlier 10-trace study", "Limitations",
            "Conclusion and future work", "References", "Trace manifest"]


def gmean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default=os.path.join(ROOT, "results_50trace"))
    ap.add_argument("--rep", default=os.path.join(ROOT, "report_50trace"))
    ap.add_argument("--pdf", default=None)
    a = ap.parse_args()
    pdf = a.pdf or os.path.join(a.rep, "TFL-TAGE-SC-L_50trace_Report.pdf")
    out, fails = [], 0

    def check(name, ok, detail=""):
        nonlocal fails
        out.append(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
        fails += not ok

    V = json.load(open(os.path.join(a.rep, "generated", "values.json")))
    raw = list(csv.DictReader(open(os.path.join(a.res, "raw_results.csv"))))
    ok = [r for r in raw if r["status"] == "ok"]
    traces = sorted({r["trace"] for r in raw})
    full = [t for t in traces if all(any(r["trace"] == t and r["predictor"] == p and r["status"] == "ok" for r in raw) for p in PREDS)]
    check("raw_results.csv has 350 rows", len(raw) == 350, str(len(raw)))
    check("report run counts", V["n_runs"] == str(len(raw)) and V["n_runs_ok"] == str(len(ok)),
          f"report {V['n_runs_ok']}/{V['n_runs']}, csv {len(ok)}/{len(raw)}")
    check("report trace counts", V["n_traces"] == str(len(traces)) and V["n_traces_agg"] == str(len(full)),
          f"report {V['n_traces']} / {V['n_traces_agg']}")

    R = {(r["predictor"], r["trace"]): r for r in ok}

    def ipc(p, t):
        return int(R[p, t]["instructions"]) / int(R[p, t]["cycles"])

    def mpki(p, t):
        return 1000.0 * int(R[p, t]["mispredictions"]) / int(R[p, t]["instructions"])

    for p in PREDS:
        k = KEY[p]
        m_ipc = statistics.fmean(ipc(p, t) for t in full)
        g_ipc = gmean([ipc(p, t) for t in full])
        m_mp = statistics.fmean(mpki(p, t) for t in full)
        nb = sum(int(R[p, t]["branches"]) for t in full); nm = sum(int(R[p, t]["mispredictions"]) for t in full)
        acc = 100.0 * (nb - nm) / nb
        sp = 100 * (gmean([ipc(p, t) / ipc("bimodal", t) for t in full]) - 1)
        for name, val, nd, sign in (("mean_ipc", m_ipc, 4, False), ("gm_ipc", g_ipc, 4, False), ("mpki", m_mp, 3, False),
                                    ("acc", acc, 3, False), ("speedup_bim", sp, 2, True)):
            want = f"{val:+.{nd}f}" if sign else f"{val:,.{nd}f}"
            check(f"{k}_{name} = {want}", V[f"{k}_{name}"] == want, f"report {V[f'{k}_{name}']}")
        if p != "tsl_proposed":
            red = 100 * (1 - statistics.fmean(mpki("tsl_proposed", t) for t in full) / m_mp)
            imp = 100 * (gmean([ipc("tsl_proposed", t) / ipc(p, t) for t in full]) - 1)
            wins = sum(int(R["tsl_proposed", t]["mispredictions"]) < int(R[p, t]["mispredictions"]) for t in full)
            iwins = sum(int(R["tsl_proposed", t]["cycles"]) < int(R[p, t]["cycles"]) for t in full)
            check(f"vs_{k}: MPKI reduction {red:.2f}%, IPC {imp:+.3f}%, MPKI wins {wins}, IPC wins {iwins}",
                  V[f"vs_{k}_pct_mpki"] == f"{red:,.2f}" and V[f"vs_{k}_ipc"] == f"{imp:+.3f}"
                  and V[f"vs_{k}_mpki_win"] == str(wins) and V[f"vs_{k}_ipc_win"] == str(iwins),
                  f"report {V[f'vs_{k}_pct_mpki']}%, {V[f'vs_{k}_ipc']}%, {V[f'vs_{k}_mpki_win']}, {V[f'vs_{k}_ipc_win']}")

    # every \val used in the sources is defined
    used = set()
    for fn in [os.path.join(a.rep, "main.tex")] + glob.glob(os.path.join(a.rep, "sections", "*.tex")):
        src = re.sub(r"(?<!\\)%.*", "", open(fn, encoding="utf-8").read())   # drop comments
        used |= set(re.findall(r"\\val\{([^}]+)\}", src))
    missing = sorted(used - set(V))
    check(f"all {len(used)} \\val keys used in the LaTeX sources are defined", not missing, ", ".join(missing))
    placeholders = [fn for fn in glob.glob(os.path.join(a.rep, "sections", "*.tex"))
                    if "RESULTS-TEXT" in open(fn, encoding="utf-8").read()]
    check("no unfinished RESULTS-TEXT placeholders", not placeholders, ", ".join(map(os.path.basename, placeholders)))

    # figures
    figs = sorted(glob.glob(os.path.join(a.res, "figures", "*.png")))
    check("10 figures (PNG) generated", len(figs) == 10, str(len(figs)))
    for fpath in figs + sorted(glob.glob(os.path.join(a.rep, "figures", "*.pdf"))):
        check(f"figure non-empty: {os.path.relpath(fpath, ROOT)}", os.path.getsize(fpath) > 5000, str(os.path.getsize(fpath)))
    tex = open(os.path.join(a.rep, "main.tex"), encoding="utf-8").read()
    for fn in re.findall(r"figures/(fig[^}]+\.pdf)", tex):
        check(f"figure referenced by main.tex exists: {fn}", os.path.exists(os.path.join(a.rep, "figures", fn)))

    # PDF
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    if not os.path.exists(pdf):
        check("PDF exists", False, pdf)
    else:
        doc = pymupdf.open(pdf)
        text = "\n".join(pg.get_text() for pg in doc)
        check("PDF opens", doc.page_count > 0, f"{doc.page_count} pages")
        flat = re.sub(r"\s+", " ", text)
        for s in SECTIONS:
            check(f"PDF contains section '{s}'", s in flat)
        check(f"PDF states {V['n_traces']} traces", f"{V['n_traces']} SPEC CPU2017 traces" in flat or f"{V['n_traces']} traces" in flat)
        imgs = sum(len(pg.get_images()) + len(pg.get_drawings()) > 0 for pg in doc)
        check("PDF pages with embedded graphics", imgs >= 10, str(imgs))
        cut = flat.find("Relation to the earlier 10-trace study", flat.find("Discussion") + 1)
        main_text = flat[:cut] if cut > 0 else flat
        new_vals = set(V.values())
        hits = [o for o in OLD_AGGREGATES if o in main_text and o.lstrip("+").rstrip("%") not in
                {v.lstrip("+") for v in new_vals}]
        check("no old 10-trace aggregate values in the main text", not hits, ", ".join(hits))
        check("PDF has no unresolved references ('??')", "??" not in flat)

    out.append(f"\n{len(out)} checks, {fails} failed")
    open(os.path.join(a.res, "report_verification.txt"), "w").write("\n".join(out) + "\n")
    print("\n".join(l for l in out if l.startswith("FAIL")) or "all checks passed")
    print(out[-1].strip())
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
