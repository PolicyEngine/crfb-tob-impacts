#!/usr/bin/env python3
"""
Phase 2 Submission Script: Submit reform calculation jobs to Google Cloud Batch.

This script creates Cloud Batch jobs to compute reform impacts for all combinations
of reforms, years, and scoring types (static/dynamic) in parallel.

Usage:
    python submit_reforms.py [--reforms REFORMS] [--years YEARS] [--scoring SCORING]
                             [--workers WORKERS] [--project PROJECT] [--region REGION]

Examples:
    # Test with 2 reforms, 2 years, both scoring types (8 tasks)
    python submit_reforms.py --reforms option1,option2 --years 2026,2027

    # Full run with all reforms and years (1,200 tasks)
    python submit_reforms.py --years 2026-2100

    # Only dynamic scoring
    python submit_reforms.py --scoring dynamic

    # Use more workers for faster completion
    python submit_reforms.py --years 2026-2100 --workers 400
"""

import argparse
import uuid
import sys
from datetime import datetime
from google.cloud import batch_v1

# Add parent directory to path to import reforms
sys.path.insert(0, '../src')
from reforms import REFORMS


# Configuration
DEFAULT_PROJECT = "policyengine-api"
DEFAULT_REGION = "us-central1"
DEFAULT_BUCKET = "crfb-ss-analysis-results"
CONTAINER_IMAGE = f"gcr.io/{DEFAULT_PROJECT}/ss-calculator:latest"


def parse_years(years_str):
    """Parse years string into list of years."""
    if '-' in years_str:
        start, end = years_str.split('-')
        return list(range(int(start), int(end) + 1))
    else:
        return [int(y.strip()) for y in years_str.split(',')]


def parse_reforms(reforms_str):
    """Parse reforms string into list of reform IDs."""
    if reforms_str.lower() == 'all':
        return list(REFORMS.keys())
    else:
        return [r.strip() for r in reforms_str.split(',')]


def parse_scoring(scoring_str):
    """Parse scoring string into list of scoring types."""
    if scoring_str.lower() == 'all':
        return ['static', 'dynamic']
    elif scoring_str.lower() in ['static', 'dynamic']:
        return [scoring_str.lower()]
    else:
        raise ValueError(f"Invalid scoring type: {scoring_str}. Must be 'static', 'dynamic', or 'all'")


def create_reform_job(project_id, region, reforms, years, scoring_types, workers, bucket_name):
    """Create and submit Cloud Batch job for reform calculations."""

    batch_client = batch_v1.BatchServiceClient()

    # Generate unique job ID
    job_id = f"reforms-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Generate all task combinations
    tasks = []
    for reform_id in reforms:
        if reform_id not in REFORMS:
            print(f"Warning: Unknown reform '{reform_id}', skipping...")
            continue
        for year in years:
            for scoring in scoring_types:
                tasks.append((reform_id, year, scoring))

    num_tasks = len(tasks)

    print(f"\n{'=' * 80}")
    print(f"SUBMITTING REFORM JOB")
    print(f"{'=' * 80}")
    print(f"Job ID: {job_id}")
    print(f"Reforms: {len(reforms)} ({', '.join(reforms)})")
    print(f"Years: {len(years)} ({min(years)}-{max(years)})")
    print(f"Scoring: {', '.join(scoring_types)}")
    print(f"Total tasks: {num_tasks}")
    print(f"Parallel workers: {workers}")
    print(f"Estimated time: {(num_tasks * 20 / workers / 60):.1f} hours")
    print(f"Bucket: gs://{bucket_name}/")
    print(f"Container: {CONTAINER_IMAGE}")
    print(f"{'=' * 80}\n")

    # Create task group
    task_group = batch_v1.TaskGroup()
    task_group.task_count = num_tasks
    task_group.parallelism = min(workers, num_tasks)  # Run up to 'workers' in parallel

    # Create runnable
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = CONTAINER_IMAGE
    runnable.container.entrypoint = "/bin/bash"

    # Build command that maps task index to specific reform/year/scoring combination
    # Format tasks as: "reform_id:year:scoring"
    tasks_str = ' '.join([f"{r}:{y}:{s}" for r, y, s in tasks])
    command = f"""
    TASKS=({tasks_str})
    TASK=${{TASKS[$BATCH_TASK_INDEX]}}
    IFS=':' read -r REFORM_ID YEAR SCORING <<< "$TASK"
    echo "Task $BATCH_TASK_INDEX processing: $REFORM_ID / $YEAR / $SCORING"
    python /app/compute_reform.py $REFORM_ID $YEAR $SCORING {bucket_name} {job_id}
    """
    runnable.container.commands = ["-c", command]

    # Configure task spec
    task_spec = batch_v1.TaskSpec()
    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 2
    task_spec.max_run_duration = "7200s"  # 2 hour timeout per task (conservative)

    # Resource allocation (2 CPUs, 8GB RAM per task)
    # Now that dataset caching is removed, memory should match local (0.9GB observed)
    # Using conservative 8GB to allow for some overhead during HuggingFace dataset downloads
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 2000  # 2 CPUs
    resources.memory_mib = 8192  # 8GB RAM (conservative - local only uses ~1GB)
    task_spec.compute_resource = resources

    task_group.task_spec = task_spec

    # Configure allocation policy (use regular instances for reliability)
    # Note: Spot instances were being preempted, causing task failures
    # Using e2-standard-4 (4 vCPU, 16GB RAM) - sufficient now without dataset caching
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.STANDARD
    instance_policy.machine_type = "e2-standard-4"  # 4 vCPU, 16GB RAM

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
        "job_type": "reforms",
        "phase": "2"
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
    print(f"\nExpected completion: ~{(num_tasks * 20 / workers / 60):.1f} hours")
    print(f"Results will be saved to: gs://{bucket_name}/results/{job_id}/")
    print(f"\nWhen complete, download results with:")
    print(f"  python download_results.py --job-id {job_id}")
    print(f"{'=' * 80}\n")

    return job_id


def main():
    parser = argparse.ArgumentParser(
        description="Submit reform calculation jobs to Google Cloud Batch"
    )
    parser.add_argument(
        '--reforms',
        type=str,
        default='all',
        help='Reforms to compute (e.g., "option1,option2" or "all")'
    )
    parser.add_argument(
        '--years',
        type=str,
        default='2026-2100',
        help='Years to compute (e.g., "2026,2027" or "2026-2100")'
    )
    parser.add_argument(
        '--scoring',
        type=str,
        default='all',
        help='Scoring types: "static", "dynamic", or "all" (default: all)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=200,
        help='Number of parallel workers (default: 200)'
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

    # Parse arguments
    try:
        reforms = parse_reforms(args.reforms)
        years = parse_years(args.years)
        scoring_types = parse_scoring(args.scoring)
    except Exception as e:
        print(f"Error parsing arguments: {e}")
        return 1

    if not reforms or not years or not scoring_types:
        print("Error: Must specify at least one reform, year, and scoring type")
        return 1

    # Submit job
    try:
        job_id = create_reform_job(
            args.project,
            args.region,
            reforms,
            years,
            scoring_types,
            args.workers,
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
