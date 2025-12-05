#!/bin/bash
# Monitor Option 1 Static jobs

JOB1="years-20251204-164800-hopzx8"
JOB2="years-20251204-164802-q4f475"
PROJECT="policyengine-api"

while true; do
    clear
    echo "========================================"
    echo "OPTION 1 STATIC - $(date)"
    echo "========================================"

    echo ""
    echo "=== Job 1: 2026-2027 (64GB) ==="
    gcloud batch jobs describe $JOB1 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null || echo "UNKNOWN"
    gcloud batch tasks list --job=$JOB1 --location=us-central1 --project=$PROJECT --format="table(name.basename(),status.state)" 2>/dev/null | head -10

    echo ""
    echo "=== Job 2: 2028-2100 (32GB) ==="
    gcloud batch jobs describe $JOB2 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null || echo "UNKNOWN"
    TASKS=$(gcloud batch tasks list --job=$JOB2 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    SUCCEEDED=$(echo "$TASKS" | grep -c "SUCCEEDED" || echo 0)
    RUNNING=$(echo "$TASKS" | grep -c "RUNNING" || echo 0)
    FAILED=$(echo "$TASKS" | grep -c "FAILED" || echo 0)
    echo "Tasks: $SUCCEEDED succeeded, $RUNNING running, $FAILED failed (of 73)"

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
