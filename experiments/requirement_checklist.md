# Requirement checklist

Source: `Branch_Prediction_Assignment_Simple.docx` (read in full) + project brief.
Legend: [x] done · [~] partial · [ ] not done · [!] blocked. Status as of 2026-10-30 16:20.

## Assignment requirements
- [x] Branch predictor implemented in ChampSim — `champsim/branch/tagescl.bpred`, proposed config `tfl_tage_scl.bpred`
- [x] Own idea / modification — target-free backward-branch inference enabling IMLI-SIC, IMHIST, backward history (report §4.1, §5)
- [x] Motivation and contribution explained — report §3, §5; `research/design_rationale.md`
- [x] Suitable baselines selected and justified — report §7.5 (4 repo predictors + re-implemented TAGE and TAGE-SC-L)
- [x] IPC, accuracy (all + conditional), MPKI, misprediction counts, storage — `submission/results/`
- [x] Tables and graphs — report (11 tables, 5 figures), XLSX "Graphs" sheet, `results/figures/`
- [x] Analysis incl. why IPC moves less than MPKI — report §9 (data-driven decomposition)
- [x] Research workflow followed — literature → limitation → idea → implementation → experiments → comparison → analysis

## Deliverable 1 — Technical report (DOCX) — `submission/Branch_Predictor_Report.docx`
- [x] Problem statement · [x] Motivation · [x] Proposed predictor · [x] Architecture and working
- [x] Novelty/modification (and what is *not* claimed) · [x] Methodology · [x] Baselines · [x] Traces
- [x] Results and comparison · [x] Analysis and discussion · [x] Ablation · [x] Limitations · [x] Conclusion · [x] References
- [~] PDF version not produced (no converter available offline; DOCX satisfies "PDF/DOCX")

## Deliverable 2 — Complete ChampSim ZIP — `submission/TFL_TAGE_SCL_ChampSim.zip` (1.4 MB, 313 files)
- [x] Complete source · [x] Predictor · [x] Configuration (wrapper .bpred + macros) · [x] Scripts, harness, raw outputs, docs
- [x] Excludes traces, binaries, objects, venv; README explains trace setup
- [x] Verified: extracted, built with stock `build_champsim.sh tfl_tage_scl ...`, 1M/10M xz run identical to experiment binary (IPC 0.843805, 102,619 mispredictions); scripts regenerate identical result CSVs

## Deliverable 3 — README.md — `submission/README.md` (also in ZIP)
- [x] Prerequisites · [x] Build · [x] Configure · [x] Run · [x] Experiment/reproduction commands
- [x] Traces · [x] Parameters · [x] Result processing/graphs · [x] Known limitations
- [~] Trace download URL could not be verified (server did not respond); stated as such

## Deliverable 4 — Results and comparison file — `submission/results/`
- [x] `Branch_Predictor_Results.xlsx` (Summary, Per-trace, IPC, MPKI, Accuracy(all), Accuracy(cond), Ablation, Graphs)
- [x] `results_summary.csv`, `results_per_trace.csv` (incl. raw-output path per run), `ablation_mpki.csv`
- [x] Aggregates, relative improvements, storage, notes on metric definitions

## Project-process requirements
- [x] Workspace inspected; version/build/interface verified; trailing-space directory handled via symlink
- [x] 10 traces located, verified (`xz -t`, length), smoke-tested
- [x] Version control; originals preserved (nothing renamed/deleted; original `bin/`, `obj/` untouched)
- [x] Literature review · [x] Candidate comparison · [x] Design rationale
- [x] Baselines (40 ChampSim runs) · [x] Candidates · [x] Optimization · [x] Ablation · [x] Final evaluation (70 runs)
- [x] All reported runs complete, exit 0, no trace wrap-around; ChampSim MPKI matches harness
- [x] Final binaries built from the frozen source (hash recorded per binary)
- [~] Generalization (Stage H): additional traces judged useful but **not downloaded** — needs approval (see experiment_log.md)
