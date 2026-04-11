# Documentation Map

This repository now has three distinct documentation surfaces:

- current operational documentation for the active CRFB `2026-2100`
  14-option rerun and delivery workflow
- archival report material from the earlier eight-option package
- a new citable manuscript track for formal publication and SSRN-style use

If you are trying to understand what we are doing now, start with the current
handbook, not the archival Jupyter Book.

## Start Here

- [paper/README.md](../paper/README.md)
  - citable manuscript track, separate from the live dashboard
- [docs/current/README.md](current/README.md)
  - human-oriented entry point for the live methodology, workflow, and
    deliverables
- [analysis/long_run_rescoring_findings.md](../analysis/long_run_rescoring_findings.md)
  - live audit log, anomaly tracking, and sentinel results
- [REPRODUCIBILITY.md](../REPRODUCIBILITY.md)
  - pinned worktrees, rerun contract, and exact reproduction notes
- [data/README.md](../data/README.md)
  - detailed `option13` balanced-fix methodology and the `2100` HI endpoint
    treatment

## Current Handbook

- [docs/current/README.md](current/README.md)
  - overview and source-of-truth order
- [docs/current/methodology.md](current/methodology.md)
  - what is being modeled, how the scenarios are defined, and how to interpret
    current versus legacy results
- [docs/current/pipeline.md](current/pipeline.md)
  - exact H5 generation, Modal scoring, special-case assembly, and validation
    gates
- [docs/current/deliverables.md](current/deliverables.md)
  - what goes to the dashboard, what goes to the spreadsheet, and release
    checklist

## Archival Material

- [jupyterbook/README.md](../jupyterbook/README.md)
  - archival eight-option report build notes
- [docs/TRUST_FUND_REVENUE_METHODOLOGY.md](TRUST_FUND_REVENUE_METHODOLOGY.md)
  - archived Option 2 / 2026 methodology memo
- [docs/LATE_TAIL_PUBLISHABILITY_2026-04-09.md](LATE_TAIL_PUBLISHABILITY_2026-04-09.md)
  - point-in-time late-tail audit memo, partly superseded by the current
    long-run findings note

## Source Of Truth Order

When documents disagree, use this order:

1. live run artifacts and validation metadata
2. [analysis/long_run_rescoring_findings.md](../analysis/long_run_rescoring_findings.md)
3. the current handbook under [docs/current/](current/README.md)
4. the manuscript track under [paper/](../paper/README.md) for citable narrative framing
5. [REPRODUCIBILITY.md](../REPRODUCIBILITY.md)
6. archival Jupyter Book and legacy memos
