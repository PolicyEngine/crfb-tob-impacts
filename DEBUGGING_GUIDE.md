# PolicyEngine Cloud Batch Debugging Guide

## Architecture Overview

### Correct Architecture (Year-Based Parallelization)
```
Year 2026 Task:
  ├─ Download dataset (once)          ~0s
  ├─ Calculate baseline (once)        ~14s
  └─ Run 8 reforms sequentially       ~26min
      ├─ option1                      ~3.3min
      ├─ option2                      ~3.3min
      ├─ ... (6 more)
      └─ option8                      ~3.3min

Year 2027 Task: (runs in parallel with 2026)
  ├─ Download dataset (once)          ~0s
  ├─ Calculate baseline (once)        ~14s
  └─ Run 8 reforms sequentially       ~26min
```

**Total wall time**: ~26 minutes for 2 years × 8 reforms = 16 total simulations

### Incorrect Architecture (Reform-Based - DO NOT USE)
```
Task 0: Download 2026 → Baseline 2026 → Reform option1
Task 1: Download 2026 → Baseline 2026 → Reform option2  ❌ Duplicate work!
Task 2: Download 2026 → Baseline 2026 → Reform option3  ❌ Duplicate work!
... (massive duplication)
```

## Memory Requirements

### Local Testing Results
```bash
# Test command:
PYTHONPATH=src /usr/bin/time -l python3 batch/compute_year.py 2026 static test-bucket test-job option1 option2

# Results for 2 reforms:
Peak memory: 4.76GB
Total time: 431s (~7.2 minutes)
Per reform: ~3.3 minutes
```

### Cloud Requirements
- **Per year-task**: 16GB RAM (tested requirement for 8 reforms + overhead)
- **Machine type**: e2-highmem-2 (2 vCPU, 16GB RAM)
- **Why 16GB?**: 4.76GB for 2 reforms → ~16GB for 8 reforms + OS/container overhead

## How to Debug Cloud Jobs

### 1. Submit a Test Job
```bash
# Test with 2 years × 4 reforms
./test_year_based.sh

# Or manually:
python3 batch/submit_years.py \
  --years 2026,2027 \
  --reforms option1,option2,option3,option4 \
  --scoring static \
  --bucket crfb-ss-analysis-results
```

### 2. Monitor Job Status
```bash
# Check job state
gcloud batch jobs describe JOB_ID --location=us-central1 --format="yaml(status)"

# List all jobs
gcloud batch jobs list --location=us-central1

# Check individual task status
gcloud batch tasks list --location=us-central1 --job=JOB_ID \
  --format="table(name.basename(),status.state,status.statusEvents[-1].description:wrap)"
```

### 3. View Logs in Real-Time
```bash
# Get all logs for a job
gcloud logging read "resource.labels.job_uid:\"JOB_ID\"" \
  --freshness=30m \
  --format='value(textPayload)' \
  | grep -E '(YEAR-BASED|baseline|Reform revenue|Impact|COMPLETE|ERROR|Killed)'

# Monitor memory usage
gcloud logging read "resource.labels.job_uid:\"JOB_ID\"" \
  --freshness=30m \
  --format='value(textPayload)' \
  | grep -E '(Memory|OOM|137)'
```

### 4. Check for Common Errors

#### Error: Exit Code 137 (OOM)
```
Task state is updated from RUNNING to FAILED with exit code 137
```

**Cause**: Out of memory

**Fix**:
1. Check actual memory usage in logs (`free -h` output)
2. Increase memory allocation in `submit_years.py`:
   ```python
   resources.memory_mib = 20480  # Increase to 20GB if needed
   instance_policy.machine_type = "e2-highmem-4"  # 4 vCPU, 32GB RAM
   ```

#### Error: Exit Code 50002 (VM Communication Lost)
```
Batch no longer receives VM updates with exit code 50002
```

**Cause**: VM was preempted or lost connection

**Fix**: Job will automatically retry on a new VM

#### Error: Variable Not Found
```
Variable gov_revenue does not exist
```

**Fix**: Use correct PolicyEngine variable names:
- ✅ `income_tax` (for revenue calculations)
- ✅ `household_net_income` (for household impacts)
- ❌ `gov_revenue` (doesn't exist)

### 5. Download and Inspect Results
```bash
# List results
gsutil ls gs://crfb-ss-analysis-results/results/JOB_ID/

# Download results
gsutil cp gs://crfb-ss-analysis-results/results/JOB_ID/*.csv .

# View results
cat 2026_static_results.csv
```

## Performance Expectations

### For 2 Years × 8 Reforms (Static Scoring)

**Expected timeline:**
```
T+0:00   Job submitted
T+0:05   VMs provisioned
T+0:06   Tasks start executing
T+0:06   Dataset downloads complete (instant)
T+0:20   Baselines calculated (~14s each)
T+26:00  All reforms complete
T+26:05  Results saved to Cloud Storage
```

**If it takes longer:**
- Check logs for dataset download delays (should be <1 min)
- Check for memory pressure causing slowdowns
- Verify reforms are running, not retrying

### For Full Run (75 Years × 8 Reforms × 2 Scoring Types)

**Tasks**: 75 years × 2 scoring types = 150 parallel tasks

**Resources needed**:
- 150 × 16GB = 2,400GB total RAM across cluster
- Batch will schedule based on quota

**Expected time**:
- Per task: ~26 minutes (8 reforms)
- Wall time: ~26-30 minutes (if sufficient quota for parallelization)
- Sequential: ~65 hours (if quota-limited to serial execution)

## Optimization Tips

### 1. Use HuggingFace Datasets
```python
# ✅ Fast: Pre-computed datasets
dataset_name = "hf://policyengine/test/2026.h5"

# ❌ Slow: Generate dataset at runtime
dataset_name = "enhanced_cps_2024"  # Takes 10+ minutes!
```

### 2. Batch Similar Reforms
Group reforms that modify similar parameters to potentially share calculations.

### 3. Monitor Costs
```bash
# Check current costs
gcloud billing accounts list
gcloud billing budgets list --billing-account=ACCOUNT_ID
```

**Estimated costs** (us-central1 pricing):
- e2-highmem-2: ~$0.13/hour
- 150 tasks × 0.5 hours = 75 machine-hours
- Total: ~$10 per full run

## Troubleshooting Checklist

- [ ] Docker image built successfully?
- [ ] Image pushed to gcr.io?
- [ ] Job submitted without errors?
- [ ] VMs provisioning (status: SCHEDULED → RUNNING)?
- [ ] Tasks executing (not stuck in PENDING)?
- [ ] No OOM errors (exit code 137)?
- [ ] Logs showing progress (baseline calculated, reforms running)?
- [ ] Results appearing in Cloud Storage?
- [ ] Results have correct values (non-zero impacts)?

## Getting Help

If stuck:
1. Capture full job details: `gcloud batch jobs describe JOB_ID --location=us-central1`
2. Get recent logs: `gcloud logging read "resource.labels.job_uid:\"JOB_ID\"" --freshness=30m`
3. Check task states: `gcloud batch tasks list --job=JOB_ID --location=us-central1`
4. Review this guide for common issues
5. Compare timing/memory to local test results
