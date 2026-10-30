# Requirement checklist

Source: `Branch_Prediction_Assignment_Simple.docx` (read in full) + project brief.
Legend: [x] done · [~] in progress · [ ] not started · [!] blocked

## Assignment requirements
- [~] Branch predictor implemented in ChampSim
- [~] Own idea / modification / novelty, clearly explained
- [~] Motivation and contribution explained
- [~] Suitable baselines selected and justified
- [~] IPC, branch prediction accuracy, MPKI (+ other metrics) measured
- [ ] Tables and graphs
- [ ] Analysis of results and explanation of observed behaviour
- [ ] Research workflow followed: study → understand → limitation → idea → implement → run → compare → analyze

## Deliverable 1 — Technical report (PDF/DOCX)
- [ ] Problem statement · [ ] Motivation · [ ] Proposed predictor · [ ] Architecture and working
- [ ] Novelty/modification · [ ] Methodology · [ ] Baselines · [ ] Benchmarks/traces
- [ ] Results and comparison · [ ] Analysis and discussion · [ ] Conclusion · [ ] References

## Deliverable 2 — Complete ChampSim ZIP
- [ ] Complete source · [ ] Implemented predictor · [ ] Configuration files · [ ] Supporting files
- [ ] Excludes traces/binaries; explains how to get traces · [ ] Extraction verified

## Deliverable 3 — README.md
- [ ] Build/installation · [ ] Configure predictor · [ ] Run predictor · [ ] Experiment commands
- [ ] Benchmarks/traces · [ ] Configuration details · [ ] Reproduction instructions · [ ] Known limitations

## Deliverable 4 — Results and comparison file (CSV/XLSX)
- [ ] Baseline results · [ ] Proposed results · [ ] IPC / accuracy / MPKI comparison
- [ ] Other metrics (misprediction counts, conditional accuracy, storage) · [ ] Tables · [ ] Graphs · [ ] Analysis

## Project-process requirements
- [x] Workspace inspected; ChampSim version, build system and predictor interface verified
- [x] 10 traces located, sizes/formats recorded, integrity (`xz -t`) checked, smoke-tested
- [x] Version control established (original snapshot committed; traces/binaries excluded)
- [x] Original files, binaries, traces and earlier results preserved (nothing renamed/deleted)
- [~] Literature review (agents A, B, D done; C pending)
- [ ] Candidate comparison · [ ] Design rationale
- [~] Baselines on 10 traces (ChampSim running)
- [ ] Candidate experiments · [ ] Optimization · [ ] Ablation · [ ] Final evaluation · [ ] Generalization decision
- [ ] Final verification (rebuild, rerun, ZIP check, consistency)
