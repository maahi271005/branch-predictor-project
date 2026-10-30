# Candidate comparison

Status: final (design frozen at commit `660997e`). Numbers are mean MPKI over the 10 traces from the
functional harness; "tune" = instructions 1000M–1150M, "main" = the reported window (50M–250M).
Full per-trace data: `experiments/results/harness/`.

## Candidates considered

| ID | Candidate | Limitation addressed | Mechanism | Prior art | Expected | Risk / cost |
|---|---|---|---|---|---|---|
| K0 | TAGE (re-implementation) | gshare/perceptron cannot use very long histories cheaply | tagged geometric-history tables | Seznec 2006/2011 | strong baseline | low |
| K1 | + statistical corrector + loop (TAGE-SC-L) | TAGE learns statistically biased / H2P branches poorly | GEHL-style corrector tables, loop predictor | Seznec 2014/2016 | −5…8% MPKI | moderate code size |
| **N1** | **target-free backward inference** | IMLI / backward-branch features need targets; this ChampSim interface provides only `ip` and outcome | backward(B) ⇔ pc(next branch) ≤ pc(B); per-branch bwd bit for not-taken instances; conditional ⇔ seen not-taken | none found for next-*branch* PC (a ChampSim PR uses next *instruction* PC, which the predictor never sees) | enables N1a–c | low (≈1 KB) |
| N1a | IMLI-SIC | inner-loop iteration correlation | 512-entry table hashed with IMLIcount | Seznec et al. 2015 | small | low |
| N1b | IMHIST | outer-loop correlation at same inner iteration | per-IMLI-value outcome history + SC table | Seznec CBP-2016 code (successor of IMLI-OH) | small | low |
| N1c | backward-branch global history | loop-exit pattern correlation | history of backward-branch outcomes, 2 SC tables | Seznec 2016 SC component | small | low |
| N1d | IMLI hashed into 2 global SC tables | — | — | IMLI paper §4.2 | small | low |
| N1e | IMLI without conditional filter / region-based (BrIMLI-like) | conditional filter lags | count all taken backward branches; region reset | Seznec cookbook 2024 (region idea) | unknown | low |
| N2 | per-branch allocation throttle | H2P branches thrash TAGE (Lin & Tarsa: median 13,093 allocations per H2P) | PC-indexed payoff counter gates allocation | global throttles only (Seznec 2014/24/25, BATAGE CAT); Lin & Tarsa suggest filtering | −0.2…0.6% | could starve long-history branches |
| X1 | 2 history bits per branch | unconditional branches add little information | insert 2 bits of (pc^pc>>2)^taken | Seznec CBP code | ? | doubles history consumption |
| X2 | longer MAXHIST (1000/2000) | very long correlations | geometric series to 1000/2000 | Seznec uses 3000 with 36 tables | ? | sparser tables |

## Evidence (mean MPKI, 10 traces)

| Candidate | tune | main | Decision |
|---|---|---|---|
| hashed_perceptron (repo, 64 KB) | 3.3805 | 3.2475 | baseline |
| K0 TAGE | 3.4163 | 3.2947 | baseline; ≈ hashed perceptron, worse on mcf/xz |
| K1 TAGE-SC-L (no IMLI) | 3.1880 | 3.0727 | base (−5.4% vs hashed perceptron on main) |
| K1 + N1a (IMLI) | 3.1739 | 3.0648 | keep |
| K1 + N1a + N1b | 3.1695 | — | keep |
| K1 + N1a + N1c | 3.1674 | — | keep |
| **K1 + N1a + N1b + N1c (proposed)** | **3.1580** | **3.0455** | **selected** — best on both regions |
| + N1d | 3.1644 | 3.0501 | rejected (N1d alone +0.19% on tune) |
| N1e mode 1 / mode 2 | 3.1784 / 3.1791 | — | rejected; mode 2 loses the gcc gain |
| N2 throttle on K1+N1a (3 settings) | 3.1738 / 3.1759 / 3.1767 | — | rejected: no effect |
| N2 throttle on K0 (TAGE only) | 3.3996 / 3.3975 | — | −0.5% on TAGE: mechanism works, but is subsumed by TAGE-SC-L's "allocate with p=1/32 when the corrected prediction was right" rule |
| X1 / X2 | +0.28% / +0.15%, +0.96% | — | rejected |

## Why the final choice
1. It is the best configuration on the tuning region **and** on the independent reported window
   (the ranking was decided on tune and confirmed on main).
2. Every component of the contribution (N1 → N1a/b/c) is enabled by one small mechanism that is
   specific to, and verified for, the PC-only ChampSim interface.
3. It stays within the 64 KB class of the strongest repo baseline (508,666 vs 524,542 bits).
4. The negative results (N2 subsumed, N1d/N1e, X1/X2) are reported, not hidden.
