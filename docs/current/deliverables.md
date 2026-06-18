# Current Deliverables

This page defines what gets shipped and how legacy comparisons should be
handled.

## Primary Outputs

The intended current delivery surface is:

- one unified `results.csv`; it contains current-contract static rows and
  behavioral rows built from current full-H5 endpoint artifacts
- a `scoring_type` column that selects the scoring track
- dashboard data built from the current results only
- release packages and dashboard data built from the current full-H5 results

The public/release result paths are:

- `results.csv`
- `results.csv.metadata.json`
- `dashboard/public/data/results.csv`
- `dashboard/public/data/results_contract.json`
- `dashboard/public/data/distributional.json`
- `results/release_packages/crfb_tob_release_<timestamp>/`

Behind the scenes, the builder combines static and labor-supply response source
artifacts into the unified `results.csv`. The raw Modal source CSVs live under
`results/modal_runs_production/` as provenance inputs, not public result
surfaces. Public-facing code and docs should not ask readers to choose between
separate static and response artifact families. Labor-supply response rows are
included only when regenerated from the current full-H5 production contract.

## Delivery Rules

### Dashboard

The dashboard should show current rerun values only.

That means:

- no legacy standard rows in the dashboard current-results path
- no stale response subset files from earlier runs
- no stale stitched values carried forward for convenience

Labor-supply response results in the current delivery bundle must come from the
current full-H5 production lineage. Earlier response rows remain stale and must
not be stitched into the dashboard.

### Legacy Comparisons

Legacy comparisons should live outside the production dashboard data path. The
repository delivery bundle should not ship stale prior-reference CSV or XLSX
artifacts as current results.
- validation summaries during the audit period

Do not treat spreadsheet legacy columns as a substitute for current dashboard
data.

## Assembly Artifacts

These scripts define the current delivery build:

- [scripts/build_dashboard_payroll_denominators.py](../../scripts/build_dashboard_payroll_denominators.py)
- [scripts/publish_full_h5_static_dashboard_results.py](../../scripts/publish_full_h5_static_dashboard_results.py)
- [modal_batch/reform_full_h5.py](../../modal_batch/reform_full_h5.py)
- [scripts/aggregate_reform_full_h5_results.py](../../scripts/aggregate_reform_full_h5_results.py)
- [scripts/publish_dashboard_results.py](../../scripts/publish_dashboard_results.py)
- [scripts/build_release_package.py](../../scripts/build_release_package.py)

The spreadsheet-with-prior-reference output is the right place to preserve the
old values while the dashboard moves to the rebuilt current values.

`scripts/build_release_package.py` is the client/review package boundary. It
copies the current results, dashboard data, source denominator files, relevant
build scripts, paper sections, and release tests into `results/release_packages/`, then writes
`release_manifest.json` with SHA-256 checksums and optionally a `.zip` archive.

## Publication Boundary

Use this simple rule:

- if an artifact is powering the dashboard, it should contain only current
  rerun values
- if an artifact is for comparison or client review, it may carry legacy
  reference columns

## Release Checklist

- standard results come from the current full-H5 selected-panel path
- sentinel checks are clean in representative early, middle, and late years
- dashboard artifacts use only current results
- spreadsheet comparison artifacts are the only place where legacy values are
  carried forward
- the live audit note reflects the final release state:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)
- independent review should start from
  [REFORM_MODELING_BIBLE.md](REFORM_MODELING_BIBLE.md),
  [v2-baseline-method.md](v2-baseline-method.md), and
  `dashboard/public/data/results_contract.json`

## Archive Boundary

The deleted Jupyter Book and older point-in-time memos are historical context,
not the release contract for the current delivery. The public split is now the
Next dashboard for current results and the Quarto paper for citation-grade
methods.
