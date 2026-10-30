# TFL-TAGE-SC-L — a TAGE-SC-L branch predictor with target-free loop-structure history (ChampSim)

This package contains a branch predictor implemented in ChampSim, the baselines it is compared
against, the scripts used for every experiment, and the raw and processed results.

**Proposed predictor (`branch/tfl_tage_scl.bpred`)**: a TAGE-SC-L style predictor (TAGE + loop
predictor + statistical corrector) extended with three loop-structure components — IMLI-SIC,
IMHIST and a backward-branch history — which are normally impossible in this ChampSim version
because the predictor receives no branch target. They are enabled by a **target-free backward-branch
inference**: a taken branch B jumped backward exactly when the address of the next branch passed to
`predict_branch` is ≤ the address of B. Storage: 508,666 bits (62.1 KB), within the 64 KB class of
the strongest predictor shipped with ChampSim (hashed perceptron, 524,542 bits).

## 1. Contents

| Path | What |
|---|---|
| `champsim/` (in the ZIP) | complete ChampSim source (2021 `build_champsim.sh` version) with the new predictors |
| `champsim/branch/tagescl.bpred` | implementation of the predictor family (all components and switches) |
| `champsim/branch/tfl_tage_scl.bpred` | **proposed configuration** |
| `champsim/branch/tage_scl.bpred`, `tage.bpred` | re-implemented baselines (TAGE-SC-L without IMLI components; TAGE only) |
| `champsim/branch/{bimodal,gshare,perceptron,hashed_perceptron}.bpred` | baselines shipped with ChampSim (unchanged) |
| `champsim/src/main.cc`, `src/ooo_cpu.cc`, `inc/ooo_cpu.h` | **stats-only** additions: exact branch/misprediction counts and per-branch-type mispredictions (timing unchanged) |
| `experiments/scripts/` | build, run, parse, harness and analysis scripts |
| `experiments/harness/` | functional branch-stream replay harness + IMLI inference verification tool |
| `experiments/results/` | raw ChampSim outputs of every reported run, harness outputs, run logs |
| `results/` | `Branch_Predictor_Results.xlsx`, CSV files, figures |
| `Branch_Predictor_Report.docx` | technical report |
| `research/` | literature review, candidate comparison, design rationale, research notes |
| `experiments/*.md` | experiment plan, experiment log, requirement checklist |

Traces, binaries and object files are not included (see Section 3 for the traces).

## 2. Prerequisites
- Linux, `g++` with C++11 (tested: g++ 13.3.0, Ubuntu 24.04), GNU make, bash, `xz`.
- Python 3 (tested 3.12) for the scripts. The analysis/figure script additionally needs
  `matplotlib`, `openpyxl` and `python-docx`:
  ```
  python3 -m venv build/venv
  build/venv/bin/pip install matplotlib==3.9.2 openpyxl==3.1.5 python-docx==1.1.2
  ```
- About 1 GB RAM per simulation; the experiments ran 12–14 simulations in parallel on an 18-thread machine.

## 3. Traces
The 10 SPEC CPU2017 traces of the 3rd Data Prefetching Championship (DPC-3), each 2,000M instructions:

```
602.gcc_s-1850B   605.mcf_s-1152B      607.cactuBSSN_s-2421B  619.lbm_s-2676B    620.omnetpp_s-141B
623.xalancbmk_s-10B 625.x264_s-12B     631.deepsjeng_s-928B   638.imagick_s-824B 657.xz_s-2302B
```
Place them as `champsim/dpc3_traces/<name>.champsimtrace.xz`. They are not included (5.2 GB). They
were provided for the course; the DPC-3 trace server used by `scripts/download_dpc3_traces.sh` is
`http://hpca23.cse.tamu.edu/champsim-traces/speccpu/<name>.champsimtrace.xz` (it did not respond
when checked on 2026-10-30, so availability there is unverified). Note that the
script's own list (`scripts/dpc3_max_simpoint.txt`) contains the *max-weight* simpoint of each
benchmark, which for some benchmarks (e.g. gcc: 734B) differs from the simpoints used here — download
the exact file names above. Check them with `xz -t`.

## 4. Build

### 4.1 Standard ChampSim workflow
```
cd champsim
./build_champsim.sh tfl_tage_scl no no no no lru 1       # proposed predictor
./build_champsim.sh tage_scl          no no no no lru 1  # TAGE-SC-L baseline
./build_champsim.sh tage              no no no no lru 1  # TAGE baseline
./build_champsim.sh hashed_perceptron no no no no lru 1  # (also bimodal, gshare, perceptron)
```
Binaries appear as `bin/<predictor>-no-no-no-no-lru-1core`.

### 4.2 Out-of-tree builds (used for the experiments)
`experiments/scripts/build.sh <binary_name> <predictor> [compiler flags]` builds the same
configuration without touching `bin/`, `obj/` or the generated `*.cc` files, so variants can be
built side by side (output in `build/bin/`):
```
experiments/scripts/build.sh tsl_proposed tagescl -DTSL_IMHIST -DTSL_BHIST
experiments/scripts/build.sh tsl_base     tagescl -DTSL_NO_IMLI
```

## 5. Configuring the predictor
All switches are compile-time macros of `branch/tagescl.bpred` (pass with `-D` or `#define` them in
a wrapper `.bpred` as in `tfl_tage_scl.bpred`):

| Macro | Effect |
|---|---|
| `TSL_IMHIST` | per-IMLI-value outcome history (IMHIST) component — on in the proposed design |
| `TSL_BHIST` | backward-branch global history components — on in the proposed design |
| `TSL_NO_IMLI` | remove IMLI-SIC and all IMLI-derived components |
| `TSL_NO_SC` | remove the statistical corrector (and with it all IMLI components) |
| `TSL_NO_LOOP` | remove the loop predictor |
| `TSL_NO_LOCAL` | remove the local-history corrector tables |
| `TSL_IMLI_MODE=0/1/2` | IMLI counting rule: 0 = paper definition with inferred-conditional filter (default); 1 = all taken backward branches; 2 = region-based |
| `TSL_IMLI_GEHL` | also hash IMLIcount into two global corrector tables |
| `TSL_THROTTLE`, `TSL_THR_LIMIT`, `TSL_THR_SHIFT` | per-branch TAGE allocation throttle (evaluated, not used) |
| `TSL_LOG_TAGE`, `TSL_MAXHIST`, `TSL_HBITS` | tagged-table size, longest history, history bits per branch |

The predictor prints its configuration and storage (bits) at start-up.

## 6. Running
```
cd champsim
./run_champsim.sh tfl_tage_scl-no-no-no-no-lru-1core 50 200 605.mcf_s-1152B.champsimtrace.xz
# -> results_200M/605.mcf_s-1152B.champsimtrace.xz-tfl_tage_scl-no-no-no-no-lru-1core.txt
```
or directly:
```
bin/<binary> -warmup_instructions 50000000 -simulation_instructions 200000000 -traces dpc3_traces/<trace>.champsimtrace.xz
```
Reported metrics (end of the output, "Region of Interest Statistics"):
`CPU 0 cumulative IPC`, `Branch Prediction Accuracy` (all branch types), `MPKI`, and the added lines
`BP_STATS num_branch/mispredictions/sim_instr` and `BP_TYPE_MISSES` (mispredictions per branch type:
NOT_BRANCH, DIRECT_JUMP, INDIRECT, CONDITIONAL, DIRECT_CALL, INDIRECT_CALL, RETURN, OTHER).

## 7. Reproducing the reported results
From the root of the extracted ZIP (the directory containing `champsim/`, `experiments/` and
`README.md`; all scripts locate ChampSim as `<root>/champsim`):
```
# baselines shipped with ChampSim
for p in bimodal gshare perceptron hashed_perceptron; do experiments/scripts/build.sh $p $p; done
python3 experiments/scripts/run_matrix.py --stage B_baseline_50M_200M \
    --bins bimodal,gshare,perceptron,hashed_perceptron --warm 50 --sim 200 -j 12

# re-implemented baselines, proposed predictor, ablations
B=experiments/scripts/build.sh
$B tage tagescl -DTSL_NO_SC -DTSL_NO_LOOP;  $B tage_l tagescl -DTSL_NO_SC
$B tsl_base tagescl -DTSL_NO_IMLI;          $B tsl_imli tagescl
$B tsl_proposed tagescl -DTSL_IMHIST -DTSL_BHIST
$B tsl_prop_noloop  tagescl -DTSL_IMHIST -DTSL_BHIST -DTSL_NO_LOOP
$B tsl_prop_nolocal tagescl -DTSL_IMHIST -DTSL_BHIST -DTSL_NO_LOCAL
python3 experiments/scripts/run_matrix.py --stage G_final_50M_200M \
    --bins tsl_proposed,tsl_base,tsl_imli,tage,tage_l,tsl_prop_noloop,tsl_prop_nolocal --warm 50 --sim 200 -j 14

# tables, CSV/XLSX and figures
build/venv/bin/python experiments/scripts/analyze.py --out submission/results
```
`run_matrix.py` is resumable: a run is skipped when its output exists, completed, and was produced by
a binary with the same hash and the same window.

### Functional harness (MPKI only, minutes instead of hours)
```
g++ -O3 -std=c++11 experiments/harness/extract.cc -o build/harness/extract
build/harness/extract champsim/dpc3_traces/605.mcf_s-1152B.champsimtrace.xz build/branchstreams/605.mcf_s-1152B.br 250000000
build/harness/extract <trace> build/branchstreams_tune/<name>.br 150000000 1000000000   # tuning region
python3 experiments/scripts/harness_eval.py --region main "prop=-DTSL_IMHIST -DTSL_BHIST" "base=-DTSL_NO_IMLI"
```
The harness compiles the unmodified `.bpred` against a minimal `ooo_cpu.h` and replays the exact
branch sequence ChampSim feeds the predictor (no wrong-path fetch in this ChampSim); it matches
ChampSim's misprediction counts to within ≈0.05% (warmup-boundary offset).

### Backward-inference verification
```
g++ -O2 -std=c++11 experiments/harness/verify_imli.cc -o build/harness/verify_imli
build/harness/verify_imli champsim/dpc3_traces/605.mcf_s-1152B.champsimtrace.xz 50000000
```

## 8. Experimental parameters
- 1 core, no L1I/L1D/L2C/LLC prefetchers, LRU LLC (ChampSim defaults for this version).
- 50M warmup + 200M measured instructions, every predictor, every trace (window = instructions 0–250M).
- Parameter tuning used a different window of the same traces (instructions 1000M–1150M).

## 9. Known limitations
- 10 SimPoint regions of 10 SPEC CPU2017 programs; no independent program set was used.
- This ChampSim models direction prediction only (no BTB/target misses, no wrong-path execution),
  updates the predictor immediately with the true outcome, and counts all branch types in accuracy
  and MPKI. Results are not directly comparable with newer ChampSim versions or CBP numbers.
- The IMLI counter depends on inferring which branches are conditional (seen not-taken); on traces
  dominated by never-exiting backward branches it differs from an oracle counter.
- Cosmetic: builds with `TSL_NO_SC` print "[IMLI mode 0]" although IMLI components are inactive
  without the corrector (left unchanged so the source hash of the reported runs is preserved).
