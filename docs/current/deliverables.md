# Current Deliverables

This page defines what gets shipped and how legacy comparisons should be
handled.

## Primary Outputs

The intended current delivery surface is:

- one unified 14-option static results table
- one unified standard-option dynamic results table
- dashboard data built from the current results only
- one spreadsheet that includes prior or legacy reference values for
  comparison

The main tracked output paths are:

- `results/all_static_results_latesthf_2026_2100_14options.csv`
- `results/all_dynamic_results_latesthf_2026_2100_standard_options.csv`
- `results/all_static_results_latesthf_2026_2100_14options_with_prior_reference.csv`
- `results/all_static_results_latesthf_2026_2100_14options_with_prior_reference.xlsx`
- `dashboard/public/data/all_static_results.csv`
- `dashboard/public/data/all_dynamic_results.csv`
- `dashboard/public/data/option13_balanced_fix.csv`

## Delivery Rules

### Dashboard

The dashboard should show current rerun values only.

That means:

- no legacy standard rows in the dashboard current-results path
- no stale dynamic subset files from earlier conventional runs
- no stale stitched values carried forward for convenience
- special cases should use the assembled current `option13` and
  `option14_stacked` rows

For the current release, the public dynamic surface covers standard reforms
`option1` through `option12`. Special-case dynamic rows are not part of the
delivery bundle.

### Spreadsheet

The spreadsheet is where legacy values belong.

Use it for:

- old versus new comparisons
- client-facing legacy-reference columns
- validation summaries during the audit period

Do not treat spreadsheet legacy columns as a substitute for current dashboard
data.

## Assembly Artifacts

These scripts define the current delivery build:

- [scripts/assemble_special_case_results.py](../../scripts/assemble_special_case_results.py)
- [scripts/build_latesthf_14option_delivery.py](../../scripts/build_latesthf_14option_delivery.py)
- [scripts/publish_dynamic_results.py](../../scripts/publish_dynamic_results.py)

The spreadsheet-with-prior-reference output is the right place to preserve the
old values while the dashboard moves to the rebuilt current values.

## Publication Boundary

Use this simple rule:

- if an artifact is powering the dashboard, it should contain only current
  rerun values
- if an artifact is for comparison or client review, it may carry legacy
  reference columns

## Release Checklist

- standard results come from the hardened exact-only rerun path
- special-case rows come from the assembled `option13` and `option14_stacked`
  path, not ad hoc manual edits
- sentinel checks are clean in representative early, middle, and late years
- dashboard artifacts use only current results
- spreadsheet comparison artifacts are the only place where legacy values are
  carried forward
- the live audit note reflects the final release state:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)

## Archive Boundary

Anything under `jupyterbook/` or the older point-in-time memos is still useful
for historical context, but it is not the release contract for the current
delivery.
