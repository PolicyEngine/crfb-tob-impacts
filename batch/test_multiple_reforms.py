#!/usr/bin/env python3
"""
Test script to determine memory limits by testing different numbers of reforms.
"""

import sys
from google.cloud import batch_v1
from datetime import datetime

def test_reforms(year, reforms_list, scoring_type):
    """Submit a single-task job with multiple reforms to test memory limits."""

    project_id = "policyengine-api"
    region = "us-central1"
    bucket_name = "crfb-ss-analysis-results"

    num_reforms = len(reforms_list)
    reforms_str = '-'.join(reforms_list)
    job_id = f"test-{num_reforms}reforms-{year}-{scoring_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print("=" * 80)
    print(f"MEMORY TEST: {num_reforms} reforms per task")
    print("=" * 80)
    print(f"Job ID: {job_id}")
    print(f"Reforms: {', '.join(reforms_list)}")
    print(f"Year: {year}")
    print(f"Scoring: {scoring_type}")
    print(f"Resources: 4 CPUs, 16GB RAM")
    print("=" * 80)
    print()

    # Create Batch client
    client = batch_v1.BatchServiceClient()

    # Build the command with all reforms
    reforms_args = ' '.join(reforms_list)

    script = f"""
    set -e
    echo "======================================================================"
    echo "MEMORY TEST: {num_reforms} reforms"
    echo "======================================================================"
    echo "Reforms: {reforms_args}"
    echo "Year: {year}"
    echo "Scoring: {scoring_type}"
    echo "Time: $(date)"
    echo "CPU count: $(nproc)"
    echo "======================================================================"
    echo ""

    cd /app

    echo "Running computation with {num_reforms} reforms..."
    PYTHONPATH=/app/src python3 /app/batch/compute_year.py {year} {scoring_type} {bucket_name} {job_id} {reforms_args}

    echo ""
    echo "======================================================================"
    echo "✓ COMPLETED - {num_reforms} reforms fit in 16GB RAM"
    echo "======================================================================"
    """

    # Task specification
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = "gcr.io/policyengine-api/ss-calculator:latest"
    runnable.container.entrypoint = "/bin/bash"
    runnable.container.commands = ["-c", script]

    task_spec = batch_v1.TaskSpec()
    task_spec.runnables = [runnable]
    task_spec.max_retry_count = 0
    task_spec.max_run_duration = "1200s"

    # Resources - 16GB to test limits
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 4000
    resources.memory_mib = 16384
    task_spec.compute_resource = resources

    # Task group
    task_group = batch_v1.TaskGroup()
    task_group.task_count = 1
    task_group.task_spec = task_spec

    # Allocation policy
    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.machine_type = "e2-standard-4"
    instance_policy.provisioning_model = batch_v1.AllocationPolicy.ProvisioningModel.SPOT

    instance_policy_or_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instance_policy_or_template.policy = instance_policy
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
        "type": "memory-test",
        "num_reforms": str(num_reforms),
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
    print(f"Testing: {num_reforms} reforms")
    print()
    print("Monitor with:")
    print(f"  ./monitor_test.sh {job_id}")
    print()
    print("Expected outcome:")
    print(f"  SUCCESS = {num_reforms} reforms fits in 16GB")
    print(f"  FAIL (exit 137) = {num_reforms} reforms needs more RAM")
    print("=" * 80)
    print()

    return job_id

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_multiple_reforms.py <year> <scoring_type> <reform1> [reform2] [reform3] ...")
        print("Example: python test_multiple_reforms.py 2026 static option1 option2 option3 option4")
        sys.exit(1)

    year = int(sys.argv[1])
    scoring_type = sys.argv[2]
    reforms = sys.argv[3:]

    test_reforms(year, reforms, scoring_type)
