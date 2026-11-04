# TFL-TAGE-SC-L: a target-free loop-aware branch predictor for ChampSim

TFL-TAGE-SC-L is a 62 KB TAGE-SC-L branch predictor for the 2021 version of the
[ChampSim](https://github.com/ChampSim/ChampSim) simulator. Its statistical corrector
also uses loop-structure history: IMLI-SIC, IMHIST and a backward-branch history.

These features normally require the branch target, because they must know whether a
branch jumps backward, and ChampSim's predictor interface does not provide it:

```c++
uint8_t predict_branch(uint64_t ip);
void    last_branch_result(uint64_t ip, uint8_t taken);
```

The predictor infers the direction instead. ChampSim delivers branches in program order
and fetches no wrong path, so a taken branch `B` is backward exactly when the **next
branch's PC is ≤ PC(B)**. A small per-branch table remembers the result for the
not-taken (loop-exit) instances. Measured against ChampSim's real targets, the inference
agrees on 99.9996–100 % of instances in every trace tested.
The full argument is in [research/design_rationale.md](research/design_rationale.md).

## Results at a glance

Seven predictors were run on 50 SPEC CPU2017 traces: the 10 traces used during design plus
40 traces that were never used for tuning. Each run had 50M warm-up and 200M measured
instructions, for 350 runs in total, and all 350 succeeded.

| Predictor | Storage (KB) | Geomean IPC | Speedup vs bimodal | Mean MPKI | Accuracy |
|---|---:|---:|---:|---:|---:|
| Bimodal | 4.00 | 0.7797 | +0.00 % | 9.334 | 93.089 % |
| Gshare | 4.00 | 0.8330 | +6.84 % | 4.619 | 96.580 % |
| Perceptron | 3.98 | 0.8508 | +9.13 % | 3.700 | 97.260 % |
| Hashed perceptron | 64.03 | 0.8845 | +13.45 % | 1.922 | 98.577 % |
| TAGE | 46.84 | 0.8877 | +13.86 % | 1.805 | 98.663 % |
| TAGE-SC-L | 58.14 | 0.8909 | +14.27 % | 1.663 | 98.769 % |
| **TFL-TAGE-SC-L (proposed)** | **62.09** | **0.8914** | **+14.33 %** | **1.628** | **98.795 %** |

The first four are ChampSim's own predictors. TAGE and TAGE-SC-L were re-implemented
for this project and are the proposed design with components switched off.

- **Against the 64 KB hashed perceptron:** 15.3 % lower MPKI and +0.77 % geomean IPC,
  with fewer mispredictions on 46 of 50 traces.
- **Against the same TAGE-SC-L without the loop-structure features:** 2.1 % lower MPKI and
  +0.05 % IPC. The gain is small but holds on the 40 traces that were never used for
  tuning (2.8 % lower MPKI there).

Further material:

- Full report: [TFL-TAGE-SC-L_50trace_Report.pdf](TFL-TAGE-SC-L_50trace_Report.pdf)
- Per-trace numbers and figures: [results_50trace/RESULTS.md](results_50trace/RESULTS.md)
- Everything in one workbook: [results_50trace/TFL-TAGE-SC-L_50trace_Results.xlsx](results_50trace/TFL-TAGE-SC-L_50trace_Results.xlsx)

## Repository layout

```
champsim/                      ChampSim (2021) with the project's predictors
  branch/tagescl.bpred           the predictor source (TAGE + SC + loop + target-free IMLI)
  branch/tfl_tage_scl.bpred      proposed configuration   (tagescl + TSL_IMHIST + TSL_BHIST)
  branch/tage_scl.bpred          TAGE-SC-L baseline       (tagescl + TSL_NO_IMLI)
  branch/tage.bpred              TAGE baseline            (tagescl + TSL_NO_SC + TSL_NO_LOOP)
  inc/, src/                     core with stats-only additions (exact per-type branch counters)
experiments/
  scripts/                       build, run, trace-check and analysis scripts
  harness/                       fast functional (MPKI-only) replay harness + IMLI verifier
  traces/                        trace list, checksums, Zenodo metadata, trace map
  results/                       raw ChampSim and harness output of every run
results_50trace/                 processed results: CSVs, figures, workbook, consistency checks
report_50trace/                  LaTeX source of the report (numbers generated from the CSVs)
research/                        literature review, candidate comparison, design rationale
archive/10trace_study/           earlier 10-trace study: report, audit, workbook, figures
```

The project was first evaluated on the 10 original traces only, and that study also includes
the ablation results. It is kept in [archive/10trace_study/](archive/10trace_study/README.md).
Its raw outputs are in `experiments/results/` (`B_baseline_*`, `G_final_*`, `AUDIT_*`, `harness/`).
The 50-trace runs reproduce its cycle and misprediction counts exactly.

## Requirements

- Linux or WSL2, `bash`, `g++` (C++11; tested with g++ 15.2), `xz`, `make`
- `python3` with the standard library only, for running simulations and the analysis
- Optional, for figures, the workbook and report verification: `matplotlib`, `openpyxl`, `pymupdf`
- Optional, to rebuild the PDF: [tectonic](https://tectonic-typesetting.github.io/)
- About 16 GB of disk space for the 50 traces

## Quick start: one predictor, one trace

```bash
cd champsim
./build_champsim.sh tfl_tage_scl no no no no lru 1     # -> bin/tfl_tage_scl-no-no-no-no-lru-1core

mkdir -p dpc3_traces                                   # put e.g. 657.xz_s-2302B.champsimtrace.xz here
./run_champsim.sh tfl_tage_scl-no-no-no-no-lru-1core 50 200 657.xz_s-2302B.champsimtrace.xz
# output: results_200M/657.xz_s-2302B.champsimtrace.xz-tfl_tage_scl-no-no-no-no-lru-1core.txt
```

Replace `tfl_tage_scl` with `tage_scl`, `tage`, `hashed_perceptron`, `perceptron`, `gshare` or
`bimodal` to build any of the other predictors.

## Getting the traces

The traces are the *SPEC CPU 2017 ChampSim Traces* on Zenodo
([record 10960004](https://zenodo.org/records/10960004), CC-BY-4.0). The 50 traces used are listed in
[experiments/traces/target_traces.tsv](experiments/traces/target_traces.tsv), and their sizes and
checksums are in [experiments/traces/trace_manifest.csv](experiments/traces/trace_manifest.csv).

The scripts expect the traces in `champsim/dpc3_traces/`. The committed
[trace map](experiments/traces/trace_map.tsv) points there with paths relative to the
repository root.

```bash
mkdir -p champsim/dpc3_traces
# download any missing traces from Zenodo (resumable, md5-checked), then verify all of them
python3 experiments/scripts/reconcile_traces.py --trace-dir champsim/dpc3_traces --download
experiments/scripts/check_traces.sh champsim/dpc3_traces experiments/traces/trace_integrity.txt
python3 experiments/scripts/reconcile_traces.py --trace-dir champsim/dpc3_traces \
        --check experiments/traces/trace_integrity.txt    # rewrites trace_manifest.csv and trace_map.tsv
```

If your traces are stored somewhere else, point `--trace-dir` at that folder, or edit the
paths in `trace_map.tsv`. Absolute paths work, and relative paths are read from the repository root.

## Reproducing the full evaluation

```bash
# 1. build the seven binaries into build/bin (out-of-tree; champsim/bin is not touched)
bash experiments/scripts/build_all_50trace.sh

# 2. run 7 predictors x 50 traces, 50M warm-up + 200M measured, 14 in parallel.
#    Resumable: re-running skips completed runs. About 12-13 h on an 8-core / 16-thread CPU.
python3 experiments/scripts/run_matrix.py --stage M50_50M_200M \
        --bins bimodal,gshare,perceptron,hashed_perceptron,tage,tsl_base,tsl_proposed \
        --trace-map experiments/traces/trace_map.tsv --warm 50 --sim 200 -j 14

# 3. CSVs -> figures -> report values -> workbook -> PDF -> verification
python3 -m venv build/venv && build/venv/bin/pip install matplotlib openpyxl pymupdf
bash experiments/scripts/finalize_50trace.sh
```

Step 3 writes `results_50trace/` and `report_50trace/`. Every number in the report is
generated from the result CSVs and checked afterwards; see `results_50trace/checks.txt` and
`results_50trace/report_verification.txt`. If you only want the CSVs, run
`python3 experiments/scripts/analyze_50trace.py`, which needs only the standard library.

## Predictor configuration

The predictors are all built from `champsim/branch/tagescl.bpred` and configured with
compile-time switches:

| Flag | Effect |
|---|---|
| `TSL_NO_SC` / `TSL_NO_LOOP` | disable the statistical corrector / loop predictor |
| `TSL_NO_IMLI` | disable every loop-structure (IMLI-derived) SC component |
| `TSL_NO_LOCAL` | disable the local-history SC tables |
| `TSL_IMHIST` | per-IMLI-value outcome history table (IMHIST) |
| `TSL_BHIST` | SC tables indexed by a history of backward branches only |
| `TSL_LOG_TAGE=n`, `TSL_MAXHIST=n`, `TSL_HBITS=n` | table size, longest history, history bits per branch |
| `TSL_THROTTLE`, `TSL_IMLI_MODE`, `TSL_IMLI_GEHL` | explored candidates, not in the final design |

To build a variant out of tree, run
`experiments/scripts/build.sh <name> tagescl -D<FLAG> ...`. The binary goes to `build/bin/<name>`.

## Fast MPKI exploration (functional harness)

The design was explored without the ~20 min ChampSim run per trace. The harness extracts
each trace's branch stream once, then replays it through the unmodified `.bpred` file. Its
results match ChampSim's misprediction counts to about 0.005 %.

```bash
mkdir -p build/harness build/branchstreams build/branchstreams_tune
g++ -O3 -o build/harness/extract experiments/harness/extract.cc
# reported window (instructions 0-250M) and a separate tuning window (1000M-1150M)
build/harness/extract champsim/dpc3_traces/657.xz_s-2302B.champsimtrace.xz build/branchstreams/657.xz_s-2302B.br 250000000
build/harness/extract champsim/dpc3_traces/657.xz_s-2302B.champsimtrace.xz build/branchstreams_tune/657.xz_s-2302B.br 150000000 1000000000

python3 experiments/scripts/harness_eval.py --region tune \
        tsl_base="-DTSL_NO_IMLI" proposed="-DTSL_IMHIST -DTSL_BHIST"
```

`harness_eval.py` covers the 10 original traces. Do the extraction for each of them first.
`experiments/harness/verify_imli.cc` checks the target-free backward-branch inference
against ChampSim's real branch targets.

## Methodology notes

- **Simulator:** ChampSim 2021, 1 core, no prefetchers, LRU LLC. The core changes only add
  statistics, and IPC was verified to be bit-identical to an unmodified build.
- **Metrics:** IPC is ChampSim's cumulative IPC. MPKI and accuracy count every branch type
  (ChampSim's definition), and conditional-only figures are reported separately.
  Storage is the predictor's own `storage_bits()`.
- **Aggregation:** arithmetic-mean MPKI over traces, and geometric mean of the per-trace
  IPC ratios.
- **No tuning on the reported data:** parameters were tuned on instructions 1000M–1150M and
  on the 10 original traces only. The 40 additional traces were never used during design.

Limitations and the analysis of why IPC moves much less than MPKI are covered in the report.

## Acknowledgements

- ChampSim is distributed under its own license ([champsim/LICENSE](champsim/LICENSE)).
- The TAGE, TAGE-SC-L and IMLI algorithms are by A. Seznec and co-authors. The
  re-implementation follows the published papers cited in the report.
- Traces: *SPEC CPU 2017 ChampSim Traces*, Zenodo record 10960004.
