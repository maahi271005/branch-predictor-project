# Topic B: Perceptron, hashed perceptron, MPP, and SC/hybrid architectures

Research notes for the ChampSim (2021) branch-prediction assignment. Written 2026-10-30.

**How to read the provenance tags**
- **[READ]**: I extracted the text of the PDF (`pdftotext`) and read the relevant section. Quotes and numbers come from that text.
- **[READ-garbled]**: I read the text, but PDF extraction scrambled tables or formulas, so I had to reconstruct them. Treat these values as approximate.
- **[SEARCH-ONLY]**: I saw only the bibliographic record or a search-result snippet, not the full text.
- **[INFERRED]**: my own reasoning or calculation. No paper states it.

---

## 0. Simulator interface constraints (verified in repo source) [READ]

- `champsim/src/ooo_cpu.cc` lines ~104–134 (and ~344–384) call `predict_branch(ip)`. The very next action is `last_branch_result(ip, branch_taken)`. Both run in the same fetch step, so update is immediate and nothing is in flight between them.
- The call is made for **every** instruction with `is_branch` set. Types are inferred from registers at ~280–300: DIRECT_JUMP, INDIRECT, CONDITIONAL, DIRECT_CALL, INDIRECT_CALL, RETURN, OTHER. The CPU knows the `branch_type`, but the predictor receives **only `ip`**. No target is passed either; it goes only to the L1I prefetcher hook.
- The mispredict count covers every branch type, so unconditional jumps, calls, and returns count when a predictor says not-taken. Every non-conditional branch has `branch_taken = 1`.
- `build_champsim.sh` copies `branch/<name>.bpred` to `branch/branch_predictor.cc`. That file is currently a copy of bimodal.
- Traces (`champsim/dpc3_traces`) are 602.gcc_s-1850B, 605.mcf_s-1152B, 607.cactuBSSN_s-2421B, 619.lbm_s-2676B, 620.omnetpp_s-141B, 623.xalancbmk_s-10B, 625.x264_s-12B, 631.deepsjeng_s-928B, 638.imagick_s-824B, 657.xz_s-2302B.

Consequences [INFERRED]:
1. Speculative-history machinery is unnecessary. Predict/update immediately reconstructs the non-speculative history.
2. Any filter that learns "always taken" per PC catches unconditional branches, calls, and returns for free. It also keeps them out of the weight tables. This is the MPP "branch filter", which Jiménez's CBP2025 paper reports as its *single most valuable* optimization (see §2c).
3. **Target-free backward-branch detection is possible and exact for taken branches.** After a taken branch A, execution runs sequentially from A's target until the next branch B, so `ip(B) >= target(A)`. A backward taken branch has its own address on the sequential path from its target, so `ip(B) <= ip(A)`. A forward taken branch gives `ip(B) >= target(A) > ip(A)`. Therefore, for a taken A, `ip(B) <= ip(A)` holds exactly when A is backward. A per-PC "is-backward" bit learned on taken instances also classifies A's not-taken instances. `predict_branch(B)` is the first call that sees `ip(B)`, and it runs after A's update and before B's prediction, which is exactly when IMLI must be updated. Possible exceptions: interrupts or context switches inside traces, and returns or indirect jumps, which the always-taken filter should exclude anyway. This is the basis for extension idea #2.

---

## 1. Audit of the existing predictors in `champsim/branch/` [READ, storage = INFERRED arithmetic]

### 1a. `perceptron.bpred`: the original Jiménez & Lin global perceptron
- **Structure:** 163 perceptrons. Each has 25 weights (bias plus h = 24 history weights), clamped to 8-bit range [-128, 127] but stored as `int`.
- **Index:** `ip % 163`, using the full raw IP. 163 is prime, so the distribution is reasonable.
- **Output:** `y = w0 + Σ (h_i ? +w_i : -w_i)`. Predicts taken when `y >= 0`.
- **Training:** if `y > θ` and taken, or `y < -θ` and not-taken, skip. Otherwise apply bias `w0 += t` and `w_i += (h_i == t) ? +1 : -1`, saturating. This is exactly the HPCA'01 rule ("train if mispredicted or |y| <= θ").
- **Threshold:** θ = (int)(1.93·24 + 14) = (int)60.32 = **60**. The paper says a weight then needs 1 + floor(log2 θ) = 7 bits, so 8-bit weights leave headroom.
- **History:** `spec_global_history` (shifted with the prediction) and `global_history` (shifted with the outcome). Because update is immediate, `spec` is reset to `global` on a mispredict and is already equal to it otherwise, so the two are always identical after update [INFERRED]. Both are 64-bit variables, but only the low 24 bits are used.
- **Storage:** 163 × 25 × 8 = **32,600 bits = 4,075 B ≈ 3.98 KiB**, plus 24 bits of history (48 if both registers are counted). Total ≈ **32,648 bits ≈ 4.0 KB**. The 100-entry `perceptron_state_buf` is a SimpleScalar artifact; only one entry is ever live, so it is not predictor state.
- **Quirks:**
  - The header claims the configuration matches the Alpha 21264 budget, but HPCA'01 Table 1 says the best history at 4 KB is **28**, not 24 (h=24 is closer to the 2 KB row, which is 22). For 4 KB at h = 28: 4096·8/(29·8) ≈ 141 perceptrons.
  - Unconditional branches, calls, and returns are shifted into the global history as taken bits. They are also predicted and trained, which uses perceptron rows. With only 163 rows, aliasing is severe on large-footprint traces such as gcc, xalancbmk, and omnetpp [INFERRED].
  - **No functional bugs found.** The `!!(history & mask) == taken` trick is correct because `branch_taken` is 0 or 1.
  - The design uses only **1/16 of the 64 KB budget**. HPCA'01 says the best history length for 64 KB is 59. At h = 59 and 8-bit weights, 64 KB holds 65536/60 ≈ 1092 perceptrons [INFERRED].

### 1b. `hashed_perceptron.bpred`: Jiménez's 2019 ChampSim hashed perceptron (GEHL-like)
- **Structure:** 16 tables of 4096 weights, stored as `int` and clamped to [-128, 127], so 8-bit weights.
- **History lengths:** {0, 3, 4, 6, 8, 10, 14, 19, 26, 36, 49, 67, 91, 125, 170, 232}. Table 0 has length 0, so it is a PC-indexed bias table.
- **Global history:** 20 words of 12 bits = 240 bits (`NGHIST_WORDS = 232/12 + 1`). The newest bit enters the LSB of word 0, and bits carry from each word's MSB into the next word.
- **Index for table i:** XOR of the folded 12-bit chunks covering the first `n_i` history bits, then `^= pc`, then `& 4095`. This is the gshare-style `{mi, AxG, ∅}` mapping from Tarjan & Skadron.
- **Prediction:** `yout = Σ_i T_i[idx_i]`, with **taken iff `yout >= 1`**. A sum of 0 is therefore predicted not-taken, which differs from the `>= 0` convention in the papers.
- **Training:** if mispredicted or `|yout| < θ` (strict; O-GEHL and MPP use <=), add +1 or -1 to every selected weight, saturating at ±127/−128.
- **Dynamic θ (O-GEHL style):** θ starts at **10**. The counter `tc` increments on each mispredict, and θ++ when it reaches **SPEED = 18**. It decrements on each correct-but-weak update, and θ−− when it reaches −18. O-GEHL itself uses a 7-bit TC and starts θ at M (the number of tables), which would be 16 here.
- **Storage:** 16 × 4096 × 8 = **524,288 bits = exactly 64 KiB** of weights. Adding 240 history bits plus θ and `tc` (about 8 + 6 bits) gives ≈ **524,542 bits ≈ 64.03 KiB**. The weights alone use the whole 64 KB budget; strictly, the total is about 254 bits over.
- **Quirks / weaknesses** [INFERRED unless noted]:
  - **No path history.** Every table XORs the same 12 low PC bits, with no per-table PC rotation or skew, so aliasing patterns are correlated across tables. O-GEHL adds a 16-bit path history and its own hash per table. Tarjan & Skadron show that path-based components help.
  - **The fold is plain XOR of 12-bit chunks.** For n ≥ 24, two chunks can cancel. For example, a history that repeats with period 12 folds to 0 regardless of the PC. Short loops produce this kind of periodic pattern.
  - **Raw PC is used, unshifted.** On x86 that is fine because instructions are byte-aligned, but the high-entropy bits beyond bit 11 never reach the index.
  - **No filter for always-taken (non-conditional) branches.** They train their weights only while `|yout| < θ`, so their cost is mostly capacity and aliasing, not repeated updates.
  - **Weights are 8-bit.** O-GEHL found 4–5 bits sufficient, Tarjan found 5, and MPP uses 6. Moving to 5–6-bit weights would free roughly 25–35% of the storage for more entries or tables.
  - The global variables `yout` and `indices` carry state from predict to update. This is safe only because the update immediately follows the prediction, which is true here.
  - The author's comment says it was written "in about an hour" and "prefers simplicity over absolute accuracy". It is a baseline, not a tuned design.

### 1c. `gshare.bpred`
- 16,384 2-bit counters (stored as `int`), initialized to 2 (weakly taken). The history is 14 bits.
- **Index:** `(ip ^ ip>>14 ^ ip>>28 ^ ghist) % 16384`. This folds the PC down to 14 bits, then applies the classic gshare XOR with history length = log2(table size).
- **Storage:** 16384 × 2 = **32,768 bits = 4 KiB**, plus 14 history bits.
- **Quirks:**
  - `#define GLOBAL_HISTORY_MASK (1 << 14) - 1` has no outer parentheses. It is harmless in its only use (`&=`) but is a latent macro hazard.
  - History includes all branch types.
  - Update recomputes the hash with the same unchanged history, which is correct.
  - HPCA'01 Table 1 says the best gshare history at 4 KB is 8 bits, not 14, but that was measured on SPEC2000.

### 1d. `bimodal.bpred`
- The array has 16,384 2-bit counters, but the index is `ip % 16381` (a prime), so only 16,381 are used.
- Counters are initialized to 0 (strongly not-taken). This adds cold-start mispredicts on taken and unconditional branches; gshare starts at 2.
- **Storage:** 16384 × 2 = **32,768 bits = 4 KiB** allocated (32,762 bits used).

### Summary table
| Predictor | Main state | Bits | KB (KiB) |
|---|---|---|---|
| bimodal | 16384×2b | 32,768 | 4.0 |
| gshare | 16384×2b + 14b hist | 32,782 | 4.0 |
| perceptron | 163×25×8b + 24b hist | 32,624 (32,648 incl. both hist regs) | 3.98 |
| hashed_perceptron | 16×4096×8b + 240b hist + θ/tc | ≈524,542 | 64.03 |

---

## 2. Papers

### 2a. Jiménez & Lin, "Dynamic Branch Prediction with Perceptrons", HPCA-7, 2001 [READ]
URL accessed: https://www.cs.utexas.edu/~lin/papers/hpca01.pdf
- **Model:** one perceptron per (hashed) branch address. Inputs are global history in bipolar form (x_i ∈ {−1, +1}), with x0 = 1 for the bias. `y = w0 + Σ x_i w_i`. Predict taken iff y >= 0.
- **Training:** "if sign(y_out) ≠ t or |y_out| <= θ then for i := 0..n: w_i := w_i + t·x_i". Weights saturate.
- **Threshold:** best θ = ⌊1.93h + 14⌋ (found empirically to hold at every h). Weight width is 1 + ⌊log2 θ⌋, which ranges from 7 bits (h = 12) to 9 bits (h = 62).
- **Table 1 (best history length by budget, gshare / bi-mode / perceptron):**
  - 1 KB: 6 / 7 / 12
  - 2 KB: 8 / 9 / 22
  - 4 KB: 8 / 11 / 28
  - 8 KB: 11 / 13 / 34
  - 16 KB: 14 / 14 / 36
  - 32 KB: 15 / 15 / 59
  - 64 KB: 15 / 16 / 59
  - 128 KB: 16 / 17 / 62
  - 256 KB: 17 / 17 / 62
  - 512 KB: 18 / 19 / 62
- **Results:** on SPEC2000 int (12 benchmarks, test inputs), the 4 KB perceptron mispredicts 6.89%, which is 10.1% better than gshare and 8.2% better than bi-mode. It beats both at every budget over 1 KB. A gshare + perceptron hybrid with a 2 KB Alpha-21264-style chooser helps slightly at 16 KB but not at 4 KB.
- **Limitations stated by the authors:**
  - It learns only linearly separable functions. At 512 KB, perceptron loses to gshare on benchmarks dominated by linearly inseparable branches. When the perceptron is restricted to 18 history bits, gshare wins (4.83% vs 5.35%).
  - The dot-product adds latency; they estimate the logic at about 1 KB of SRAM area.
- **Future work stated:** a global + local hybrid, Agree-style bias bits, and using |y| as a confidence estimate for speculation control.

### 2b. Jiménez, "Multiperspective Perceptron Predictor", CBP-5 (with ISCA), June 2016 [READ]
URL accessed: https://jilp.org/cbp2016/paper/DanielJimenez1.pdf
- **Structure:** a hashed perceptron. Each feature hashes some history organization together with the PC, mod table size, to select one weight. The weights pass through a transfer function, are multiplied by per-feature coefficients, summed, and thresholded.
- **Traditional features:**
  - **GHIST(start, end):** XOR of multi-bit blocks of the global history between two positions.
  - **PATH(depth, shift, style):** addresses truncated to 16 bits; the accumulator is mixed by shift-and-add or bit-XOR.
  - **LOCAL:** a first-level table of per-branch histories, hashed into a weight table.
  - **GHISTPATH:** GHIST XOR PATH.
  - **SGHISTPATH:** a GHISTPATH over a range, from strided sampling.
  - **BIAS:** constant 0 XOR PC.
- **Novel features:**
  - **IMLI:** the backward version (Seznec et al.) plus a new **forward** version. On a forward branch, increment the count if not-taken and reset it if taken. Only forward IMLI is used at 8 KB.
  - **MODHIST(modulus, length):** records only branches whose PC ≡ 0 mod m. This fights "branch misalignment".
  - **MODPATH, GHISTMODPATH:** the same modulo filtering applied to path and combined history.
  - **RECENCY(depth, shift, style):** an LRU stack of recent branch PCs, hashed.
  - **RECENCYPOS(depth):** the position of the current PC in the recency stack, or "absent". It was the third most valuable feature.
  - **BLURRYPATH(shift, depth, shift2):** a history of PC>>k regions, shifted only when the region changes.
  - **ACYCLIC(n, shift, style):** `H[PC mod n] = outcome` (or a hashed address), which removes loop repetition.
- **Optimizations:**
  - Feature selection by genetic algorithm plus hill-climbing on truncated CBP2016 traces.
  - Coefficients per feature (genetic algorithm).
  - **Transfer function** f(x) = (a + bx)/(1 + cx + dx²), stored as a ROM indexed by weight magnitude. Weights are **6-bit** (one table is 5-bit), in sign/magnitude form, with **two sign bits sharing one magnitude**.
  - **Branch filter:** two Bloom filters (ever-taken, ever-not-taken). A branch is predicted by the perceptron only if it appears in both. A first-seen branch is predicted not-taken. Filter entries decay periodically.
  - **Alternate prediction on low |y|:** the predictor tracks each feature's standalone accuracy and, when |y| is low, uses the best 20 of 37 features.
  - **Adaptive θ** (Seznec O-GEHL algorithm), plus a "fudge factor" on the output for training.
  - Some indices are also hashed with IMLI counts or the recency position.
  - Addresses of unconditional branches, calls, and returns are included in the histories.
- **Sizes:**
  - **64.25 KB:** 37 features / 37 tables. 7 sized tables hold 10,704 weights total, and 30 tables hold 1,931 weights each, all at (5+2) bits (5-bit magnitude, 2 signs). The branch filter is 2 × 18,025 bits. Local histories are 510 × 11 bits. Total 526,208 bits.
  - **8.25 KB:** 16 features. Total 67,524 bits.
- **Results (CBP2016 traces, MPKI):** 5.335 at 8.25 KB, **4.147 at 64.25 KB**, 3.238 unlimited. For comparison, Seznec's TAGE-SC-L in the same contest reports 4.991 at 8 KB and **3.986 at 64 KB** (§2d), so MPP alone was about 4% worse at 64 KB [INFERRED comparison of the two papers' numbers].
- **Ablation at 8 KB:** the best feature is GHIST(75..150) at 0.13 MPKI, then GHISTPATH(31) at 0.11 MPKI, then RECENCYPOS at about 0.1 MPKI. One SGHISTPATH feature hurt on the full traces because it was tuned on truncated traces (the author's "Oops").
- **Quirk:** the text says "If the sum is below one, the branch is predicted taken". This conflicts with the background section, which says taken when the sum ≥ 0, and is probably a polarity typo. Check the source code before relying on either.
- **Not accessed:** the CBP2016 source code containing the exact 64 KB feature list. The paper lists only the 8 KB feature set (in its Figure 2).

### 2b'. Jiménez, "Multiperspective Perceptron Predictor with TAGE", CBP-5, 2016 [READ]
URL accessed: http://www.jilp.org/cbp2016/paper/DanielJimenez2.pdf
- **Design:** replaces and augments the SC perceptron inside Seznec's TAGE-SC-L, using the IMLI-paper code base. Features duplicated by TAGE (bias, global, local) were removed. The remaining set includes BLURRYPATH, RECENCY, RECENCYPOS, MODPATH, ACYCLIC, GHISTMODPATH, and IMLI forward and backward. Seznec's IMLI code is disabled in favor of Jiménez's own, and IMLI-OH is not used.
- **Choosing between TAGE and the perceptron:** use the perceptron when TAGE confidence is low. Otherwise compare the perceptron's confidence against thresholds, which are trained on the perceptron's correctness and strength. This is the same mechanism as TAGE-SC-L. Training θ is per-PC-hash (Seznec code).
- **64.25 KB budget:** perceptron tables 699 × 9 × 6 b = 37,746 bits; TAGE entries 406,016 bits; SC (global, local, call-stack, bias) about 50 Kbits; loop predictor 2,753 bits. Total 526,293 bits.
- **Results (MPKI):** 5.226 at 8.25 KB, **4.048 at 64.25 KB**, 2.967 unlimited. Note that 4.048 is still above Seznec's 64 KB TAGE-SC-L at 3.986 [INFERRED comparison].
- **Ablation at 64 KB:** the best feature is BLURRYPATH(8, 10), at 0.025 MPKI. The other features contribute roughly 10× less. Once TAGE is present, the marginal value of the extra features is small.

### 2c. Jiménez, "Multiperspective Perceptron Predictor", CBP 2025 (Tokyo, June 21, 2025) [READ]
URL accessed: https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final53-Jimenez.pdf (found via search; not in the original task list, but highly relevant)
- **Design:** MPP combined with TAGE-SC-L at a **192 KB** budget, with 6-bit weights. A new feature, **BACKPATH**, records the path of backward branches only. A **TAGE** feature feeds the TAGE prediction and confidence into MPP as a feature. Features were selected to minimize the *combined* MPKI, which shifts them toward modulo and other features orthogonal to TAGE.
- **Transfer function:** f(x) ≈ 3.2x / (1 − x²/1600), stored as a lookup table. The same transfer function is also applied to the TAGE-SC-L SC.
- **Combiner:** a linear combination of MPP confidence and SC confidence. Slope and bias are tuned per context, where context = (TAGE-SC-L prediction, MPP prediction, TAGE-only prediction, TAGE confidence ∈ {0, 1, 2}), giving 24 contexts. An extra per-context bias is chosen online from 64 candidates by counting misses with 3-bit counters.
- **Filtering:** two Bloom filters (24 KB) for trivial (always/never-taken) branches. The author notes a BTB "observed not-taken" bit would normally do this job.
- **Results:** 3.39 MPKI on the CBP2025 traces, 0.36 MPKI better than the baseline, with a geometric-mean speedup of 1.017.
- **Ablation:**
  - filtering trivial branches: **0.141 MPKI** (the most valuable optimization)
  - transfer function: 0.059 MPKI
  - tuned combiner vs. "use MPP if |y| > 0.5θ": 0.042 MPKI
  - speculative update: 0.033 MPKI
  - combiner constant tuning: 0.027 MPKI
- **Cites** Akkary et al., HPCA 2004, "Perceptron-Based Branch Confidence Estimation".

### 2d. Seznec, "TAGE-SC-L Branch Predictors Again", CBP-5, 2016 (SC details) [READ-garbled]
URL accessed: http://www.jilp.org/cbp2016/paper/AndreSeznecLimited.pdf
- **Roles:** TAGE gives the main prediction. The SC "confirms (general case) or reverts" it when, in similar circumstances, TAGE statistically mispredicted. The loop predictor is marginal (about 0.3%).
- **SC = Multi-GEHL (MGSC):** all tables use 6-bit counters. The prediction is the sign of the sum of centered counter values. Tables are updated using the GEHL dynamic threshold, with a **PC-indexed threshold table** (32 entries at 8 KB, 64 at 64 KB) plus a global threshold. Each GEHL component gets a **dynamic multiplicative factor (1 or 2)** based on usefulness monitoring.
- **64 KB SC components:**
  - a bias component of 3 tables, indexed by PC, TAGE prediction, TAGE confidence, and the number of the highest matching table
  - global conditional history (2 tables)
  - global backward-branch history (2 tables)
  - an IMLI-indexed table
  - a "constant IMLI" GEHL
  - three local-history GEHLs (256-, 16-, and 16-entry local history tables)
  - GEHL components have no PC-only table
  - SC storage is **58,190 bits**: 2 tables of 1K entries, 8 of 512, 9 of 256, and 1 of 128, plus 64 × 8-bit thresholds, a 12-bit global threshold, 8 × 8 6-bit multiplicative-factor counters, and the histories
- **8 KB SC:** bias tables, global history (2), backward history (2), and 64-entry local history (2). 8,872 bits.
- **Chooser:** use the SC output, except (1) when TAGE is high-confidence and |SC sum| < θ/2, where the choice comes from a monitoring counter, and (2) when TAGE is medium-confidence and |SC sum| < θ/4, where a second counter decides. This gives about 0.7% fewer mispredictions.
- **Results:** the 64 KB TAGE-SC-L reaches **3.986 MPKI** on CBP-5 train traces (523,355 bits). The 8 KB version reaches 4.991 MPKI. The SC gives about 8% (64 KB) and 6% (8 KB) misprediction reduction.
- **Value of individual changes:** feeding TAGE confidence and provider table into the bias tables gains 0.3%; the IMLI table 0.2%; replacing path history with backward-branch history 0.3%.
- **TAGE side (approximate, from garbled text) [READ-garbled]:** the 64 KB TAGE uses bank-interleaved tables (10 banks of 1K entries with 12-bit entries and 8-bit tags, plus 20 banks of 1K entries with 16-bit entries and 11-bit tags), 3000-bit global history, 27-bit path history, and 3-bit counters with a 1-bit useful counter. The 8 KB TAGE uses 128-entry banks, 1000-bit history, and a 2-bit useful counter.
- The global history uses 2 bits per direct branch and 3 bits per indirect branch, combining path and direction. This needs the branch type and target, which the ChampSim interface lacks.

### 2e. Tarjan & Skadron, "Merging Path and Gshare Indexing in Perceptron Branch Prediction", ACM TACO 2(3):280–300, Sept 2005 [READ]
URL accessed: https://www.cs.virginia.edu/~skadron/Papers/taco_bpred_sep05.pdf
- **Key idea:** drop the one-weight-per-history-bit correspondence. Each weight is selected by a hash, so the input vector is constant 1 and `out = Σ W[j][index_j]`.
- **Taxonomy:** {single or multiple indexes; information used for weight selection: A (address), G (global), P (path), L (local); combination: x (XOR), c (concat), h (hash)}.
  - global perceptron = {si, A, G}
  - path-based neural = {mi, P, G}
  - hashed (gshare-style) = {mi, AxG, ∅}: index[j] = (history_segment[j] ⊕ pc) mod n, where each segment holds log2(n) history bits
  - also {mi, PxG, ∅}, {mi, PcG, ∅}, and {mi, PxP, ∅} = pc[2i] ⊕ (pc[2i+1] << 1)
- **Final design:** combine a short path-based component ({mi, P, G} or {mi, PxP, ∅}) with a long {mi, AxG, ∅} component in one perceptron that is trained jointly.
- **Training:** train on a mispredict or |out| < θ, where θ = "1.93·h + h/2" as extracted (h is presumably the number of tables; the formula may be garbled). Weights saturate.
- **Improvements for the CBP traces:**
  - **sign-bit splitting** (2 or 4 sign bits per magnitude)
  - **static weight boosting** (bias and most-recent tables ×2)
  - head-splitting and tail-sharing (bias table 1.875× larger; the 3 oldest-history tables half size)
  - {mi, AxPxPxP, ∅}
  - **5-bit weights suffice**
  - a slight not-taken bias
- **Results (SPECint2000):** up to 15.6% better than MAC-RHSP (at 1 KB) and 27.2% better than path-based neural (at 1 MB). It is the most accurate predictor at all sizes tested. They also show ahead-pipelining to 1-cycle effective latency.
- **Key claim:** hashed indexing can predict some linearly inseparable branches, because each table behaves like a small gshare.

### 2f. Jiménez, "Piecewise Linear Branch Prediction", ISCA-32, 2005 [READ]
URL accessed: https://people.engr.tamu.edu/djimenez/taco/pdfs/isca05_dist.pdf
- **Idea:** one linear function per *path* to the branch, so the decision surface is piecewise linear and can handle some inseparable functions. W is an n × m × (h+1) array of 8-bit weights.
- **Prediction:** `y = W[pc mod n, pc mod m, 0] + Σ_i (GHR[i] ? + : −) W[pc mod n, GA[i] mod m, i]`, where GA[i] is the address of the i-th prior branch.
- **Training:** if |y| < θ or mispredicted, `W[...,i] += (GHR[i] == taken) ? 1 : −1`. θ = 2.14(h+1) + 20.58, the same formula as the path-based neural predictor.
- **Table 2 [READ-garbled]:** tuned values are listed as (h, n, m):
  - 4 KB: (19, 1, 215)
  - 8 KB: (19, 2, 176)
  - 16 KB: (23, 4, 138)
  - 32 KB: (26, 8, 118)
  - 64 KB: (43, 8, 151)
  - 128 KB: (50, 8, 288)
  - 256 KB: (51, 8, 603)

  The column order may be garbled; the products n·m·(h+1) bytes do match the budgets. Note that PWL with n or m = 1 degenerates to a path-based or global perceptron.
- **Results (SPEC CPU2000 + SimPoints, deep pipeline):**
  - at 32 KB: 5.1% mispredicted vs 5.6% for path-based neural
  - at 256 KB: 4.6% vs 5.5% (path neural) and 5.9% (2Bc-gskew)
  - IPC +8% at 256 KB, +5% vs 2Bc-gskew at 64 KB in a 20-stage pipeline
  - idealized PWL with h = 128: about 4.0%
- **Limitations:** latency (it needs ahead pipelining plus an overriding 2K bimodal) and large weight storage per path.

### 2g. Seznec, "Analysis of the O-GEometric History Length branch predictor", ISCA-32, 2005 [READ-garbled for formulas]
URL accessed: https://pages.cs.wisc.edu/~isca2005/papers/06B-03.PDF
- **GEHL:** M tables (4–12, typically 8). T0 is indexed by PC; Ti by a hash of PC, the first L(i) global history bits, and min(L(i), 16) path bits. L(i) = int(α^(i−1)·L(1) + 0.5), a geometric series, e.g. 0, 2, 4, 8, …, 128.
- **Counters and sum:** signed saturating counters, mostly **4-bit** (5-bit on the short-history tables). S = M/2 + Σ C(i), using the centered form [formula symbols lost in extraction; the M/2 centering is from my memory of the paper, so INFERRED]. Predict taken if S >= 0. Update if mispredicted or |S| <= θ.
- **Dynamic threshold fitting:** a single 7-bit counter TC. On a mispredict, TC++, and when it saturates high, θ++ and TC = 0. On a correct update with |S| <= θ, TC−−, and when it saturates low, θ−− and TC = 0. The goal is to keep #updates-on-mispredict ≈ #updates-on-correct. A good static θ ≈ M for 4-bit counters.
- **Dynamic history-length fitting:** 11 lengths. T2, T4, and T6 can each switch between a short and a long length (L(2)/L(8), L(4)/L(9), L(6)/L(10)). A 9-bit aliasing counter AC, fed by 1 tag bit on half of T7's entries, flips the mode when it saturates. This gains about 0.2 misp/KI.
- **Reference 64 Kbit (8 KB) O-GEHL:** 8 tables. T0 is 2K × 5 bits, T1 is 1K × 5 bits, and T2–T7 are 2K × 4 bits. L = 0, 3, 5(/79), 8, 12(/125), 19, 31(/200), 49. Unconditional branches are inserted into ghist as taken bits, with 1 address bit per branch in the path. The index hash is a single stage of 3-input XOR over 3n picked bits. Using 2-input XOR costs 2–3%; no XOR costs 10–11%.
- **Results:** about 2.83 misp/KI average on CBP-1 traces (best L(1)/L(10) settings), compared with 3.03 without history fitting and 2.96 without the path/unconditional tricks. A 384 Kbit version averages 2.43.
- The paper also notes a circular-buffer history (checkpoint only the head pointer) and that the predictor is robust to over- or under-sizing of parameters.

### 2h. McFarling, "Combining Branch Predictors", DEC WRL TN-36, June 1993 [SEARCH-ONLY]
URL found (not opened): https://american.cs.ucdavis.edu/academic/readings/papers/mcfarling.pdf
- The details below are from general knowledge, not from this reading. Tournament predictor: two component predictors (e.g. bimodal + gshare) plus a PC-indexed table of 2-bit chooser counters. The chooser is updated only when the components disagree, toward whichever was correct. The same report introduced gshare.
- The Alpha 21264 style chooser used in HPCA'01 is a descendant. Today, TAGE-SC-L's choosers, MPP-TAGE's confidence chooser, and the CBP2025 MPP combiner are the modern, confidence-aware versions.

### 2i. Other related work (bibliographic only unless noted) [SEARCH-ONLY]
- Seznec, San Miguel, Albericio, "The Inner Most Loop Iteration counter: a new dimension in branch history", MICRO-48, 2015. IMLIcount is the number of consecutive times the last backward conditional branch was taken. Used in the SC of TAGE-GSC. https://www.irisa.fr/alf/downloads/seznec/IMLI.pdf
- Gope & Lipasti, "Bias-Free Branch Predictor", MICRO-47, 2014, pp. 521–532. A perceptron that learns correlations only with non-biased branches by filtering biased branches out of history; also a BF-TAGE variant. https://pharm.ece.wisc.edu/papers/micro14.pdf (CBP-4 version: https://jilp.org/cbp2014/paper/DibakarGope.pdf)
- Jiménez, "Strided Sampling Hashed Perceptron Predictor", CBP-4 2014. https://jilp.org/cbp2014/paper/DanielJimenez.pdf
- Akkary, Srinivasan, Koltur, Patil, Refaai, "Perceptron-Based Branch Confidence Estimation", HPCA-10, 2004, pp. 265–275. Trained on correct/incorrect rather than taken/not-taken.
- Seznec, "Storage Free Confidence Estimation for the TAGE branch predictor", HPCA 2011 (cited in §2d).
- "Taming Wild Branches: … Bullseye Predictor", arXiv 2506.06773 (2025). Runs TAGE-SC-L and two perceptrons on hard-to-predict branches; an arbiter picks the perceptron when its |y| and running win-rate clear a dynamic threshold and TAGE is not confident. Preprint; peer review not checked.
- Jiménez, "Multiperspective Reuse Prediction", MICRO 2017 (https://people.engr.tamu.edu/djimenez/pdfs/p436-jimenez.pdf). Applies the same multi-feature perceptron idea to cache reuse prediction. Not relevant beyond the methodology.
- Loh & Jiménez, "Reducing the power and complexity of path-based neural branch prediction", WCED 2005 (modulo path-history); Seznec, "Revisiting the perceptron predictor", IRISA TR 2004. Both are cited inside the hashed_perceptron.bpred header and the MPP papers; not opened.

---

## 3. Implementable recipe notes for this ChampSim setting (~64 KB, PC-only interface) [INFERRED from the above]

1. **Always-taken / trivial filter:** a per-PC (tagged or hashed) pair of bits {seen T, seen NT}, or two small Bloom filters as in MPP. Predict from the filter until both bits are set. Train the weights only for "both seen" branches. Separately decide (and tune) whether filtered branches enter GHIST and PATH. O-GEHL and MPP *do* insert unconditional branches; Gope & Lipasti *remove* biased ones. Cost: about 2 bits × 4–8K entries ≈ 1–2 KB.
2. **Hashing:** give each table its own PC skew or rotation, e.g. `pc ^ (pc >> (shift_i))`. Add a 16-bit path history (1–2 bits of PC per branch) to short tables, as O-GEHL does. Use folded history with per-table rotation (TAGE-style compressed history registers) instead of the plain chunk XOR.
3. **Weights:** 6 bits (MPP) or 4–5 bits (O-GEHL, Tarjan). Use the centered sum 2w + 1 if the weights are 2's-complement small counters (SC style).
4. **Threshold:** O-GEHL TC (7-bit) with θ0 ≈ number of tables. Optionally keep a small PC-indexed θ table (32–64 entries, Seznec).
5. **Coefficients:** fixed ×2 for the bias and short-history tables (Tarjan's "static boosting"), or SC-style dynamic factors in {1, 2}.
6. **Optional transfer function:** MPP-2025 form f(x) = 3.2x / (1 − x²/1600) as a 64-entry LUT.
7. **For TAGE + SC at 64 KB:** a rough split could be TAGE ≈ 44–48 KB, SC ≈ 8–12 KB, filter ≈ 1–2 KB, loop predictor ≈ 0.3 KB. Seznec's 64 KB split was TAGE ≈ 463.9 Kbits, SC ≈ 58.2 Kbits, LP 1.2 Kbits. TAGE-SC-L's global history uses 2–3 path/direction bits per branch and needs the target. Here, approximate it with PC bits of the *next* branch, which encode a lower bound on the target for taken branches.

---

## 4. Open limitations (from the papers plus the setting)
- **Linear separability.** Single-index perceptrons cannot learn XOR-type functions (HPCA'01). Hashed tables help only when the relevant branches share a weight (Tarjan). PWL mitigates this per path.
- **Feature-selection overfitting.** MPP features were tuned by genetic algorithm on CBP2016 traces. One feature hurt on full traces. Transfer to SPEC CPU2017 / DPC-3 x86 traces is **untested** (no source found evaluating MPP features on the DPC-3 SPEC17 traces).
- **Marginal value inside TAGE.** At 64 KB, MPP's extra features add only about 0.1 MPKI over TAGE-SC-L (4.147 → 4.048 vs TAGE-SC-L at 3.986). Contribution per feature is ≤ 0.025 MPKI. Gains must come from cheap, orthogonal information.
- **Interface limits here.** There is no branch type or target, so IMLI, backward-branch history, and path-plus-target history cannot be used as published. Unconditional branches are counted and pollute shared tables.
- **Thresholds.** A single global θ is a compromise. Per-PC θ gives only about 0.1–0.2% (Seznec), so limited upside.
- **Hardware realism.** Transfer function lookups, Bloom filters, and genetic-algorithm-tuned constants are acknowledged to be unrealistic (MPP 2025 discussion).

---

## 5. Extension ideas (modest, testable) and prior-art status

| # | Idea | Test | Prior art found | Novelty |
|---|---|---|---|---|
| 1 | **Type-blind trivial-branch filter plus history policy**: a per-PC T/NT-seen filter bypasses the perceptron or SC for branches never seen in both directions (this covers all unconditional branches, calls, and returns here). Compare 3 history policies: (a) insert as taken, (b) insert PC bits only into the path history, (c) exclude. | MPKI on the 10 traces vs `hashed_perceptron`, at the same 64 KB (shrink one table to pay for the filter). | MPP 2016 Bloom filters; MPP 2025 reports filtering as the top optimization (0.141 MPKI); Gope & Lipasti 2014 bias-free history filtering; O-GEHL inserts unconditional branches as taken; BTB "observed NT" bit (industry, per MPP 2025). | **Low.** The mechanism is known. The new part is the history-policy comparison under a type-blind interface with SPEC17. High expected payoff. |
| 2 | **Target-free exact backward-branch inference** (§0 item 3): when `predict_branch(B)` runs, classify the previous taken branch A as backward iff `ip(B) <= ip(A)`, and store a per-PC backward bit. Use this to build IMLI (backward and forward variants), a backward-branch global history (SC component, Seznec 2016), and BACKPATH (MPP 2025). Add these as 2–3 tables in the hashed perceptron or SC. | Ablation: each feature on/off at fixed storage; also verify the inference accuracy against ChampSim's own `branch_target` with a debug-only check. | IMLI (Seznec et al. 2015), forward IMLI (MPP 2016), BACKPATH (MPP 2025) all assume the target or type is available. A ChampSim2 GitHub PR notes TAGE-SC-L ports detect loops by comparing the next PC with the current PC, using the interface's next PC. No source found that derives backward direction from the *next branch PC* under a PC-only interface. | **Modest.** Mainly an enabling trick, but a clean, checkable contribution for this interface. |
| 3 | **Context-indexed confidence arbitration between TAGE and a hashed-perceptron SC**: a small table of chooser counters indexed by (TAGE confidence class (3), TAGE provider bucket, quantized \|SC sum\|/θ (4–8 bins), agree/disagree) chooses TAGE vs SC. This replaces fixed θ/2 and θ/4 rules. Optionally learn per-context additive biases online, a cheaper variant of the MPP 2025 combiner. | Compare with the TAGE-SC-L chooser rule at equal storage (only about 100–200 bits). | Strong prior art: TAGE-SC-L chooser (2016), MPP-with-TAGE confidence chooser (2016), MPP 2025 24-context linear combiner, Bullseye (2025 arXiv), Akkary 2004 perceptron confidence, McFarling 1993 chooser. | **Low.** Present it as a "simplified, storage-cheap combiner, re-evaluated on SPEC17", not as a new idea. |
| 4 (alt) | **Online feature usefulness gating**: track each table's standalone correctness (as MPP does for its alternate prediction) and set its coefficient to 0, 1, or 2 at runtime per phase. | Compare with static coefficients. | MPP 2016 tracks per-feature accuracy (best 20 of 37 on low confidence); TAGE-SC-L uses dynamic ×1/×2 factors per GEHL component; OH-SNAP (CBP-3) dynamic coefficients [SEARCH-ONLY citation via MPP-TAGE refs]. | **Low to modest.** The combination "per-phase gating with a coefficient of 0" was not found in a quick search. |
| 5 (alt) | **Feature transfer study**: port the MPP-2016 8 KB feature set (Figure 2) into the ChampSim hashed perceptron and measure each feature's leave-one-out value on SPEC17 DPC-3 traces. | Leave-one-out ablation, same as MPP Figure 2. | None found for SPEC17 / DPC-3. | **Evaluation novelty only.** |
| 6 (alt) | **Fix-the-baseline improvements** for `hashed_perceptron`: per-table PC skew, path bits, 6-bit weights with more entries, and θ0 = 16. | Ablate each change. | All in O-GEHL, Tarjan, and MPP. | None, but a cheap win and a useful stronger baseline. |

The recommended top 3 for the assignment are #1, #2, and #3 (or #4 instead of #3 if TAGE is not used).

---

## 6. Sources

Full text read (via pdftotext):
1. D. A. Jiménez, C. Lin. Dynamic Branch Prediction with Perceptrons. HPCA-7, 2001. https://www.cs.utexas.edu/~lin/papers/hpca01.pdf
2. D. A. Jiménez. Multiperspective Perceptron Predictor. CBP-5, 2016. https://jilp.org/cbp2016/paper/DanielJimenez1.pdf
3. D. A. Jiménez. Multiperspective Perceptron Predictor with TAGE. CBP-5, 2016. http://www.jilp.org/cbp2016/paper/DanielJimenez2.pdf
4. D. A. Jiménez. Multiperspective Perceptron Predictor. CBP 2025. https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final53-Jimenez.pdf
5. A. Seznec. TAGE-SC-L Branch Predictors Again. CBP-5, 2016. http://www.jilp.org/cbp2016/paper/AndreSeznecLimited.pdf
6. D. Tarjan, K. Skadron. Merging Path and Gshare Indexing in Perceptron Branch Prediction. ACM TACO 2(3):280–300, 2005. https://www.cs.virginia.edu/~skadron/Papers/taco_bpred_sep05.pdf
7. D. A. Jiménez. Piecewise Linear Branch Prediction. ISCA-32, 2005. https://people.engr.tamu.edu/djimenez/taco/pdfs/isca05_dist.pdf
8. A. Seznec. Analysis of the O-GEometric History Length Branch Predictor. ISCA-32, 2005. https://pages.cs.wisc.edu/~isca2005/papers/06B-03.PDF
9. CBP-5 program listing: http://www.jilp.org/cbp2016/program.html

Bibliographic or snippet only (not read in full):
10. S. McFarling. Combining Branch Predictors. DEC WRL TN-36, 1993. https://american.cs.ucdavis.edu/academic/readings/papers/mcfarling.pdf
11. A. Seznec, J. San Miguel, J. Albericio. The Inner Most Loop Iteration counter. MICRO-48, 2015. https://www.irisa.fr/alf/downloads/seznec/IMLI.pdf
12. D. Gope, M. Lipasti. Bias-Free Branch Predictor. MICRO-47, 2014. https://pharm.ece.wisc.edu/papers/micro14.pdf
13. D. A. Jiménez. Strided Sampling Hashed Perceptron Predictor. CBP-4, 2014. https://jilp.org/cbp2014/paper/DanielJimenez.pdf
14. H. Akkary et al. Perceptron-Based Branch Confidence Estimation. HPCA-10, 2004. DOI 10.1109/HPCA.2004.10002
15. Bullseye predictor, arXiv 2506.06773 (2025). https://arxiv.org/abs/2506.06773
16. D. A. Jiménez. Multiperspective Reuse Prediction. MICRO 2017. https://people.engr.tamu.edu/djimenez/pdfs/p436-jimenez.pdf
17. ChampSim2 PR discussing next-PC loop detection in TAGE-SC-L port. https://github.com/rahulbera/ChampSim2/pull/2

Not accessed:
- TAGE-SC-L 2014 (CBP-4) paper
- CBP2016 MPP source code, which holds the exact 64 KB feature list
- IMLI full text
- Bias-Free full text
- McFarling full text
- O-GEHL CBP-1 original (JILP 2005, "Genesis of the O-GEHL")
