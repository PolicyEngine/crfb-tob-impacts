# Google Cloud Batch - Social Security Reform Impact Calculations

This directory contains scripts for running parallel Social Security reform impact calculations on Google Cloud Batch.

## Prerequisites

### 1. Required PolicyEngine-US Pull Requests

**IMPORTANT:** Before running any calculations, you must check out the following PRs locally since GCP runs from a local version of policyengine-us bundled into the Docker container:

| PR | Title | Description |
|----|-------|-------------|
| [#6744](https://github.com/PolicyEngine/policyengine-us/pull/6744) | Extend Economic Uprating Parameters to 2100 | Extends economic parameters (CPI, wages, income) through 2100 using SSA Trustees Report data |
| [#6750](https://github.com/PolicyEngine/policyengine-us/pull/6750) | Trust Fund Revenue Variables with LSR Recursion Fix | Adds `tob_revenue_total`, `tob_revenue_oasdi`, `tob_revenue_medicare_hi` variables for measuring trust fund revenue from Social Security benefit taxation |
| [#6830](https://github.com/PolicyEngine/policyengine-us/pull/6830) | Add Labor Supply Elasticity Age Heterogeneity | Adds age-based labor supply elasticity support (65+ threshold) for more accurate behavioral responses |

To check out all PRs into a local policyengine-us directory:

```bash
# Clone policyengine-us if not already present
git clone https://github.com/PolicyEngine/policyengine-us.git

# Fetch all PR branches and merge them
cd policyengine-us
git fetch origin pull/6744/head:pr-6744
git fetch origin pull/6750/head:pr-6750
git fetch origin pull/6830/head:pr-6830

# Create a branch with all PRs merged
git checkout main
git checkout -b combined-tob-features
git merge pr-6744 --no-edit
git merge pr-6750 --no-edit
git merge pr-6830 --no-edit

cd ..
```

### 2. GCP Authentication

```bash
# Login to GCP
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project policyengine-api
```

**Note:** GCP auth tokens expire periodically. If you get authentication errors during a long-running session, re-run both auth commands above.

### 3. Docker & Container Registry

The Docker image must be built and pushed before running batch jobs:

```bash
# Build the Docker image (from project root, not batch directory)
cd /Users/pavelmakarchuk/crfb-tob-impacts
docker build -t gcr.io/policyengine-api/ss-calculator:latest -f batch/Dockerfile .

# Push to Google Container Registry
docker push gcr.io/policyengine-api/ss-calculator:latest
```

**Note:** The Dockerfile copies the local `policyengine-us/` directory into the container, so any changes to the PRs require rebuilding and pushing the image.

## Architecture

### Year-Based Parallelization

The system parallelizes by **year**, not by reform-year combination:

- Each VM handles ONE year
- Downloads dataset ONCE per year
- Calculates baseline ONCE per year
- Runs ALL specified reforms for that year
- Much more efficient than parallelizing by reform

### VM Configuration

- **Machine type:** e2-highmem-8 (8 vCPU, 64GB RAM)
- **Timeout:** 20 minutes per task (with 1 retry)
- **Container:** `gcr.io/policyengine-api/ss-calculator:latest`
- **Storage:** Results saved to `gs://crfb-ss-analysis-results/`

### Why 64GB RAM for All Years

Initially we tried using 32GB VMs for years 2028-2100 and 64GB only for 2026-2027 (which have larger datasets). However, the TOB revenue variable calculations require more memory than expected across all years. Using 64GB for all years eliminates memory-related failures.

## Files

```
batch/
├── README.md           # This file
├── Dockerfile          # Docker image definition
├── requirements.txt    # Python dependencies for container
├── submit_years.py     # Job submission script
└── compute_year.py     # Worker script (runs inside container)
```

## Usage

### Submitting Jobs

**Recommended approach:** Submit ONE reform at a time across all 75 years. This is more reliable than submitting all 8 reforms simultaneously, which can cause resource contention.

```bash
# Submit a single reform for all years (RECOMMENDED)
python batch/submit_years.py \
  --years "$(seq -s, 2026 2100)" \
  --reforms option1 \
  --scoring static

# Submit for specific years only
python batch/submit_years.py \
  --years "2026,2027,2028,2029,2030" \
  --reforms option1 \
  --scoring static

# Dynamic scoring (includes CBO labor supply elasticities)
python batch/submit_years.py \
  --years "$(seq -s, 2026 2100)" \
  --reforms option1 \
  --scoring dynamic
```

### Available Reforms

| Reform ID | Description |
|-----------|-------------|
| option1 | Full repeal of Social Security benefit taxation |
| option2 | 85% taxation threshold |
| option3 | Increase thresholds |
| option4 | $500 tax credit |
| option5 | Medicare HI only |
| option6 | OASDI only |
| option7 | Combined approach |
| option8 | Alternative structure |

### Monitoring Jobs

```bash
# Check job status
gcloud batch jobs describe JOB_ID --location=us-central1

# List all tasks in a job
gcloud batch tasks list --job=JOB_ID --location=us-central1 --project=policyengine-api

# Count task statuses (most useful for monitoring progress)
gcloud batch tasks list --job=JOB_ID --location=us-central1 --project=policyengine-api --format="value(status.state)" | sort | uniq -c

# View logs in Cloud Console
# https://console.cloud.google.com/batch/jobs/JOB_ID?project=policyengine-api
```

#### Continuous Monitoring Script

Create a monitoring script for multiple jobs:

```bash
#!/bin/bash
# monitor_jobs.sh - Monitor multiple batch jobs

PROJECT="policyengine-api"
# Update these job IDs with your actual job IDs
OPT1_JOB="years-YYYYMMDD-HHMMSS-xxxxxx"
OPT2_JOB="years-YYYYMMDD-HHMMSS-xxxxxx"

while true; do
    clear
    echo "========================================"
    echo "BATCH JOBS STATUS - $(date)"
    echo "========================================"

    for job in $OPT1_JOB $OPT2_JOB; do
        echo ""
        echo "=== Job: $job ==="
        TASKS=$(gcloud batch tasks list --job=$job --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
        SUCC=$(echo "$TASKS" | grep -c "SUCCEEDED" 2>/dev/null || echo "0")
        RUN=$(echo "$TASKS" | grep -c "RUNNING" 2>/dev/null || echo "0")
        PEND=$(echo "$TASKS" | grep -c "PENDING" 2>/dev/null || echo "0")
        FAIL=$(echo "$TASKS" | grep -c "FAILED" 2>/dev/null || echo "0")
        echo "Tasks: $SUCC succeeded, $RUN running, $PEND pending, $FAIL failed"
    done

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
```

### Downloading Results

```bash
# List results for a job
gsutil ls gs://crfb-ss-analysis-results/results/JOB_ID/

# Download all results from a job (use -m for parallel download)
mkdir -p results/static_partial
gsutil -q -m cp "gs://crfb-ss-analysis-results/results/JOB_ID/*.csv" results/static_partial/

# Download from multiple jobs
for job_id in JOB_ID_1 JOB_ID_2 JOB_ID_3; do
    gsutil -q -m cp "gs://crfb-ss-analysis-results/results/$job_id/*.csv" results/static_partial/
done
```

## Results Processing

### Combining Results into Single CSV

**IMPORTANT:** Raw results from GCP are in raw dollars. Always convert to billions when combining.

```python
import pandas as pd
import glob

# Read all individual CSV files
all_dfs = []
for f in glob.glob("results/static_partial/*_option*_static_results.csv"):
    df = pd.read_csv(f)
    all_dfs.append(df)

# Combine and deduplicate (keep last in case of re-runs)
df_combined = pd.concat(all_dfs, ignore_index=True)
df_combined = df_combined.drop_duplicates(subset=['reform_name', 'year'], keep='last')

# Convert to billions and round to 2 decimals
value_cols = [col for col in df_combined.columns if col not in ['reform_name', 'year', 'scoring_type']]
for col in value_cols:
    df_combined[col] = (df_combined[col] / 1e9).round(2)

# Sort and save
df_combined = df_combined.sort_values(['reform_name', 'year']).reset_index(drop=True)
df_combined.to_csv("results/static_partial/combined_static_partial_billions.csv", index=False)

print(f"Saved {len(df_combined)} rows")
print(df_combined.groupby('reform_name').size())
```

### Adding New Results to Existing Combined CSV

When downloading results from new jobs, add them to the existing combined CSV:

```python
import pandas as pd
import glob

# Read existing combined CSV
df_existing = pd.read_csv("results/static_partial/combined_static_partial_billions.csv")
existing_keys = set(zip(df_existing['reform_name'], df_existing['year']))
print(f"Existing: {len(df_existing)} rows")

# Read new files (e.g., from a temp download directory)
new_dfs = []
for f in glob.glob("/tmp/new_results/*.csv"):
    df = pd.read_csv(f)
    for _, row in df.iterrows():
        key = (row['reform_name'], row['year'])
        if key not in existing_keys:
            # Convert to billions before adding
            row_dict = row.to_dict()
            value_cols = [col for col in row_dict.keys() if col not in ['reform_name', 'year', 'scoring_type']]
            for col in value_cols:
                row_dict[col] = round(row_dict[col] / 1e9, 2)
            new_dfs.append(pd.DataFrame([row_dict]))
            existing_keys.add(key)

if new_dfs:
    df_new = pd.concat(new_dfs, ignore_index=True)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined = df_combined.sort_values(['reform_name', 'year']).reset_index(drop=True)
    df_combined.to_csv("results/static_partial/combined_static_partial_billions.csv", index=False)
    print(f"Added {len(df_new)} new rows. Total: {len(df_combined)}")
```

### Output Columns

| Column | Description |
|--------|-------------|
| reform_name | Reform identifier (option1-option8) |
| year | Simulation year (2026-2100) |
| baseline_revenue | Total federal income tax revenue under current law (billions) |
| reform_revenue | Total federal income tax revenue under reform (billions) |
| revenue_impact | Change in income tax revenue (billions) |
| baseline_tob_medicare_hi | Trust fund revenue from SS taxation - Medicare HI (billions) |
| reform_tob_medicare_hi | Reform Medicare HI trust fund revenue (billions) |
| tob_medicare_hi_impact | Change in Medicare HI trust fund revenue (billions) |
| baseline_tob_oasdi | Trust fund revenue from SS taxation - OASDI (billions) |
| reform_tob_oasdi | Reform OASDI trust fund revenue (billions) |
| tob_oasdi_impact | Change in OASDI trust fund revenue (billions) |
| baseline_tob_total | Total trust fund revenue from SS taxation (billions) |
| reform_tob_total | Reform total trust fund revenue (billions) |
| tob_total_impact | Change in total trust fund revenue (billions) |
| scoring_type | "static" or "dynamic" |

## Recommended Workflow

Based on our experience running all 8 options × 75 years, here's the most reliable workflow:

### Step 1: Setup (One-time)

```bash
# 1. Clone and setup policyengine-us with required PRs
git clone https://github.com/PolicyEngine/policyengine-us.git
cd policyengine-us
git fetch origin pull/6744/head:pr-6744
git fetch origin pull/6750/head:pr-6750
git fetch origin pull/6830/head:pr-6830
git checkout main
git checkout -b combined-tob-features
git merge pr-6744 --no-edit
git merge pr-6750 --no-edit
git merge pr-6830 --no-edit
cd ..

# 2. Authenticate with GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project policyengine-api

# 3. Build and push Docker image
docker build -t gcr.io/policyengine-api/ss-calculator:latest -f batch/Dockerfile .
docker push gcr.io/policyengine-api/ss-calculator:latest
```

### Step 2: Submit Jobs (One Option at a Time)

**Don't submit all 8 options at once!** This causes resource contention and jobs get stuck. Submit 2-4 options at a time, wait for them to complete, then submit more.

```bash
# Submit first batch of options
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option1 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option2 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option3 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option4 --scoring static

# Note the job IDs printed by each command!
# Wait for these to complete (monitor with the script above)
# Then submit remaining options...

python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option5 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option6 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option7 --scoring static
python batch/submit_years.py --years "$(seq -s, 2026 2100)" --reforms option8 --scoring static
```

### Step 3: Monitor and Download

```bash
# Check status
gcloud batch tasks list --job=JOB_ID --location=us-central1 --project=policyengine-api --format="value(status.state)" | sort | uniq -c

# When all tasks show SUCCEEDED, download
mkdir -p results/static_partial
gsutil -q -m cp "gs://crfb-ss-analysis-results/results/JOB_ID/*.csv" results/static_partial/
```

### Step 4: Handle Failed/Missing Years

Some years may fail. Check what's missing and re-run only those:

```bash
# Check which years are missing for option1
python3 -c "
import pandas as pd
df = pd.read_csv('results/static_partial/combined_static_partial_billions.csv')
existing = set(df[df['reform_name']=='option1']['year'])
missing = [y for y in range(2026, 2101) if y not in existing]
if missing:
    print(f'Missing {len(missing)} years: {missing[:10]}...')
    print('Command to re-run:')
    print(f'python batch/submit_years.py --years \"{','.join(map(str, missing))}\" --reforms option1 --scoring static')
else:
    print('All 75 years complete!')
"
```

### Step 5: Combine Results

After downloading all results, combine into single CSV (see Python scripts above).

## Troubleshooting

### Jobs Getting Stuck / Not Progressing

**Symptoms:** Tasks stay in PENDING or RUNNING for a long time without completing.

**Cause:** Too many parallel VMs competing for GCP resources. When you submit 8 options × 75 years = 600 VMs simultaneously, GCP may throttle or queue them.

**Solution:**
1. Kill stuck jobs: `gcloud batch jobs delete JOB_ID --location=us-central1`
2. Submit fewer options at a time (2-4 max)
3. Wait for completion before submitting more

### Task Timeouts

**Symptoms:** Tasks fail with timeout errors after 20 minutes.

**Cause:** Usually memory pressure or slow dataset downloads.

**Solution:**
1. Check logs in Cloud Console for specific errors
2. Re-run only the failed years (they often succeed on retry)
3. If consistent failures, may need to increase timeout in `submit_years.py`

### Authentication Errors

**Symptoms:** `403 Forbidden` or authentication errors when submitting jobs.

**Solution:**
```bash
gcloud auth login
gcloud auth application-default login
```

Auth tokens expire after a few hours. Re-run these commands during long sessions.

### Mixed Formatted/Unformatted Data in Combined CSV

**Symptoms:** Some rows show values like `1352320565064.64` (raw dollars) while others show `1403.56` (billions).

**Cause:** Results from different jobs were combined inconsistently - some converted to billions, some not.

**Solution:** Rebuild the combined CSV from scratch using raw local files:

```python
import pandas as pd
import glob

# Read ALL raw CSV files (they're always in raw dollars)
all_dfs = []
for f in glob.glob("results/static_partial/*_option*_static_results.csv"):
    df = pd.read_csv(f)
    all_dfs.append(df)

df_combined = pd.concat(all_dfs, ignore_index=True)
df_combined = df_combined.drop_duplicates(subset=['reform_name', 'year'], keep='last')

# Convert ALL to billions
value_cols = [col for col in df_combined.columns if col not in ['reform_name', 'year', 'scoring_type']]
for col in value_cols:
    df_combined[col] = (df_combined[col] / 1e9).round(2)

df_combined = df_combined.sort_values(['reform_name', 'year']).reset_index(drop=True)
df_combined.to_csv("results/static_partial/combined_static_partial_billions.csv", index=False)
```

### Docker Build Issues

If the Docker build fails, ensure:
1. The `policyengine-us` directory exists in the project root with the required PRs merged
2. You're running from the project root (not the batch directory)
3. All required files exist: `src/reforms.py`, `batch/compute_year.py`, `batch/requirements.txt`

### Container Image Issues

```bash
# Verify the container exists
gcloud container images describe gcr.io/policyengine-api/ss-calculator:latest

# If not found, rebuild and push
docker build -t gcr.io/policyengine-api/ss-calculator:latest -f batch/Dockerfile .
docker push gcr.io/policyengine-api/ss-calculator:latest
```

## Cost Estimation

- Jobs use e2-highmem-8 VMs (~$0.27/hour)
- Each year takes ~15-20 minutes to compute
- 75 years × 8 options = 600 tasks
- Total compute time: ~150-200 VM-hours
- **Estimated cost: ~$40-55 per full run (all 8 options, 75 years each)**

## Lessons Learned

1. **Don't submit too many parallel jobs** - GCP has resource limits. Submit 2-4 options at a time.

2. **Use 64GB RAM for all years** - The TOB revenue calculations need more memory than expected.

3. **20-minute timeout is optimal** - Long enough to complete, short enough to fail fast and retry.

4. **Keep raw CSV files locally** - Always keep the individual `*_results.csv` files. If the combined CSV gets corrupted, you can rebuild it.

5. **Download results incrementally** - Don't wait until all 8 options complete. Download and add to combined CSV as each job finishes.

6. **Re-authenticate periodically** - GCP tokens expire. Run `gcloud auth login` and `gcloud auth application-default login` every few hours during long sessions.

7. **Monitor actively** - Jobs can get stuck. Check progress every 10-15 minutes and kill/restart stuck jobs.

## References

- Google Cloud Batch docs: https://cloud.google.com/batch/docs
- PolicyEngine US: https://github.com/PolicyEngine/policyengine-us
- GCP Console Batch: https://console.cloud.google.com/batch?project=policyengine-api
