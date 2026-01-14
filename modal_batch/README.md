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
