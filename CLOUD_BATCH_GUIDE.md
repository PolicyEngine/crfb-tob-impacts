# Google Cloud Batch Guide

## How It Works

**Architecture:**
- Runs 75 parallel tasks (one per year, 2026-2100) on Google Cloud VMs
- Each VM executes `batch/compute_year.py` with PolicyEngine microsimulation
- Results saved to Cloud Storage as individual CSVs
- Combined into final results using `combine_results.sh`

**Automatic VM Sizing:**
- **Years 2026-2027:** `e2-highmem-8` (64GB RAM) - larger datasets require more memory
- **Years 2028-2100:** `e2-highmem-4` (32GB RAM) - standard configuration
- System automatically splits into 2 separate jobs when 2026-2027 are included
- Saves ~97% of extra costs by using expensive VMs only for 2/75 years

**Cost:** ~$2-3 per job (~$0.03 per year analyzed)

## Complete Workflow

### 1. Submit Job (Automatic Splitting)

```bash
# Submit for all 75 years (2026-2100)
PYTHONPATH=src python3 batch/submit_years.py \
  --years $(seq -s, 2026 2100) \
  --reforms option5 \
  --scoring static

# System automatically creates 2 jobs:
# - Job 1: Years 2026-2027 with 64GB VMs
# - Job 2: Years 2028-2100 with 32GB VMs
#
# Output shows both job IDs and monitoring commands
```

### 2. Monitor Progress

```bash
# Use commands from submit output, e.g.:
./monitor_job.sh years-20251101-123456-abc123 option5 static &
./monitor_job.sh years-20251101-123457-def456 option5 static &

# Or check status directly:
gcloud batch jobs describe JOB_ID --location=us-central1
```

### 3. Combine Results

```bash
# After jobs complete, merge all CSVs into 2 final files
./combine_results.sh option5 JOB_ID_1 JOB_ID_2

# Output: option5_static_results.csv (all 75 years, sorted)
```

### 4. Repeat for Dynamic Scoring

```bash
# Same workflow with --scoring dynamic
PYTHONPATH=src python3 batch/submit_years.py \
  --years $(seq -s, 2026 2100) \
  --reforms option5 \
  --scoring dynamic

# Monitor and combine same way
./combine_results.sh option5 JOB_ID_3 JOB_ID_4
# Output: option5_dynamic_results.csv
```

## Key Files

| File | Purpose |
|------|---------|
| `batch/submit_years.py` | Submits jobs with automatic VM sizing |
| `batch/compute_year.py` | Runs PolicyEngine simulation on each VM |
| `src/reforms.py` | Defines reform parameters |
| `combine_results.sh` | Merges individual CSVs into final output |
| `monitor_job.sh` | Tracks job progress |

## Storage Locations

- **Cloud Storage:** `gs://crfb-ss-analysis-results/results/<JOB_ID>/`
- **Local Results:** `{reform}_{scoring}_results.csv`

## Common Commands

```bash
# Check job status
gcloud batch jobs describe JOB_ID --location=us-central1

# List running jobs
gcloud batch jobs list --location=us-central1 --filter="state:RUNNING"

# Delete completed job (results already saved)
gcloud batch jobs delete JOB_ID --location=us-central1 --quiet

# Download CSVs manually
gsutil -m cp "gs://crfb-ss-analysis-results/results/JOB_ID/*.csv" ./temp/
```

## Troubleshooting

**Job shows FAILED but has results:**
- Check actual file count: `gsutil ls gs://.../results/JOB_ID/ | wc -l`
- Cloud Batch marks job failed if ANY task fails (even 2/75)
- Process results if 73+ years completed

**Tasks stuck in PENDING:**
- Check quota: `gcloud compute project-info describe | grep -A2 "CPUS"`
- Each job uses 300 CPUs (can run ~10 jobs simultaneously with 3,000 limit)
- Delete completed jobs to free resources
