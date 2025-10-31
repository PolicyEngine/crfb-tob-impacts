#!/usr/bin/env python3
"""
Test script to run a SINGLE reform-year task for debugging.
This helps us see the actual error without wasting money on 600 failed tasks.
"""

import sys
from google.cloud import batch_v1
from datetime import datetime

def test_single_task(year, reform, scoring_type):
    """Submit a single-task job for debugging."""

    project_id = "policyengine-api"
    region = "us-central1"
    bucket_name = "crfb-ss-analysis-results"

    job_id = f"test-{reform}-{year}-{scoring_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print("=" * 80)
    print("SINGLE TASK DEBUG TEST")
    print("=" * 80)
    print(f"Job ID: {job_id}")
    print(f"Reform: {reform}")
    print(f"Year: {year}")
    print(f"Scoring: {scoring_type}")
    print(f"Region: {region}")
    print("=" * 80)
    print()

    # Create Batch client
    client = batch_v1.BatchServiceClient()

    # Define the container
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = "gcr.io/policyengine-api/ss-calculator:latest"
    runnable.container.entrypoint = "/bin/bash"
    runnable.container.commands = [
        "-c",
        f"""
        set -e
        echo "======================================================================"
        echo "STARTING SINGLE TASK TEST"
        echo "======================================================================"
        echo "Reform: {reform}"
        echo "Year: {year}"
        echo "Scoring: {scoring_type}"
        echo "Time: $(date)"
        echo "Memory available: $(free -h | grep Mem)"
        echo "CPU count: $(nproc)"
        echo "======================================================================"
        echo ""

        cd /app

        echo "Running computation..."
        PYTHONPATH=/app/src python3 /app/batch/compute_year.py \
          {year} {scoring_type} {bucket_name} {job_id} {reform}

        echo ""
        echo "======================================================================"
        echo "TASK COMPLETED SUCCESSFULLY"
        echo "======================================================================"
        """
    ]

    # Task specification with MINIMAL resources
    task_spec = batch_v1.TaskSpec()
    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 0  # No retries - we want to see the error
    task_spec.max_run_duration = "1200s"  # 20 minutes max

    # Resources - small for testing
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 4000  # 4 CPUs
    resources.memory_mib = 16384  # 16GB RAM
    task_spec.compute_resource = resources

    # Task group - just ONE task
    task_group = batch_v1.TaskGroup()
    task_group.task_count = 1
    task_group.task_spec = task_spec

    # Allocation policy - use spot VMs
    allocation_policy = batch_v1.AllocationPolicy()
    instances_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instances_policy.machine_type = "e2-standard-4"
    instances_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.SPOT

    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instances_policy

    allocation_policy.instances = [instance_policy_or_template]

    # Service account
    service_account = batch_v1.ServiceAccount()
    service_account.email = f"{project_id}@appspot.gserviceaccount.com"
    allocation_policy.service_account = service_account

    # Logs policy
    logs_policy = batch_v1.LogsPolicy()
    logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    # Job specification
    job = batch_v1.Job()
    job.task_groups = [task_group]
    job.allocation_policy = allocation_policy
    job.logs_policy = logs_policy
    job.labels = {
        "type": "debug-test",
        "reform": reform,
        "year": str(year),
        "scoring": scoring_type
    }

    # Submit job
    print("Submitting test job...")
    request = batch_v1.CreateJobRequest(
        parent=f"projects/{project_id}/locations/{region}",
        job_id=job_id,
        job=job
    )

    operation = client.create_job(request)

    print()
    print("=" * 80)
    print("✓ TEST JOB SUBMITTED")
    print("=" * 80)
    print(f"Job ID: {job_id}")
    print(f"Region: {region}")
    print()
    print("Monitor with:")
    print(f"  gcloud batch jobs describe {job_id} --location={region}")
    print()
    print("View logs:")
    print(f"  gcloud logging read \"resource.labels.job_uid={job_id}\" --limit=100 --format=\"value(textPayload)\"")
    print()
    print("Expected result:")
    print(f"  gs://{bucket_name}/results/{job_id}/{year}_{reform}_{scoring_type}_results.csv")
    print("=" * 80)
    print()

    return job_id

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python test_single_task.py <year> <reform> <scoring_type>")
        print("Example: python test_single_task.py 2026 option1 static")
        sys.exit(1)

    year = int(sys.argv[1])
    reform = sys.argv[2]
    scoring_type = sys.argv[3]

    test_single_task(year, reform, scoring_type)
