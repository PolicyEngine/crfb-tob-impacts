# Current Deliverables

This page defines what gets shipped and how legacy comparisons should be
handled.

## Primary Outputs

The intended current delivery surface is:

- one unified 14-option static results table
- one unified standard-option conventional results table
- dashboard data built from the current results only
- one spreadsheet that includes prior or legacy reference values for
  comparison

The main tracked output paths are:

- `results/all_static_results_latesthf_2026_2100_14options.csv`
- `results/all_dynamic_results_latesthf_2026_2100_standard_options.csv`
- `results/all_static_results_latesthf_2026_2100_14options_with_prior_reference.csv`
- `results/all_static_results_latesthf_2026_2100_14options_with_prior_reference.xlsx`
- `dashboard/public/data/all_static_results.csv`
- `dashboard/public/data/option13_balanced_fix.csv`

The `all_dynamic_*` filenames are historical compatibility names for the
conventional-result artifact. Public-facing text should call this track
conventional. While conventional results remain quarantined, no
`all_dynamic_results.csv` copy belongs under `dashboard/public/data/`, built
dashboard output, or `.vercel-site`.

## Delivery Rules

### Dashboard

The dashboard should show current rerun values only.

That means:

- no legacy standard rows in the dashboard current-results path
- no stale conventional subset files from earlier runs
- no stale stitched values carried forward for convenience
- special cases should use the assembled current `option13` and
  `option14_stacked` rows

For the current release, conventional results are quarantined until their
baseline levels match the static release. During quarantine, the internal
`results/all_dynamic_*` artifact may exist as a rerun input, but public
dashboard, built-site, paper, and spreadsheet outputs must not expose
conventional point estimates. Special-case conventional rows are not part of
the delivery bundle. That omission is intentional: the balanced-fix special
cases would require a separate iterative post-response solve and are not needed
for the shipped dashboard, spreadsheet, or paper.

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
- [scripts/publish_conventional_results.py](../../scripts/publish_conventional_results.py)

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
- independent review should start from
  [docs/current/fresh-review-brief.md](fresh-review-brief.md)

## Archive Boundary

The deleted Jupyter Book and older point-in-time memos are historical context,
not the release contract for the current delivery. The public split is now the
Next dashboard for current results and the Quarto paper for citation-grade
methods.
