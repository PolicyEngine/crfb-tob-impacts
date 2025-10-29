#!/usr/bin/env python3
"""
Phase 1 Submission Script: Submit baseline calculation jobs to Google Cloud Batch.

This script creates Cloud Batch jobs to compute baselines for specified years in parallel.

Usage:
    python submit_baselines.py [--years YEARS] [--project PROJECT] [--region REGION]

Examples:
    # Test with 2 years
    python submit_baselines.py --years 2026,2027

    # Full run with all 75 years
    python submit_baselines.py --years 2026-2100

    # Specify custom project and region
    python submit_baselines.py --years 2026-2100 --project my-project --region us-east1
"""

import argparse
import uuid
from datetime import datetime
from google.cloud import batch_v1


# Configuration
DEFAULT_PROJECT = "policyengine-api"
DEFAULT_REGION = "us-central1"
DEFAULT_BUCKET = "crfb-ss-analysis-results"
CONTAINER_IMAGE = f"gcr.io/{DEFAULT_PROJECT}/ss-calculator:latest"


def parse_years(years_str):
    """
    Parse years string into list of years.

    Examples:
        "2026,2027,2028" -> [2026, 2027, 2028]
        "2026-2030" -> [2026, 2027, 2028, 2029, 2030]
    """
    if '-' in years_str:
        # Range format: "2026-2100"
        start, end = years_str.split('-')
        return list(range(int(start), int(end) + 1))
    else:
        # Comma-separated: "2026,2027,2028"
        return [int(y.strip()) for y in years_str.split(',')]


def create_baseline_job(project_id, region, years, bucket_name):
    """Create and submit Cloud Batch job for baseline calculations."""

    batch_client = batch_v1.BatchServiceClient()

    # Generate unique job ID
    job_id = f"baselines-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    print(f"\n{'=' * 80}")
    print(f"SUBMITTING BASELINE JOB")
    print(f"{'=' * 80}")
    print(f"Job ID: {job_id}")
    print(f"Years: {len(years)} years ({min(years)}-{max(years)})")
    print(f"Bucket: gs://{bucket_name}/")
    print(f"Container: {CONTAINER_IMAGE}")
    print(f"Project: {project_id}")
    print(f"Region: {region}")
    print(f"{'=' * 80}\n")

    # Create task group with one task per year
    task_group = batch_v1.TaskGroup()
    task_group.task_count = len(years)
    task_group.parallelism = len(years)  # Run all in parallel

    # Create runnable (container to execute)
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = CONTAINER_IMAGE
    runnable.container.entrypoint = "/bin/bash"

    # Build command that runs the appropriate year based on task index
    # Cloud Batch provides BATCH_TASK_INDEX environment variable
    years_str = ' '.join(str(y) for y in years)
    command = f"""
    YEARS=({years_str})
    YEAR=${{YEARS[$BATCH_TASK_INDEX]}}
    echo "Task $BATCH_TASK_INDEX processing year $YEAR"
    python /app/compute_baseline.py $YEAR {bucket_name}
    """
    runnable.container.commands = ["-c", command]

    # Configure task spec
    task_spec = batch_v1.TaskSpec()
    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 2
    task_spec.max_run_duration = "3600s"  # 1 hour timeout per task

    # Resource allocation (1 CPU, 4GB RAM per task)
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 1000  # 1 CPU
    resources.memory_mib = 4096  # 4GB RAM
    task_spec.compute_resource = resources

    task_group.task_spec = task_spec

    # Configure allocation policy (use spot instances for cost savings)
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.SPOT
    instance_policy.machine_type = "e2-standard-2"

    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instance_policy
    allocation_policy.instances = [instance_policy_or_template]

    # Service account configuration
    service_account = batch_v1.ServiceAccount()
    service_account.email = f"{project_id}@appspot.gserviceaccount.com"
    allocation_policy.service_account = service_account

    # Create job
    job = batch_v1.Job()
    job.task_groups = [task_group]
    job.allocation_policy = allocation_policy
    job.labels = {
        "job_type": "baselines",
        "phase": "1"
    }

    # Log policy
    job.logs_policy = batch_v1.LogsPolicy()
    job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    # Submit job
    create_request = batch_v1.CreateJobRequest(
        parent=f"projects/{project_id}/locations/{region}",
        job_id=job_id,
        job=job,
    )

    print(f"Submitting job to Cloud Batch...")
    response = batch_client.create_job(create_request)

    print(f"\n{'=' * 80}")
    print(f"✓ JOB SUBMITTED SUCCESSFULLY")
    print(f"{'=' * 80}")
    print(f"Job ID: {job_id}")
    print(f"Status: {response.status.state.name}")
    print(f"\nMonitor progress:")
    print(f"  Command: gcloud batch jobs describe {job_id} --location={region}")
    print(f"  Console: https://console.cloud.google.com/batch/jobs/{job_id}?project={project_id}")
    print(f"\nExpected completion: ~20-25 minutes")
    print(f"Results will be saved to: gs://{bucket_name}/baselines/")
    print(f"{'=' * 80}\n")

    return job_id


def main():
    parser = argparse.ArgumentParser(
        description="Submit baseline calculation jobs to Google Cloud Batch"
    )
    parser.add_argument(
        '--years',
        type=str,
        default='2026-2100',
        help='Years to compute (e.g., "2026,2027" or "2026-2100")'
    )
    parser.add_argument(
        '--project',
        type=str,
        default=DEFAULT_PROJECT,
        help=f'Google Cloud project ID (default: {DEFAULT_PROJECT})'
    )
    parser.add_argument(
        '--region',
        type=str,
        default=DEFAULT_REGION,
        help=f'Google Cloud region (default: {DEFAULT_REGION})'
    )
    parser.add_argument(
        '--bucket',
        type=str,
        default=DEFAULT_BUCKET,
        help=f'Cloud Storage bucket name (default: {DEFAULT_BUCKET})'
    )

    args = parser.parse_args()

    # Parse years
    years = parse_years(args.years)

    if not years:
        print("Error: No years specified")
        return 1

    # Submit job
    try:
        job_id = create_baseline_job(
            args.project,
            args.region,
            years,
            args.bucket
        )
        return 0
    except Exception as e:
        print(f"\n{'=' * 80}")
        print(f"✗ ERROR SUBMITTING JOB")
        print(f"{'=' * 80}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
