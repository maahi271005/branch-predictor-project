# Design rationale — TAGE-SC-L with target-free loop-structure history

## 1. Problem
In this (2021) ChampSim the predictor interface is

    uint8_t predict_branch(uint64_t ip);
    void    last_branch_result(uint64_t ip, uint8_t taken);

called for **every** branch type, with no branch type and no target. Several of the most effective
corrector features in the literature — IMLI (Seznec et al., MICRO 2015), IMLI outer history / IMHIST,
and backward-branch histories (TAGE-SC-L 2016) — are defined in terms of *backward conditional
branches*, i.e. they need the target to decide whether a branch closes a loop. They are therefore
not directly implementable here, and a naive port would have to change the simulator core.

## 2. Key observation (contribution N1)
ChampSim feeds the predictor every branch in program order and executes no wrong path. After a
taken branch B with target T, execution continues sequentially from T until the next branch N, so
pc(N) ≥ T. If T ≤ pc(B), the sequential path from T reaches B itself, hence pc(N) ≤ pc(B); if
T > pc(B), then pc(N) ≥ T > pc(B). Therefore

    B is backward  ⇔  pc(next predicted branch) ≤ pc(B)        (exact for taken instances)

The bit is evaluated at the start of the next `predict_branch` call — exactly when IMLI is first
needed — so the counter seen by every prediction is the same as with target knowledge. Two 4 Kbit
tables complete the picture: `bwd` remembers the direction of each branch for its not-taken
(loop-exit) instances, and `cond` marks a branch as conditional once it has been seen not-taken
(unconditional branches are always reported taken by ChampSim).

**Verification** (`experiments/harness/verify_imli.cc`, 50M instructions per trace, ground truth
= ChampSim's own `branch_target = next_instr.ip`): per-instance agreement 99.9996–100% on all 10
traces. The resulting IMLI counter tracks an oracle (type- and target-aware) counter closely where
the counter carries information (clamped at 16: mcf 99.7%, x264 99.7%, gcc 96.4%, xz 95.7%,
imagick 92.4%); it diverges where the oracle counter sits near saturation because of backward
conditional branches that almost never exit (lbm, cactuBSSN, omnetpp) — a property of the IMLI
definition, not of the inference.

## 3. Architecture (frozen configuration, 508,666 bits = 62.1 KB)
- **TAGE**: 8K×2-bit bimodal; 12 tagged tables × 2K entries, history lengths geometric 4…640,
  tags 8–13 bits, 3-bit counters, 1-bit u; folded-history indexing with path history (27 bits);
  use_alt_on_na (4×5-bit); allocation of up to 2 entries, only over u=0 and weak/medium entries,
  strong u=0 entries decayed instead; TICK-based u aging (BORNTICK=1024); allocation with p=1/32
  when the final (corrected) prediction was right. (Seznec 2011/2016.)
- **Loop predictor**: 64 entries, 4-way, 10-bit trip counts, confidence 15 (L-TAGE).
- **Statistical corrector** (6-bit counters, adaptive threshold, TAGE-SC-L 2016 chooser rules):
  3 bias tables (PC × TAGE prediction × confidence / provider bank), 4 global-history GEHL tables
  (6–40), 3 path GEHL tables (9–25), 4 local-history GEHL tables (3–16, 256 local histories).
- **Loop-structure components enabled by N1**:
  - IMLI-SIC: 512×6-bit table indexed by hash(PC, IMLIcount) (paper definition: count consecutive
    taken iterations of the last backward conditional branch, reset on its exit);
  - IMHIST: 256 × 10-bit outcome histories, one per IMLI value (outcome of conditional branches at
    the same inner-loop iteration in previous outer iterations) + one 1K×6-bit SC table;
  - backward-branch history: 16-bit history of backward-branch outcomes + two 1K×6-bit SC tables.

## 4. Decisions backed by measurements
See `research/candidate_comparison.md` and the harness results in `experiments/results/harness/`. In short: the SC is the
main lever (−6.7% MPKI vs TAGE on tune); the N1-enabled components add a further −0.9% (main) over
TAGE-SC-L without them; a per-branch allocation throttle helps plain TAGE (−0.5%) but is subsumed in
TAGE-SC-L; longer histories, 2-bit history insertion, IMLI-in-GEHL and the region-based IMLI variant
did not help on these traces.

## 5. Honest scope of the contribution
- TAGE-SC-L, IMLI-SIC, IMHIST and backward-branch histories are published (Seznec et al.). Our
  contribution is the **target-free inference** that makes them available — exactly for taken
  branches — in a PC+outcome-only interface without changing the simulator, its verification
  against ground truth, the integration, and the measured evaluation (incl. negative results).
- The gain from the loop-structure components is modest (≈1% MPKI), consistent with Seznec's own
  report that IMLI was "a big disappointment on CBP2016 traces" (+0.2%).
- The design is evaluated on 10 SimPoint regions only; parameters were tuned on a different region
  of the same programs, not on different programs.
