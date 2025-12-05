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

def submit_single_job(years, reforms, scoring_type, bucket_name, machine_type, memory_mib, cpu_milli, memory_label, job_id=None):
    """Submit a single Cloud Batch job with specified VM configuration."""

    if job_id is None:
        job_id = generate_job_id()

    project_id = "policyengine-api"
    region = "us-central1"

    # Job configuration
    num_tasks = len(years)

    print("="*80)
    print("SUBMITTING YEAR-BASED JOB")
    print("="*80)
    print(f"Job ID: {job_id}")
    print(f"Years: {len(years)} ({min(years)}-{max(years) if len(years) > 1 else min(years)})")
    print(f"Machine: {machine_type} ({memory_label} RAM)")
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
    set -e  # Exit immediately if any command fails

    YEARS=({years_array})
    YEAR=${{YEARS[$BATCH_TASK_INDEX]}}
    echo "Task $BATCH_TASK_INDEX processing year $YEAR with {len(reforms)} reforms"
    echo "=== Starting computation at $(date) ==="

    python /app/batch/compute_year.py $YEAR {scoring_type} {bucket_name} {job_id} {reforms_args}

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
    task_spec.max_run_duration = "1200s"  # 20 min timeout per year

    # Resource allocation - adaptive based on years
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = cpu_milli
    resources.memory_mib = memory_mib
    task_spec.compute_resource = resources

    # Create task group
    task_group = batch_v1.TaskGroup()
    task_group.task_count = num_tasks
    task_group.parallelism = num_tasks  # Run all years in parallel
    task_group.task_spec = task_spec

    # Configure allocation policy
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.STANDARD
    instance_policy.machine_type = machine_type

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

def submit_job(years, reforms, scoring_type, bucket_name):
    """
    Submit Cloud Batch jobs with automatic VM sizing.

    Automatically splits into two jobs if 2026/2027 are included:
    - Job 1: Years 2026-2027 with e2-highmem-8 (64GB RAM)
    - Job 2: Other years with e2-highmem-4 (32GB RAM)

    This saves ~97% of the extra cost vs using 64GB for all years.
    """

    # Split years by memory requirements
    high_memory_years = sorted([y for y in years if y in [2026, 2027]])
    standard_memory_years = sorted([y for y in years if y not in [2026, 2027]])

    job_ids = []

    # Submit high-memory job if needed (2026-2027)
    if high_memory_years:
        print("\n" + "="*80)
        print("COST OPTIMIZATION: Submitting separate job for high-memory years (2026-2027)")
        print("="*80)
        print(f"Years requiring 64GB RAM: {', '.join(map(str, high_memory_years))}")
        print("="*80 + "\n")

        job_id = submit_single_job(
            years=high_memory_years,
            reforms=reforms,
            scoring_type=scoring_type,
            bucket_name=bucket_name,
            machine_type="e2-highmem-8",  # 8 vCPU, 64GB RAM
            memory_mib=65536,  # 64GB
            cpu_milli=8000,    # 8 CPUs
            memory_label="64GB"
        )
        job_ids.append((job_id, high_memory_years))
        print()

    # Submit standard-memory job if needed (all other years)
    # NOTE: Using 64GB for all years due to TOB variable memory requirements
    if standard_memory_years:
        if high_memory_years:
            print("\n" + "="*80)
            print("Submitting separate job for remaining years (2028-2100)")
            print("="*80)
            print(f"Years using 64GB RAM: {min(standard_memory_years)}-{max(standard_memory_years)}")
            print("="*80 + "\n")

        job_id = submit_single_job(
            years=standard_memory_years,
            reforms=reforms,
            scoring_type=scoring_type,
            bucket_name=bucket_name,
            machine_type="e2-highmem-8",  # 8 vCPU, 64GB RAM (increased for TOB variables)
            memory_mib=65536,  # 64GB
            cpu_milli=8000,    # 8 CPUs
            memory_label="64GB"
        )
        job_ids.append((job_id, standard_memory_years))
        print()

    # Print summary if multiple jobs
    if len(job_ids) > 1:
        print("\n" + "="*80)
        print("✓ SUBMITTED 2 JOBS (COST-OPTIMIZED)")
        print("="*80)
        for i, (job_id, job_years) in enumerate(job_ids, 1):
            year_range = f"{min(job_years)}-{max(job_years)}" if len(job_years) > 1 else str(job_years[0])
            print(f"Job {i}: {job_id}")
            print(f"  Years: {year_range} ({len(job_years)} years)")
        print()
        print("Monitor both jobs:")
        for job_id, job_years in job_ids:
            print(f"  ./monitor_job.sh {job_id} {reforms[0]} {scoring_type}")
        print("="*80 + "\n")

    return job_ids[0][0] if len(job_ids) == 1 else [jid for jid, _ in job_ids]

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
