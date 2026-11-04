# Archive: earlier 10-trace study (superseded by the 50-trace evaluation)

This folder preserves the deliverables of the **earlier evaluation of TFL-TAGE-SC-L on
10 SPEC CPU2017 traces** (50M warm-up + 200M measured instructions, ChampSim 2021, 1 core, no
prefetchers, LRU LLC). It is kept for reference only. **The current results are in
`results_50trace/` and the current report is `report_50trace/`** (50 traces, 7 predictors, 350 runs).

| Folder | Contents |
|---|---|
| `submission/` | original submission: report (.docx), results workbook, figures, CSVs |
| `final_deliverables/` | audited and corrected 10-trace report (.docx/.md), audit log, audit data, figures, scripts |

The project ZIP of the original submission is not included: its contents (`champsim/`,
`experiments/`, `research/`) are the root of this repository.

The raw ChampSim outputs of the 10-trace study are at
`experiments/results/B_baseline_50M_200M/`, `G_final_50M_200M/`, `AUDIT_seed1_50M_200M/` and the
functional-harness results (exploration, tuning, ablation) at `experiments/results/harness/`.

The 50-trace experiment re-simulated the 10 original traces from scratch; those 70 runs reproduce
the cycle and misprediction counts of this study exactly (see `results_50trace/checks.txt`).
