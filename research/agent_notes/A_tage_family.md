# Topic A — TAGE and tagged predictors (research notes)

Author: research agent A. Date: 2026-10-30.
Scope: TAGE (2006), L-TAGE (2007), "A New Case for TAGE" (MICRO 2011), TAGE-SC-L (CBP-4 2014 / CBP-5 2016),
BATAGE (TACO 2018), Seznec's "TAGE engineering cookbook" (2024) and CBP-2025 TAGE-SC, plus allocation/useful-bit
related work. The goal is an implementation in the old ChampSim (2021) `branch/*.bpred` interface at about 64 KB.

## Legend: what was read and what was inferred

- **[READ]** I downloaded the primary document and read the relevant sections myself (full text or source code).
- **[READ-PARTIAL]** I read only some sections: abstract/intro, or specific pages rendered as images.
- **[SECONDARY]** I only saw a summary, either from a fetch tool or a search snippet. Verify before you cite it.
- **[INFERRED]** My own reasoning, extrapolation or arithmetic. Not stated by the authors.

Read-only copies of the downloads are in the session scratchpad (`.../scratchpad/dl/` and `.../scratchpad/A_tage/`).
Those paths are temporary. Re-download from the URLs in the Sources list.

---

## 0. TL;DR for the implementer

1. **Baseline to build first:** a "pure" TAGE with 1 bimodal table and about 12 tagged tables, using geometric history
   lengths (e.g. 4…640 as in L-TAGE). Use folded-history (CSR) index/tag hashing, a 3-bit ctr, a 1–2 bit u, and 8–13
   bit tags. Add USE_ALT_ON_NA. Allocate 1–2 entries on a misprediction. Manage u with the TICK counter. This fits in
   about 59–61 KB (configs in §8).
2. **ChampSim simplifications:** `last_branch_result` comes straight after `predict_branch`, so the update is
   immediate. That means:
   - no Immediate Update Mimicker,
   - no speculative history repair,
   - no re-read at retire,
   - **local-history components (LSC / local SC) become trivially implementable.** In real hardware they are the
     hard part (Seznec 2011, 2024).
3. **The predictor sees every branch type and has no target.** Every branch, including jumps, calls and returns, must
   be pushed into the global history (as in TAGE). Use PC bits instead of target bits for path history. x86 PCs are
   not 4-byte aligned, so **do not** apply BATAGE's `PC_SHIFT 2` (that was for ARM CBP-2016 traces) [INFERRED].
4. **Most promising student extension areas** (prior art in §9):
   - (a) per-branch (PC-indexed) allocation throttling for TAGE;
   - (b) "CAT for TAGE" using TAGE counter-state statistics as a proxy for BATAGE's NHC/MHC (Michaud 2018 lists
     this as an open problem; Seznec 2024/2025 partially addressed it with a different signal);
   - (c) localized/adaptive u-bit aging.

---

## 1. TAGE 2006 — Seznec & Michaud [READ]

- **Citation:** A. Seznec, P. Michaud, "A case for (partially) TAgged GEometric history length branch prediction",
  *Journal of Instruction-Level Parallelism* (JILP) vol. 8, Feb/Apr 2006.
- **URL accessed:** https://inria.hal.science/hal-03408381/document (HAL copy, 24 pp.). Read §1–§4.
  - HAL blocks browser user-agents with an "Anubis" bot challenge; `curl -A curl/8.5.0` works.
- **Structure:**
  - Base predictor T0: a PC-indexed bimodal of 2-bit counters.
  - M tagged components Ti, each indexed by hash(PC, global history h[0:L(i)], path history).
  - Geometric lengths: L(i) = (int)(α^(i−1)·L(1) + 0.5).
  - Entry: 3-bit signed ctr (sign = prediction), partial tag, and a **2-bit u counter** (in this paper).
- **History:**
  - Global history includes non-conditional branches (as a taken bit).
  - A 16-bit path history uses 1 address bit per branch.
  - Circular buffer for speculative repair.
- **Prediction:**
  - The provider is the hitting component with the longest history.
  - altpred is what would have been predicted if the provider had missed (next hitting component, else the base).
  - §3.2.4 "newly allocated" optimization:
    - An entry counts as newly allocated if u == 0 and ctr is weak (0 or −1).
    - On such entries, altpred is often more accurate (INT-3, MM-1, MM-2).
    - The choice is monitored globally by a single **4-bit counter** (later named USE_ALT_ON_NA).
- **Update:**
  - **u counter:**
    - Updated only when altpred ≠ pred. Incremented if pred is correct, decremented otherwise.
    - Graceful aging: periodically reset the MSB column of all u, then the LSB column.
    - Period **256K branches**.
  - **Correct prediction:** update the provider ctr.
  - **Misprediction:** update the provider ctr. If the provider is not the longest table, try to allocate **at most
    one** entry in some Tk with k > i:
    - (A) If some Tk has u_k == 0, allocate there. Otherwise decrement u of all Tj (j > i) and do not allocate.
    - (B) Anti ping-pong: if Tj and Tk (j < k) are both free, pick Tj with twice the probability of Tk (LFSR).
    - (C) New entry gets ctr = weak correct and u = 0 ("strong not useful").
- **Results** (CBP-1 traces, 20 traces × 30M instructions, chained without reset):
  - 64 Kbit 8-component TAGE: 2.61 misp/KI, vs. O-GEHL 2.83.
  - 1 Mbit: 2.05 vs. 2.27.
  - 15 components gave "no significant return" over 8 at those sizes.
- **CBP-rules configs** (64 Kbit + 256 bits):
  - 5-component: tags 8, 8, 9, 9; 1K-entry tables; lengths (5, 15, 44, 130); **2.678 misp/KI**.
  - 8-component: tags 9, 9, 10, 10, 11, 11, 12; 512-entry tables; lengths (5, 9, 15, 25, 44, 76, 130);
    **2.553 misp/KI**.
  - Both: bimodal 8K pred bits + 2K hysteresis bits (1 hysteresis bit shared by 4 entries).
- **Other findings:**
  - Tag width should grow with history length; a false match hurts more on long-history tables.
  - Associativity helps only at 32 Kbit; it is "essentially useless" at ≥ 64 Kbit.
  - 2-bit ctr + 1-bit u is sufficient on most traces (57 Kbit TAGE: 2.78 vs. 2.61).
  - The paper also introduces ITTAGE (indirect) and COTTAGE.

## 2. L-TAGE 2007 — Seznec [READ-PARTIAL: pp. 1, 4–7 viewed as images; the PDF text layer is font-garbled]

- **Citation:** A. Seznec, "The L-TAGE Branch Predictor", JILP vol. 9, May 2007 (CBP-2 winner, realistic track).
- **URL accessed:** https://jilp.org/vol9/v9paper6.pdf
- **Configuration:**
  - 13-component TAGE: 1 bimodal + 12 tagged, 256 Kbit budget, plus a loop predictor.
  - **3.314 misp/KI** on the CBP-2 traces.
- **Table 1 (exact):**

  | | Base | T1, T2 | T3, T4 | T5 | T6 | T7 | T8, T9 | T10 | T11 | T12 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | History length | 0 | 4, 6 | 10, 16 | 25 | 40 | 64 | 101, 160 | 254 | 403 | 640 |
  | Entries | 16K pred + 4K hyst | 1K | 2K | 2K | 2K | 1K | 1K | 1K | 0.5K | 0.5K |
  | Tag width (bits) | — | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |

  - Each entry has a 3-bit ctr and a 2-bit u.
  - TAGE total is 241.5 Kbit. The loop predictor is 13 Kbit. Extra state is 1,344 bits (two 640-bit global
    histories, two 16-bit path histories, 4-bit USE_ALT_ON_NA, 19-bit u-reset counter, 2-bit PRNG, 7-bit WITHLOOP).
  - Grand total 261,952 bits.
- **Prediction:**
  - If (provider ctr not weak) OR (USE_ALT_ON_NA < 0), use the provider. Otherwise use altpred.
  - "Weak" means newly allocated.
- **u update and aging:**
  - u is updated when altpred ≠ pred.
  - Alternating reset: MSB and LSB are cleared alternately, and the significance of the u0/u1 bits is flipped after
    each reset.
  - Period **512K branches** (256K in the 2006 paper). The optimal period grows with predictor size.
- **ctr update:** the provider ctr is updated. **If the provider u == 0, altpred is also updated.**
- **Allocation:**
  - At most 1 entry per misprediction.
  - The search for a free entry starts at Tb: b = i+1 with probability 1/2, i+2 with probability 1/4, i+3 with
    probability 1/4 (a 2-bit PRNG).
  - New entry: ctr weak correct, u = 0.
- **Loop predictor:**
  - 256 entries, 4-way.
  - Entry: 14-bit past iteration count, 14-bit current count, 14-bit tag, 2-bit confidence, 8-bit age (52 bits).
  - Used when confidence is saturated, i.e. the same trip count has been seen 3 times.
  - Age-based replacement: set to 255 on allocation; replace only at age 0.
- **Separate user/kernel histories** (the CBP-2 traces contained both). Not relevant to ChampSim user traces
  [INFERRED].

## 3. "A New Case for the TAGE Branch Predictor" — Seznec, MICRO-44 2011 [READ]

- **Citation:** A. Seznec, MICRO'11, Porto Alegre, pp. 117–127. DOI 10.1145/2155620.2155635.
- **URL accessed:** https://www.cs.cmu.edu/~18742/papers/Seznec2011.pdf (11 pp.). HAL id: hal-00639193.
- **Methodology:**
  - CBP-3 (JWAC-2) framework: 40 traces of about 50M micro-ops (CLIENT, INT, MM, SERVER, WS), with user and system
    activity.
  - The metric is MPPKI (misprediction penalty per kilo-instructions).
  - Updates are delayed to retire.
- **Reference 64 KB TAGE (§3.4)** — 13 components, (6, 2000) geometric series, 65,408 bytes:
  - Bimodal: 32K prediction bits + 8K hysteresis bits.
  - Tagged tables:

    | Tables | Entries per table |
    |---|---|
    | T1 | 2K |
    | T2–T7 | 4K |
    | T8–T9 | 2K |
    | T10–T12 | 1K |

  - Tag width for Ti is printed as "max(6+i, 15)".
  - [INFERRED] I could not reproduce 65,408 B with either max() or min(). min(6+i, 15) with 3-bit ctr + 1-bit u
    gives about 69 KB. Treat the tag formula as uncertain or a typo. The intent is clearly "tags grow with i, about
    7…15 bits".
- **Changes vs. 2006/2007:**
  - **Single u bit** per entry.
  - **Multiple allocation:** on a misprediction allocate up to **4** entries (in practice 3–4) in non-consecutive
    tables Tk, k > provider, choosing u = 0 entries. New entries get ctr = weak correct and u = 0. This works for
    large predictors (256–512 Kbit). For small predictors (e.g. 64 Kbit) or few tables, footprint limits still favor
    allocating 1 entry.
  - **Global u reset via an 8-bit allocation monitor:**
    - +1 when an allocation attempt fails because u = 1, −1 when it finds u = 0.
    - When it saturates (more failures than successes), reset **all** u bits.
    - In practice this happens when about half of the used entries are useful.
    - Stated to beat the earlier 2-bit u management.
- **Implementation tradeoffs:**
  - 5–8 tables suit 32–64 Kbit; 12–15 tables suit 256–512 Kbit.
  - About 12-bit tags suit 13 tables; wider tags help for long histories.
  - The maximum history can range from about 100 to more than 1000 with similar accuracy.
- **Delayed update (§4):**
  - Scenario results (MPPKI), TAGE vs. gshare vs. GEHL:

    | Scenario | TAGE | gshare | GEHL |
    |---|---|---|---|
    | [I] oracle immediate | 609 | 944 | 664 |
    | [A] re-read at retire | 617 | 970 | 685 |
    | [B] read only at fetch | 640 | 1292 | 801 |
    | [C] re-read only on mispredictions | 625 | 1011 | 744 |

  - TAGE suffers least because only 1–2 entries are involved per prediction.
  - Bank-interleaved single-port tables have a small cost.
  - **Not relevant to ChampSim** (immediate update) [INFERRED].
- **Side predictors (ISL-TAGE = TAGE + IUM + Loop + SC):**
  - **IUM:** if a prediction comes from the same table entry as an in-flight, executed-but-unretired branch, use that
    branch's outcome. Unneeded in ChampSim.
  - **Loop predictor:** 64 entries, 4-way skewed. Entry: 10-bit past count, 10-bit retire count, 10-bit tag, 3-bit
    confidence, 3-bit age, 1 direction bit (37 bits). High confidence after 7 identical trips. TAGE+IUM 609 → 593
    MPPKI.
  - **Statistical Corrector (global):**
    - 4 GEHL-like tables with lengths (0, 6, 10, 17), 1K × 6-bit each (24 Kbit), indexed with PC/history and the
      TAGE prediction.
    - Sum = Σ centered counters (2·ctr+1) + 8 × centered TAGE provider ctr.
    - Revert TAGE if the sum disagrees and |sum| > a dynamic threshold (GEHL-style threshold adaptation).
    - 593 → 580 MPPKI.
  - **TAGE-LSC (local-history SC):**
    - 32-entry local history table; LGEHL of 5 tables × 1K × 6-bit, lengths (0, 4, 10, 17, 31).
    - A 30 Kbit LSC alone on TAGE+IUM gives 559 MPPKI. It "dwarfs" the loop predictor plus global SC.
    - Full TAGE+IUM+loop+SC+LSC: 555 MPPKI.
    - 512 Kbit TAGE-LSC: 562 MPPKI vs. ISL-TAGE 581.
- **Robustness:**
  - History series (3,300) → 575, (4,1000) → 563, (8,5000) → 563 MPPKI.
  - 9 components at (6,1000): 566. 6 components at (6,500): 583.
- **Stated limitation:** FTL++ and OH-SNAP slightly beat TAGE-LSC on the 7 hardest traces (about 2222–2227 vs. 2287
  MPPKI). The paper attributes this to correlation forms that TAGE does not capture.

## 4. TAGE-SC-L (CBP-4 2014, CBP-5 2016) — Seznec [READ: 2016 paper and full 64 KB source; 2014 paper skimmed]

- **Citations:**
  - A. Seznec, "TAGE-SC-L Branch Predictors", CBP-4, 2014 (HAL hal-01086920).
  - A. Seznec, "TAGE-SC-L Branch Predictors Again", CBP-5, Seoul, June 2016 (HAL hal-01354253).
- **URLs accessed:**
  - Paper: https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf
  - Code: https://jilp.org/cbp2016/code/AndreSeznecLimited.tar.gz (`cbp64KB/predictor.h`, 1714 lines)
  - CBP-4 paper: https://inria.hal.science/hal-01086920/document
- **Headline results** (CBP-5 training traces):
  - 64 KB (523,355 bits): 3.986 MPKI.
  - 8 KB: 4.991 MPKI.
  - SC is worth about 8% (64 KB) and about 6% (8 KB). The loop predictor is worth about 0.3%.
- **64 KB TAGE component (from the paper and code):**
  - **Bimodal:** 8K prediction bits + 2K hysteresis bits (hysteresis shared by 4; `LOGB 13`, `HYSTSHIFT 2`).
  - **Bank-interleaved tagged storage:** `NHIST 36` logical tables (18 distinct lengths, each used twice).
    - Low group: 10 banks × 1K entries, 12 bits each, tag 8.
    - High group: 20 banks × 1K entries, 16 bits each, tag 12.
    - `BORN 13` splits the groups.
    - The bank for logical table i is rotated by (PC ^ phist) mod #banks, so all tables share physical space.
  - **History lengths:** `MINHIST 6`, `MAXHIST 3000`. Computed m[i] for the 18 distinct lengths:
    6, 9, 12, 18, 26, 37, 54, 78, 112, 161, 232, 335, 482, 695, 1002, 1444, 2081, 3000.
  - Some logical tables are disabled (`NOSKIP`). 2-way associativity applies only to the middle lengths
    (`BORNINFASSOC 9` .. `BORNSUPASSOC 23`), worth −0.6%.
  - `CWIDTH 3` ctr, `UWIDTH 1` u (the comment says 2-bit u "not worth" it at 512 Kbit), `PHISTWIDTH 27` path
    history.
  - `NNN 1`: allocate up to 1+NNN = 2 entries.
  - 16 USE_ALT_ON_NA counters (5-bit), indexed by ((HitBank−1)/8, AltConf).
- **Index/tag hashing** (code, worth copying for ChampSim):
  - `gindex = PC ^ (PC >> (|logg − bank| + 1)) ^ foldedhist_i(L_i → logg bits) ^ F(phist, min(L_i, 27), bank)`.
    F is a bank-dependent rotate-and-XOR mix of path history.
  - `gtag = PC ^ fold(L_i → TB bits) ^ (fold(L_i → TB−1 bits) << 1)`.
  - **Folded history (CSR) update:**
    `comp = (comp<<1) ^ h[new]; comp ^= h[old at L] << (L % CLEN); comp ^= comp >> CLEN; comp &= mask`.
  - **History insertion per branch:**
    - Not 1 bit: 2 bits for direct branches, 3 for indirect.
    - Bits come from `T = (PC ^ (PC>>2)) ^ taken` (indirect: also target bits).
    - Path bits come from `PC ^ (PC>>2) ^ (PC>>4)`.
    - ChampSim has no type or target information, so use 2 bits of `(pc ^ pc>>2) ^ taken` for every branch
      [INFERRED].
- **TAGE prediction (code):**
  - HitBank = longest hit. AltBank = next hit. alttaken = AltBank's ctr or bimodal.
  - If USE_ALT_ON_NA[idx] ≥ 0 and |2·ctr+1| == 1 (weak), predict alttaken. Otherwise predict LongestMatchPred.
  - HighConf: |2ctr+1| ≥ 7. MedConf: == 5. LowConf: == 1.
- **TAGE update (code, exact rules):**
  1. **Allocation decision.** `ALLOC = (tage_pred != taken) && HitBank < NHIST`.
     - If the longest entry is "pseudo-new" (weak ctr) and LongestMatchPred was correct, do not allocate.
     - Train USE_ALT_ON_NA when LongestMatchPred ≠ alttaken.
     - If the **final** prediction (after SC) was correct, still allocate with probability 1/32.
  2. **Allocation.**
     - Start near HitBank+1 or +2 (randomized, about 25% chance of skipping one more).
     - Walk upward over pairs of logical tables.
     - Take an entry if u == 0 **and |2ctr+1| ≤ 3** (`OPTREMP`: a u = 0 entry with medium/strong ctr is not
       replaced; its ctr is decayed toward 0 instead). This "nearly fills the gap between 1-bit and 2-bit u".
     - New entry: ctr = taken ? 0 : −1.
     - Allocate up to 2 entries, skipping consecutive tables.
  3. **Penalty/TICK u-reset.**
     - Penalty counts u = 1 entries met. NA is the number of allocations.
     - `TICK += Penalty − 2·NA`, clamped at ≥ 0.
     - When `TICK ≥ BORNTICK (1024)`, every u is halved (`u >>= 1`) and TICK is reset.
  4. **ctr update.**
     - If the provider ctr was weak and mispredicted, also update the alt entry (or the bimodal). This "acts as a
       protection".
     - Always update the provider ctr.
     - If the ctr becomes weak, set u = 0.
     - If alt was correct and strongly saturated (|2ctr+1| == 7) and the provider u == 1 and the provider was
       correct, clear u.
  5. **u update.** If LongestMatchPred ≠ alttaken and LongestMatchPred was correct, u++.
  - Paper trick for 8 KB: DIP-like allocation, sometimes setting u = 1 instead of 0 on allocation (−0.2%).
- **SC (64 KB):**
  - Bias tables indexed by PC + TAGE prediction/confidence/HitBank.
  - GEHL components on global branch history, global backward-branch history, IMLI, and 3 local histories (256, 16,
    16 entries).
  - 6-bit counters, PC-indexed dynamic thresholds, per-component multiplicative weights, a small chooser.
  - 58,190 bits total.
- **CBP-4 2014 note [READ-PARTIAL]:**
  - "For the limited size predictor, … allocating two entries on a misprediction is slightly better than allocating a
    single entry."
  - "When the misprediction ratio is high, one should avoid to allocate many entries (avoiding pollution)", i.e. it
    dynamically picks 1 vs. 2.
  - **This is early prior art for global allocation throttling in TAGE.**
- **Stated limitations (2016 conclusion):** the championship design uses an unrealistic number of tables, tag widths
  and SC schemes. Simpler designs reach similar accuracy.

## 5. BATAGE — Michaud, ACM TACO 15(3):30, 2018 [READ: paper and author source code]

- **Citation:** P. Michaud, "An Alternative TAGE-like Conditional Branch Predictor", *ACM Transactions on
  Architecture and Code Optimization* 15(3), Article 30, 2018. DOI 10.1145/3226098.
- **URLs accessed:**
  - Open-access author version: https://inria.hal.science/hal-01799442/document (25 pp.)
  - Author C++ simulator: https://files.inria.fr/pacap/michaud/BATAGE_simulator-1.zip (`batage.h`, `batage.cc`,
    CBP-2016 glue)
- **Diagnosis: the "cold counter problem".**
  - TAGE allocates on nearly every misprediction and resets the ctr. With no global correlation the new ctr is
    often initialized in the wrong direction.
  - An up/down counter cannot tell "cold" from "weakly biased".
  - Bernoulli analysis: reaching within 5% of optimal takes 8 occurrences at q = 0.1 and 20 at q = 0.3.
  - This is why TAGE benefits from an SC.
- **Dual counter (n1, n0):**
  - Replaces ctr + u in tagged entries: 3 bits each, `nmax = 7`, so a 6-bit payload.
  - Prediction: n1 > n0.
  - Update:
    ```
    if taken { if (n1 < 7) n1++; else if (n0 > 0) n0--; }
    else     { if (n0 < 7) n0++; else if (n1 > 0) n1--; }
    ```
  - Decay: decrement the larger of n1/n0.
  - The bimodal stays a conventional counter. In the code it is mapped to an equivalent dual counter for
    comparison.
- **Bayesian confidence:**
  - Misprediction estimate m̂ = (1 + min(n1, n0)) / (2 + n1 + n0) (Laplace's rule).
  - High if m̂ < 1/3, medium if = 1/3, low if > 1/3.
  - Hardware form:
    - `medium = (n1 == 2n0+1) || (n0 == 2n1+1)`
    - `low = (n1 < 2n0+1) && (n0 < 2n1+1)`
    - `m = 2·low + medium`; a tag miss gives m = 3.
- **Prediction:** pick the hitting entry with the **smallest m**, ties going to the **longest** history, with the
  bimodal as candidate L0. The code adds a small "meta" tweak: an entry with n0+n1 == 1 is treated as high
  confidence when the meta counter ≥ 0.
- **Update (Table 3; Lp = provider, Ln = next hitting entry shorter than Lp):**
  - Hitting entries longer than Lp (skipped as cold) are always updated with the outcome.
  - Lp is updated, **except** it is decayed when Lp > L0, both Lp and Ln are high confidence, and Ln predicted
    correctly ("entry probably useless").
  - Ln is updated if Lp is not high confidence.
- **Eviction rule (replaces u bits):** a high-confidence entry cannot be evicted. Entries become evictable via decay.
- **Allocation:**
  - Only on mispredictions, at most 1 entry.
  - Start at Lm+s, where Lm is the longest hit and s is a random value in [1, SKIPMAX].
  - Take the first not-high-confidence entry.
  - High-confidence entries skipped on the way are decayed with probability PDEC (1/4 in the paper).
- **Controlled Allocation Throttling (CAT) (Fig. 6):**
  - A cat counter sets the allocation probability. Allocate only if `rand % MINAP ≥ cat·MINAP/(CATMAX+1)`.
  - While scanning, count skipped "MHC" entries: moderately high confidence, 0.17 < m̂ < 1/3, i.e. high but not
    {n0 = 0, n1 ≥ 4} / {n1 = 0, n0 ≥ 4}.
  - After a successful allocation: `cat += CATR_NUM − mhc·CATR_DEN`, clamped to [0, CATMAX].
  - Rationale: many not-high-confidence entries relative to MHC entries means allocation is too aggressive.
  - Paper: CATR = 3/4. Code: 2/3, `CATMAX = (2<<15)−1`, `MINAP = 16`.
- **Code config (8 KB tuned for CBP-2016):**
  - `NUMG 26` tagged banks of `LOGG 7` (128 entries).
  - `TAGBITS 12` (including 2 "GHG" bits identifying the history-length group under bank interleaving).
  - `MINHIST 4`, `MAXHIST 700`. Lengths: 4, 5, 6, 7, 9, 11, 13, 16, 20, 25, 31, 38, 47, 58, 72, 88, 109, 134, 164,
    202, 249, 306, 376, 463, 569, 700.
  - Path history 30 × 6 bits.
  - Bimodal: 4K prediction bits, 1K × 2 hysteresis bits.
  - Bank interleaving à la TAGE-SC-L, with `MIDBANK 10`.
  - Two code-only extras: `USE_META` and "controlled decay" (`USE_CD`; a cd counter like cat governs the decay
    probability on skipped entries).
  - The skip count in the code is randomized with an upper bound scaled by the provider's |n1−n0|.
  - History hashing uses a folded-history class (Michaud's 2001 tech report / PPM-like CBP-2004).
  - The index mixes the direction-history fold with a path-history fold for short lengths (≤ 30).
  - The tag mixes a bit-reversed direction fold with the path fold.
- **Results** (CBP-2016, 223 tuning / 440 evaluation traces; arithmetic mean MPKI):

  | Predictor | Size | MPKI |
  |---|---|---|
  | TAGE | 7 KB | 4.42 |
  | TAGE-GSC | 8 KB | 4.27 |
  | **BATAGE** | 7 KB | **4.29** |
  | BATAGE-GSC | 8 KB | 4.24 |

  - Conclusion: BATAGE "does not need statistical correction".
  - Ablation: CAT off → 4.43, i.e. no better than TAGE. Restricting selection to the 2 longest hits → 4.38
    (4.58 without CAT). PPM-like longest-only → 4.62.
  - The 8 KB BATAGE matches the MPKI of the CBP-2016 8 KB winner. 32 KB and 64 KB points appear only in Fig. 1:
    gains are "modest on average, but tangible".
- **Allocation throttling on TAGE (§6.3):**
  - A fixed allocation probability (1/2, 1/4) helps some traces and hurts others.
  - A "magic CAT" (TAGE fed BATAGE's cat value in lockstep) shows significant potential on several tens of traces.
  - **"Finding a CAT method for TAGE is a topic for future research."** Footnote: Seznec was aware of the benefit
    but "had not found a way to control it" (as of July 2017).
- **Stated limitations:** dual-counter decay versus u bits "work differently, and perhaps they provide distinct
  advantages". CAT parameters must be retuned when NUMG/LOGG change. Per the code comments, larger predictors may
  need a larger CATMAX.

## 6. Seznec 2024 "TAGE: an engineering cookbook" and CBP-2025 TAGE-SC [READ: slides viewed as images; CBP-2025 paper read]

- **Citations:**
  - A. Seznec, "TAGE: an engineering cookbook", Inria Research Report RR-9561, Nov 2024 (hal-04804900).
    - 4-page note plus about 70 slides. Simulator: https://files.inria.fr/pacap/seznec/TageCookBook/ (not
      downloaded).
  - A. Seznec, "TAGE-SC for CBP2025", CBP-2025, Tokyo, June 2025.
- **URLs accessed:**
  - https://hal.science/hal-04804900/document (rendered with ghostscript; poppler mis-renders pages past 10)
  - https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf
- **Results** (CBP-2016 traces, about 512 Kbit):

  | Configuration | MPKI |
  |---|---|
  | Full TAGE-SC-L 2016 | 4.140 |
  | Pure TAGE 2016 | 4.451 / 4.391 |
  | "Realistic" pure TAGE: 7 physical tables = 14 logical, 2 logical tables per physical table | 4.603 → 4.527 |
  | Same, with non-geometric lengths concentrated in the middle | 4.494 |
  | Same, with allocation/replacement optimizations | **4.406** |
  | Realistic TAGE-SC, global information only | 4.146 |

  - TAGE-SC-L's SC is worth 5.7% over TAGE at iso-storage.
  - u: 1 bit 4.528, 2 bits 4.494. Tags: 11 bits 4.515, 12 bits 4.494.
- **Allocation/replacement optimizations (slides 37–41, CBP-2025 §2.2), total −0.088 MPKI (2%):**
  - **Filtering allocation (−0.04).**
    - If the misprediction ratio is high (> 1/9, via a counter), reduce allocation on long-history tables (T8+).
    - If the ratio of correct predictions on **weak** counters is low (tracked with **probabilistic counters**,
      Riley & Zilles HPCA 2006), allocate with probability 1/8 when < 50% and 1/2 when < 16/31.
    - CBP-2025 version: 1/16 below 1/2, 1/4 below 16/31, 1/2 below 8/15. More entries are allocated when
      confidence is high.
  - **First u setting (−0.02):** set u = 1 on the first allocated entry. Randomly reset u when the prediction is
    weak and allocation is denied.
  - **Protect recently useful entries (−0.01):** set u to 2 instead of 1 so the entry survives one smooth reset.
    Only reset u when 4/5 of entries are useful if the misprediction rate is high.
  - **Update HCPRED and AltPred on a weak, mispredicting Pred (−0.015).**
  - **HCPRED** ("longest hitting not-weak entry") replaces altpred in the selection, shortening the critical path.
  - 2-way (skewed) associativity is worth about 4.383, with zcache/elbow-style relocation.
- **CBP-2025 TAGE-SC (192 KB):**
  - 3.363 MPKI on the CBP-2025 traces; TAGE-only 3.781.
  - 28 banks of 2K 19-bit entries; 3-bit bimodal counters; 5 path bits per branch.
  - History 3..1000, favoring middle lengths.
  - The loop predictor is dropped: new IMLI variants (BrIMLI/TaIMLI) capture loops.
- **Prior-art consequence:**
  - *Global* allocation throttling in TAGE now exists in published form (2014 crude, 2024/2025 refined).
  - It is a **global, confidence-based** filter, not a per-branch one and not BATAGE-style CAT.

## 7. Other related work (prior-art checks)

- **PPM-like predictor**, P. Michaud, JILP 7, 2005 (CBP-1) [READ-PARTIAL; https://inria.hal.science/hal-03406188/document].
  - 5 tables; u bit; m bit in the bimodal to control new-entry ctr init.
  - **Folded global history via circular shift register (CSR)**, e.g. 20 → 8 bits.
  - Origin of the folding used by all TAGE code.
- **Pruett, Zangeneh, Fakhrzadehgan, Lin, Patt**, "Dynamically Sizing the TAGE Branch Predictor", CBP-5 2016
  [READ-PARTIAL; https://jilp.org/cbp2016/paper/StephenPruettFinal.pdf].
  - Reconfigurable tiles reassign storage among history lengths every 100K-prediction quantum, plus a victim cache.
  - 64 KB: 4.265 MPKI.
  - Prior art for per-table capacity adaptation.
- **Lin & Tarsa**, "Branch Prediction Is Not a Solved Problem", IISWC 2019 [READ-PARTIAL: abstract and intro, from
  a copy another agent downloaded].
  - TAGE-SC-L mispredictions on SPECint 2017 come from (1) a small number of systematically hard-to-predict (H2P)
    branches and (2) rare branches.
  - Scaling predictor resources does not fix them.
- **Behrendt, Pun, Nair**, "Taming Wild Branches: … Bullseye Predictor", CBP-2025 / arXiv 2506.06773
  [SECONDARY via WebFetch summary].
  - A per-PC H2P Identification Table (26 × 8 ways) flags branches with ≥ 2048 executions, ≥ 256 mispredictions and
    low accuracy.
  - Flagged branches get local/global perceptrons.
  - Once a perceptron wins 128 times in a row, **TAGE/SC updates for that PC are suppressed** (update filtering).
  - The update filtering alone reportedly gives < 0.3%. Total about 1.4% MPKI reduction at +28 KB.
  - **Closest prior art to "per-branch throttling", but it needs a side predictor and suppresses all updates, not
    allocation.**
- **Cai, Deshmukh, Lai, Mansoorshahi, Tatulescu, Nudelman, Patt**, "TAGE-SC-L with a Code Structure Correlator",
  CBP-2025 [READ-PARTIAL: bloom-filter section].
  - A PC Bloom filter: a branch is inserted after its first misprediction by an O-GEHL-style CSC.
  - TAGE-SC-L predicts and **is updated only for branches in the filter**, so easy branches never consume TAGE
    entries.
  - −0.04 MPKI.
  - **Prior art for "keep easy/always-taken branches out of TAGE".**
- **Chang, Evers, Patt**, "Improving branch prediction accuracy by reducing pattern history table interference",
  PACT 1996 [NOT READ; cited as ref. [7] in BATAGE]. The classic "filter highly biased branches out of the PHT"
  idea.
- **Gope & Lipasti**, "Bias-Free Branch Predictor", MICRO 2014 (https://pharm.ece.wisc.edu/papers/micro14.pdf)
  [NOT READ; search snippet only]. Filters biased branches out of the *history*, not out of TAGE tables.
- **CBP-NG (7th championship) 1st place, "MORSL"** (Koizumi et al.) [SECONDARY via SIGARCH blog]. Uses an
  "allocation-guided access filter": 1-bit tables indexed by PC and PC ^ short history record whether a branch ever
  allocated into longer TAGE tables. This is used for **energy** (read only the two shortest tables), not accuracy.
- **Riley & Zilles**, "Probabilistic counter updates for predictor hysteresis and stratification", HPCA 2006
  [NOT READ; cited by Seznec 2025]. Useful for cheap low-rate statistics.
- **Seznec**, "Storage Free Confidence Estimation for the TAGE branch predictor", HPCA 2011 (inria-00512130)
  [downloaded, not read]. Confidence classes from the provider ctr state, used by SC/choosers.
- **Not found** in searches: a published **per-PC allocation throttle for TAGE driven by allocation success**,
  **per-bank/per-region u-bit aging**, or a **TAGE-native CAT using ctr-state ratios**. "Not found" is not proof of
  novelty: I could not fully check ISCA/MICRO/HPCA 2019–2026 or patents (a USPTO patent on usefulness-based
  replacement showed up in search and was not read).

---

## 8. ChampSim (2021) implementation recipe [INFERRED unless noted]

### Interface facts (checked in `champsim/src/ooo_cpu.cc` lines 111/134 and 352/385)

- `predict_branch(ip)` is immediately followed by `last_branch_result(ip, taken)` for each branch, in order. So:
  - keep the computed indices, tags, HitBank and AltBank from predict in globals and reuse them in update;
  - update history **after** the table update.
- `branch_taken` for unconditional branches is 1. The predictor cannot tell types apart, so all branches go through
  TAGE.
  - The bimodal learns unconditional branches after one occurrence.
  - The first misprediction on each new jump/call/return triggers an allocation, giving a small pollution of about
    one tagged entry per static unconditional branch.
  - Initializing the bimodal to weakly-taken may reduce this.
- The functions are `O3_CPU` members, but globals/static arrays are fine for 1-core runs. Use per-cpu arrays if
  multi-core matters.

### Storage configurations near 64 KB (computed)

- **Config A — classic TAGE, 12 tagged tables**, lengths 4, 6, 10, 16, 25, 40, 64, 101, 160, 254, 403, 640 (the
  L-TAGE series):
  - Bimodal 16K × 1 prediction bit + 4K hysteresis bits = 20,480 bits.
  - Tagged tables, each entry 3-bit ctr + 2-bit u + tag:

    | Tables | Entries | Tag widths (bits) |
    |---|---|---|
    | T1, T2 | 2K | 8, 8 |
    | T3–T6 | 4K | 9, 9, 10, 10 |
    | T7–T10 | 2K | 11, 11, 12, 12 |
    | T11, T12 | 1K | 13, 13 |

  - Tagged bits = 462,848. **Total 483,328 bits = 59.0 KB.** The remainder covers histories, a loop predictor or a
    small SC.
- **Config B — 1-bit u (Seznec 2011 style)**, tags 9…14, sizes 2K/4K×5/2K×3/1K×3: 492,544 bits = 60.1 KB.
- **BATAGE at 64 KB:**
  - NUMG = 26, LOGG = 10 (1K entries per bank), TAGBITS = 12.
  - Bimodal LOGB 14, LOGB2 12.
  - **503,808 bits = 61.5 KB.** TAGBITS = 13 gives 64.75 KB, over budget.
  - CATMAX, CATR and MINAP must be retuned (code comment).
- **History buffer:** about 640–3000 bits plus path history. Small, but count it.

### Hashing for x86 ChampSim

- Use `pc ^ (pc >> k)` mixes, not `pc >> 2`.
- Fold the global history with CSRs: one for the index (LOGG bits), and two for the tag (TB and TB−1 bits, the second
  shifted by 1, as in TAGE-SC-L).
- Add a path history of 16–27 bits with 1 PC bit per branch.
- Optionally insert 2 history bits per branch: `(pc ^ pc>>2) ^ taken` (TAGE-SC-L style), which helps distinguish
  paths without targets.

### Important "must-have" TAGE details (easy to forget)

- USE_ALT_ON_NA: a 4–5 bit counter. A few counters indexed by the provider bank group is better.
- Do not allocate if the weak longest match was itself correct.
- Allocate with probability 1/32 even on a correct final prediction (only matters once there is an SC on top).
- OPTREMP: replace only u = 0 entries with |2ctr+1| ≤ 3; decay others.
- TICK u-reset: `TICK += penalty − 2·NA`; reset or halve u at the threshold.
- Update the alt entry when the provider is weak and wrong.

### Expected gains

- These are modest. The DPC-3 SPEC17 traces mix very predictable FP codes (lbm, cactuBSSN, imagick) with H2P-heavy
  integer codes (mcf, deepsjeng, xz, gcc, omnetpp).
- Extension gains will likely concentrate on mcf, deepsjeng, xz and omnetpp. Report per-trace MPKI, not just the
  mean.

---

## 9. Open limitations and candidate student extensions (with prior-art status)

### Idea 1 — Per-branch (PC-indexed) allocation throttling ("H2P-aware allocation") for TAGE

- **Limitation addressed:** H2P branches (Lin & Tarsa) mispredict often. Each misprediction allocates 1–2 tagged
  entries that rarely become useful, which:
  - evicts useful entries of other branches (thrashing);
  - creates cold counters that mislead (Michaud's cold-counter problem).
- Global throttles (Seznec 2014/2024/2025; BATAGE CAT) also throttle well-behaved branches in the same phase.
- **Mechanism sketch:**
  - A small PC-hashed table, e.g. 1K × 4–5 bits (about 0.5 KB), holding a per-branch "allocation payoff" counter.
  - Increment when an entry the branch hits becomes useful (u set: provider correct, altpred wrong).
  - Decrement when the branch triggers an allocation.
  - Map the counter to an allocation probability (1, 1/2, 1/4, 1/16) via an LFSR, keeping a floor so the branch can
    recover.
  - Optionally also reduce the number of allocated entries (2 → 1) and confine allocation to shorter tables.
  - Easy to test in ChampSim; costs < 1 KB.
- **Prior art:**
  - Global versions: TAGE-SC-L 2014 (1 vs. 2 entries by misprediction ratio); Seznec 2024 cookbook / CBP-2025
    (probabilistic-counter filter on weak-entry confidence); BATAGE CAT.
  - Per-PC update suppression via a side predictor: Bullseye 2025.
  - Per-PC gating of easy branches: Cai et al. 2025.
  - I did **not** find a published per-PC allocation-payoff throttle inside TAGE.
  - Novelty: moderate. Clearly position it as "per-branch CAT" and compare against a global-throttle baseline,
    implementing Seznec's filter or BATAGE CAT as the comparison.

### Idea 2 — "CAT for TAGE" via counter-state ratios (porting BATAGE's NHC/MHC signal)

- **Limitation addressed:** Michaud 2018 shows that magic CAT gives large gains on tens of traces for TAGE, and
  explicitly leaves "a CAT method for TAGE" as future research.
- **Mechanism sketch:** during the allocation scan over tables k > provider, classify each candidate:
  - "NHC-like": u = 0 and weak ctr;
  - "MHC-like": u = 0 and |2ctr+1| ∈ {3, 5}, or u = 1 and not saturated.
  - Update a cat counter as in BATAGE Fig. 6: `cat += a − b·mhc` on a successful allocation, and gate the allocation
    probability by cat.
- **Prior art:**
  - Seznec 2024/2025 partially answer Michaud's question with a *different* signal (accuracy of weak
    longest-match entries, via probabilistic counters) and report −0.04 MPKI from filtering.
  - A direct NHC/MHC-style port is not something I found published.
  - Risk: TAGE's ctr is less informative than BATAGE's dual counter (that is Michaud's point), so the signal may be
    weaker.
  - It is a clean, honest experiment either way.

### Idea 3 — Localized/adaptive u-bit aging

- **Limitation addressed:** u reset is global:
  - L-TAGE: periodic MSB/LSB alternation (256K/512K branches);
  - 2011: global 8-bit success/failure monitor that resets all u;
  - 2016: TICK halves all u.
- A thrash in one history-length region (e.g. long tables under H2P pressure) unprotects useful short-table entries
  everywhere.
- **Mechanism sketch:**
  - Per-table (or per-table-group) TICK counters. Only tables where allocation failures dominate get their u halved.
  - Alternatively, age per set by clearing u of entries that are hit but not useful over a window.
- **Prior art:**
  - Global schemes as above.
  - The cookbook's "protect recently useful entries (u = 2)", "u = 1 on first allocated entry", and "reset only when
    4/5 are useful if the misprediction rate is high".
  - TAGE-SC-L 2016 code has two physical groups (low/high) but resets both together.
  - BATAGE removes u in favor of confidence-protected entries plus probabilistic decay.
  - I found no published per-table aging study. Novelty: moderate. Expected gain: small, but cheap to test.

### Idea 4 — Keep trivially biased / unconditional branches out of the tagged tables (ChampSim-specific engineering)

- **Limitation addressed:** with no type information, every jump/call/return passes through TAGE.
  - Every first occurrence (and every re-occurrence after a bimodal eviction) mispredicts and allocates.
  - Weakly biased "almost always" branches can also trigger allocations.
- **Mechanism sketch:**
  - A per-PC "never seen not-taken" bit or Bloom filter, or a saturating bias counter.
  - While the branch has never been not-taken: predict taken and skip TAGE update/allocation.
  - On the first not-taken outcome, hand the branch to TAGE.
- **Prior art:**
  - Strong: Chang/Evers/Patt 1996 branch filtering; Cai et al. CBP-2025 Bloom-filter gating; Fan's CBP-NG per-PC
    bias override [SECONDARY].
  - Not novel. Good as a baseline cleanup and for the "accuracy over all branch types" metric.
  - Expected gain is small, because TAGE allocates only on mispredictions [INFERRED].

### Idea 5 — Leverage immediate update: local-history SC (LSC) on top of TAGE

- In ChampSim, speculative local history is a non-issue.
- Seznec 2011: a 30 Kbit LSC alone gives about −8% of TAGE's loss; local components are about 3% in CBP-2025.
- **Not novel** (published 2011), but likely the single largest accuracy lever per KB beyond pure TAGE.
- Overlaps with the SC/perceptron topic.

### Idea 6 — BATAGE as the base and adding a tiny SC or per-PC CAT

- BATAGE-GSC is only marginally better than BATAGE (4.24 vs. 4.29).
- A per-PC variant of CAT (Idea 1 applied to BATAGE) is untested as far as I found. It inherits BATAGE's
  retuning burden.

### Recommended top 3 for a student project

1. **Idea 1** (per-PC allocation throttling).
2. **Idea 2** (TAGE-native CAT via ctr-state ratios).
3. **Idea 3** (per-table-group u aging).

For all three:
- Baseline: Config A TAGE (± an LSC).
- Ablations: global throttle (Seznec-style) vs. per-PC throttle.
- Metrics: per-trace MPKI and accuracy over all branches, plus allocations per kilo-instruction (APKI, as in
  BATAGE Fig. 9) and the u-reset frequency. These diagnostics make the mechanism's effect visible.

---

## Sources

Access status: **downloaded and read** unless marked otherwise.

1. Seznec & Michaud, "A case for (partially) TAgged GEometric history length branch prediction", JILP 8, 2006.
   https://inria.hal.science/hal-03408381/document
2. Seznec, "The L-TAGE Branch Predictor", JILP 9, 2007. https://jilp.org/vol9/v9paper6.pdf
   (pp. 1, 4–7 read as images; the text layer is garbled)
3. Seznec, "A New Case for the TAGE Branch Predictor", MICRO-44, 2011, DOI 10.1145/2155620.2155635.
   https://www.cs.cmu.edu/~18742/papers/Seznec2011.pdf (HAL: hal-00639193)
4. Seznec, "TAGE-SC-L Branch Predictors", CBP-4, 2014. https://inria.hal.science/hal-01086920/document (skimmed)
5. Seznec, "TAGE-SC-L Branch Predictors Again", CBP-5, 2016. https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf
   - Code: https://jilp.org/cbp2016/code/AndreSeznecLimited.tar.gz (64 KB `predictor.h` read)
   - Program page: https://jilp.org/cbp2016/program.html
6. Michaud, "An Alternative TAGE-like Conditional Branch Predictor", ACM TACO 15(3):30, 2018, DOI 10.1145/3226098.
   https://inria.hal.science/hal-01799442/document
   - Code: https://files.inria.fr/pacap/michaud/BATAGE_simulator-1.zip
7. Seznec, "TAGE: an engineering cookbook", Inria RR-9561, 2024. https://hal.science/hal-04804900/document
   (slides read as images)
8. Seznec, "TAGE-SC for CBP2025", CBP-2025.
   https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final37-Seznec.pdf
9. Michaud, "A PPM-like, tag-based branch predictor", JILP 7, 2005. https://inria.hal.science/hal-03406188/document
   (skimmed)
10. Pruett et al., "Dynamically Sizing the TAGE Branch Predictor", CBP-5, 2016.
    https://jilp.org/cbp2016/paper/StephenPruettFinal.pdf (intro read)
11. Cai et al., "TAGE-SC-L with a Code Structure Correlator", CBP-2025.
    https://ericrotenberg.wordpress.ncsu.edu/files/2025/06/cbp2025-final27-Cai.pdf (bloom-filter section read)
12. Behrendt, Pun, Nair, "Taming Wild Branches: … Bullseye Predictor", arXiv 2506.06773 / CBP-2025.
    https://arxiv.org/html/2506.06773 (SECONDARY: tool summary)
13. Lin & Tarsa, "Branch Prediction Is Not A Solved Problem", IISWC 2019 (abstract read; local copy obtained by a
    sibling agent).
14. SIGARCH blog, "7th Branch Prediction Championship: Part I" (CBP-NG; MORSL, Fan, Dang & Rotenberg).
    https://www.sigarch.org/7th-branch-prediction-championship-part-i/ (SECONDARY)
15. Seznec, "Storage Free Confidence Estimation for the TAGE branch predictor", HPCA 2011.
    https://inria.hal.science/inria-00512130/document (downloaded, not read)
16. Not accessed / not read, cited only via other papers:
    - Chang, Evers & Patt, PACT 1996;
    - Gope & Lipasti, "Bias-Free Branch Predictor", MICRO 2014 (https://pharm.ece.wisc.edu/papers/micro14.pdf);
    - Riley & Zilles, HPCA 2006;
    - ACM DL BATAGE PDF (https://dl.acm.org/doi/pdf/10.1145/3226098; bot-blocked, the HAL copy was used instead);
    - BranchNet (MICRO-53).
