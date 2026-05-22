# Modal Batch Compute

Alternative to GCP Batch for running PolicyEngine simulations. Uses [Modal](https://modal.com) for serverless compute.

**Key feature**: Imports directly from `src/reforms.py` - same reform definitions as GCP batch, no code duplication.

## Setup

```bash
# Install Modal CLI
pip install modal

# Authenticate (one-time)
modal token new
```

## Usage

Use the package CLI for any publishable or paid run. By default it resolves
long-run H5s through the installed `policyengine.py` US bundle, writes a
reproducibility bundle, and refuses raw local H5/checkout arguments. A local
`policyengine.py` checkout can be mounted only as an explicit temporary override
while a release is pending.

Direct `modal run modal_batch/compute.py::...` commands are for local debugging
only and must not be used for production CRFB scores.

### Sniff Test (Quick Validation)

Run 3 sample years (2030, 2050, 2080) to validate results look reasonable:

```bash
crfb-tob modal-refresh \
  --modal-target run_reforms \
  --reforms option9,option10,option11 \
  --years 2030,2050,2080 \
  --scoring static \
  --output results/sniff_static.csv
```

While a `policyengine.py` release is pending, mount that checkout explicitly:

```bash
crfb-tob modal-refresh \
  --policyengine-py-path /path/to/policyengine.py \
  --modal-target run_reforms \
  --reforms option9,option10,option11 \
  --years 2030,2050,2080 \
  --scoring static \
  --output results/sniff_static.csv
```

### Test Single Reform/Year

```bash
crfb-tob modal-refresh \
  --modal-target run_reforms \
  --reforms option9 \
  --years 2030 \
  --scoring conventional \
  --output results/option9_2030_conventional.csv
```

### Full Run (All Years)

Run all years for specified reforms:

```bash
# New options only (static)
crfb-tob modal-refresh --modal-target run_reforms --reforms option9,option10,option11 --years 2026-2035 --scoring static --output results/new_options_static.csv

# New options only (conventional)
crfb-tob modal-refresh --modal-target run_reforms --reforms option9,option10,option11 --years 2026-2035 --scoring conventional --output results/new_options_conventional.csv

# Custom year range
crfb-tob modal-refresh --modal-target run_reforms --reforms option9 --years 2026-2035 --scoring static --output results/option9_static.csv
```

### Durable Scenario Artifacts

For debugging and publication reruns, prefer scenario artifacts when wall-clock
time matters and we want detailed auditability. This submits one Modal job for
each baseline/reform/year scenario and saves:

- `metrics.npz`: household-level scenario outputs used by the score
- `weights.npz`: household IDs and calibrated weights used to aggregate metrics
- `aggregates.json`: weighted national totals by output variable
- `metadata.json`: dataset metadata, tax-assumption contract, sample settings,
  support/calibration metadata, and baseline reconciliation details
- `scenario.h5`: raw scenario microdata when raw-H5 persistence is enabled

The final delta CSV is derived locally from the saved artifacts:

```bash
crfb-tob modal-refresh \
  --modal-target submit_scenario_artifacts \
  --reforms option1,option2,option3 \
  --years 2026-2035,2040,2045 \
  --scoring static \
  --output results/artifact_backed_static.csv \
  --submission-manifest results/modal_submissions/artifact_backed_static.json

uv run python scripts/recover_modal_scenario_artifacts.py \
  --manifest results/modal_submissions/artifact_backed_static.json
```

### Raw Reform H5 Retention

Future reform cells save raw scenario H5s by default starting in 2026 under the
Modal volume path:

```text
/results/<run-prefix>/reform_raw_h5/year=YYYY/reform=optionX/scenario.h5
/results/<run-prefix>/reform_raw_h5/year=YYYY/reform=optionX/metadata.json
```

To mirror those artifacts to Cloudflare R2 or another S3-compatible store, set a
Modal secret name locally before submitting and put the bucket credentials in
that secret:

```bash
export CRFB_REFORM_RAW_H5_OBJECT_STORE_MODAL_SECRET=cloudflare-r2-axiom
export CRFB_R2_BUCKET=crfb-artifacts
export CRFB_R2_ACCOUNT_ID=<account id>
export CRFB_REFORM_RAW_H5_OBJECT_STORE_PREFIX=crfb/reform_raw_h5
```

The secret should provide either `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or
`CRFB_R2_ACCESS_KEY_ID`/`CRFB_R2_SECRET_ACCESS_KEY`. If a bucket is configured
but endpoint or credentials are missing, the Modal worker fails closed rather
than silently dropping raw H5 retention.

### Raw-H5 Diagnostics

Raw H5 snapshots are a diagnostic escape hatch only. They require an explicit
flag and explicit paths so a local checkout cannot be picked up accidentally:

```bash
crfb-tob modal-refresh \
  --no-policyengine-py-managed-datasets \
  --modal-target run_reforms \
  --policyengine-us-path /path/to/pinned/policyengine-us \
  --projected-datasets-path /path/to/projected_datasets \
  --snapshot-path /path/to/snapshot \
  --reforms option9 \
  --years 2030 \
  --scoring static \
  --output results/raw_h5_diagnostic.csv
```

## Comparison with GCP Batch

| Aspect | GCP Batch (`batch/`) | Modal (`modal_batch/`) |
|--------|---------------------|------------------------|
| Reform definitions | `src/reforms.py` | `src/reforms.py` (same!) |
| Setup | Docker build + push | None (pip install) |
| Monitoring | Custom scripts | Built-in dashboard |
| Results | Download from GCS | Returned directly |
| Parallelization | Batch job config | Automatic |
| Cold start | ~5-10 min | ~1-2 min |

## Architecture

- **compute.py**: Modal app with compute functions
  - Uses `modal.Mount` to mount `src/` directory into container
  - Imports from `src/reforms.py` (same as GCP batch)
  - Same output columns as GCP batch for compatibility
  - `compute_year()`: Compute all reforms for a single year (parallelized by year)
  - `test_single()`: Test one reform/year
  - `sniff_test()`: Quick 3-year validation
  - `run_reforms()`: Full parallel run

Results are returned directly to your local machine - no GCS download needed.

## Monitoring

View running jobs at: https://modal.com/apps/policyengine/main
