# Final deliverables (audited)

This directory contains the audited and corrected deliverables of the branch-predictor project
(TFL-TAGE-SC-L). The original deliverables in `submission/` and all experiment data in
`experiments/results/` were **not modified**; everything here is regenerated from the raw
simulator outputs by the scripts in `scripts/`.

## Contents

| File | What it is |
|---|---|
| `TFL-TAGE-SC-L_Final_Report.docx` (+ `.md`) | Revised technical report (15 sections incl. "Design Trade-offs and Motivation"); all numbers generated from the audit data |
| `TFL-TAGE-SC-L_Results.xlsx` | Corrected results workbook: summary, proposed-vs-baseline comparisons, per-trace IPC/MPKI/accuracy/mispredictions, raw counters with file paths, storage (with breakdown and assumptions), ablation (harness), harness-vs-ChampSim, noise floor, graphs |
| `figures/fig1…fig7_*.png` | Corrected figures (overall summary, MPKI per trace, IPC vs bimodal, MPKI-reduction vs IPC-gain, accuracy, ablation, storage vs MPKI) |
| `Branch_Predictor_Viva_Notes.docx` (+ `.md`) | Concise answers to 18 viva questions, using verified figures only |
| `Final_Audit_and_Corrections.docx` (+ `.md`) | Every issue found, original vs corrected value, evidence and status; final verification table |
| `audit/` | Machine-readable audit data: `per_run.csv`, `summary.csv`, `relative.csv`, `storage.csv`, `ablation.csv`, `harness_vs_champsim.csv`, `seed_sensitivity.csv`, `checks.txt` (all 1,258 consistency checks), `audit.json` |
| `scripts/` | The scripts that produce all of the above (see below) |

## Data provenance

| Result | Source | Kind |
|---|---|---|
| IPC, MPKI, accuracy of all 11 configurations | `experiments/results/B_baseline_50M_200M/`, `G_final_50M_200M/` (110 raw ChampSim outputs) | ChampSim timing simulation |
| IPC noise check (alternative RNG seed) | `experiments/results/AUDIT_seed1_50M_200M/` (20 runs, created by this audit) | ChampSim timing simulation |
| Ablation, exploration | `experiments/results/harness/{main,tune}/` | functional replay harness (MPKI only) |
| MPKI noise floor | `audit/seed_sensitivity.csv` (created by this audit) | functional replay harness |

Window for every ChampSim run: 50M warm-up + 200M measured instructions (instructions 0–250M) of each of the 10
DPC-3 SPEC CPU2017 traces; ChampSim 2021, 1 core, no prefetchers, LRU LLC.

## Reproducing the analysis

From the project root (`/home/maahi/BRANCH_PREDICTOR_PROJECT`):

```
python3 final_deliverables/scripts/recompute_metrics.py          # independent re-parse + checks -> audit/
python3 final_deliverables/scripts/seed_sensitivity.py -j 16     # noise floor (harness; ~10 min; needs build/branchstreams)
build/venv/bin/python final_deliverables/scripts/build_results.py    # figures + workbook + audit/storage.csv
build/venv/bin/python final_deliverables/scripts/make_final_docs.py  # report, viva notes, audit log (.docx + .md)
```

`recompute_metrics.py` uses only the Python standard library and its own parser (it does not reuse the original
`experiments/scripts/parse_results.py`), so it is an independent check of the original pipeline. The other scripts
need the project's virtual environment (`build/venv`, with matplotlib 3.9.2, openpyxl 3.1.5, python-docx 1.1.2).

The ChampSim seed check was run with the project's existing runner:
```
# binaries built from build/seed_copies/tagescl_seed1.bpred (a copy of branch/tagescl.bpred differing only in the RNG seed)
python3 experiments/scripts/run_matrix.py --stage AUDIT_seed1_50M_200M --bins audit_prop_seed1,audit_tsl_seed1 --warm 50 --sim 200 -j 18
```

## What was changed and what was not

- No predictor, simulator or experiment-configuration file was modified by the audit.
- New files only: everything in `final_deliverables/`, the seed copies and seed binaries in `build/`
  (`build/seed_copies/`, `build/bin/audit_*`), and the run directory `experiments/results/AUDIT_seed1_50M_200M/`.
- See `Final_Audit_and_Corrections.md` for the list of corrections and remaining unresolved items.
