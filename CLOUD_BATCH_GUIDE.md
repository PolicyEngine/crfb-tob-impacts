# Archived Google Cloud Batch Guide

This guide is intentionally archived. The old Google Cloud Batch pipeline
produced split static/dynamic CSVs that are no longer part of the CRFB contract.

Use the current Modal/full-H5 pipeline instead:

- Public results: `results.csv`
- Dashboard copy: `dashboard/public/data/results.csv`
- Durable provenance inputs:
  - `reform_full_h5/year=YYYY/reform=OPTION/scenario.h5`
  - `reform_full_h5/year=YYYY/reform=OPTION/metadata.json`
  - `reform_full_h5/year=YYYY/reform=OPTION/complete.json`
- Production launcher: `modal_batch/reform_full_h5.py::submit_reform_full_h5`
- Result aggregation: `scripts/aggregate_reform_full_h5_results.py`

Do not restart the old Cloud Batch workflow for current CRFB work.
