# Current Methodology

This page describes the live modeling contract for the current CRFB rerun.

## Scope

The active package contains the standard reforms `option1` through `option12`.
Legacy non-contract variants are not part of the current dashboard, release, or
reform-modeling contract.

The main delivery window is `2026-2100`.

## Standard Series Contract

For the current clean static rerun, the intended contract is:

- target source: `trustees_2025_current_law`
- calibration profile: `ss-payroll-tob`
- tax assumption: `trustees-2025-core-thresholds-v1`
- exact-calibration-only acceptance for delivered years
- donor-backed composite support augmentation from `2075` onward, with exact
  final calibration and late-year support gates
- pinned local worktrees for both `policyengine-us` and `policyengine-us-data`
- a run-level reproducibility bundle that records the exact code/data lineage,
  including dirty sibling-repo overrides when present

That contract replaces the older mixed lineage that produced the legacy stitched
standard file.

## Trustees Tax-Threshold Assumption

The named tax assumption `trustees-2025-core-thresholds-v1` operationalizes the
Trustees/OACT long-run taxation-of-benefits assumption for microsimulation.
SSA/OACT clarified by email to PolicyEngine on May 5, 2026 that the long-range
assumption applies both to income-tax rate brackets and to federal income-tax
thresholds such as standard deductions.

Operationally, this means:

- Social Security benefit-tax combined-income thresholds remain fixed in nominal
  dollars.
- Federal income-tax rate brackets and related federal income-tax thresholds
  follow current-law C-CPI-U indexing for the first ten projection years, through
  `2034`.
- Beginning in `2035`, those federal income-tax brackets and thresholds rise
  with average wages.

The implemented core-threshold bundle covers ordinary income-tax brackets,
standard deductions, aged/blind standard deduction additions, capital-gains
thresholds, and AMT thresholds. This is a Trustees-lineage scoring assumption
for the CRFB long-run TOB work, not default statutory current law.

## Late-Year Support

Starting in `2075`, the clean long-run path uses
`donor-backed-composite-v1` support augmentation before the final entropy
calibration. This addresses a far-horizon support problem: the original CPS
records alone can force too much taxation-of-benefits weight onto a small set
of households, even when aggregate calibration targets are technically
feasible.

The current sentinel recipe is:

- fixed `2100` support supplement
- top `120` synthetic target types
- `20` real donor tax units per target
- base-household prior scale `0.15`
- support-solve tolerance `5%`
- activation from `2075` onward

The support supplement is donor-backed rather than free synthetic data. It maps
synthetic late-year household targets to nearby real `2024` donor tax units,
preserves entity structure, and retargets unstable tail components such as
pension and dividend-like income. The support solve only determines feasible
support and priors; the final delivered H5 still must exactly match the
Trustees Social Security, taxable-payroll, OASDI TOB, and HI TOB targets.

Publication gating therefore rejects approximate donor-augmented outputs but
allows donor-backed support when the final calibration is exact, metadata is
stamped, and late-year support gates pass. Those gates include separate
taxation-of-benefits contributor checks documented in
[late-year-support-gates.md](late-year-support-gates.md).

## Scenario Families

### Standard options `1-12`

These are scored by rescoring reforms against validated yearly H5 datasets.

The important methodological point is that the current standard series is meant
to come from exact yearly microdata plus direct reform rescoring, not from
patching the old stitched CSVs in place.

## Static Versus Supplemental Labor-Supply Response

The released static series uses the cleaned Trustees baseline lineage and is
the primary CRFB dashboard scoring surface. The supplemental labor-supply
response series shares the same baseline levels before being published
alongside the static release.

For the labor-supply response release, the intended differences from plain upstream
`policyengine-us` main are:

- Trustees long-run uprating behavior
- age-based labor-supply elasticities for behavioral-response scoring

Labor-supply response scoring should therefore be interpreted as a
partial-equilibrium estimate under PolicyEngine's elasticity assumptions, not
as a separate legacy workflow or as an exact replica of JCT/CBO conventional
practice.

Operationally:

- the publication-facing dashboard defaults to static scoring and includes
  supplemental behavioral rows only where generated from the current full
  reform H5 contract
- any labor-supply response release must start from durable
  `reform_full_h5/year=YYYY/reform=optionX/scenario.h5` artifacts; aggregate
  CSVs and non-contract sample panels are not production inputs

## Reproducibility Boundary

The repo-level standard now is:

- `uv sync --frozen` for the Python environment
- pinned local worktrees for `policyengine-us` and `policyengine-us-data`
- calibrated H5 snapshots with machine-readable metadata
- a launch-time reproducibility bundle under `results/repro_bundles/`

That bundle records:

- the exact git SHAs and dirty status for the three repos involved
- the sibling `pyproject.toml` and `uv.lock` files that define the local model
  and data worktree environments
- the exact calibrated snapshot manifest
- a complete per-file SHA256 inventory for the calibrated snapshot
- the resolved enhanced CPS blob hash and path used by the recalibrated H5s
- any tracked or untracked local overrides that were present in dirty sibling
  repos

So the reproducibility contract is no longer just “remember which worktree we
used”; it is an artifact that travels with the run.

For release-grade runs, that bundle can also be frozen into local snapshot and
repo tar archives with `scripts/freeze_repro_bundle.py`.

## Interpretation Rules

- Current dashboard outputs should reflect only the current rerun results.
- Prior or legacy values belong only in comparison spreadsheets.
- The deleted legacy Jupyter Book is historical context, not the live
  methodology spec.
- The live anomaly and validation record is
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md).

## What Still Lives Elsewhere

- pinned dependency and environment notes:
  [REPRODUCIBILITY.md](../../REPRODUCIBILITY.md)
- live audit trail and sentinel evidence:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
