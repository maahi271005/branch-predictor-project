# Topic C: loop prediction, IMLI, confidence estimation, and hard-to-predict (H2P) branches

Author: research sub-agent C. Date: 2026-10-30.
Scope: literature extraction, plus a small proxy measurement study on our 10 DPC-3 traces. I changed nothing under the project except creating this file.

**Legend.** **[READ]** means I read the primary text (PDF or source code) myself. **[PARTIAL]** means I read only some sections. **[NOT READ]** means I know it only from search-engine snippets or citations, so treat any details as unverified. **[INFERRED]** marks my own reasoning. **[MEASURED]** marks numbers from my proxy simulator (Section 7). Those numbers are not from ChampSim and not from the project's predictor.

---

## 0. TL;DR for the team

1. **Backward-branch detection needs no target and no core change.** In our interface, `predict_branch(ip)` is called for every branch in program order. Let X be a branch that was taken, and let Y be the IP of the next branch passed to `predict_branch`. Then **X was a backward branch (target <= X) if and only if Y <= X.**
   - Proof: execution from X's target T is sequential up to Y, so T <= Y. If T <= X, sequential execution from T reaches X itself (a branch) or an earlier branch, so Y <= X. If T > X, then Y >= T > X.
   - **[MEASURED]** This agreed with the true target (the trace's next-instruction IP) on **100.00000%** of taken branches. That covers all 10 traces, 90M instructions each, about 74M taken branches in total.
   - This enables IMLI, BrIMLI/TaIMLI, backward-branch global history, and loop-branch identification. The information arrives one branch late, but that is exactly when a real design would use it: before predicting the next branch.
2. **IMLI** (Seznec et al., MICRO 2015) is cheap: 708 bytes for both components in the paper. In 2015 it gave about 6–7% MPKI reduction on the CBP3 and CBP4 traces. Two caveats come from Seznec himself:
   - His CBP2016 code comments call IMLI-SIC "a big disappointment on CBP2016 traces".
   - His 2024 cookbook says IMLI "was found as disappointing". His re-engineered BrIMLI/TaIMLI recovered about 0.05 MPKI (around 1.5%) on the CBP2025 traces.
   - Expect a small gain, mostly on loop-heavy code. It needs an SC/perceptron-style adder to plug into.
3. **H2P concentration on our traces:**
   - **[MEASURED]** On a 52 KB TAGE proxy, the H2P branches (Lin and Tarsa criteria) cause:
     - **94%** of mispredictions on mcf, with 13–14 H2P branches.
     - **83%** on xz (19 H2Ps).
     - **86%** on omnetpp (11–12 H2Ps).
     - **20–32%** on deepsjeng (11–20 H2Ps).
     - About 0% on gcc, xalancbmk, cactuBSSN, imagick and x264.
   - mcf (17.4 MPKI) and xz (11.2 MPKI) alone carry about **74%** of the 10-trace mean-MPKI mass. deepsjeng and omnetpp add another 23%.
   - **These four traces are where any gain must come from.**
4. **Per-branch H2P allocation throttling is a double-edged sword.** **[MEASURED, proxy]** Allocating with probability 1/4 for online-detected H2P PCs:
   - helps mcf (−1.5%), xz (−0.9%) and omnetpp (−0.9%);
   - **hurts deepsjeng by +4.1%**;
   - nets −0.57% on the mean.
   - At probability 1/16, deepsjeng loses 8%. Restricting H2P allocations to short-history tables hurts badly (+2.8% mean).
   - Prior art already does global (not per-branch) allocation filtering: TAGE-SC-L, BATAGE CAT, the Seznec 2024 cookbook and RUNLTS (CBP2025). Bullseye (CBP2025) suppresses TAGE updates per PC, but only after a perceptron has taken over that PC.
5. **A loop predictor is a marginal gain.** In the literature it gives 0.3–1.2% (Seznec CBP2014/2016). **[MEASURED, proxy]** I saw −0.07% on the mean. It is cheap (about 160–312 B), so keep a small one only if there is spare budget.
6. **TAGE confidence by counter value works as published.** **[MEASURED]** In the proxy, weak and nearly-weak providers mispredict 30–39% of the time. Saturated providers mispredict 0–6%. On mcf and xz, though, the saturated class still holds about 40% of all mispredictions.
   - That is the "confidently wrong" behaviour typical of H2P branches. It argues for an SC-style corrector over raw confidence gating.

---

## 1. IMLI: Seznec, San Miguel, Albericio, MICRO 2015 **[READ]**

- **Citation:** A. Seznec, J. San Miguel, J. Albericio, "The Inner Most Loop Iteration counter: a new dimension in branch history", MICRO-48, 2015, pp. 347–357. DOI 10.1145/2830772.2830831. HAL record: hal-01208347.
- **Accessed:** https://www.irisa.fr/alf/downloads/seznec/IMLI.pdf (author's copy, full text read).

### 1.1 IMLI counter definition (verbatim logic)
- "We consider that any backward conditional branch is a loop exit branch." An inner-most loop is one "whose body does not contain any backward branch".
- "IMLIcount [is] the number of times that the last encountered backward conditional branch has been consecutively taken." The heuristic, from Section 4.1:
  ```
  if (backward) { if (taken) IMLIcount++; else IMLIcount = 0; }
  ```
- "In practice, IMLIcount will be 1 or 0 on the first iteration depending on the construction of the multidimensional loop."
- Speculative management means checkpointing the counter (10 bits). The text says the new count is derived from the "presence/absence of any forward branches in the instruction fetch block". "Forward" looks like a typo for "backward" **[INFERRED]**.

### 1.2 IMLI-SIC (Same Iteration Correlation)
- Targets branches where Out[N][M] ≈ Out[N−1][M], i.e. the same inner iteration number gives the same outcome.
- A single table indexed by a **hash of (PC, IMLIcount)** is added to the statistical corrector (SC) of TAGE-GSC, or to GEHL. It is summed like any other neural table.
- 512 entries "capture most of the potential benefit". The benefit grows further if IMLIcount is also inserted into the indices of two global-history SC tables.
- IMLI-SIC subsumes most of the loop predictor. With TAGE-GSC, the loop predictor's benefit dropped from 0.034 to 0.013 MPKI on CBP4, and from 0.094 to 0.010 on CBP3.
- **Results:** TAGE-GSC went from 2.473 to 2.373 MPKI on CBP4, and from 3.902 to 3.733 on CBP3. The gains came mostly from a few traces: SPEC2K6-04 (−2.37), SPEC2K6-12 (−1.16), WS04 (−3.20), MM07 (−2.17) and CLIENT02 (−0.64). Most other traces did not change.

### 1.3 IMLI-OH (Outer History)
- Targets Out[N][M] correlated with Out[N−1][M] and Out[N−1][M−1], the same correlation the Wormhole predictor exploits.
- **IMLI history table:** 1 Kbit. "The outcome of a branch at address B is stored at address (B*64)+IMLIcount." That tracks 16 distinct branch addresses × 64 iterations.
- **PIPE vector:** 16 bits. It holds Out[N−1][M] before it is overwritten.
- **IMLI-OH predictor table:** 256 entries, indexed by PC hashed with Out[N−1][M] and Out[N−1][M−1].
- A delayed-update experiment (up to 63 branches) cost 0.002 MPKI.
- IMLI-OH on top of IMLI-SIC gave a further ~2.0–2.3%.

### 1.4 Storage and totals
- **708 bytes in total:** a 384 B IMLI-SIC table, a 128 B history table, a 192 B OH table, and 4 B for PIPE plus the counter.
- **TAGE-GSC:** 2.473 → 2.313 MPKI on CBP4 (−6.8%) and 3.902 → 3.649 on CBP3 (−6.1%).
- **Table 1 (TAGE-GSC):**

  | Config | Size | CBP4 MPKI | CBP3 MPKI |
  |---|---|---|---|
  | Base | 228 Kbit | 2.473 | 3.902 |
  | +L (local + loop) | 256 Kbit | 2.365 | 3.670 |
  | +I (IMLI) | 234 Kbit | 2.313 | 3.649 |
  | +I+L | 261 Kbit | 2.226 | 3.555 |

- The best configuration (TAGE-SC-L + IMLI at 256 Kbit) reached 2.228 MPKI, against 2.365 for CBP4's TAGE-SC-L.

### 1.5 How the CBP2016 TAGE-SC-L code actually uses IMLI **[READ: source]**
Sources: the gem5 port (`src/cpu/pred/statistical_corrector.cc`, `tage_sc_l_64KB.cc`, `BranchPredictor.py`) and the LLBP repository copy of Seznec's code (`bpmodels/tage/tage_scl.cc`).

- **Counter update:** it runs only for conditional direct branches. If `target < PC`, a not-taken outcome sets `IMLIcount = 0`; a taken outcome increments it, saturating at 2^8 − 1. In the same place, the SC's backward-taken history is updated: `BWHIST = (BWHIST<<1) + (taken & (target<PC))`.
- **IMLI-SIC:** one GEHL table, `Gpredict(PC, IMLIcount, Im={8}, INB=1, LOGINB=8)`, which works out to 128 effective entries of 6-bit counters. The index is `(PC ^ h ^ h>>(8-i) ^ ...) & mask`. The table's output is scaled by a per-PC-group dynamic weight of ×1 or ×2.
- **"Constant-IMLI" history (IMHIST), the CBP2016 successor of IMLI-OH:** `IMHIST[IMLIcount] = (IMHIST[IMLIcount]<<1) + taken` runs on every conditional branch. This keeps 256 histories of 10 bits, one per IMLI value. It feeds 2 GEHL tables with lengths {10, 4} and 2×256 entries.
- The original code comments: `// IMLI-SIC -> Micro 2015 paper: a big disappointment on CBP2016 traces`. The CBP2016 paper (Section 6) says "IMLI-based table improves by 0.2%".

### 1.6 Later evolution **[READ]**
- **Seznec, "TAGE-SC for CBP2025"** (CBP2025 workshop) and the **TAGE cookbook** (Inria RR-9561, 2024, hal-04804900) define:
  - **BrIMLI:** the number of consecutive taken backward branches *within the same region* (256 B in the cookbook, 64 B in CBP2025). It is "reset on the first taken backward branch that does not belong to the region".
  - **TaIMLI:** the same idea, but keyed on the *target* region.
  - These cover "loops with multiple exit points, nested loops, etc." CBP2025 adds a second pair with 4-byte regions (exact PC or exact target). There are 4 tables of 2K entries in total.
  - Reported contribution: 0.050 MPKI out of 3.363, against 0.013 for IMLI in the 192 KB CBP2016 code. "This new form of IMLI is able to correctly predict most loops with constant number of iterations."
  - The cookbook also uses a "global forward path" (taken forward branches only) and a "filtered backward path" (the backward path recorded only when BrIMLI or TaIMLI resets).
- **Multiperspective Perceptron** (Jiménez, CBP2016; gem5 `multiperspective_perceptron.cc`) **[READ: source]** keeps four IMLI-style counters: backward-taken, backward-not-taken, forward-taken and forward-not-taken runs. All four need `target < pc`.

### 1.7 Applicability to our interface **[INFERRED + MEASURED]**
- **Backward-ness of taken branches is exact,** with no target needed (Section 0, item 1).
- **Backward-ness of not-taken branches** is needed for the IMLI reset. It is a static property, so learn it from the branch's earlier taken instances: one bit per PC, in a small direct-mapped table such as 4K × 1 bit (512 B). A loop branch is almost always taken before it is first not-taken. Alternative: reset when the PC of the last counted backward branch is not taken.
- **"Conditional" filter:** our interface also delivers jumps, calls and returns. ChampSim forces their outcome to taken. Two options:
  - Count only PCs that have been seen not-taken at least once (1 bit per PC, which can share the same table).
  - Use Seznec's BrIMLI definition. It never needs the "not-taken backward" event at all, because a backward taken branch from a different region resets the counter. **This is the most robust choice for our interface.**
- **[MEASURED]** IMLI with the conditional filter matched type-aware "true" IMLI at:
  - 99.0% of conditional predictions on mcf, 99.8% on x264, 95% on xz, and 86% on deepsjeng and imagick;
  - only 0.3%, 0%, 1% and 9% on gcc, lbm, cactuBSSN and omnetpp.
  The low numbers come from never-exiting backward conditional branches (outer or event loops) that saturate "true" IMLI. That is a property of the IMLI definition, not of the inference.
- **Minimal core change, if allowed:** pass `branch_target` and `branch_type` (both already in `ooo_model_instr`; see `src/ooo_cpu.cc` line 335) to the predictor. **This is not needed for IMLI.**

---

## 2. Lin and Tarsa: "Branch Prediction Is Not a Solved Problem" **[READ arXiv v1]**

- **Citation:** C.-K. Lin and S. J. Tarsa (Intel), IISWC 2019 (IEEE Xplore 9042108).
- **Accessed:** https://arxiv.org/pdf/1906.08170 (v1, 13 Jun 2019). I did **not** access the IEEE version, which may differ.

**Setup**
- ChampSim with a Skylake-like pipeline, using CBP2016 TAGE-SC-L 8KB and 64KB.
- SPECint 2017 with expanded inputs: 10B-instruction traces cut into 30M-instruction slices.
- Large-code-footprint (LCF) traces: gcc plus 5 production applications.

**H2P definition (per 30M-instruction slice, under TAGE-SC-L 8KB)**
- less than 99% prediction accuracy;
- at least 15,000 executions;
- at least 1,000 mispredictions.

**Statistics**
- **Concentration:**
  - About 29 H2Ps per benchmark appear in 3 or more inputs.
  - On average, **55.3% of mispredictions in a slice come from about 10 H2Ps.**
  - The top 5 "heavy hitters" cause 37% of mispredictions.
- **Per-benchmark share of mispredictions due to H2Ps (Table I):** mcf 96.9%, omnetpp 77.6%, xalancbmk 28.6%, x264 54.2%, deepsjeng 31.2%, xz 80.5%.
- **Average accuracy** (overall → excluding H2Ps): mcf 0.921 → 0.998, xz 0.897 → 0.980, deepsjeng 0.946 → 0.963.
- **IPC opportunity:** perfect branch prediction is worth 18.5% IPC at 1× pipeline and 55.3% at 4×. Moving from 8KB to 64KB TAGE-SC-L returns just 2.7% IPC. H2Ps are 75.7% of the perfect-prediction opportunity at 1× (SPECint).
- **TAGE allocation churn:**
  - The median allocation count per H2P is **13,093**, versus 4 for non-H2P branches.
  - Only 3,990 unique entries are allocated per H2P.
  - Each H2P accounts for about 3.6% of all allocations, versus under 0.01% for each non-H2P branch.
- **Dependency branches:** for each H2P's correlated "dependency branches", the min and max history positions lie within TAGE-SC-L 64KB's 3,000-branch reach. Their positions vary widely, which the authors call "history variation".
- **Rare branches (LCF traces):** 85% of static branches execute fewer than 100 times. They account for about 34% of the IPC opportunity.

**Recommendations**
- Keep TAGE-SC-L and add specialised mechanisms.
- Use machine learning and pattern matching for H2Ps (offline-trained CNNs, as in their companion work).
- Use on-chip phase learning and long-term statistics for rare branches.
- Explicitly: "design filters for a BPU to reduce data variation when predicting H2Ps… make more efficient use of limited on-BPU storage". **This is prior art for any H2P allocation-filtering idea.**

**Caveat:** the paper describes TAGE-SC-L as including "the IMLI loop predictor (L)". In TAGE-SC-L, "L" is the loop predictor; IMLI lives in the SC. Do not quote that sentence.

---

## 3. Loop predictors **[READ]**

### 3.1 L-TAGE (CBP-2, JILP vol. 9, 2007)
- **Accessed:** https://jilp.org/vol9/v9paper6.pdf. I read pages 3–6 as images because text extraction fails on this PDF.
- **Organisation:** 256 entries, 4-way associative. Each entry has:
  - a 14-bit past iteration count;
  - a 14-bit current iteration count;
  - a 14-bit partial tag;
  - a 2-bit confidence counter;
  - an 8-bit age counter.
  That is 52 bits per entry and 13 Kbit in total.
- **When it is used:** "provides the global prediction when the loop has successively been executed 3 times with the same number of iterations." Otherwise TAGE predicts.
- **Replacement:** an entry can be replaced only if its age is 0. Age is set to 255 on allocation. It is decremented when the entry was a possible replacement target, and incremented when the entry is used and provides a valid prediction. It is reset to 0 "whenever the branch is determined as not being a regular loop".

### 3.2 TAGE-SC-L loop predictor (CBP4 2014 and CBP5 2016)
- **Accessed:** https://jilp.org/cbp2014/paper/AndreSeznec.pdf and https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf.
- **Entry: 39 bits.** It holds a 10-bit past iteration count, a 10-bit retire iteration count, a 10-bit partial tag, a 4-bit confidence counter, a 4-bit age counter and 1 direction bit.
- **Use:** it predicts once the loop has executed **7 times** with the same trip count.
- **Allocation and age:** age is set to 7 on allocation. Replacement is age-based.
- **Size:** 32 entries (1,248 bits) at 64KB; 8 entries (312 bits) at 8KB.
- **Benefit:** "approximately 1%" (256 Kbit) and 1.2% (32 Kbit) in CBP2014; "approximately 0.3%" in CBP2016. The loop predictor was **ignored or disabled** in Seznec's "realistic" 2024 cookbook TAGE-SC and in CBP2025 TAGE-SC.

### 3.3 Exact behaviour (gem5 `loop_predictor.cc`, TAGE-SC-L parameters) **[READ: source]**
- **Parameters:** `useDirectionBit=1`, `restrictAllocation=1` (allocate with probability 1/4), `initialLoopAge=7`, `initialLoopIter=0`, 4-bit confidence, 4-bit age, 10-bit tag, 10-bit iteration count, 4-way.
- **Valid** when `conf == 15` **or** `conf * numIter > 128`.
- **Prediction:** if `currentIter + 1 == numIter`, predict `!dir`; otherwise predict `dir`.
- **Use decision:** the loop prediction overrides only if the global 7-bit `WITHLOOP` counter is ≥ 0. That counter trains only when the loop prediction and the TAGE prediction differ.
- **On a loop misprediction while valid:** the entry is freed.
- **Allocation:** happens when there is no hit and the final prediction was wrong. The entry is allocated only if its age is 0; otherwise its age is decremented.
- The entry tracks only iterations, so it needs **no branch target**. It works unchanged in our interface. Always-taken unconditional branches never gain confidence: the trip-count logic needs a direction change.

### 3.4 IMLI versus the loop predictor
IMLI-SIC mostly subsumes the loop predictor (Section 1.2). **[MEASURED, proxy]**
- Adding the TAGE-SC-L loop predictor (64 entries) to the 52 KB TAGE proxy changed the 10-trace mean by −0.07%. Every per-trace change was ≤ 0.02 MPKI, which is within run-to-run noise.
- The loop branches with regular trip counts are in xalancbmk (90%) and x264 (99%). TAGE already predicts those (MPKI 0.56 and 0.13).
- mcf has 24 loop exits per kilo-instruction, but only 0.4% of them have a repeating trip count. They are data-dependent, which puts them in H2P territory and out of loop-predictor reach.

---

## 4. Confidence estimation

### 4.1 Jacobsen, Rotenberg, Smith, MICRO-29 (1996) **[READ]**
- **Title:** "Assigning Confidence to Conditional Branch Predictions".
- **Accessed:** https://ftp.cs.wisc.edu/sohi/papers/1996/micro.confidence.pdf.
- **Method:** a confidence table of Correct/Incorrect Registers (CIR) indexed like gshare (PC xor global history). The best practical reduction is a **resetting counter**: 4 bits, incremented on a correct prediction, reset to 0 on a misprediction, saturating at 15 or 16. A prediction is high-confidence when the counter is at or above a threshold.
- **Results** (IBS benchmarks, 64K-entry gshare):
  - Ideal static profiling puts 63% of mispredictions in a set covering 20% of dynamic branches.
  - The one-level dynamic method puts **89% of mispredictions into 20% of dynamic branches**.
  - Two-level schemes are not worth the cost.
  - Small tables (4K entries and below) do worse, because resetting counters amplify aliasing.
- **Relevance:** a resetting-counter table indexed by PC is a cheap online H2P detector. It can also serve as a per-branch "recent misprediction" signal (Section 6).

### 4.2 Seznec, "Storage Free Confidence Estimation for the TAGE branch predictor", HPCA 2011 **[READ: Inria RR-7371]**
- **Access:** HAL inria-00512130; the HPCA DOI is 10.1109/HPCA.2011.5749750. HAL blocks automated download. I read a copy of RR-7371 v2 (20 pages) that another agent had already placed in the shared scratchpad. I did not read the HPCA camera-ready.
- **Classes are based only on TAGE outputs:**
  - **Bimodal provider:**
    - low-conf-bim: a weak counter, about 30%+ misprediction rate;
    - medium-conf-bim: within 8 branches after a BIM-provided misprediction, at 57–87 MKP (mispredictions per kilo-prediction);
    - high-conf-bim: below 10 MKP.
  - **Tagged provider, by |2·ctr+1|:**
    - Wtag (=1): about 325–340 MKP;
    - NWtag (=3): about 313 MKP;
    - NStag (=5): about 213–225 MKP;
    - Stag (=7): 17–29 MKP.
- **Counter tweak:** the transition into the saturated state on a correct prediction happens only with probability 1/128. That pushes the Stag misprediction rate down to about 1–5 MKP, at a cost below 0.02 MPKI. The result is three usable classes: low (about 30%), medium (8–12%) and high (below 1%).
- **TAGE-SC-L actually uses** `lowConf = |2c+1|==1`, `medConf = |2c+1|==5` and `highConf = |2c+1| >= 2^cbits − 1` (gem5 `statistical_corrector.cc`). It feeds HighConf/LowConf/MedConf into the SC bias-table index and the SC/TAGE chooser (CBP2016 Section 4.4).
- **[MEASURED, proxy TAGE without SC]**
  - Weak, nearly-weak and nearly-saturated providers mispredict 29–39%, 29–39% and 8–30% of the time.
  - Saturated providers: 0.0–0.3% on easy traces, but 6.3% (mcf), 5.7% (xz), 2.7% (deepsjeng) and 2.0% (omnetpp). On those traces they hold 36–41% of mispredictions.
  - So confidence gating alone cannot reach the H2P mispredictions on our heavy traces.

### 4.3 BATAGE dual-counter confidence and CAT (Michaud, TACO 2018)
- **Paper NOT READ.** DOI 10.1145/3226098; ACM returned 403 and HAL blocked the download. I **read the author's code**: https://files.inria.fr/pacap/michaud/BATAGE_simulator-1.zip (`batage.cc` / `batage.h`).
- **Dual counters** (n_taken, n_nottaken):
  - `lowconf`: n1 < 2·n0+1 and n0 < 2·n1+1;
  - `mediumconf`: n1 == 2·n0+1 or n0 == 2·n1+1;
  - otherwise high confidence.
- **Controlled Allocation Throttling (CAT)** is a single global counter `cat`:
  - On a misprediction, allocation is attempted with probability ≈ 1 − cat/(CATMAX+1), quantised in steps of 1/MINAP, with MINAP = 16.
  - While scanning candidate tables, each skipped high-confidence (but not very-high-confidence) entry increments `mhc`. A successful allocation does `cat += CATR_NUM − mhc*CATR_DEN`, with CATR = 2/3.
  - **CAT is global, not per branch.**

---

## 5. Recent H2P-focused work

| Work | Venue / year | Accessed | Read? | What it does | Relevance to us |
|---|---|---|---|---|---|
| BranchNet (Zangeneh, Pruett, Lym, Patt) | MICRO 2020, pp. 118–130 | https://hps.ece.utexas.edu/pub/BranchNet_Micro2020.pdf | PARTIAL (abstract, intro, results) | **Offline-trained** CNNs (built on Tarsa et al.) for a few H2Ps. Key insight: some H2Ps correlate with *counts* of other branches in a noisy history, which TAGE cannot compress. Results: −7.6% MPKI (up to 15.7%) versus unlimited MTAGE-SC. The iso-latency 32KB Mini-BranchNet plus 64KB TAGE-SC-L gives −9.6% MPKI (up to 17.7%) and +1.3% IPC. Iso-storage (8KB Mini-BranchNet plus 56KB TAGE-SC-L) gives −5.5% MPKI. Needs ISA/OS support for the models. | Not implementable (offline training, profiling). Its "count" insight supports IMLI-like counting features. |
| Whisper (Khan, Ugur, Nathella, Sunwoo, Litz, Jiménez, Kasikci) | MICRO 2022 (Best Paper) | https://meugur.github.io/files/whisper-micro-22.pdf | PARTIAL (abstract, intro) | Profile-guided `brhint` instructions. Picks a **per-branch history length** from a geometric series, hashes it to 8 bits, and encodes a read-once monotone Boolean formula extended with implication and converse non-implication. Results: −16.8% mispredictions and +2.8% speedup over 64KB TAGE-SC-L on 12 data-centre applications. | Not implementable (ISA hints, offline). Its per-branch history-length idea suggests online per-branch history-length selection. |
| LLBP (Schall, Sandberg, Grot) | MICRO 2024, pp. 464–479 | https://xinhecuican.tech/pdf/SchallEtalMICRO2024TheLast-LevelBranchPredictor.pdf (mirror of the Edinburgh Research Explorer accepted version); code at https://github.com/dhschall/LLBP | PARTIAL | A 512KB second-level pattern store for 64KB TAGE-SC-L. Contexts are a rolling XOR hash of the last W unconditional-branch PCs; patterns are prefetched into an in-core buffer. Result: −0.5 to −25.9% MPKI (avg. −8.9%) on server traces. On Tomcat, 160 branches (0.8%) cause 40% of mispredictions. Cites "6 branches cause up to 50%" on SPEC. | Way over budget. Its context idea needs unconditional-branch identification: ours is approximate ("never seen not-taken"). |
| Bullseye (Behrendt, Pun, Nair) | CBP2025 workshop; arXiv 2506.06773 | https://arxiv.org/pdf/2506.06773 | READ | An H2P Identification Table (per-PC executions, mispredictions, accuracy). Adaptive admission: Exec ≥ 2048 + 16·N_H2P, Mispred ≥ 256, Acc < f(N). Admitted branches get a 512-execution trial of two perceptrons (hashed-window local history, folded global history). The perceptron overrides when it has strong confidence and TAGE does not. **TAGE and SC updates are filtered for a PC after 128 consecutive perceptron-correct, TAGE-never-better predictions.** Results: 3.4513 → 3.4045 MPKI (159KB TAGE-SC-L plus 28KB). Update filtering alone gave "<0.3%". | **Closest prior art for per-PC "stop training TAGE on H2Ps".** Its filtering is conditional on a replacement predictor taking over. |
| RUNLTS (Koizumi et al.) | CBP2025 | https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final44-Koizumi.pdf | PARTIAL | **Storage-free thrashing detection for TAGE.** Newly allocated entries are marked with the rare (ctr ∈ {0, −1}, u = 1) state. Two counters track fresh-entry hits versus evictions-before-use, and the allocation rate is adjusted. Global. Also uses register-value and "BrIMLI+TaIMLI" SC tables. | Prior art for allocation-utility tracking (global). |
| TAGE-SC for CBP2025 (Seznec) | CBP2025 | https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf | READ | Allocation filtering by the confidence of weak longest-match counters, measured with probabilistic counters. Allocation probability is 1/16 when that confidence is below 1/2, 1/4 below 16/31, and 1/2 below 8/15. Several entries are allocated per miss; U is set to 1 or 2 for protection. BrIMLI and TaIMLI as in Section 1.6. | Global allocation-filter prior art, plus the IMLI evolution. |
| TAGE: an engineering cookbook (Seznec) | Inria RR-9561, 2024, hal-04804900 | copy in shared scratchpad (HAL blocks automated access) | PARTIAL (slide part, via ghostscript) | "If the misprediction ratio is high then reduce the possibility of allocation on long history tables (T8 and higher)." Weak-counter-success-based allocation probabilities. Filtering allocation is worth −0.04 MPKI. "IMLI related: was found as dissapointing [sic]". | Global prior art. **My proxy says restricting H2P branches to short tables hurts** (Section 7). |
| SONet; LVCP (CBP2025); "The LLBP Revisited" (HPCA 2026); Tarsa et al. CNN (arXiv 2019); Wormhole (Albericio et al., MICRO 2014); Sherwood and Calder loop termination (2000) | various | search snippets only | NOT READ | LVCP reportedly uses a PC-indexed tagged H2P table to gate its load-value component. | Cite only after reading. |

**Existing TAGE allocation throttles (prior art you must not claim) [READ: source]**
- CBP2016 TAGE-SC-L (gem5 `TAGE_SC_L_TAGE::adjustAlloc`) allocates with probability 1/32 when the *final* prediction was correct but TAGE was wrong.
- It dynamically chooses one or two allocations from a TICK counter (CBP2014 paper).
- It also has the BATAGE CAT, cookbook, CBP2025 and RUNLTS mechanisms listed above.
- **I found no published per-branch (per-PC) allocation throttle that runs without an alternative predictor.** I cannot claim one does not exist: my search was a handful of web queries.

---

## 6. Proposed modest, testable mechanisms (with prior-art check and falsification)

All of these fit the `predict_branch` / `last_branch_result` interface. Storage figures are rough.

### Idea C1: target-free backward detection as the enabling layer (about 0.5–1 KB)
- **Mechanism:**
  - Keep `prevPC` and `prevTaken`. At `predict_branch(Y)`, if `prevTaken`, then `bwd = (Y <= prevPC)`.
  - Store `bwd` and a `seenNotTaken` bit in a direct-mapped 4K × 2-bit table (1 KB).
  - Derive from it IMLIcount (8–10 bits), BrIMLI (region = PC>>6 or PC>>8), a backward-taken global history (16 bits), and a forward-taken path hash.
- **Prior art:** none for the inference itself, because CBP frameworks provide targets. It is an engineering observation.
- **Falsifier:** any disagreement between inferred and true backward-ness in ChampSim. A debug check against `branch_target` (`src/ooo_cpu.cc` line 335) would find it. **[MEASURED] 0 disagreements in about 74M taken branches.** The remaining risk is a ChampSim behaviour I did not model, such as `predict_branch` skipped for some branches. I checked: it is called for every `is_branch` instruction in trace order (`src/ooo_cpu.cc` lines 111 and 352).

### Idea C2: IMLI-SIC and BrIMLI tables in the SC/perceptron sum (about 0.5–2 KB)
- **Mechanism:** add one 512–2K × 6-bit table indexed by hash(PC, BrIMLI) and one by hash(PC, IMLIcount) to whatever adder-based corrector the team builds (TAGE-SC or hashed perceptron). Optionally add the IMHIST constant-IMLI history: 256 × 10-bit histories feeding 2 tables of 256 entries.
- **Prior art:** fully published (Sections 1.2–1.6). The only twist is the target-free derivation.
- **Expected:** small. Seznec measured 0.2% (CBP2016) to about 1.5% (CBP2025, re-engineered).
- **[MEASURED, crude]** I ran a "saturated (PC, IMLI) counter overrides a low-confidence TAGE prediction" opportunity test. It was **inconclusive**: IMLI keys were no better than PC-only keys on mcf, omnetpp or deepsjeng. This only shows there is no large *standalone* signal. It does not test IMLI inside an adaptive-threshold SC.
- **Falsifier:** if adding both tables to the team's SC reduces 10-trace mean MPKI by less than 0.3%, and no single trace improves by more than 1%, drop it and reclaim the storage.

### Idea C3: utility-gated per-branch allocation throttling (about 1–2 KB) **[novelty uncertain]**
- **Mechanism:**
  - Mark freshly allocated TAGE entries. In hardware, use RUNLTS's spare (ctr ∈ {0, −1}, u = 1) encoding or a 1-bit field.
  - When a fresh entry is first used as provider, record success or failure in a small PC-indexed table: 1K entries of two 4–5-bit counters, halved together on overflow.
  - If a PC's fresh-entry success rate is below 25% with at least 16 samples, allocate for that PC with probability 1/8.
- **Prior art:**
  - Global versions: RUNLTS thrashing detection, BATAGE CAT, Seznec CBP2025 and cookbook weak-counter filtering.
  - Per-PC filtering conditioned on a takeover predictor: Bullseye.
  - The suggestion in Lin and Tarsa: "design filters".
  - The per-PC, utility-gated, standalone combination is the delta. Present it as a variant, not a new idea.
- **[MEASURED, proxy]**
  - Mean −0.21%: mcf −0.1%, xz −0.3%, omnetpp −0.6%. deepsjeng was neutral, which unlike blind throttling means it was **not hurt**.
  - Blind per-branch H2P throttling at probability 1/4 gave a mean of −0.57% but deepsjeng +4.1%. At 1/16 it gave −0.16% with deepsjeng +8.3%.
- **Falsifier:** inside the real predictor (TAGE plus SC), it must reduce the 4-heavy-trace mean MPKI by at least 0.5% and not raise any trace by more than 0.3%. Otherwise drop it. Also, if a *global* CAT-like throttle matches it within 0.1%, the per-PC part is not justified.

### Idea C4: H2P-aware "SC-only" fallback (budget-neutral) **[INFERRED, not tested]**
- **Mechanism:** for PCs flagged H2P (Jacobsen-style resetting counter or windowed misprediction rate), when the TAGE provider is weak or nearly weak, let the SC decide by its sign without the usual TAGE-confidence veto. This is a per-branch chooser in place of the global chooser counters.
- **Prior art:**
  - TAGE-SC-L already picks between TAGE and SC with global or PC-indexed counters (CBP2016 Section 4.4: "2 counters for the chooser").
  - The CBP2014 USE_ALT_ON_NA array is PC-indexed.
  - So this is close to existing practice. The delta is gating by an H2P flag.
- **Falsifier:** if the gain over a PC-indexed chooser is below 0.2% MPKI on mcf and xz, drop it.

### Idea C5: small TAGE-SC-L-style loop predictor (about 160 B for 32 entries)
- **Prior art:** fully published (Section 3). It works unchanged without a target.
- **[MEASURED, proxy]** About 0% on our traces.
- **Falsifier:** if it gains less than 0.05% mean MPKI once IMLI-SIC is present, remove it. Seznec drops it in his realistic designs.

### Idea C6: a few-entry H2P local-history perceptron (2–8 KB) **[INFERRED]**
- **Mechanism:** a Bullseye-lite design. An H2P table of 16–32 entries admits PCs. Each admitted PC gets a hashed-window local-history perceptron, which overrides only on strong confidence plus a running win-rate above 55%.
- **Prior art:** Bullseye (−1.4% at 28 KB on the CBP2025 traces), and TAGE-SC-L's local-history SC tables.
- **Falsifier:** if the improvement on mcf, xz and omnetpp is below 1% at 8 KB, give the storage back to the TAGE tables.

---

## 7. Proxy measurement study **[MEASURED]**

**What it is**
- A standalone C++ tool, run outside the project: `/tmp/claude-1000/-home-maahi-BRANCH-PREDICTOR-PROJECT/ec2d847f-c33b-4f80-8500-0fe78b7782e4/scratchpad/C/tools/analyze.cc`. The scratchpad is session-scoped and may disappear.
- It reads each `.champsimtrace.xz` read-only. It replicates ChampSim's branch classification exactly (`src/ooo_cpu.cc`, the register-based rules) and its taken-forcing for unconditional branches.
- It sends all branches to a **52 KB TAGE proxy**:
  - 16K × 2-bit bimodal;
  - 12 tagged tables of 2K entries, with history lengths 4 to 640, 3-bit counters and 2-bit u;
  - L-TAGE-style single allocation and halving u-reset every 2^18 branches;
  - no SC;
  - immediate update.
- It ran the first 90M instructions of each trace. MPKI is counted after a 10M-instruction warm-up, over all branch mispredictions (as ChampSim counts them).
- Randomised allocation makes run-to-run noise about ±0.3% on the heavy traces, and ±0.005 MPKI absolute on the light ones.
- **This is not the team's predictor and not the DPC-3 simulation window.** Use it for direction only.

**Workload facts (90M instructions)**

| Trace | Branches per KI | Static PCs | Base MPKI | H2Ps per 30M slice | % of mispredictions from H2Ps |
|---|---|---|---|---|---|
| 602.gcc_s-1850B | 256 | 44 (!) | 0.065 | 0 | 0 |
| 605.mcf | 250 | 176 | 17.40 | 13–14 | 94% |
| 607.cactuBSSN | 6 | 1,565 | 0.012 | 0 | 0 |
| 619.lbm | 15 | 6 | 0.316 | 1 | 99.8% |
| 620.omnetpp | 210 | 1,523 | 4.19 | 11–12 | 85–87% |
| 623.xalancbmk | 260 | 2,306 | 0.557 | 0 | 0 |
| 625.x264 | 40 | 214 | 0.126 | 0–1 | 0–29% |
| 631.deepsjeng | 148 | 1,260 | 4.53 | 11–20 | 20–32% |
| 638.imagick | 161 | 118 | 0.087 | 0–1 | 0–50% |
| 657.xz | 131 | 497 | 11.25 | 19 | 82–84% |

- The H2P misprediction shares for mcf, omnetpp, xz and deepsjeng match Lin and Tarsa's TAGE-SC-L 8KB numbers closely (96.9%, 77.6%, 80.5% and 31.2%).
- The "allocation share" of H2Ps equals their misprediction share in this proxy, because it allocates on every misprediction.
- **The gcc simpoint executes only 44 static branches in 90M instructions.** It is not representative of gcc's usual large footprint.

**Variants (MPKI)**

| Trace | Base | H2P throttle 1/4 | H2P throttle 1/16 | Global throttle 3/4 | Utility-gated (C3) | H2P short tables only | +Loop predictor |
|---|---|---|---|---|---|---|---|
| gcc | 0.065 | 0.064 | 0.064 | 0.065 | 0.064 | 0.065 | 0.065 |
| mcf | 17.404 | 17.140 | 17.060 | 17.324 | 17.390 | 18.112 | 17.409 |
| cactuBSSN | 0.012 | 0.012 | 0.012 | 0.012 | 0.012 | 0.012 | 0.010 |
| lbm | 0.316 | 0.313 | 0.311 | 0.314 | 0.316 | 0.330 | 0.314 |
| omnetpp | 4.188 | 4.150 | 4.191 | 4.164 | 4.161 | 4.166 | 4.163 |
| xalancbmk | 0.557 | 0.553 | 0.569 | 0.556 | 0.555 | 0.559 | 0.557 |
| x264 | 0.126 | 0.127 | 0.128 | 0.127 | 0.126 | 0.129 | 0.130 |
| deepsjeng | 4.529 | **4.715** | **4.903** | 4.574 | 4.526 | 4.688 | 4.528 |
| imagick | 0.087 | 0.087 | 0.087 | 0.087 | 0.087 | 0.087 | 0.086 |
| xz | 11.245 | 11.148 | 11.142 | 11.229 | 11.213 | 11.465 | 11.240 |
| **Mean** | 3.853 | 3.831 (−0.57%) | 3.847 (−0.16%) | 3.845 (−0.20%) | 3.845 (−0.21%) | 3.961 (**+2.8%**) | 3.850 (−0.07%) |

How the variants work:
- **H2P throttle:** an online per-PC tracker flags a PC as H2P if it had at least 16 mispredictions in its last 256 executions. TAGE then allocates for that PC with the stated probability.
- **Global throttle:** every allocation happens with probability 3/4.
- **Short tables only:** an H2P PC may allocate only in T1–T6, with probability 7/8.

**Lessons [INFERRED from MEASURED]**
1. Long-history allocations *are* useful for H2Ps. Blocking them costs 4% on mcf. This contradicts the cookbook's global heuristic when it is applied per branch.
2. Blind throttling trades mcf and xz gains for deepsjeng losses. deepsjeng's mispredictions are spread over many moderately hard branches (top-10 share is only about 20%), and TAGE learns some of them with more allocations.
3. Utility gating is safe but small.

Other measurements:
- **Branch mix:** returns, calls and jumps are 17–36% of branches on gcc, mcf, omnetpp and deepsjeng. These always-taken branches pass through `predict_branch`.
- **Fraction of taken branches that are backward:** 29–78%.

---

## 8. Sources

| # | Reference | URL accessed | Status |
|---|---|---|---|
| 1 | Seznec, San Miguel, Albericio, IMLI, MICRO 2015 | https://www.irisa.fr/alf/downloads/seznec/IMLI.pdf | READ |
| 2 | Lin and Tarsa, Branch Prediction Is Not a Solved Problem, IISWC 2019 | https://arxiv.org/pdf/1906.08170 (v1) | READ (arXiv v1 only) |
| 3 | Seznec, The L-TAGE Branch Predictor, JILP vol. 9, 2007 | https://jilp.org/vol9/v9paper6.pdf | PARTIAL (pages 3–6) |
| 4 | Seznec, TAGE-SC-L Branch Predictors, CBP4, 2014 | https://jilp.org/cbp2014/paper/AndreSeznec.pdf | READ |
| 5 | Seznec, TAGE-SC-L Branch Predictors Again, CBP5, 2016 | https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf | READ |
| 6 | Seznec, Storage Free Confidence Estimation for TAGE, HPCA 2011 / Inria RR-7371 | HAL inria-00512130 (copy from shared scratchpad) | READ (RR version) |
| 7 | Jacobsen, Rotenberg, Smith, Assigning Confidence to Conditional Branch Predictions, MICRO-29, 1996 | https://ftp.cs.wisc.edu/sohi/papers/1996/micro.confidence.pdf | READ |
| 8 | Zangeneh, Pruett, Lym, Patt, BranchNet, MICRO 2020 | https://hps.ece.utexas.edu/pub/BranchNet_Micro2020.pdf | PARTIAL |
| 9 | Khan et al., Whisper, MICRO 2022 | https://meugur.github.io/files/whisper-micro-22.pdf | PARTIAL |
| 10 | Schall, Sandberg, Grot, The Last-Level Branch Predictor, MICRO 2024 | https://xinhecuican.tech/pdf/SchallEtalMICRO2024TheLast-LevelBranchPredictor.pdf | PARTIAL |
| 11 | Behrendt, Pun, Nair, Bullseye, CBP2025 | https://arxiv.org/pdf/2506.06773 | READ |
| 12 | Koizumi et al., RUNLTS, CBP2025 | https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final44-Koizumi.pdf | PARTIAL |
| 13 | Seznec, TAGE-SC for CBP2025 | https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf | READ |
| 14 | Seznec, TAGE: an engineering cookbook, Inria RR-9561, 2024 | hal-04804900 (copy from shared scratchpad) | PARTIAL |
| 15 | Michaud, An Alternative TAGE-like Conditional Branch Predictor (BATAGE), TACO 2018 | paper: DOI 10.1145/3226098 (not accessible); code: https://files.inria.fr/pacap/michaud/BATAGE_simulator-1.zip | Code READ, paper NOT READ |
| 16 | gem5 TAGE-SC-L, loop predictor, SC and MPP sources | https://github.com/gem5/gem5/tree/stable/src/cpu/pred | READ (relevant files) |
| 17 | LLBP repository copy of CBP2016 TAGE-SC-L code | https://github.com/dhschall/LLBP (`bpmodels/tage/tage_scl.cc`, `tage_scl.h`) | READ (IMLI parts) |
| 18 | ChampSim (local, old 2021 version): call sites and branch classification | `src/ooo_cpu.cc` lines 111/134, 280–335 and 352/384 | READ |

**Not read (from snippets only; do not cite details):**
- SONet (Springer 2025)
- LVCP (CBP2025)
- "The Last-Level Branch Predictor Revisited" (HPCA 2026)
- Tarsa et al., CNN branch prediction (arXiv 2019)
- Wormhole (Albericio et al., MICRO 2014 / CBP4)
- Sherwood and Calder, Loop Termination Prediction (2000)
- Jiménez, Hanson, Lin, Boolean-formula prediction (PACT 2001)
- Chang, Evers, Patt, branch filtering (PACT 1996)
