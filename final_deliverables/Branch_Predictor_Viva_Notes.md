# Branch Predictor Viva Notes

Answers use only figures verified from the raw ChampSim outputs (10 SPEC CPU2017 traces, 50M warm-up + 200M measured instructions) unless marked *harness*.

## 1. What is our proposed branch predictor?

TFL-TAGE-SC-L: our re-implementation of a TAGE-SC-L-style predictor (TAGE + loop predictor + statistical corrector) extended with three loop-structure corrector components — IMLI-SIC, IMHIST and a backward-branch history — made possible by a target-free backward-branch inference. 508,666 bits (62.09 KB). File: `branch/tagescl.bpred`, configuration `branch/tfl_tage_scl.bpred`.

## 2. What problem are we solving?

The 2021 ChampSim interface gives the predictor only the PC and, afterwards, the outcome — no branch type, no target. Loop-structure features need to know which branches are backward, so they cannot be computed directly. We recover that information inside the predictor and measure what it buys.

## 3. Why a TAGE-SC-L-style design?

It is the established high-accuracy design at this storage budget. In our runs TAGE alone (3.295 MPKI) is not better than the 64 KB hashed perceptron (3.247) because it loses on mcf and xz; adding the statistical corrector fixes that (3.072).

## 4. What does each component do?

- **TAGE**: tagged tables indexed with geometrically increasing global-history lengths (4–640); the longest match predicts.

- **Loop predictor**: learns constant trip counts and predicts the exit.

- **Statistical corrector**: a perceptron-like sum of small counters (bias, global, path, local history) that overrides TAGE when TAGE is statistically unreliable.

- **IMLI-SIC**: a corrector table indexed by PC and the inner-loop iteration number.

- **IMHIST**: for each iteration number, the recent outcomes at that iteration — captures correlation with the previous outer-loop iteration.

- **Backward-branch history**: a global history of only backward-branch outcomes (loop-exit patterns).

## 5. What exactly did we modify?

We added the target-free backward inference (plus `bwd`/`cond` bit tables) and used it to drive IMLI-SIC, IMHIST and the backward-branch history inside our TAGE-SC-L. We also built the evaluation tooling (replay harness, verification tool, scripts). TAGE-SC-L itself, IMLI-SIC, IMHIST and backward histories are Seznec et al.'s published techniques.

## 6. What is target-free backward-branch inference?

After a taken branch B, the next branch the predictor sees, N, lies on the straight-line path from B's target T, so pc(N) ≥ T. If T ≤ pc(B) that path reaches B itself, so pc(N) ≤ pc(B); otherwise pc(N) > pc(B). So B was backward iff pc(N) ≤ pc(B). It is exact here because ChampSim presents every branch in order with no wrong path (verified in `read_from_trace()`); measured agreement with ChampSim's real target: 99.9996–100% on all ten traces.

## 7. How do prediction and training work?

Predict: update loop state from the previous branch → TAGE longest match (or alternate) → loop override if confident → corrector sum → corrector overrides unless TAGE is confident and the sum is small. Train (immediately, true outcome): corrector counters and threshold, loop entry, TAGE counters/useful bits and allocation of up to two entries on a TAGE misprediction, global/path/local histories, IMLI/IMHIST/backward history.

## 8. How is MPKI calculated?

MPKI = 1000 x mispredictions / retired instructions in the measured region (200M). Mispredictions count every branch type, as ChampSim does. Mean MPKI is the arithmetic mean over the ten traces; percentage reductions are computed from the means.

## 9. What is IPC and how does it differ from MPKI?

IPC = instructions / cycles — overall performance. MPKI only counts prediction errors. An avoided misprediction saves the fetch stall (~22–50 cycles here), which matters little when the program is stalled on memory. So MPKI can drop a lot while IPC barely changes.

## 10. Why is our model better than the hashed perceptron in our experiments?

Mean MPKI 3.046 vs 3.247 (6.2% lower), lower on all 10 traces, IPC +0.43% (geomean; higher on 9, lower by 0.02% on lbm), with 15,876 fewer bits. The gain comes mostly from TAGE's long tagged histories plus the corrector; the hashed perceptron in the repository is a simple, untuned design.

## 11. How much does it improve over TAGE-SC-L?

MPKI 3.0717 → 3.0456: 0.0260 absolute, 0.85% (lower on 6 traces, ≤ 0.0007 higher on the 4 near-zero traces). Harness seed runs: +0.84% to +0.89% across four seeds — far above the noise. IPC: +0.058% geomean — small; a ChampSim re-run of both designs with a different random seed gives +0.055% (seed changes alone move the geomean IPC of a design by +0.001% and +0.003%).

## 12. Trade-off between accuracy, IPC, storage and complexity?

+32,347 bits (3.95 KB, +6.8%) over TAGE-SC-L for −0.85% MPKI and +0.058% IPC. Extra logic: one comparison per branch, two bit tables, four corrector tables. Area, power and latency were not measured.

## 13. What does the ablation study show?

*Harness*, Δ MPKI when removed: statistical corrector +8.1%, local-history SC tables +2.9%, all IMLI-derived components +0.9%, backward history +0.36%, IMHIST +0.28%, loop predictor +0.10% (within noise). ChampSim runs of five of these configurations agree.

## 14. Which components give the largest measured improvements?

The statistical corrector (and within it the local-history tables). Of the published loop-structure components that the target-free inference enables, the backward-branch history contributes most (+0.36% MPKI when removed), then IMHIST (+0.28%), then IMLI-SIC (0.23% from TAGE-SC-L to TAGE-SC-L + IMLI in ChampSim).

## 15. Why do some benchmarks gain more than others?

Gains need (a) many mispredictions left to remove, (b) loop structure the new features capture, and (c) a pipeline where a saved misprediction is visible: xz and deepsjeng (CPI ~1) gain most in IPC; mcf and omnetpp gain in MPKI but are memory-bound; FP traces have nothing left to remove.

## 16. What are the limitations?

Ten traces only; tuning on other windows of the same programs; simplified simulator (direction only, immediate update, no wrong path); inference relies on in-order presentation; small IPC gain over TAGE-SC-L; no area/power/latency evaluation; our TAGE-SC-L is a re-implementation, not Seznec's championship code.

## 17. What is our contribution and what is existing research?

Existing: TAGE, TAGE-SC-L, statistical corrector, loop predictor, IMLI-SIC, IMHIST, backward histories (Seznec et al.), perceptrons (Jiménez & Lin). Ours: the target-free inference using only predictor-visible information, its verification, the integration into this ChampSim, and the evaluation including negative results. The closest related work, a ChampSim fork's TAGE-SC-L adapter (2026), uses the next *instruction* address taken from the simulator, which the 2021 predictor interface does not provide.

## 18. Can we claim to beat state-of-the-art research?

No. We beat the baselines we evaluated under identical conditions. Published predictors were evaluated on different traces, simulators and storage budgets, and our TAGE-SC-L is a smaller re-implementation; a state-of-the-art claim would need the same benchmarks, budget and simulator.