# Google Cloud Batch - Social Security Reform Impact Calculations

This guide documents the batch computation system for running Social Security reform impact calculations across 75 years (2026-2100) using Google Cloud Batch.

## Overview

**What it does:**
- Runs parallel PolicyEngine microsimulations for 8 reform options × 75 years × 2 scoring types
- Each VM calculates one year's worth of reform impacts
- Results saved to Cloud Storage and combined into final CSVs

**Key outputs:**
- `all_static_results.csv` - Static scoring results (600 rows: 8 options × 75 years)
- `all_dynamic_results.csv` - Dynamic scoring results with labor supply responses

**Cost:** ~$40-55 for a full run (all 8 options, both scoring types)

## Prerequisites

### 1. PolicyEngine-US Setup

The Docker container bundles a local copy of PolicyEngine-US with required PRs:

```bash
# Clone policyengine-us with required PRs
git clone https://github.com/PolicyEngine/policyengine-us.git
cd policyengine-us

# Checkout PR #6750 (TOB revenue variables + tier fixes)
git fetch origin pull/6750/head:pr-6750
git checkout pr-6750

# Merge PR #6830 (labor supply elasticity)
git fetch origin pull/6830/head:pr-6830
git merge pr-6830 --no-edit

cd ..
```

**Required PRs:**
| PR | Description |
|----|-------------|
| #6750 | Trust fund revenue variables with TOB tier fixes |
| #6830 | Labor supply elasticity age heterogeneity |

### 2. GCP Authentication

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project policyengine-api
```

### 3. Build Docker Image

```bash
# From project root
docker buildx build --platform linux/amd64 -t gcr.io/policyengine-api/crfb-analysis:latest --push .
```

**Important:** The Dockerfile copies `./policyengine-us/` into the container. Rebuild after any PolicyEngine changes.

## Key Files

| File | Purpose |
|------|---------|
| `batch/compute_year.py` | Core computation logic - runs on each VM |
| `batch/submit_years.py` | Job submission with automatic VM sizing |
| `batch/requirements.txt` | Python dependencies for container |
| `Dockerfile` | Container image definition |
| `src/reforms.py` | Reform parameter definitions |
| `monitor_all.sh` | Job monitoring script |

## Architecture

### VM Configuration
- **Machine:** e2-highmem-8 (8 vCPU, 64GB RAM)
- **Timeout:** 60 minutes per task (1 hour)
- **Container:** `gcr.io/policyengine-api/crfb-analysis:latest`
- **Storage:** `gs://crfb-ss-analysis-results/`

### Automatic VM Sizing
The system automatically splits jobs when years 2026-2027 are included (they require more memory due to larger datasets).

## Usage

### Submit Jobs

```bash
# Submit one option for all 75 years
python batch/submit_years.py \
  --years "2026,2027,2028,...,2100" \
  --reforms option5 \
  --scoring static

# The system auto-splits into 2 jobs:
# - Job 1: Years 2026-2027 (64GB VMs)
# - Job 2: Years 2028-2100 (64GB VMs)
```

**Available reforms:** option1, option2, option3, option4, option5, option6, option7, option8

**Scoring types:** static, dynamic

### Monitor Jobs

Use the monitoring script:

```bash
./monitor_all.sh
```

Or check individual jobs:

```bash
# Job status
gcloud batch jobs describe JOB_ID --location=us-central1

# Task counts
gcloud batch tasks list --job=JOB_ID --location=us-central1 \
  --project=policyengine-api --format="value(status.state)" | sort | uniq -c
```

### Download Results

```bash
# Download from a completed job
gsutil -m cp "gs://crfb-ss-analysis-results/results/JOB_ID/*.csv" /tmp/results/

# Convert to billions and add to combined CSV
find /tmp/results -name "*.csv" -exec tail -n +2 {} \; | \
  awk -F',' 'BEGIN{OFS=","} {for(i=3;i<=NF;i++){$i=$i/1e9} print}' >> all_static_results.csv
```

## Output Columns

| Column | Description |
|--------|-------------|
| reform_name | Reform identifier (option1-option8) |
| year | Simulation year (2026-2100) |
| baseline_revenue | Federal income tax revenue under current law (billions) |
| reform_revenue | Federal income tax revenue under reform (billions) |
| revenue_impact | Change in income tax revenue (billions) |
| baseline_tob_oasdi | TOB revenue to OASDI trust fund - baseline (billions) |
| reform_tob_oasdi | TOB revenue to OASDI trust fund - reform (billions) |
| tob_oasdi_impact | Change in OASDI TOB revenue (billions) |
| baseline_tob_medicare_hi | TOB revenue to HI trust fund - baseline (billions) |
| reform_tob_medicare_hi | TOB revenue to HI trust fund - reform (billions) |
| tob_medicare_hi_impact | Change in HI TOB revenue (billions) |
| scoring_type | "static" or "dynamic" |
| employer_ss_tax_revenue | Income tax from employer SS (Options 5-6 only) |
| employer_medicare_tax_revenue | Income tax from employer Medicare (Options 5-6 only) |
| oasdi_gain | New revenue to OASDI (Options 5-6 only) |
| hi_gain | New revenue to HI (Options 5-6 only) |
| oasdi_loss | Lost TOB revenue from OASDI (Options 5-6 only) |
| hi_loss | Lost TOB revenue from HI (Options 5-6 only) |
| oasdi_net_impact | Net OASDI trust fund impact (Options 5-6 only) |
| hi_net_impact | Net HI trust fund impact (Options 5-6 only) |

### Trust Fund Impact Columns

**For Options 1-4, 7-8:** Use `tob_oasdi_impact` and `tob_medicare_hi_impact`

**For Options 5-6:** Use `oasdi_net_impact` and `hi_net_impact`

Options 5-6 use "direct branching" where employer payroll tax income tax revenue is allocated directly to trust funds:
- Option 5: Direct branching (employer SS → OASDI, employer Medicare → HI)
- Option 6: Phased allocation with 6.2pp threshold during 2026-2032

The net impact = gain - loss:
```
oasdi_net = oasdi_gain - oasdi_loss
hi_net = hi_gain - hi_loss
```

## Troubleshooting

### Task Timeouts
If tasks fail with timeout errors, check logs in Cloud Console. The 60-minute timeout handles most cases.

### Authentication Errors
GCP tokens expire. Re-run authentication commands during long sessions:
```bash
gcloud auth login
gcloud auth application-default login
```

### Failed Tasks
Some tasks may fail randomly. Download partial results and re-run only missing years:
```bash
# Find missing years
grep "^option5," all_static_results.csv | awk -F',' '{print $2}' | sort -n > have.txt
seq 2026 2100 > need.txt
comm -23 need.txt have.txt  # Shows missing years

# Re-run missing years
python batch/submit_years.py --years "2034,2086" --reforms option5 --scoring static
```

### Docker Image Issues
```bash
# Verify image exists
gcloud container images describe gcr.io/policyengine-api/crfb-analysis:latest

# Rebuild if needed
docker buildx build --platform linux/amd64 --no-cache \
  -t gcr.io/policyengine-api/crfb-analysis:latest --push .
```

## Lessons Learned

1. **Submit 2-4 options at a time** - Too many parallel jobs cause resource contention
2. **Use 64GB RAM** - TOB calculations need more memory than expected
3. **60-minute timeout works well** - Long enough to complete, catches stuck tasks
4. **Download incrementally** - Don't wait for all jobs; download as each completes
5. **Keep raw CSVs** - Individual result files allow rebuilding combined CSV if needed
6. **Monitor actively** - Check every 10-15 minutes and restart stuck jobs
7. **Re-authenticate periodically** - GCP tokens expire after a few hours

## Common Commands Reference

```bash
# Submit job
python batch/submit_years.py --years "2026,2027,...,2100" --reforms option1 --scoring static

# Monitor job
gcloud batch jobs describe JOB_ID --location=us-central1

# List task states
gcloud batch tasks list --job=JOB_ID --location=us-central1 --format="value(status.state)" | sort | uniq -c

# Download results
gsutil -m cp "gs://crfb-ss-analysis-results/results/JOB_ID/*.csv" ./results/

# Delete completed job
gcloud batch jobs delete JOB_ID --location=us-central1 --quiet

# List all jobs
gcloud batch jobs list --location=us-central1 --filter="state:RUNNING"
```
