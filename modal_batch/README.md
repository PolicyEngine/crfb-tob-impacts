# Modal Batch Compute

This directory contains the current Modal entrypoints for the CRFB model. Do
not use historical wrapper commands or deleted legacy compute modules; those are
outside the current contract.

## Canonical Entry Points

### Full Reform H5 Cells

Use `modal_batch/reform_full_h5.py::submit_reform_full_h5` for durable full-H5
reform cells. This is the path for paid production cells that must persist
`reform_full_h5/year=YYYY/reform=REFORM/scenario.h5`, metadata, and completion
records.

```bash
modal run modal_batch/reform_full_h5.py::submit_reform_full_h5 -- \
  --reforms option1,option2 \
  --years 2026,2100 \
  --scoring-type static \
  --launch-mode sentinel \
  --ledger-path docs/current/reform-modeling-progress.json \
  --submission-manifest results/modal_submissions/reform_full_h5_example.json \
  --dry-run
```

Remove `--dry-run` only after the canonical ledger approves the exact paid
launch. Full paid launches must use `docs/current/reform-modeling-progress.json`
and preserve the full H5 artifacts.

## Reproducibility Bundle

Before a paid run, write a reproducibility bundle using one of the current Modal
targets:

```bash
uv run python -m src.cli write-repro-bundle \
  --output results/intended_output.csv \
  --scoring static \
  --reforms option1,option2 \
  --years 2026,2100 \
  --modal-target reform_full_h5
```

The production `--modal-target` value is `reform_full_h5`.
