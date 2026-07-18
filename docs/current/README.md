# Current CRFB Handbook

## Start Here

This is the current documentation spine for the CRFB trust-fund-taxation work.
The controlling modeling contract is
[`REFORM_MODELING_BIBLE.md`](REFORM_MODELING_BIBLE.md); the baseline method and
Trustees 2026 target lineage are in
[`v2-baseline-method.md`](v2-baseline-method.md).

It is designed to answer four questions quickly:

1. What are we actually modeling?
2. How are the outputs produced?
3. Which artifacts are current versus legacy?
4. What do we send externally?

## What This Covers

- the standard `option1` through `option12` long-run analysis
- the v2 populace/TR2026 baseline construction and full reform-H5 scoring path
- the delivery boundary between current dashboard outputs and legacy
  spreadsheet-reference values

## Current Workflow At A Glance

The diagram below documents the current release workflow.

```mermaid
flowchart LR
  A["Trustees current-law targets"] --> B["Exact H5 generation in policyengine-us-data"]
  B --> C["Current full-H5 rescoring for 14 reforms"]
  C --> D["Unified results.csv"]
  D --> E["Dashboard current results"]
  D --> F["Release package and paper exhibits"]
  C --> G["Audit notes and sentinel validation"]
```

## Read In This Order

- [REFORM_MODELING_BIBLE.md](REFORM_MODELING_BIBLE.md)
  - current full-H5 retention, R2 durability, aggregation, and release rules
- [v2-baseline-method.md](v2-baseline-method.md)
  - current v2 populace/TR2026 baseline construction and validation limits
- [methodology.md](methodology.md)
  - scope, scenario families, modeling assumptions, and interpretation rules
- [pipeline.md](pipeline.md)
  - production workflow, scripts, and validation gates
- [late-year-support-gates.md](late-year-support-gates.md)
  - publication hard stops for late-year household support and TOB contributor
    support
- [deliverables.md](deliverables.md)
  - dashboard, spreadsheet, and release checklist
- [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
  - live run status and anomaly log

## Operating Rules

- Treat legacy stitched standard outputs as comparison artifacts only.
- Treat the deleted legacy Jupyter Book as historical context only; the current
  surfaces are the dashboard, Quarto paper, and operational docs.
- Keep prior or legacy values in comparison spreadsheets only, not in the
  dashboard current-results path.
- If a current run artifact conflicts with a prose note, trust the artifact and
  update the prose. Legacy run ledgers are historical evidence only, not current
  release controls.

## Where To Go Next

- Need the modeling contract:
  [methodology.md](methodology.md)
- Need the exact commands and scripts:
  [pipeline.md](pipeline.md)
- Need the shipping surface:
  [deliverables.md](deliverables.md)
- Need the latest audit status:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
