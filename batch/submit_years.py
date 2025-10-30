#!/usr/bin/env python3
"""
Submit year-based parallel jobs to Google Cloud Batch.

This uses the CORRECT architecture:
- Parallelize by YEAR, not by reform-year combination
- Each year-worker downloads dataset once, calculates baseline once, runs all reforms
- Much more efficient and faster!

Usage:
    python submit_years.py --years 2026,2027 --scoring static --reforms option1,option2,option3,option4
"""

import argparse
import datetime
import os
import random
import string
from google.cloud import batch_v1

def generate_job_id(prefix="years"):
    """Generate unique job ID with timestamp and random suffix."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{timestamp}-{random_suffix}"

def submit_job(years, reforms, scoring_type, bucket_name):
    """Submit a Cloud Batch job with year-based parallelization."""

    job_id = generate_job_id()
    project_id = "policyengine-api"
    region = "us-central1"

    # Job configuration
    num_tasks = len(years)

    print("="*80)
    print("SUBMITTING YEAR-BASED JOB")
    print("="*80)
    print(f"Job ID: {job_id}")
    print(f"Years: {len(years)} ({', '.join(map(str, years))})")
    print(f"Reforms per year: {len(reforms)} ({', '.join(reforms)})")
    print(f"Scoring: {scoring_type}")
    print(f"Total tasks: {num_tasks} (one per year)")
    print(f"Total reforms to compute: {num_tasks * len(reforms)}")
    print(f"Bucket: gs://{bucket_name}/")
    print(f"Container: gcr.io/policyengine-api/ss-calculator:latest")
    print("="*80)
    print()

    # Create batch client
    client = batch_v1.BatchServiceClient()

    # Define the task: run compute_year.py for each year
    task_spec = batch_v1.TaskSpec()

    # Build command that maps BATCH_TASK_INDEX to year
    years_array = ' '.join(map(str, years))
    reforms_args = ' '.join(reforms)

    script = f"""
    YEARS=({years_array})
    YEAR=${{YEARS[$BATCH_TASK_INDEX]}}
    echo "Task $BATCH_TASK_INDEX processing year $YEAR with {len(reforms)} reforms"

    # Add detailed timing and memory monitoring
    echo "=== Starting computation at $(date) ==="
    echo "=== Memory before start ==="
    free -h

    python /app/batch/compute_year.py $YEAR {scoring_type} {bucket_name} {job_id} {reforms_args}

    echo "=== Memory after completion ==="
    free -h
    echo "=== Finished at $(date) ==="
    """

    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = "gcr.io/policyengine-api/ss-calculator:latest"
    runnable.container.entrypoint = "/bin/bash"
    runnable.container.commands = ["-c", script]

    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 1  # Allow one retry per task
    task_spec.max_run_duration = "3600s"  # 1 hour timeout per year

    # Resource allocation based on local testing:
    # Local test: 2 reforms used 4.76GB peak memory
    # For 8 reforms: need ~16GB to be safe (includes OS/container overhead)
    # Using 2 CPUs to match e2-highmem-2 machine type (2 vCPU, 16GB RAM)
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 2000  # 2 CPUs per task (matches e2-highmem-2)
    resources.memory_mib = 16384  # 16GB RAM per task (tested requirement)
    task_spec.compute_resource = resources

    # Create task group
    task_group = batch_v1.TaskGroup()
    task_group.task_count = num_tasks
    task_group.parallelism = num_tasks  # Run all years in parallel
    task_group.task_spec = task_spec

    # Configure allocation policy
    # Using e2-highmem-2: 2 vCPU, 16GB RAM (sufficient for our 16GB requirement)
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.STANDARD
    instance_policy.machine_type = "e2-highmem-2"  # 2 vCPU, 16GB RAM

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
        "job_type": "year_based",
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
    print("When complete, check results:")
    print(f"  gsutil ls gs://{bucket_name}/results/{job_id}/")
    print("="*80)

    return job_id

def main():
    parser = argparse.ArgumentParser(description="Submit year-based parallel jobs")
    parser.add_argument("--years", required=True, help="Comma-separated years (e.g., 2026,2027)")
    parser.add_argument("--reforms", required=True, help="Comma-separated reform IDs (e.g., option1,option2,option3,option4)")
    parser.add_argument("--scoring", required=True, choices=["static", "dynamic"], help="Scoring type")
    parser.add_argument("--bucket", default="crfb-ss-analysis-results", help="Cloud Storage bucket")

    args = parser.parse_args()

    years = [int(y.strip()) for y in args.years.split(",")]
    reforms = [r.strip() for r in args.reforms.split(",")]

    submit_job(years, reforms, args.scoring, args.bucket)

if __name__ == "__main__":
    main()
