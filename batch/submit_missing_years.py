#!/usr/bin/env python3
"""
Submit a Google Cloud Batch job to re-run specific missing years.

Usage:
    python submit_missing_years.py SCORING_TYPE BUCKET_NAME YEARS...

Arguments:
    SCORING_TYPE: 'static' or 'dynamic'
    BUCKET_NAME: Cloud Storage bucket name
    YEARS: Space-separated list of years to compute (e.g., '2026 2027')
"""

import sys
import json
from datetime import datetime
from google.cloud import batch_v1

def create_batch_job(project_id, region, job_name, years, scoring_type, bucket_name):
    """Create a Cloud Batch job to compute specific years."""

    client = batch_v1.BatchServiceClient()

    # Container image
    image = "gcr.io/policyengine-api/ss-calculator:latest"

    # Create tasks for each year
    tasks = []
    for i, year in enumerate(years):
        task = batch_v1.TaskSpec()

        # Command: python compute_year.py YEAR SCORING_TYPE BUCKET_NAME JOB_ID REFORMS...
        # Run option1 only (matching the original 75-year test)
        task.runnables = [
            batch_v1.Runnable(
                container=batch_v1.Runnable.Container(
                    image_uri=image,
                    commands=[
                        "python",
                        "/app/batch/compute_year.py",
                        str(year),
                        scoring_type,
                        bucket_name,
                        job_name,
                        "option1"  # Only option1 to match original test
                    ]
                )
            )
        ]

        task.max_run_duration = "7200s"  # 2 hour timeout per year

        tasks.append(task)

    # Task group with all years
    task_group = batch_v1.TaskGroup()
    task_group.task_count = len(years)
    task_group.task_spec = tasks[0]  # Template (will be overridden by task array)
    task_group.parallelism = len(years)  # Run all years in parallel

    # Resources: Match the original 75-year test configuration
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 4000  # 4 vCPUs
    resources.memory_mib = 16384  # 16 GB RAM (matching successful year 2028 test)

    task_group.task_spec.compute_resource = resources

    # Allocation policy - use standard VMs (not Spot)
    instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instances.install_gpu_drivers = False
    instances.policy = batch_v1.AllocationPolicy.InstancePolicy(
        machine_type="n1-standard-4"  # 4 vCPUs, 15 GB RAM
    )

    allocation_policy = batch_v1.AllocationPolicy()
    allocation_policy.instances = [instances]

    # Job configuration
    job = batch_v1.Job()
    job.task_groups = [task_group]
    job.allocation_policy = allocation_policy
    job.logs_policy = batch_v1.LogsPolicy()
    job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    # Create the job
    create_request = batch_v1.CreateJobRequest()
    create_request.job = job
    create_request.job_id = job_name
    create_request.parent = f"projects/{project_id}/locations/{region}"

    return client.create_job(create_request)


def main():
    if len(sys.argv) < 4:
        print("Usage: python submit_missing_years.py SCORING_TYPE BUCKET_NAME YEARS...")
        print("Example: python submit_missing_years.py dynamic crfb-ss-analysis-results 2026 2027")
        sys.exit(1)

    scoring_type = sys.argv[1]
    bucket_name = sys.argv[2]
    years = [int(y) for y in sys.argv[3:]]

    # Configuration
    project_id = "policyengine-api"
    region = "us-central1"

    # Generate unique job ID
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"missing-years-{timestamp}-{'-'.join(map(str, years))}"

    print(f"Submitting Cloud Batch job to compute missing years...")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Scoring type: {scoring_type}")
    print(f"Job ID: {job_name}")
    print(f"Bucket: {bucket_name}")
    print()

    job = create_batch_job(project_id, region, job_name, years, scoring_type, bucket_name)

    print(f"✓ Job submitted successfully!")
    print(f"Job name: {job.name}")
    print(f"Tasks: {len(years)} (one per year)")
    print()
    print(f"Monitor with:")
    print(f"  gcloud batch jobs describe {job_name} --location={region}")
    print(f"  gcloud batch tasks list --location={region} --job={job_name}")
    print()
    print(f"Results will be saved to:")
    print(f"  gs://{bucket_name}/results/{job_name}/")


if __name__ == "__main__":
    main()
