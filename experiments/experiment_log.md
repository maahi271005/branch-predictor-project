# Experiment log

All MPKI values count all branch types (ChampSim's definition). "tune" = instructions 1000M–1150M
(50M warmup + 100M measured), "main" = instructions 0–250M (50M warmup + 200M measured).
Harness results: `experiments/results/harness/<region>/<variant>.txt` (header records flags and source hash).
ChampSim results: `experiments/results/<stage>/<binary>/<trace>.txt` (header records binary hash, window, command, exit code).

## Stage A — validation (2026-10-30)
| ID | What | Result | Output |
|---|---|---|---|
| A1 | `xz -t` on the 10 traces | all OK; each trace = 2,000M instructions (128 GB uncompressed) | task log |
| A2 | bimodal, ChampSim 1M/10M, 10 traces | all complete; IPC/accuracy/MPKI identical to the previous lab's CSV (e.g. mcf 0.329782 / 90.0509% / 24.7064) → stats-only core edits are timing-neutral | `results/A_validation/bimodal/` |
| A3 | original prebuilt `bin/bimodal-...-1core` on mcf | same branch stats, cycles differ by 0.003% (binary built from a different source/compiler) — not used, left untouched | `results/A_validation/ORIGINAL_bin_bimodal/` |
| A4 | harness vs ChampSim, bimodal mcf 1M/10M | 247,076 vs 247,064 mispredictions (warmup-boundary offset ≈ one ROB of branches) | — |
| A5 | target-free backward inference vs ChampSim target, 50M instr/trace | per-instance agreement 99.9996–100% on all 10 traces | `results/A_validation/imli_inference_check.txt` |
| A6 | inferred IMLI counter vs oracle IMLI | clamped-16 agreement 95.7–99.7% (mcf, x264, xz, gcc), 92% imagick; low on lbm/cactuBSSN/omnetpp where the oracle counter sits saturated/large (never-exiting backward conditional branches) | same file |
| A7 | tagescl (full) ChampSim 1M/10M on mcf, xz | runs; 487,658 bits; harness agrees (103,049 vs 103,048 on xz) | `results/A_validation/tsl_full/` |

## Stage B — baselines
| ID | What | Status |
|---|---|---|
| B1 | bimodal, gshare, perceptron, hashed_perceptron × 10 traces, ChampSim 50M/200M, 12 parallel | running (25/40 at last check) — `results/B_baseline_50M_200M/` |
| B2 | same 4 predictors, harness MPKI, main window | done (see harness/main once regenerated) |

## Stage C/E — exploration and tuning (harness, tune region)
| ID | Variant(s) | Mean MPKI (10) | Decision |
|---|---|---|---|
| C1 | hashed_perceptron | 3.3805 | reference |
| C1 | TAGE (≈45 KB) / TAGE+L | 3.4163 / 3.4137 | TAGE alone ≈ hashed perceptron; loop ≈ 0 |
| C1 | TAGE-SC-L no IMLI / with IMLI | 3.1880 / 3.1739 | SC is the main lever (−6.7% vs TAGE); IMLI −0.44% |
| E1 | 2 history bits/branch; MAXHIST 1000, 2000; HB2+1300 | +0.28%, +0.15%, +0.96%, +0.33% | keep 1 bit, MAXHIST 640 |
| E1 | per-branch allocation throttle (3 settings) on TAGE-SC-L | −0.00%, +0.06%, +0.09% | no effect in full design |
| E2 | same throttle on TAGE only | −0.49%, −0.55% | effective on TAGE; subsumed in TAGE-SC-L by the "allocate with p=1/32 when the final prediction was correct" rule → reported as negative/explained result |
| E3 | IMLI mode 1 (no conditional filter), mode 2 (region) | +0.14%, +0.16% | keep mode 0 (paper definition) |
| E3 | IMLI in two global SC tables | +0.19% | alone: no |
| E3 | IMHIST; backward history; all three | −0.14%; −0.21%; −0.30% | candidates |
| E4 | IMHIST+BHIST without IMLI_GEHL (tune) | 3.1580 (−0.50% vs IMLI only) | **selected** |
| E4 | main window: hashed_perc / TAGE / TSL no IMLI / +IMLI / +IMHIST+BHIST / +IMLI_GEHL too | 3.2475 / 3.2947 / 3.0727 / 3.0648 / **3.0455** / 3.0501 | ranking confirmed on the reported window; design frozen (commit 660997e) |

## Stage F — ablation (harness, both regions; `results/harness/F_ablation_{main,tune}.txt`)
| Removed from proposed | Δ mean MPKI main | Δ tune |
|---|---|---|
| loop predictor | +0.10% | +0.09% |
| IMHIST | +0.28% | +0.30% |
| backward-branch history | +0.36% | +0.37% |
| all IMLI-derived components | +0.89% | +0.95% |
| local-history SC tables | +2.94% | +2.84% |
| whole SC (= TAGE + loop) | +8.13% | +8.10% |

## Stage G — final ChampSim evaluation (50M + 200M, 10 traces)
| ID | Binaries | Status |
|---|---|---|
| G1 | tsl_proposed, tsl_base, tsl_imli, tage, tage_l, tsl_prop_noloop, tsl_prop_nolocal (70 runs, 14 parallel, started 15:03) | running — `results/G_final_50M_200M/` |
