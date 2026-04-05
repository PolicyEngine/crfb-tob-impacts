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

### Sniff Test (Quick Validation)

Run 3 sample years (2030, 2050, 2080) to validate results look reasonable:

```bash
cd modal_batch
modal run compute.py::sniff_test --reforms option9,option10,option11 --scoring static
```

### Test Single Reform/Year

```bash
modal run compute.py::test_single --reform option9 --year 2030 --scoring dynamic
```

### Full Run (All Years)

Run all years for specified reforms:

```bash
# New options only (static)
modal run compute.py::run_reforms --reforms option9,option10,option11 --scoring static --output results/new_options_static.csv

# New options only (dynamic)
modal run compute.py::run_reforms --reforms option9,option10,option11 --scoring dynamic --output results/new_options_dynamic.csv

# Custom year range
modal run compute.py::run_reforms --reforms option9 --years 2026-2035 --scoring static
```

### Manifest-Driven Scenario Runs

For robust long-running work, use the manifest-driven scenario submitter. It
uploads a remote run manifest first, then launches one detached Modal app per
`(year, scenario)` and records per-scenario `submitted/started/success/error`
sentinels on the results volume. Baseline is currently mandatory for this
workflow, and each year also persists a shared weight bundle so recovered runs
can be aggregated without reopening the original H5s. By default, the submitter
also creates a fresh immutable per-run H5 snapshot under
`projected_datasets_snapshots/` before launch so one run cannot mix dataset
vintages across detached cells.

```bash
uv run python scripts/submit_modal_scenario_run.py \
  --reforms option1,option2,option3 \
  --years 2026,2030 \
  --scoring static
```

Recover the remote run tree and inspect status with:

```bash
uv run python scripts/recover_modal_run.py \
  --run-id modal-scenarios_YYYYMMDD_HHMMSS_microseconds_hash_nonce \
  --output-root results/modal_runs
```

Once scenario artifacts are recovered locally, aggregate them into reform
tables with:

```bash
uv run python scripts/aggregate_modal_run.py \
  --run-dir results/modal_runs/modal-scenarios_YYYYMMDD_HHMMSS_microseconds_hash_nonce \
  --output results/modal_scenarios.csv
```

Aggregation is strict by default: it fails if the run still has pending or
failed cells. Use `--allow-incomplete` only for explicit partial inspection.

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
  - `run_cells_detached()`: Detached fire-and-forget cell submission
  - `materialize_scenario_from_run()`: One scenario per detached Modal app
  - `submit_modal_scenario_run.py`: Manifest-driven submitter
  - `recover_modal_run.py`: Download/summarize helper for manifest-backed runs
  - `aggregate_modal_run.py`: Offline aggregation from recovered household metrics

## Monitoring

View running jobs at: https://modal.com/apps/policyengine/main
