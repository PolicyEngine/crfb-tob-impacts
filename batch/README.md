# Google Cloud Batch - Social Security Policy Impact Analysis

This directory contains scripts to run PolicyEngine simulations at scale using Google Cloud Batch.

## Overview

**Problem:** Running 1,200 simulations (8 reforms × 75 years × 2 scoring types) sequentially takes ~200 hours.

**Solution:** Use Google Cloud Batch to run simulations in parallel, completing in ~2-3 hours.

## Architecture

### Two-Phase Approach

**Phase 1: Compute Baselines (75 tasks, ~20 mins)**
- Calculate baseline income tax for each year (2026-2100)
- Each year uses PolicyEngine's year-specific dataset
- Results saved to Cloud Storage for reuse

**Phase 2: Compute Reforms (1,200 tasks, ~2-4 hrs)**
- Calculate reform impacts for all combinations:
  - 8 reforms × 75 years × 2 scoring types = 1,200 calculations
- Each task downloads its year's baseline from Phase 1
- Supports both static and dynamic scoring
- Results saved to Cloud Storage

**Phase 3: Download & Combine (2 mins)**
- Download all 1,200 result files
- Combine into CSV files for analysis

## Files

```
batch/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container definition
├── compute_baseline.py       # Phase 1 worker script
├── compute_reform.py         # Phase 2 worker script
├── submit_baselines.py       # Phase 1 job submission
├── submit_reforms.py         # Phase 2 job submission
└── download_results.py       # Results aggregation
```

## Setup (One-Time)

### 1. Build and Push Docker Container (~10-15 mins)

```bash
cd /Users/pavelmakarchuk/crfb-tob-impacts
gcloud config set project policyengine-api
gcloud builds submit --tag gcr.io/policyengine-api/ss-calculator:latest batch/
```

This builds the container with Python 3.13, PolicyEngine, and your reform definitions.

### 2. Verify Cloud Storage Bucket

```bash
gsutil ls gs://crfb-ss-analysis-results/
```

Should show the bucket was created. If not:
```bash
gsutil mb -l us-central1 gs://crfb-ss-analysis-results/
```

## Running Jobs

### Test Run (Recommended First!)

Test with 2 years, 2 reforms, both scoring types = 8 simulations:

```bash
cd batch

# Phase 1: Compute baselines for 2 years (~1-2 mins)
python submit_baselines.py --years 2026,2027

# Wait for completion, then Phase 2
python submit_reforms.py --reforms option1,option2 --years 2026,2027

# Download results
python download_results.py --job-id reforms-YYYYMMDD-HHMMSS-xxxxxx
```

**Verify:**
- Results match your notebook values for 2026-2027
- Both static and dynamic results present
- No errors in Cloud Batch logs

### Full Run (All 1,200 Simulations)

```bash
cd batch

# Phase 1: Compute all 75 baselines (~20 mins)
python submit_baselines.py --years 2026-2100
# Output: Job ID for monitoring

# Monitor Phase 1
gcloud batch jobs describe baselines-YYYYMMDD-HHMMSS-xxxxxx --location=us-central1

# When Phase 1 completes, run Phase 2 (~2-4 hrs with 200 workers)
python submit_reforms.py --years 2026-2100
# Output: Job ID for monitoring

# Monitor Phase 2
gcloud batch jobs describe reforms-YYYYMMDD-HHMMSS-xxxxxx --location=us-central1

# When complete, download results
python download_results.py --job-id reforms-YYYYMMDD-HHMMSS-xxxxxx
```

**Output files:**
- `../data/policy_impacts_static.csv` - All static scoring results
- `../data/policy_impacts_dynamic.csv` - All dynamic scoring results
- `../data/policy_impacts_all.csv` - Combined results

## Command Options

### submit_baselines.py

```bash
python submit_baselines.py \
  --years 2026-2100        # Years to compute (range or comma-separated)
  --project policyengine-api  # Google Cloud project
  --region us-central1     # Google Cloud region
  --bucket crfb-ss-analysis-results  # Cloud Storage bucket
```

### submit_reforms.py

```bash
python submit_reforms.py \
  --reforms all            # Reforms: "all", "option1,option2", etc.
  --years 2026-2100        # Years to compute
  --scoring all            # Scoring: "all", "static", or "dynamic"
  --workers 200            # Number of parallel workers (default: 200)
  --project policyengine-api
  --region us-central1
  --bucket crfb-ss-analysis-results
```

**Faster completion:** Use `--workers 400` or `--workers 600` (may require quota increase)

### download_results.py

```bash
python download_results.py \
  --job-id reforms-YYYYMMDD-HHMMSS-xxxxxx  # From submit_reforms.py output
  --bucket crfb-ss-analysis-results
  --output-dir ../data     # Where to save CSV files
```

## Monitoring Jobs

### Check Job Status

```bash
# List all jobs
gcloud batch jobs list --location=us-central1

# Describe specific job
gcloud batch jobs describe JOB_ID --location=us-central1

# View logs
gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=JOB_ID" --limit=50
```

### Web Console

https://console.cloud.google.com/batch?project=policyengine-api

## Cost

**Per full run (1,200 simulations):**
- Phase 1: 75 workers × 20 mins = ~$0.25
- Phase 2: 200 workers × 2 hrs = ~$4.00
- Storage: ~$0.01
- **Total: ~$4.25**

Using spot/preemptible instances (60-80% cheaper than regular VMs).

## Troubleshooting

### "No baseline found for year YYYY"
- Phase 1 didn't complete or failed
- Check Phase 1 job logs
- Re-run `submit_baselines.py` if needed

### "Container image not found"
- Docker container wasn't built or pushed
- Re-run: `gcloud builds submit --tag gcr.io/policyengine-api/ss-calculator:latest batch/`

### "Quota exceeded"
- Need more than default concurrent VMs
- Request quota increase: https://console.cloud.google.com/iam-admin/quotas?project=policyengine-api
- Search for "CPUs" or "Batch API"

### Results don't match notebook
- Check that reforms in `src/reforms.py` match notebook
- Verify PolicyEngine version matches
- Test with single year first to debug

## Customization

### Change Reforms

Edit `src/reforms.py` and rebuild container:
```bash
gcloud builds submit --tag gcr.io/policyengine-api/ss-calculator:latest batch/
```

### Use Different Dataset

PolicyEngine automatically uses year-specific datasets based on the `period` parameter in simulations. No changes needed.

### Add More Workers

Edit `submit_reforms.py` and change `default=200` to `default=400` in the `--workers` argument, or use the flag when submitting:
```bash
python submit_reforms.py --workers 400 --years 2026-2100
```

## References

- Google Cloud Batch docs: https://cloud.google.com/batch/docs
- PolicyEngine US: https://github.com/PolicyEngine/policyengine-us
- Project notebook: `jupyterbook/policy-impacts-dynamic.ipynb`
