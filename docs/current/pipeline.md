# Current Pipeline

This page describes how the current outputs are supposed to be built.

## Production Flow

1. Generate exact yearly H5 datasets in the pinned `policyengine-us-data`
   worktree using the Trustees current-law target source and
   `trustees-2025-core-thresholds-v1`. Every year, including `2075+`, calibrates
   real populace survey households with no synthetic support.
2. Validate dataset metadata and exact coverage before any scoring run is
   submitted.
3. Freeze a run-level reproducibility bundle that captures code SHAs, dirty
   overrides, sibling dependency manifests, the full snapshot file inventory,
   the snapshot calibration manifest, and the underlying enhanced CPS blob
   hash.
4. Score standard reforms `option1` through `option12` against those saved H5
   datasets.
5. Build the current-contract standard delivery table.
6. For any labor-supply response release, generate durable full reform H5s under
   the Bible contract first, then aggregate from those saved H5s only.
7. Refresh dashboard payroll denominator files from source data and the explicit
   2100 HI extrapolation rule.
8. Push current results to dashboard artifacts and keep legacy values out of the
   release surface.
9. Build the release package and checksum manifest.

`trustees-2025-core-thresholds-v1` means fixed nominal Social Security benefit-tax
thresholds, plus Trustees/OACT long-run income-tax indexing: federal
income-tax brackets and related thresholds use current-law C-CPI-U indexing
through `2034`, then average-wage indexing from `2035` onward. SSA/OACT
confirmed by email to PolicyEngine on May 5, 2026 that the long-range
assumption applies both to income-tax rate brackets and to federal income-tax
thresholds such as standard deductions.

The current pipeline uses no synthetic support at any horizon. Every delivered
year — including `2075`–`2100` — calibrates real survey households only and
clears the publication gates with margin (far-horizon taxation-of-benefits
contributor effective sample sizes of `107`–`156`). The final calibration must
remain exact for every delivered year.

## Key Scripts

- [scripts/write_repro_bundle.py](../../scripts/write_repro_bundle.py)
  - writes the same reproducibility bundle for non-standard or local run paths
- [scripts/freeze_repro_bundle.py](../../scripts/freeze_repro_bundle.py)
  - archives the calibrated snapshot plus repo `HEAD` tarballs referenced by a
    reproducibility bundle
- [scripts/publish_full_h5_static_dashboard_results.py](../../scripts/publish_full_h5_static_dashboard_results.py)
  - publishes full-H5 selected-panel static outputs, annual dashboard display
    rows, and current dashboard static data
- [modal_batch/reform_full_h5.py](../../modal_batch/reform_full_h5.py)
  - guarded Modal submitter for one-cell-per-call full reform H5 generation
- [scripts/aggregate_reform_full_h5_results.py](../../scripts/aggregate_reform_full_h5_results.py)
  - post-H5 aggregation path; production aggregates must come from saved full
    reform H5 artifacts, not non-contract sample panels
- [scripts/build_dashboard_payroll_denominators.py](../../scripts/build_dashboard_payroll_denominators.py)
  - refreshes dashboard OASDI/GDP and HI taxable-payroll denominators used by
    percent-payroll views
- [scripts/build_release_package.py](../../scripts/build_release_package.py)
  - copies current outputs, dashboard data, source files, build scripts, paper
    sections, and release tests into a checksummed release package

## Validation Gates

The rebuild is supposed to fail closed on these checks:

- exact calibration quality for delivered years
- required profile `ss-payroll-tob`
- required target source from the v2/TR2026 baseline manifest
- required tax assumption `trustees-2025-core-thresholds-v1`
- pinned `policyengine-us` worktree via `CRFB_POLICYENGINE_US_PATH`
- late-year household and policy-target support gates, including separate
  OASDI/HI taxation-of-benefits contributor checks documented in
  [late-year-support-gates.md](late-year-support-gates.md)
- no synthetic household support in the current v2/populace published H5s
- a reproducibility bundle stamped before submission, including dirty sibling
  repo overrides if they exist
- launch-time env vars for required target source and tax assumption derived
  from the snapshot contract itself, not just implicit runtime defaults

If any of those checks fail, the right response is to stop and fix the run
contract, not to patch the output table downstream.

## Validation And Audit

The release process should include:

- targeted sentinel years in the early, middle, and late horizon
- a read of the live findings note:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
- checks that suspicious legacy anomalies do not reappear in the rebuilt series
- confirmation that the delivery assembly uses only current-contract full-H5
  standard inputs
- `pytest -q tests/test_release_artifacts.py`
- `pytest -q tests/test_release_package.py`
- `npm run lint` and `npm run build` under `dashboard/`

## What We No Longer Treat As Acceptable

- patching the stale stitched standard file into the dashboard as if it were a
  clean rebuild
- using the deleted legacy Jupyter Book as the current operational guide
