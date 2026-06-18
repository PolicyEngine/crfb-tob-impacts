# Archived Google Cloud Batch Guide

This guide is intentionally archived. The old Google Cloud Batch pipeline
produced split static/dynamic CSVs that are no longer part of the CRFB contract.

Use the current Modal/full-H5 pipeline instead:

- Public results: `results.csv`
- Dashboard copy: `dashboard/public/data/results.csv`
- Raw provenance inputs:
  - `results/modal_runs_production/static_cells.csv`
  - `results/modal_runs_production/behavioral_endpoint_cells.csv`
- Orchestrator: `modal_batch/run_panel.py`
- Result publisher: `scripts/publish_dashboard_results.py`

Do not restart the old Cloud Batch workflow for current CRFB work.
