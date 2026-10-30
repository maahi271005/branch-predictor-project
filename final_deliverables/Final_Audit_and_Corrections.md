# Final Audit and Corrections

This log records the independent audit of the project (deliverables in `submission/`, data in `experiments/results/`). Original files were not modified; corrected outputs are in `final_deliverables/`. Scripts: `recompute_metrics.py`, `seed_sensitivity.py`, `build_results.py`, `make_final_docs.py`.

## Summary

- 110 raw ChampSim outputs re-parsed independently; 1,258 checks, 0 failures.

- **All headline numbers in the original summary were correct** to the precision reported (mean MPKI, geometric-mean speedups, per-trace counters).

- Corrections concern: one storage figure, the harness-accuracy claim, imprecise implementation descriptions, misleading or unreadable graphs, missing noise analysis, and the scope of the novelty claim.

## 1. Numerical errors

| Issue | Original | Corrected | Reason / evidence | Status |
|---|---|---|---|---|
| Summary table (mean MPKI, speedups) | e.g. proposed 3.046 MPKI, 1.1008x | 3.04561 MPKI, 1.100780x (unchanged) | Recomputed from raw outputs; matches to 6 decimals | Verified |
| MPKI denominator | '200M instructions' | 200,000,000–200,000,003 retired instructions; ChampSim uses num_retired − warm-up | 4-wide retirement overshoots; effect < 1e-8 relative | Resolved (documented) |
| Accuracy aggregation | 'Accuracy' in summary table | Pooled over all branches; mean-of-traces also given | Two definitions differ by up to 0.2 pp | Resolved (labelled) |
| Perceptron storage | 32,648 bits | 32,624 bits | Speculative-history copy is identical under immediate update; counted once | Resolved |

## 2. Methodology issues

| Issue | Original claim | Corrected claim | Evidence | Status |
|---|---|---|---|---|
| Harness accuracy | 'matches ChampSim within ≈0.05%' | Mean MPKI within 0.03%; per trace ≤0.04% for simple predictors but up to 0.82% for TAGE-SC-L family (xalancbmk, imagick) | harness_vs_champsim.csv; cause: ChampSim presents a branch first instruction twice (current=next initialisation in read_from_trace); verified first records of xalancbmk/imagick/mcf are branches, xz is not and matches exactly | Resolved |
| No noise estimate | Differences of 0.1–0.3% reported as component effects | Seed noise SD ≤ 0.028% (4 seeds); IMHIST, BHIST, IMLI effects robust; loop predictor inconclusive | seed_sensitivity.csv | Resolved |
| IPC gain over TAGE-SC-L | +0.058% presented as a gain | Small but reproducible: a ChampSim re-run of both designs with a different random seed gives +0.055% (seed changes alone move the geomean IPC of a design by +0.001% and +0.003%) | AUDIT_seed1_50M_200M runs | Resolved |
| Tuning vs. evaluation windows | Tuning on 1000M–1150M, evaluation on 0–250M | Verified; but the final choice between two candidates also used reported-window harness data | Re-extraction of imagick at 1,000,000,000 matches the tuning stream byte-for-byte; experiment_log E4 | Resolved (disclosed) |
| Comparable runs | Same configuration for all | Verified: same 10 traces, window, simulator objects; all exit 0, completed, no wrap | checks.txt; build timestamps | Verified |
| Frozen configuration | Frozen at commit 660997e | Verified: all 7 TAGE-family binaries built from the current source hash; harness ablation files keyed to it | checks.txt | Verified |
| Ablation source | Ablation figure unlabelled as to source | Ablation is harness (MPKI only); 6 configurations cross-checked in ChampSim | ablation.csv, Table 7 | Resolved |

## 3. Implementation inconsistencies (report vs. code)

| Issue | Original description | Actual code | Status |
|---|---|---|---|
| IMLI-SIC weight | not mentioned | counter counted twice in the corrector sum (`lsum += 2 * ctrsum(...)`) | Resolved (documented) |
| Alternate-entry training | 'alternate trained for weak providers' | only when a weak provider mispredicted | Resolved |
| IMHIST update order | 'per-IMLI-value history' | on a loop exit IMLI is reset before recording, so the exit outcome goes to IMHIST[0]; restricted to branches seen not-taken | Resolved (documented) |
| Backward history scope | 'backward-branch outcomes' | all backward branches, conditional or not (unlike IMLI, no conditional filter) | Resolved (documented) |
| Banner of TAGE-only builds | prints '[IMLI mode 0]' | IMLI is inactive without the corrector; cosmetic | Unchanged (source hash preserved) |
| Callback semantics | assumed | verified: guarded call, in-order, immediate update, no wrong path; first instruction duplicated | Verified |

## 4. Graph errors

| Figure (original) | Problem | Correction | Status |
|---|---|---|---|
| IPC normalised to bimodal | y-axis from 0 to 1.2: differences between 45–64 KB predictors invisible | plotted as % change over bimodal, labelled with formula | Resolved |
| Accuracy per trace | 0–100% bar axis hides differences; only all-branch accuracy; not used in report | dot plot, both definitions, axis 80–100% labelled; discussed in report | Resolved |
| MPKI reduction vs IPC gain | labels of cactuBSSN/lbm/imagick overlap; only vs hashed perceptron | near-origin points listed in a box; second panel vs TAGE-SC-L; axis formulas | Resolved |
| Ablation | source (harness) not stated; no noise; no ChampSim cross-check | harness label, ChampSim markers, seed ranges | Resolved |
| Aggregate summary | speedup axis started at 0.98 (bars exaggerate) | speedup shown as % from 0; values verified | Resolved |
| MPKI per trace | values verified; legend placement fixed earlier | regenerated from audited data | Verified |
| (new) Storage vs MPKI | — | added for the trade-off analysis | Added |

## 5. Storage and complexity accounting

| Item | Finding | Status |
|---|---|---|
| TFL-TAGE-SC-L 508,666 bits | Component breakdown sums exactly to storage_bits(); folded-history registers (422 bits) and RNG (64 bits) excluded — stated | Verified |
| Hashed perceptron 524,542 bits | 524,288 weight bits + 240 history bits + threshold (8 bits, assumed) + counter (6 bits) | Verified with assumption |
| 'Smaller than hashed perceptron' | holds by 15,876 bits, also with excluded state counted | Verified |
| Area/power/latency | not measured by ChampSim; only qualitative discussion | Not verifiable |

## 6. Unsupported or over-broad research claims

| Claim | Correction | Status |
|---|---|---|
| 'No prior use of the next predicted branch's address' | Narrowed: closest related work (ChampSim2 PR #2, 2026) uses the next instruction address from the simulator queue; ours uses only predictor-visible information. Not claimed as a new prediction technique. | Resolved |
| Lin & Tarsa percentages | 96.9% (mcf), 80.5% (xz), 55.3% average; 13,093 median allocations per H2P — checked against the paper text | Verified |
| TAGE-SC-L 3.986 MPKI at 523,355 bits | checked against the CBP-5 paper text | Verified |
| Superiority | Only over the baselines evaluated here; no state-of-the-art claim | Resolved |

## 7. Missing evidence

- No evaluation beyond the ten required traces (generalisation untested).

- One ChampSim run per configuration (plus one alternative-seed run for two configurations).

- No hardware area, power or latency estimate.

- Trace download server unreachable when checked; trace provenance relies on the course-provided files.

## Final verification table

| Claim or result | Evidence source | Independently verified? | Status |
|---|---|---|---|
| Mean MPKI of all 11 configurations (e.g. proposed 3.0456) | raw ChampSim outputs | Yes | Verified using raw ChampSim results |
| Proposed vs hashed perceptron: −6.22% MPKI, +0.43% IPC | raw ChampSim outputs | Yes | Verified using raw ChampSim results |
| Proposed vs TAGE-SC-L: −0.85% MPKI | raw ChampSim outputs + seed runs | Yes | Verified using raw ChampSim results |
| Proposed vs TAGE-SC-L: +0.058% IPC | raw ChampSim outputs + seed re-run | Yes | Verified; consistent but small |
| MPKI lower than hashed perceptron on 10/10 traces | raw ChampSim outputs | Yes | Verified using raw ChampSim results |
| Ablation contributions (IMHIST, BHIST, IMLI, local, SC) | harness, 2 windows, 4 seeds; 4 configs in ChampSim | Yes (harness) | Supported only by harness results (cross-checked in ChampSim where run) |
| Loop predictor contribution | harness + ChampSim | Yes | Unresolved — within noise |
| Backward inference exactness (99.9996–100%) | verify_imli.cc vs ChampSim's branch_target | Yes | Verified (tool output) |
| Storage 508,666 bits; < hashed perceptron | source code accounting | Yes | Verified (logical bits; HP threshold width assumed) |
| Spreadsheet figures and graphs | regenerated from audit data | Yes | Verified using spreadsheet calculations only (derived from raw) |
| Hardware area / power / latency | none | No | Not independently verified |
| Generalisation beyond 10 traces | none | No | Unresolved |