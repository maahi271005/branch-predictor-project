# Experiment plan

Status: draft v1 (2026-10-30). Updated as stages complete; see `experiment_log.md` for what actually ran.

## Fixed methodology

| Item | Setting | Reason |
|---|---|---|
| Simulator | ChampSim (2021 `build_champsim.sh` version) in this repo, 1 core, no prefetchers, LRU LLC | the configuration the course repo ships; isolates the branch predictor |
| Core change | stats-only: exact branch/misprediction counters and per-type misses (no timing change; verified bit-identical IPC vs. previous lab runs) | needed for exact counts and conditional-only accuracy |
| Workloads | the 10 required DPC-3 SPEC CPU2017 traces (2,000M instructions each, all pass `xz -t`) | assignment requirement |
| Reported window | 50M warmup + 200M measured instructions, every trace, every predictor | DPC-3 practice is 50M/200–250M; traces never wrap (2B instructions) |
| Tuning window | instructions 1000M–1150M of each trace (50M warmup + 100M) via the functional harness | keeps parameter tuning off the reported window |
| IPC | full ChampSim timing simulation | only source of IPC |
| MPKI exploration | functional replay harness (`experiments/harness`) driving the unmodified `.bpred` | ChampSim has no wrong-path fetch, so predictor call sequence = trace branch order; harness matches ChampSim to ~0.005% (warmup-boundary offset only) |

### Metrics
- **IPC**: `CPU 0 cumulative IPC` of the ROI.
- **Accuracy (ChampSim definition)**: (branches − mispredictions) / branches over **all** branch types (the old interface predicts direction for every branch; unconditional ones count as taken).
- **Conditional accuracy**: same, conditional branches only. Reported separately, never mixed.
- **MPKI**: 1000 × mispredictions / measured instructions (all types; conditional-only MPKI also reported).
- **Storage**: bits of predictor state, counted by the predictor itself (`storage_bits()`), cross-checked by hand.

### Aggregation
- Arithmetic mean MPKI over the 10 traces (and over the 7 integer traces).
- Geometric mean of per-trace IPC speedup vs. a reference predictor.
- Arithmetic mean IPC shown for information only.
- Relative MPKI reductions computed from the means, not averaged per trace (near-zero-MPKI FP traces would dominate).

## Predictors

### Baselines
| Name | Source | Storage | Why |
|---|---|---|---|
| bimodal | repo | 4 KB | simplest reference, ChampSim default |
| gshare | repo | 4 KB | classic global-history predictor |
| perceptron | repo (Jiménez & Lin 2001) | 4 KB | reference paper 1 |
| hashed_perceptron | repo | 64 KB | strongest predictor shipped with the repo; same storage class as the proposal |
| TAGE (re-implemented) | `tagescl.bpred -DTSL_NO_SC -DTSL_NO_LOOP` | ≈ 47 KB | reference paper 2; isolates the tagged predictor |
| TAGE-SC-L (re-implemented, no novelty) | `tagescl.bpred` with the novel mechanisms disabled | ≤ 64 KB | state-of-the-art family; the proposal must beat this, not only the repo baselines |

### Proposed predictor
TAGE-SC-L style base plus the candidate contributions (to be confirmed by Stage C/D):
- **N1 — target-free IMLI**: exact backward-branch inference from the next fetched branch address, enabling IMLI-SIC (Seznec et al., MICRO 2015) in an interface that provides no branch target.
- **N2 — per-branch allocation throttling**: a small PC-indexed "allocation payoff" table lowers TAGE allocation probability for branches whose allocations repeatedly fail to become useful (hard-to-predict branches), preserving capacity for learnable branches. Prior art found so far is global throttling only (Seznec 2014/2024/2025, BATAGE CAT).

Each mechanism is kept only if it improves mean MPKI on the tuning region and does not regress the reported window materially.

## Stages
- **A Validation** — done: traces, build, smoke tests, harness equivalence, IMLI inference check.
- **B Baselines** — 4 repo baselines × 10 traces in ChampSim (50M/200M) + harness MPKI.
- **C Exploration** — implement TAGE → +L → +SC → +IMLI → +N2 incrementally; harness on tuning region; each step compiled, smoke-tested, checked for sane MPKI.
- **D Candidate comparison** — all candidates on all 10 traces (harness, reported window) + ChampSim IPC for the front-runners.
- **E Optimization** — limited sweeps on the tuning region: history lengths (MAXHIST), table count/size within 64 KB, tag widths, N2 thresholds, history bits per branch.
- **F Ablation** — final design minus each component (SC, loop, local, IMLI, N1 inference variant, N2) on all 10 traces.
- **G Final evaluation** — frozen configuration; ChampSim 50M/200M on all 10 traces for: bimodal, gshare, perceptron, hashed_perceptron, TAGE, TAGE-SC-L (no novelty), proposed, and the ablations.
- **H Generalization** — decide whether more traces are warranted; present cost first, no automatic downloads.

## Falsification criteria
- N1 is not supported if enabling IMLI does not reduce MPKI on any trace beyond noise, or if the oracle-target IMLI (computable in the verification tool) would be required to see a benefit.
- N2 is not supported if the throttled variant does not lower mean MPKI vs. the same predictor without it, or if gains appear only on the tuning region and vanish on the reported window.
- The overall design is not supported if it fails to beat the re-implemented TAGE-SC-L at equal storage.
