# Topic D: Recent Branch Prediction Research, Alternatives, and Experimental Methodology

Agent D research notes, written 2026-10-30. This is a research-only pass: nothing in the project was modified except this file.

**Evidence legend** (used throughout):
- **[READ]**: I read it directly, either in the local source code or in the primary PDF or web page (the text, or a figure I looked at).
- **[READ-2nd]**: verified only through a secondary source, such as an abstract page, search-result metadata, or another paper that cites it.
- **[INFERRED]**: my own reasoning or extrapolation. It is not a claim made by any source.
- **[FIG~]**: a number I read by eye from a bar chart in the cited paper. Treat it as roughly ±0.3 MPKI or ±0.3 percentage points.

---

## 0. TL;DR

1. **The newest "championship" state of the art is CBP2025** (6th Championship Branch Prediction, ISCA 2025, Tokyo, June 21 2025), sponsored by Arm [READ]. It had a 192KB budget and two tracks, BrMisPKI and CycWpPKI.
   - 1st place: **RUNLTS** (Nagoya Inst. Tech / U. Tokyo).
   - 2nd place: **TAGE-SC for CBP2025** (Seznec, SiFive).
   - 3rd place: **LVCP** (ICT-CAS).
   - Gains over a 192KB-scaled TAGE-SC-L were small: RUNLTS reduced BrMisPKI by about 5.3% on the full trace set [READ, closing slides].
   - Bottom line: TAGE-SC-L is still the backbone of the best predictors. The winning gains come from:
     - better TAGE allocation and replacement,
     - an improved IMLI,
     - extra information channels (register and load values).
2. **For our OLD ChampSim interface** (`predict_branch(ip)` and `last_branch_result(ip, taken)`, with no type, no target, and no values), the feasible high-value ideas are:
   - (a) A faithful **64KB TAGE-SC-L** port (CBP2016).
   - (b) The **TAGE allocation/replacement refinements** from Seznec's 2024 "TAGE engineering cookbook" and CBP2025 entry. These need zero extra storage and are internal policy only.
   - (c) **IMLI-style loop-iteration components**, approximated without a target address. BrIMLI can be approximated without a target; TaIMLI cannot.

   Value-based predictors (RUNLTS register digests, LVCP, BALL) and LLBP (512KB backing store) are not feasible here.
3. **Methodology:**
   - **Final runs:** use **50M warmup + 200M (or 250M) simulated instructions** per trace. DPC-3, whose traces we use, used 50M warmup + 250M sim [READ].
   - **Aggregation:**
     - Report per-trace MPKI.
     - Report the **arithmetic mean MPKI** (CBP convention [READ]).
     - Report the **geomean IPC speedup** vs. a baseline (DPC-3 convention [READ]).
   - **Caveats:**
     - Old ChampSim's MPKI and "accuracy" count **all branch types**, not only conditionals.
     - The predictor is updated immediately with the outcome, an oracle-timing idealization.
     - The IPC impact of a mispredict comes from fetch stalling until the branch executes, plus a 1-cycle penalty. There is no wrong-path modelling.

---

## 1. Survey of post-2016 branch prediction research

All entries below were verified to exist: I checked the title, authors, venue, and URL in this session.

### 1.1 Championship results

#### CBP-5 (2016), the baseline everyone still cites
- **Venue:** 5th JILP Workshop on Computer Architecture Competitions (JWAC-5), ISCA 2016, Seoul. URL: https://jilp.org/cbp2016/
- **Rules** [READ-2nd, via the CBP2016 call page]:
  - Three tracks: **8KB, 64KB, and unlimited**, each with an extra 2048 bits allowed (e.g., for global history).
  - Evaluated on **conditional branches**.
  - Score is the **weighted average MPKI** over the traces.
  - The initial trace set had 223 traces (200 × 100M instructions + 23 × 1B instructions).
- **Program (5 papers)** [READ-2nd, program page]:
  1. Seznec, "TAGE-SC-L Branch Predictors Again". https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf. The 64KB version reports **3.986 MPKI** on the CBP-5 training traces [READ-2nd].
  2. Seznec, "Exploring branch predictability limits with the MTAGE+SC predictor" (unlimited track). BranchNet calls MTAGE-SC "the best predictor in the unlimited storage category of CBP 2016" [READ].
  3. Jiménez, "Multiperspective Perceptron Predictor" (MPP). https://jilp.org/cbp2016/paper/DanielJimenez1.pdf. It is a hashed perceptron with many "perspectives" (history feature types) and an 8.25KB evaluation [READ-2nd].
  4. Jiménez, "Multiperspective Perceptron Predictor with TAGE". https://jilp.org/cbp2016/paper/DanielJimenez2.pdf
  5. Pruett, Zangeneh, Fakhrzadehgan, Lin, Patt, "Dynamically Sizing the TAGE Branch Predictor". https://jilp.org/cbp2016/paper/StephenPruettFinal.pdf. Core idea: TAGE table sizes are static, so storage is reallocated at run time toward the most congested tables/entries. Reported 5.370 MPKI at 8KB and 4.265 MPKI at 64KB [READ-2nd, abstract]. That is worse than TAGE-SC-L 64KB (3.986), so it did not win.
- **Winners:**
  - The 64KB TAGE-SC-L is called "the 64KB CBP2016 winning TAGE-SC-L predictor" in the CBP2025 rules [READ].
  - The 8KB TAGE-SC-L won the 8KB track, according to Michaud's BATAGE paper [READ-2nd].
  - MTAGE-SC won the unlimited track [READ, BranchNet].

#### CBP2025 (6th Championship Branch Prediction)
- **Venue and organization:** Co-located with ISCA 2025, Tokyo, June 21 2025. Sponsored by Arm; organizing chair Rami Sheikh.
  - Site: https://ericrotenberg.wordpress.ncsu.edu/cbp2025/
  - Closing slides: https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/CBP2025-Closing-Remarks.pdf [READ, all slides]
- **Rules** [READ, CBP2025 page]:
  - Budget: **192KB**. Contestants may keep the 64KB CBP2016 TAGE-SC-L and add 128KB.
  - Only conditional branches are scored. All other branches are predicted perfectly by the framework [READ, simulator page].
  - Two tracks, ranked by arithmetic mean:
    - **BrMisPKI**: conditional mispredictions per kilo-instruction.
    - **CycWpPKI**: cycles on the wrong path per kilo-instruction.
  - `spec_update()` may update histories with the actual outcome but **may not update tables** with it, so table updates happen at resolve/execute time.
  - Complexity is not part of the ranking.
- **Traces** [READ, simulator page]:
  - 105 training traces of 10M–130M instructions, plus secret test traces (now on Zenodo, https://zenodo.org/records/15883615).
  - **The first half of each trace is warmup; stats are taken on the second half.**
  - Categories (from the slides): int, fp, web, media, compress, infra.
- **Results** [READ, closing slides; baseline = 192KB-scaled TAGE-SC-L]:

  | Entry | Change vs. 192KB TAGE-SC-L |
  |---|---|
  | **1st: RUNLTS** | BrMisPKI −7.2% (training) / **−5.3% (full)**; CycWpPKI −3.6% / −2.5% |
  | **2nd: TAGE2025** (Seznec) | BrMisPKI about −1.9% / −2.2% |
  | **3rd: LVCP** | BrMisPKI about −1.6% / −1.3% |
  | MPP2025, DD-TAGE ("A Deep Dive Into TAGE-SC-L"), Bullseye | about 0 to −1% |
  | PIP (Ensemble of Programming-Idiom Predictors), CS-TAGE (TAGE-SC-L with Code Structure Correlator), BALL (Branch-ALU-Load-Load, via load value prediction) | **worse than baseline** |

- **Lesson** [INFERRED]: even with 3× the budget and a year of effort by expert teams, gains over TAGE-SC-L are in the single-digit percent range. Several entries overfit the training traces: the training vs. full-set deltas differ, and BALL goes from +3% to +6.6% worse.

#### CBP2025 entries worth knowing

1. **RUNLTS: Register-value-aware predictor Utilizing Nested Large TableS.**
   - Authors: Koizumi, Maekawa, Mizuno, Kuroki, Tsumura, Shioya.
   - PDF: https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final44-Koizumi.pdf [READ]
   - It is TAGE-SC-L based, with these additions:
     - a 128K-entry bimodal table;
     - a non-geometric set of history lengths;
     - **storage-free allocation-thrashing detection**. Counter states 0/−1 with the u-bit set "rarely appear", so they are repurposed to mark newly allocated entries, and that marker throttles the allocation rate;
     - **Seznec's improved IMLI (BrIMLI/TaIMLI)**, with a larger weight on IMLI;
     - **call-stack-based history** in the SC;
     - FTL++-style pipeline-aware updates;
     - **register-value digests** feeding an SC component. This gave "the largest and broadest gain".
   - Results: 3.197 BrMisPKI and 140.3 CycWpPKI on the second halves of the 105 training traces. Total storage 1,570,890 bits (about 192KB).
   - Note: 64KB TAGE-SC-L **allocates two entries per misprediction**, while conventional TAGE allocates one [READ, RUNLTS §4].
2. **TAGE-SC for CBP2025** (André Seznec, SiFive).
   - PDF: https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf [READ]
   - Results:
     - 64KB CBP2016 TAGE-SC-L: 3.750 MPKI on the CBP2025 traces.
     - Brute-force scaled to about 192KB: 3.438 MPKI.
     - CBP2025 TAGE-SC: **3.363 MPKI**.
     - Ablation: TAGE only gives 3.781; TAGE + SC using only TAGE outputs gives 3.612.
   - **Allocation/replacement optimizations** (from the cookbook), quoted in essence:
     - On a TAGE misprediction where the longest-match counter is weak, **also update the alternate entry**.
     - On a misprediction, **allocate several entries in different tables**. The first allocated entry gets u=1, which protects it until the next smooth u-reset.
     - **Probabilistic allocation filtering.** Probabilistic counters estimate confidence in a weak longest-match counter. If that confidence is below 1/2, allocate with probability 1/16; below 16/31, with probability 1/4; below 8/15, with probability 1/2. Allocate more entries when confidence is high.
     - **Protect recently useful entries** by setting u directly to 2, so they survive a full reset interval.
     - 2-way skewed associativity in tagged tables, with elbow-cache/zcache-style reorganization on replacement.
   - SC changes:
     - **BrIMLI**: counts consecutive taken backward branches *within the same 64B region*.
     - **TaIMLI**: the same count, keyed on the *target* region.
     - A doubled IMLI with 4B regions.
     - "Forward path" and "backward path" histories.
     - Adaptive multiplicative weights for the local/IMLI components.
     - Threshold updates only when |sum| > threshold/2.
   - Local history in SC is worth only **about 3%** accuracy.
   - Path history uses 5 bits per branch. History lengths run from 3 to 1000 and are not strictly geometric; middle lengths are favored.
3. **LVCP: A Load Value Correlated Predictor for TAGE-SC-L.** Authors: Yang Man, Lingrui Gou, Yuhang Liu, Yungang Bao, Ninghui Sun (ICT-CAS). 3rd place [READ, closing slides]. I did not read the paper; the idea is load-value correlation.
4. **Bullseye: "Taming Wild Branches: Overcoming Hard-to-Predict Branches using the Bullseye Predictor".** Authors: Behrendt, Pun, Nair (UBC). arXiv:2506.06773, https://arxiv.org/abs/2506.06773 [READ-2nd]. It targets H2P branches. Result at CBP2025: about 0% change on the full set [READ, slides].

### 1.2 TAGE refinements (non-championship)

- **BATAGE: Michaud, "An Alternative TAGE-like Conditional Branch Predictor", ACM TACO 15(3), Article 30, 2018.**
  - DOI 10.1145/3226098, https://dl.acm.org/doi/10.1145/3226098 [READ-2nd]
  - Core idea: replace each TAGE entry's up/down counter and u-bit with **two counters (taken count and not-taken count)**. This gives a Bayesian-style confidence estimate, and it addresses cold counters and thrashing.
  - Claims the design makes the statistical corrector "practically superfluous".
  - Allocation happens only on mispredictions at retirement, with at most one entry per misprediction.
  - Cost: similar storage to TAGE, with simpler SC needs.
  - RUNLTS considered it as a baseline [READ].
- **Seznec, "TAGE: an engineering cookbook", Inria Research Report RR-9561, Nov 2024.**
  - https://hal.science/hal-04804900 [READ-2nd: cited with this ID by both CBP2025 Seznec and RUNLTS; the report itself was not opened]
  - Describes a "realistic" TAGE-SC:
    - 7 physical tagged tables shared among the logical tables;
    - the allocation/replacement refinements listed above;
    - the redefined IMLI;
    - HCpred (the highest-confidence, not-low-confidence match) used as the alternate prediction.
  - Scales from 64Kbit to 512Kbit [READ, as described in CBP2025 Seznec].
  - Has associated code (per Seznec's Inria page, via search snippet).
  - **This is the single most useful recent reference for a TAGE-based student project** [INFERRED].
- **Dynamically Sizing TAGE** (Pruett et al., CBP-5, 2016): see §1.1.

### 1.3 Larger-than-budget or "beyond the predictor" approaches

- **LLBP: Schall, Sandberg, Grot, "The Last-Level Branch Predictor", MICRO 2024**, pp. 464–479.
  - DOI 10.1109/MICRO61859.2024.00042. PDF: https://www.research.ed.ac.uk/en/publications/the-last-level-branch-predictor/
  - Code: https://github.com/dhschall/LLBP (built on the CBP5 framework).
  - Core idea [READ-2nd, abstract and repo]:
    - A large second-level pattern store sits behind TAGE-SC-L.
    - Patterns are organized by **program context** (roughly the call chain, from the `RCR` class).
    - The patterns for upcoming contexts are prefetched into a small, fast "pattern buffer", which hides the backing store's latency.
  - Results: a 512KB LLBP behind a 64KB TAGE-SC-L **reduces MPKI by 0.5–25.9% (avg. 8.9%)** on server workloads. Mispredictions waste 3.6–20% (avg. 9.2%) of cycles on a modern server CPU. Infinite storage would cut mispredictions by up to 36%.
  - Cost: +512KB, **not** comparable to a 64KB budget.
  - Follow-up: LLBP-X ("The Last-Level Branch Predictor Revisited", listed for HPCA 2026), https://github.com/dhschall/LLBP-X [READ-2nd].
- **Whisper: Khan, Ugur, Nathella, Sunwoo, Litz, Jiménez, Kasikci, "Whisper: Profile-Guided Branch Misprediction Elimination for Data Center Applications", MICRO 2022** (Best Paper), pp. 19–34.
  - DOI 10.1109/MICRO56248.2022.00017 [READ-2nd]
  - Core idea: **offline profiling** finds mispredicting contexts and synthesizes small Boolean formulas over hashed history, using read-once monotone Boolean formulas and randomized formula testing. The formulas are injected as **hint instructions**.
  - Results: **−16.8% mispredictions** and a 2.8% average speedup vs. TAGE-SC-L on 12 data-center apps.
  - Needs ISA and compiler support, so it is not applicable to a hardware-only ChampSim predictor.
- **BranchNet: Zangeneh, Pruett, Lym, Patt, "BranchNet: A Convolutional Neural Network to Predict Hard-To-Predict Branches", MICRO 2020**, pp. 118–130.
  - DOI 10.1109/MICRO50266.2020.00022, https://hps.ece.utexas.edu/pub/BranchNet_Micro2020.pdf [READ]
  - Core idea: CNNs are **trained offline** on profiles and predict a few H2P branches; TAGE-SC-L predicts the rest.
  - Big-BranchNet + MTAGE-SC reduces MPKI from 3.42 to 3.16 (−7.6%, up to 15.7%).
  - **Mini-BranchNet: −9.6% MPKI (up to 17.7%) vs. 64KB TAGE-SC-L, with a 1.3% geomean IPC gain (up to 7.9%)**.
  - Big wins on leela, xz, mcf, deepsjeng. Small win on omnetpp (its H2Ps are data-dependent). **No gain on gcc** (many static branches, large footprint). x264, perlbench, xalancbmk, and exchange2 have few H2Ps.
  - Methodology note: an extra 20M warmup for MTAGE-SC gave "not significant" improvement [READ].
  - Requires offline training plus per-binary model weights. **Not feasible** under our online-only interface.
- **Tarsa, Lin, Keskin, Chinya, Wang, "Improving Branch Prediction By Modeling Global History with Convolutional Neural Networks"**, arXiv:1906.09889 (ISCA 2019 AIDArc workshop) [READ-2nd]. It is the precursor to BranchNet: offline-trained CNN "helper" predictors for H2Ps.
- **Branch Runahead: Pruett & Patt, "Branch Runahead: An Alternative to Branch Prediction for Impossible to Predict Branches", MICRO 2021.**
  - DOI 10.1145/3466752.3480053, https://hps.ece.utexas.edu/pub/PruettPatt_BranchRunahead.pdf [READ-2nd]
  - Core idea: extract **dependence chains** for H2P branches and pre-execute them on a separate Dependence Chain Engine, so the outcome is computed before fetch needs it.
  - Needs a data-flow/execution model, so it is not implementable inside `predict_branch(ip)`.
- **BLBP: Garza, Mirbagher-Ajorpaz, Khan, Jiménez (et al.), "Bit-level Perceptron Prediction for Indirect Branches", ISCA 2019**, pp. 27–38.
  - DOI 10.1145/3307650.3322217, https://www.elbagarza.com/pdfs/blbp_isca2019.pdf [READ-2nd]
  - A perceptron predicts the target address bit by bit for **indirect** branches.
  - Not relevant to our interface: old ChampSim only does direction, and its target "prediction" is perfect.

### 1.4 Characterization and "is it solved" papers

- **Lin & Tarsa, "Branch Prediction Is Not A Solved Problem: Measurements, Opportunities, and Future Directions", IISWC 2019**, pp. 228–238.
  - DOI 10.1109/IISWC47752.2019.9042108, arXiv:1906.08170 [READ]
  - They **used ChampSim** with a Skylake-like configuration.
  - With TAGE-SC-L 8KB, mispredictions are an 18.5% IPC opportunity at the baseline pipeline scale. Going from 8KB to 64KB TAGE-SC-L returns only 2.7% IPC.
  - Mispredictions come from (1) a few systematic **H2P** branches and (2) **rare branches** in large code footprints.
  - Across SPECint2017, **55.3%** of mispredictions per 30M-instruction slice come from about 10 H2Ps on average, and the top 5 "heavy hitters" cause 37%.
  - H2P criterion: accuracy below 99% under TAGE-SC-L 8KB, at least 15,000 executions, and at least 1,000 mispredictions per 30M slice.
  - In TAGE-SC-L 64KB, the median number of table allocations per H2P branch is **3,990**, vs. **4** for a non-H2P branch. H2Ps cause allocation thrashing.
  - Per-benchmark table: see §3.
- **Vikas, Gratz, Jiménez, "Workload Characterization for Branch Predictability"**, arXiv:2512.15827 (Dec 2025). It is an archival version of a 2020 TAMU MS thesis.
  - Proposes **branch working-set size** and **branch predictability** as workload descriptors that correlate with TAGE and perceptron MPKI. Uses 2,451 traces [READ-2nd].
- **Feliu, Perais, Jiménez, Ros, "Rebasing Microarchitectural Research with Industry Traces", IISWC 2023**, pp. 100–114.
  - https://webs.um.es/aros/papers/pdfs/jfeliu-iiswc23.pdf [READ-2nd]
  - **ChampSim infers branch type from x86-specific register reads/writes, because the trace format does not encode it.** For converted CVP-1 (AArch64) traces this mis-classifies branches.
  - This matters because it shows how fragile ChampSim's branch-type inference is. For our native x86 DPC-3 traces the inference is the intended use case [INFERRED].

---

## 2. Methodology

### 2.1 Metrics

- **MPKI** = mispredictions / (instructions / 1000), over the measured (post-warmup) region.
  - CBP uses **conditional-branch MPKI** only.
  - **Old ChampSim's printed MPKI counts mispredictions of every branch type** that goes through `predict_branch` (see §4) [READ, code].
  - Note: Lin & Tarsa's "accuracy" and Limaye's "mispredict rate" are per-branch rates, not MPKI. Converting requires branch density: MPKI ≈ (branches/instr) × mispredict rate × 1000.
- **Accuracy** = (branches − mispredicts) / branches. It is dominated by easy branches. Prefer MPKI.
- **IPC / speedup.** CBP2025 adds **CycWpPKI** (wrong-path cycles per kilo-instruction), a timing-aware metric. In old ChampSim the equivalent signal is IPC.

### 2.2 Storage budgets (how papers compare)

| Competition | Budget |
|---|---|
| CBP-5 (2016) | 8KB, 64KB, and unlimited tracks, each +2048 bits allowance [READ-2nd] |
| CBP2025 | 192KB [READ] |

- Papers (TAGE-SC-L, RUNLTS, Seznec 2025) give a **bit-level storage table** per component: entries × (counter + tag + u bits), plus history registers, and they separately list "prediction-time" structures.
- **Recommendation:** for our ~64KB, include a storage-accounting table in the report, in bits, for every table and history register. Compare against the 64KB CBP2016 TAGE-SC-L as the reference point.

### 2.3 Warmup and simulation length

| Setting | Values | Status |
|---|---|---|
| **DPC-3 official** (our traces come from DPC-3) | **50M warmup, 250M simulated instructions**. 46 SPEC CPU2017 traces with LLC MPKI ≥ 1, unweighted. Score = geomean of single-core speedups + geomean of 4-core speedups. Source: https://dpc3.compas.cs.stonybrook.edu/slides/dpc3_opening.pdf | [READ] |
| **CBP2025** | first half warmup, second half measured | [READ] |
| **Local `run_champsim.sh`** | takes N_WARM and N_SIM in **millions**. The README example is 1M/10M. The default in `main.cc` is warmup 1,000,000 and sim 10,000,000 | [READ] |
| Common ChampSim paper practice | "50M warmup / 200M sim" is widespread. The DPC-3 rule is 50M/250M | [INFERRED for the 200M variant; I did not find a single authoritative source for it] |

- **Branch predictor warm-up sensitivity:** BranchNet found +20M extra warmup for an unlimited MTAGE-SC "not significant" [READ]. A 64KB TAGE warms well within tens of millions of instructions [INFERRED].
- **Trace wrap-around:** if a trace ends, ChampSim prints `*** Reached end of trace ... Repeating trace` and restarts it [READ, `ooo_cpu.cc` lines 31–35]. The predictor would then re-see the same code, which inflates accuracy. **Check for this message in every output file.**
- The DPC-3 traces are SimPoint-selected regions, "max simpoint only" per the README [READ]. The suffix (e.g., `-1152B`) is commonly understood as the number of billions of instructions skipped [INFERRED; not verified].

### 2.4 Aggregation across benchmarks

- **MPKI:** report the per-trace table plus the **arithmetic mean MPKI**. This is the CBP-5 weighted average and the CBP2025 arithmetic mean [READ]. The arithmetic mean of MPKI is meaningful because MPKI is a rate per fixed unit of work, but it is dominated by the high-MPKI traces (mcf, xz) [INFERRED].
- **IPC:** report the **geometric mean of per-trace speedups** (IPC_new / IPC_base), as DPC-3 does [READ]. The classic justification for geomean of normalized ratios is Fleming & Wallace, "How not to lie with statistics: the correct way to summarize benchmark results", CACM 29(3):218–221, 1986, DOI 10.1145/5666.5673 [READ-2nd]. See also L. K. John, "More on finding a single number to indicate overall performance of a benchmark suite", SIGARCH CAN 32(1):3–8, 2004 [READ-2nd].
- **Avoid averaging % MPKI reductions** across traces with tiny MPKI. For example, cactuBSSN at about 0.0x MPKI can show ±50% from a handful of mispredicts. If you report relative reductions, use the reduction of the mean MPKI, or a geomean of MPKI ratios with an epsilon, and say which [INFERRED].
- Optionally split **INT** (gcc, mcf, omnetpp, xalancbmk, x264, deepsjeng, xz) vs. **FP** (cactuBSSN, lbm, imagick) subtotals. Branch effects concentrate in INT.

### 2.5 Statistical caveats

1. **Simulation is deterministic.** There is no run-to-run noise, so confidence intervals over repeated runs are meaningless. The real uncertainty is **sampling**: one SimPoint per benchmark may not represent the whole program. Lin & Tarsa found 9.5 phases per 10B-instruction workload on average [READ].
2. **Overfitting / tuning on the test set.** We have only 10 traces. CBP2025's training vs. full-set gaps show tuned gains shrink on unseen traces: RUNLTS went from −7.2% to −5.3%, and MPP2025 from −1.1% to about −0.3% [READ]. Mitigations [INFERRED]:
   - Tune on a different region (e.g., warmup offset or a short early window).
   - Or tune on 5 traces and validate on the other 5.
   - Report the final numbers only once.
3. **Small differences are not meaningful.** For example, a 0.01-MPKI difference on a 200M window corresponds to 2,000 mispredicts. It is real but may not generalize [INFERRED].
4. **Old-ChampSim timing model limits IPC conclusions** (see §4). Use MPKI as the primary metric and IPC as secondary.

---

## 3. Characterization of our 10 SPEC CPU2017 workloads

Sources:
- **L&A** = Limaye & Adegbija, "A Workload Characterization of the SPEC CPU2017 Benchmark Suite", ISPASS 2018, pp. 149–158, DOI 10.1109/ISPASS.2018.00028, https://tosiron.com/papers/2018/SPEC2017_ISPASS18.pdf [READ]. Intel hardware counters (`br_inst_exec.all_branches`, `br_misp_exec.all_branches`), whole ref runs, *all* branch types, the real Intel predictor.
- **L&T** = Lin & Tarsa IISWC 2019, Table I [READ]: TAGE-SC-L **8KB**, expanded inputs, 10B-instruction traces. The PDF text extraction scrambled the column layout, so the column-to-value mapping is my reconstruction [INFERRED but consistent].
- **BN** = BranchNet MICRO 2020, Fig. 1 [READ, FIG~]: **64KB TAGE-SC-L** MPKI on SPECint2017 speed, SimPoint-weighted ref inputs.

Facts stated in L&A's text [READ]:
- Branches average 14.743% of instructions; 78.662% of those are conditional.
- **605.mcf_s has the highest branch share (32.939%)** and **619.lbm_s the lowest (3.646%)**.
- INT has higher mispredict rates than FP; the average is 2.198%.
- 641.leela_s is the worst at 8.636%.

| Trace | L&A % branches (Fig 3b) [FIG~] | L&A mispredict rate % (Fig 6b) [FIG~] | Implied HW MPKI [INFERRED = col2×col3×10] | L&T TAGE-SC-L-8KB accuracy / % mispreds from H2Ps | BN 64KB TAGE-SC-L MPKI [FIG~] | Branch character (summary) |
|---|---|---|---|---|---|---|
| 602.gcc_s-1850B | ~23 | ~2.4 | ~5.5 | not in Table I (L&T excluded gcc as large-footprint, "rare branches") | ~3.6 | Large code footprint, many static branches each contributing a little. BranchNet: **no gain**. Capacity/aliasing-bound, so more TAGE entries and good allocation help most. |
| 605.mcf_s-1152B | **~33 (highest)** | ~4.6 | ~15 | 0.921 / **96.9%** | **~14.5 (highest)** | Very branch-dense, few static branches (median 99/slice). Data-dependent H2Ps, e.g. qsort comparisons (BN). Dominates the arithmetic-mean MPKI. |
| 607.cactuBSSN_s-2421B | ~4 | ~0.1 | ~0.04 | n/a (FP) | n/a | Loop-dominated FP code; near-perfectly predictable. |
| 619.lbm_s-2676B | **3.6 (lowest, text)** | ~1.7 | ~0.6 | n/a | n/a | Very few branches. Low MPKI despite a nonzero rate. Memory-bound, so IPC is insensitive to the BP. |
| 620.omnetpp_s-141B | ~23 | ~2.5 | ~5.8 | 0.975 / 77.6% | ~3.9 | Pointer-chasing discrete-event simulation. H2Ps are **data-dependent** (BN: small CNN gain). Misses on long-latency loads make each mispredict expensive in IPC [INFERRED]. |
| 623.xalancbmk_s-10B | ~24 | ~0.4 | ~1.0 | **0.997** / 28.6% | ~0.4 | Branch-dense but highly predictable. Second-largest code footprint after gcc (L&T). |
| 625.x264_s-12B | ~4.5 | ~2.8 | ~1.3 | 0.946 / 54.2% | ~0.8 | Few branches overall. Some H2Ps in motion search/encoding decisions [INFERRED]. |
| 631.deepsjeng_s-928B | ~15.5 | ~3.4 | ~5.3 | 0.946 / 31.2% (many static H2Ps: ~40 per input) | ~3.9 | Chess search. Many moderately hard branches spread out, so the gain from any single fix is limited. |
| 638.imagick_s-824B | ~11 | ~0.4 | ~0.4 | n/a | n/a | FP image processing; mostly regular loops. |
| 657.xz_s-2302B | ~17 | ~6.9 | ~12 | **0.897 (lowest of L&T's set excl. leela)** / **80.5%** | ~7.1 | Compression: data-dependent match/literal decisions. H2P-heavy (63 static H2Ps per input). BranchNet: large gain. |

**Expected ranking on our traces** [INFERRED; verify with a bimodal/gshare baseline run]:
- **mcf > xz > {gcc, omnetpp, deepsjeng} > {x264, xalancbmk} > {lbm, imagick, cactuBSSN}**.
- Single DPC-3 SimPoints can deviate from whole-program numbers. The DPC-3 trace selection (LLC MPKI ≥ 1) was chosen for memory behaviour, not branches.
- The FP traces will contribute almost nothing to mean MPKI. Treat them as "do no harm" sanity checks: a complex predictor should not regress them through aliasing or slow warmup.

Related: Panda, Song, Dean, John, "Wait of a Decade: Did SPEC CPU 2017 Broaden the Performance Horizon?", HPCA 2018, pp. 271–282, DOI 10.1109/HPCA.2018.00032 [READ-2nd]. PCA-based redundancy and similarity analysis of CPU2017. I did not extract branch numbers from it.

---

## 4. ChampSim versions and the branch-prediction model

### 4.1 OLD ChampSim (this project; verified in local source) [READ]

- **Interface.** Defined in `inc/ooo_cpu.h:212-215` as O3_CPU member functions:
  ```cpp
  uint8_t predict_branch(uint64_t ip);
  void    initialize_branch_predictor(), last_branch_result(uint64_t ip, uint8_t taken);
  ```
  The predictor is a `branch/*.bpred` file, selected by `build_champsim.sh`. Tables are typically indexed `[NUM_CPUS]`, as in `branch_predictor.cc`.
- **Which branches are predicted.** `src/ooo_cpu.cc:343-385` (non-CloudSuite path; the CloudSuite path is at 103-135):
  - For every instruction with `is_branch`, it calls `predict_branch(ip)` and then **immediately** `last_branch_result(ip, branch_taken)`.
  - Branch type is inferred at trace-read time (`ooo_cpu.cc:280-329`) from register read/write patterns (SP, flags, IP, other).
  - Direct jumps, indirect branches, calls, indirect calls, and returns are forced `branch_taken = 1`.
  - So **all branch types** (conditional, direct jump, indirect, call, indirect call, return, other) go through the direction predictor. The predictor **does not receive the type or target**, so it must learn "always taken" per IP for unconditional branches.
- **Misprediction** = `branch_taken != prediction` (direction only).
  - There is **no BTB/target modelling**: a taken prediction is treated as having the correct target. `branch_target` is set from the next trace IP and only passed to the L1I prefetcher hook.
  - On a mispredict after warmup, `fetch_stall = 1` (`ooo_cpu.cc:363-373`).
  - When the mispredicted branch **completes execution**, `fetch_resume_cycle = current + BRANCH_MISPREDICT_PENALTY` (`ooo_cpu.cc:1728-1731, 1750-1753`).
  - `BRANCH_MISPREDICT_PENALTY` is **1** (`inc/ooo_cpu.h:23`).
  - So the effective penalty is **branch-resolution latency + 1 cycle**. There is no wrong-path fetch, execution, or cache pollution.
  - A correct taken prediction ends the fetch group for the cycle (`instrs_to_read_this_cycle = 0`).
  - Core parameters: FETCH_WIDTH 6, ROB 352 (`inc/instruction.h:6`), DECODE_LATENCY 2.
- **Warmup.**
  - During warmup, mispredictions are counted but **do not stall fetch**, while the predictor trains normally.
  - At `finish_warmup()` (`src/main.cc:172-205`), `num_branch`, `branch_mispredictions`, and the type counters are reset.
- **Stats printed** (`src/main.cc:97-114`):
  - `Branch Prediction Accuracy = (num_branch - mispred)/num_branch`, where **the denominator includes all branch types**. That inflates accuracy with trivially predictable unconditionals.
  - `MPKI = 1000*mispred/(num_retired - warmup_instructions)`. Mispredictions are counted at **fetch** and instructions at **retire**, a negligible mismatch.
  - Type breakdown: NOT_BRANCH, DIRECT_JUMP, INDIRECT, CONDITIONAL, DIRECT_CALL, INDIRECT_CALL, RETURN, OTHER.
- **Update timing.** `last_branch_result` runs in the same cycle as the prediction, with the true outcome. That gives **perfect, immediate history and table update**: no speculative-history repair, no update delay, no prediction latency.
  - This is more idealized than CBP2025, where tables update at resolve time ("The CBP2025 framework implements it at branch resolution time !!" [READ, Seznec footnote 6]).
  - Large or slow predictors are therefore flattered [INFERRED].
- **Integrity caveat** [INFERRED].
  - Because `predict_branch` is an `O3_CPU` member function, the predictor code *could* read `IFETCH_BUFFER` (including `branch_type` and even `branch_taken`). Reading the outcome or type that way would be oracle leakage or interface violation.
  - The predictor should use only `ip` and the outcomes delivered via `last_branch_result`.
  - It is fine to infer "this IP has never been not-taken", which is legitimately learned.
- **Trace wrap:** see §2.3.

### 4.2 NEWER ChampSim (GitHub develop branch) [READ-2nd, via fetch of `branch/hashed_perceptron/hashed_perceptron.h` and `src/ooo_cpu.cc`]

- Signatures:
  ```cpp
  bool predict_branch(champsim::address pc, champsim::address predicted_target, bool always_taken, uint8_t branch_type);
  void last_branch_result(champsim::address pc, champsim::address branch_target, bool taken, uint8_t branch_type);
  ```
  These are modules (one directory per predictor) and there is a separate **BTB module** interface.
- Prediction is called for every instruction going into the fetch buffer. The result is OR-ed with the BTB's `always_taken`.
- A mispredict = **target mismatch** (any type), or **direction mismatch for conditional/other**.
- Some mispredicts (direct jumps/calls; conditionals with correct direction but wrong target) are resolved **at decode** (`fetch_resume_time = now + BRANCH_MISPREDICT_PENALTY`); others resolve at execute.
- Stats are per branch type (`branch_type_misses`) and region-of-interest snapshots.
- Implications for comparing with our old version [INFERRED]:
  - Newer ChampSim MPKI includes BTB/target misses and separates types.
  - The old version's MPKI is direction-only over all types.
  - Numbers are **not directly comparable** across versions, or with CBP (conditional-only, perfect non-conditional).
- ChampSim reference paper: Gober, Chacon, Wang, Gratz, Jiménez, Teran, Pugsley, Kim, "The Championship Simulator: Architectural Simulation for Education and Competition", arXiv:2210.14324, 2022 [READ-2nd].

---

## 5. Recommendations for this project

### 5.1 Methodology (concrete)

1. **Tuning runs:** 10M warmup + 50M sim, used only to screen ideas [INFERRED; for speed].
2. **Final runs:** **50M warmup + 200M sim** (`./run_champsim.sh <bin> 50 200 <trace>`). Use 50M/250M if time allows, to match DPC-3 exactly.
   - Grep outputs for "Reached end of trace". If it appears, the window is too long for that trace.
   - Sensitivity check: rerun the best predictor and the baseline with 100M warmup. The ranking should not change.
3. **Report:**
   - per-trace MPKI and IPC;
   - **arithmetic mean MPKI** (all 10 traces, plus the INT-7 subset);
   - **geomean IPC speedup** vs. the bimodal (or gshare) baseline;
   - a storage table in bits.
4. **State the caveats** in the report:
   - MPKI includes all branch types (old ChampSim);
   - immediate, non-speculative update;
   - the penalty model (resolve + 1 cycle, no wrong path);
   - one SimPoint per benchmark;
   - only 10 traces, so overfitting risk.
5. **Do not average % reductions** that include near-zero-MPKI FP traces.

### 5.2 Most promising recent ideas feasible within `predict_branch(ip)` / `last_branch_result(ip, taken)` and ~64KB

1. **Baseline: a faithful 64KB TAGE-SC-L (CBP2016)** with TAGE, SC, and loop predictor.
   - Feed **all** branches into global/path history. They are all we see. Including unconditionals as path information is consistent with CBP practice [INFERRED].
   - Expected: the largest single MPKI drop vs. bimodal or hashed perceptron.
2. **TAGE allocation/replacement refinements** (Seznec cookbook 2024 / CBP2025; RUNLTS throttling). These are **pure policy and need ~0 extra bits**:
   - multi-entry allocation, with the first entry protected (u=1);
   - **probabilistic allocation filtering** based on the confidence of weak longest-match entries;
   - u=2 protection for recently useful entries;
   - update the alternate entry on a weak-provider mispredict;
   - optionally RUNLTS-style thrashing detection via the repurposed (ctr ∈ {0,−1}, u=1) states.

   This directly targets the **H2P allocation-thrashing** pathology quantified by Lin & Tarsa (3,990 allocations per H2P vs. 4). It should help mcf, xz, and gcc (capacity) most [INFERRED].
   - Seznec's CBP2025 TAGE gained 3.438 → 3.363 MPKI at 192KB from these plus SC/IMLI changes.
   - The gain at 64KB is unknown and possibly smaller [INFERRED].
3. **IMLI-style components in the SC** (Seznec's BrIMLI, i.e. same-region backward-taken counts).
   - The original IMLI needs "backward taken" and therefore a target. Our interface gives only IPs and outcomes.
   - Approximation [INFERRED]: treat a taken branch whose *next observed branch IP* is ≤ its own IP as backward-taken. A loop-closing branch at X with target T < X is followed by branches in [T, X].
   - TaIMLI (target region) cannot be computed exactly. BrIMLI (branch region) can, given that backward detection.
   - Benefit is in loop-nest-heavy codes (imagick, cactuBSSN, x264, possibly xz). It is small on mean MPKI because those traces already have low MPKI.
- **Not feasible here:**
  - RUNLTS register digests, LVCP, and BALL need register/load **values**, and the old trace has register IDs only.
  - LLBP needs a 512KB backing store.
  - BranchNet, Tarsa CNN, and Whisper need offline profiling/training and ISA hints.
  - Branch Runahead needs dependence-chain execution.
  - BLBP is for indirect *targets*, which are not modelled.
  - Call-stack history (RUNLTS) needs call/return identification, which `predict_branch(ip)` does not provide [INFERRED].

---

## 6. Sources

### Championships
- CBP2025 home/rules: https://ericrotenberg.wordpress.ncsu.edu/cbp2025/ [READ]
- CBP2025 simulator/traces page: https://ericrotenberg.wordpress.ncsu.edu/cbp2025-simulator-framework/ [READ]
- CBP2025 closing slides (results): https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/CBP2025-Closing-Remarks.pdf [READ]
- CBP2025 traces (Zenodo): https://zenodo.org/records/15883615 [READ-2nd]
- Seznec, "TAGE-SC for CBP2025": https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf [READ]
- Koizumi et al., "RUNLTS": https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final44-Koizumi.pdf [READ]
- Behrendt, Pun, Nair, "Taming Wild Branches … Bullseye": https://arxiv.org/abs/2506.06773 [READ-2nd]
- CBP-5 (2016): https://jilp.org/cbp2016/ and https://jilp.org/cbp2016/program.html [READ-2nd]
- Seznec, "TAGE-SC-L Branch Predictors Again", CBP-5: https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf [READ-2nd]
- Jiménez, "Multiperspective Perceptron Predictor", CBP-5: https://jilp.org/cbp2016/paper/DanielJimenez1.pdf [READ-2nd]
- Pruett et al., "Dynamically Sizing the TAGE Branch Predictor", CBP-5: https://jilp.org/cbp2016/paper/StephenPruettFinal.pdf [READ-2nd]
- DPC-3 opening slides (methodology): https://dpc3.compas.cs.stonybrook.edu/slides/dpc3_opening.pdf [READ]

### Papers
- Seznec, "TAGE: an engineering cookbook", Inria RR-9561, 2024: https://hal.science/hal-04804900 [READ-2nd]
- Michaud, "An Alternative TAGE-like Conditional Branch Predictor" (BATAGE), TACO 2018: https://dl.acm.org/doi/10.1145/3226098 [READ-2nd]
- Schall, Sandberg, Grot, "The Last-Level Branch Predictor", MICRO 2024: https://www.research.ed.ac.uk/en/publications/the-last-level-branch-predictor/ ; code https://github.com/dhschall/LLBP ; LLBP-X https://github.com/dhschall/LLBP-X [READ-2nd]
- Khan et al., "Whisper", MICRO 2022: https://dl.acm.org/doi/10.1109/MICRO56248.2022.00017 [READ-2nd]
- Zangeneh, Pruett, Lym, Patt, "BranchNet", MICRO 2020: https://hps.ece.utexas.edu/pub/BranchNet_Micro2020.pdf [READ]
- Tarsa et al., "Improving Branch Prediction By Modeling Global History with CNNs", arXiv:1906.09889: https://arxiv.org/abs/1906.09889 [READ-2nd]
- Pruett & Patt, "Branch Runahead", MICRO 2021: https://hps.ece.utexas.edu/pub/PruettPatt_BranchRunahead.pdf [READ-2nd]
- Garza et al., "Bit-level Perceptron Prediction for Indirect Branches", ISCA 2019: https://www.elbagarza.com/pdfs/blbp_isca2019.pdf [READ-2nd]
- Lin & Tarsa, "Branch Prediction Is Not A Solved Problem", IISWC 2019: https://arxiv.org/abs/1906.08170 [READ]
- Vikas, Gratz, Jiménez, "Workload Characterization for Branch Predictability", arXiv:2512.15827: https://arxiv.org/abs/2512.15827 [READ-2nd]
- Feliu, Perais, Jiménez, Ros, "Rebasing Microarchitectural Research with Industry Traces", IISWC 2023: https://webs.um.es/aros/papers/pdfs/jfeliu-iiswc23.pdf [READ-2nd]
- Limaye & Adegbija, "A Workload Characterization of the SPEC CPU2017 Benchmark Suite", ISPASS 2018: https://tosiron.com/papers/2018/SPEC2017_ISPASS18.pdf [READ]
- Panda, Song, Dean, John, "Wait of a Decade: Did SPEC CPU 2017 Broaden the Performance Horizon?", HPCA 2018: https://www.semanticscholar.org/paper/0231ffa4b9b095efbf0f302898cd7abd7dd0b764 [READ-2nd]
- Gober et al., "The Championship Simulator", arXiv:2210.14324: https://arxiv.org/abs/2210.14324 [READ-2nd]
- Fleming & Wallace, "How not to lie with statistics…", CACM 1986, DOI 10.1145/5666.5673 [READ-2nd]
- John, "More on finding a single number…", SIGARCH CAN 2004 [READ-2nd]
- Newer ChampSim source: https://github.com/ChampSim/ChampSim (develop branch: `src/ooo_cpu.cc`, `branch/hashed_perceptron/hashed_perceptron.h`) [READ-2nd, via fetch summary]

### Local code read
All paths are under `/home/maahi/BRANCH_PREDICTOR_PROJECT/champsim/`:
- `src/ooo_cpu.cc`: lines 25–35, 95–140, 270–390, 555–562, 1720–1760
- `src/main.cc`: lines 8–17, 97–114, 172–205, 520–570, 860–935
- `inc/ooo_cpu.h`: lines 16–23, 76–83, 212–219
- `inc/instruction.h`: line 6
- `branch/branch_predictor.cc`
- `run_champsim.sh`
- `README.md`
