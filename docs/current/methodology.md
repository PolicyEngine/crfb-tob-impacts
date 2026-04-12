# Current Methodology

This page describes the live modeling contract for the current CRFB rerun.

## Scope

The active package has three parts:

- standard reforms `option1` through `option12`
- the `option13` balanced-fix baseline that starts in `2035`
- `option14_stacked`, which layers the structural reform on top of the
  `option13` balanced-fix baseline

The main delivery window is `2026-2100`.

## Standard Series Contract

For the current clean static rerun, the intended contract is:

- target source: `trustees_2025_current_law`
- calibration profile: `ss-payroll-tob`
- tax assumption: `trustees-core-thresholds-v1`
- exact-calibration-only acceptance for delivered years
- no donor-backed support augmentation in the production rebuild path
- pinned local worktrees for both `policyengine-us` and `policyengine-us-data`
- a run-level reproducibility bundle that records the exact code/data lineage,
  including dirty sibling-repo overrides when present

That contract replaces the older mixed lineage that produced the legacy stitched
standard file.

## Scenario Families

### Standard options `1-12`

These are scored by rescoring reforms against validated yearly H5 datasets.

The important methodological point is that the current standard series is meant
to come from exact yearly microdata plus direct reform rescoring, not from
patching the old stitched CSVs in place.

### `option13`

`option13` is a special-case balanced-fix baseline beginning in `2035`.

Its construction is intentionally different from the standard options:

- `2026-2034` are current-law placeholders because the balanced-fix baseline
  does not start before `2035`
- `2035-2099` come from the special-case balanced-fix raw outputs
- the `2100` endpoint uses the corrected local rerun plus the HI Trustees
  endpoint treatment documented in [data/README.md](../../data/README.md)

### `option14_stacked`

`option14_stacked` is built by chaining the structural reform on top of the
`option13` balanced-fix baseline.

Operationally, that means:

- `option13` reform revenue becomes the baseline revenue for
  `option14_stacked`
- `option12` standard reform outputs provide the stacked structural deltas
- `2026-2034` are again current-law placeholders because the stacked baseline
  starts in `2035`

## Static Versus Dynamic

The static rebuild path is the current priority and uses the contract above.

When dynamic reruns are run, the intended differences from plain upstream
`policyengine-us` main are:

- Trustees long-run uprating behavior
- age-based labor-supply elasticities for behavioral-response scoring

Dynamic should therefore be interpreted as an extension of the same baseline
lineage, not as a separate legacy workflow.

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
- The archival Jupyter Book is historical context, not the live methodology
  spec.
- The live anomaly and validation record is
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md).

## What Still Lives Elsewhere

- detailed balanced-fix gap-closing logic:
  [data/README.md](../../data/README.md)
- pinned dependency and environment notes:
  [REPRODUCIBILITY.md](../../REPRODUCIBILITY.md)
- live audit trail and sentinel evidence:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
