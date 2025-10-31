#!/usr/bin/env python3
"""
Submit reform-year parallel jobs to Google Cloud Batch.

MAXIMUM PARALLELIZATION:
- Creates one task per reform-year combination
- All tasks run simultaneously
- Fastest possible execution (~15-20 minutes for all results)

Usage:
    python submit_years_parallel.py --years 2026,2027 --scoring static --reforms option1,option2
"""

import argparse
import datetime
import os
import random
import string
from google.cloud import batch_v1

def generate_job_id(prefix="reformyear"):
    """Generate unique job ID with timestamp and random suffix."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{timestamp}-{random_suffix}"

def submit_job(years, reforms, scoring_type, bucket_name, region="us-central1"):
    """Submit a Cloud Batch job with reform-year parallelization."""

    job_id = generate_job_id()
    project_id = "policyengine-api"

    # Create all reform-year combinations
    reform_year_pairs = [(reform, year) for reform in reforms for year in years]
    num_tasks = len(reform_year_pairs)

    print("="*80)
    print("SUBMITTING FULLY PARALLELIZED JOB (ONE TASK PER REFORM-YEAR)")
    print("="*80)
    print(f"Job ID: {job_id}")
    print(f"Years: {len(years)} ({min(years)}-{max(years)})")
    print(f"Reforms: {len(reforms)} ({', '.join(reforms)})")
    print(f"Scoring: {scoring_type}")
    print(f"Total tasks: {num_tasks} (one per reform-year combination)")
    print(f"Bucket: gs://{bucket_name}/")
    print(f"Container: gcr.io/policyengine-api/ss-calculator:latest")
    print(f"Expected time: ~15-20 minutes for all tasks to complete")
    print("="*80)
    print()

    # Create batch client
    client = batch_v1.BatchServiceClient()

    # Define the task: run compute_year.py for each reform-year
    task_spec = batch_v1.TaskSpec()

    # Build arrays of reforms and years
    reforms_array = ' '.join(reform_year_pairs[i][0] for i in range(num_tasks))
    years_array = ' '.join(str(reform_year_pairs[i][1]) for i in range(num_tasks))

    script = f"""
    set -e  # Exit immediately if any command fails

    REFORMS=({reforms_array})
    YEARS=({years_array})
    REFORM=${{REFORMS[$BATCH_TASK_INDEX]}}
    YEAR=${{YEARS[$BATCH_TASK_INDEX]}}

    echo "Task $BATCH_TASK_INDEX processing reform=$REFORM year=$YEAR"
    echo "=== Starting computation at $(date) ==="

    python /app/batch/compute_year.py $YEAR {scoring_type} {bucket_name} {job_id} $REFORM

    # Only reach here if python succeeded
    echo "=== Finished at $(date) ==="
    """

    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = "gcr.io/policyengine-api/ss-calculator:latest"
    runnable.container.entrypoint = "/bin/bash"
    runnable.container.commands = ["-c", script]

    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 1  # Allow one retry per task
    task_spec.max_run_duration = "1200s"  # 20 minute timeout per reform-year

    # Resource allocation: Each task computes ONE reform only
    # Can use smaller instances since we're only computing one reform
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 4000  # 4 CPUs per task
    resources.memory_mib = 16384  # 16GB RAM should be sufficient for one reform
    task_spec.compute_resource = resources

    # Create task group
    task_group = batch_v1.TaskGroup()
    task_group.task_count = num_tasks
    # Limit parallelism to 250 to avoid throttling (HuggingFace, GCR, spot VM limits)
    task_group.parallelism = min(250, num_tasks)
    task_group.task_spec = task_spec

    # Configure allocation policy
    # Using e2-standard-4: 4 vCPU, 16GB RAM (sufficient for one reform)
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.SPOT
    instance_policy.machine_type = "e2-standard-4"  # 4 vCPU, 16GB RAM

    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instance_policy
    allocation_policy.instances = [instance_policy_or_template]

    # Service account
    service_account = batch_v1.ServiceAccount()
    service_account.email = f"{project_id}@appspot.gserviceaccount.com"
    allocation_policy.service_account = service_account

    # Logging policy
    logs_policy = batch_v1.LogsPolicy()
    logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    # Create job
    job = batch_v1.Job()
    job.task_groups = [task_group]
    job.allocation_policy = allocation_policy
    job.logs_policy = logs_policy
    job.labels = {
        "job_type": "reform_year_parallel",
        "scoring": scoring_type
    }

    # Submit job
    print("Submitting job to Cloud Batch...")
    print()

    create_request = batch_v1.CreateJobRequest()
    create_request.job = job
    create_request.job_id = job_id
    create_request.parent = f"projects/{project_id}/locations/{region}"

    response = client.create_job(create_request)

    print("="*80)
    print("✓ JOB SUBMITTED SUCCESSFULLY")
    print("="*80)
    print(f"Job ID: {job_id}")
    print(f"Status: {response.status.state.name}")
    print()
    print("Monitor progress:")
    print(f"  Command: gcloud batch jobs describe {job_id} --location={region}")
    print(f"  Console: https://console.cloud.google.com/batch/jobs/{job_id}?project={project_id}")
    print()
    print(f"Results will be saved to: gs://{bucket_name}/results/{job_id}/")
    print()
    print("="*80)

    return job_id

def main():
    parser = argparse.ArgumentParser(description="Submit fully parallelized reform-year jobs")
    parser.add_argument("--years", required=True, help="Comma-separated years (e.g., 2026,2027)")
    parser.add_argument("--reforms", required=True, help="Comma-separated reform IDs (e.g., option1,option2)")
    parser.add_argument("--scoring", required=True, choices=["static", "dynamic"], help="Scoring type")
    parser.add_argument("--bucket", default="crfb-ss-analysis-results", help="Cloud Storage bucket")
    parser.add_argument("--region", default="us-central1", help="GCP region (e.g., us-central1, us-east1)")

    args = parser.parse_args()

    years = [int(y.strip()) for y in args.years.split(",")]
    reforms = [r.strip() for r in args.reforms.split(",")]

    submit_job(years, reforms, args.scoring, args.bucket, args.region)

if __name__ == "__main__":
    main()
