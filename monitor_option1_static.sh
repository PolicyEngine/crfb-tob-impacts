#!/bin/bash
# Monitor option 1 static jobs

PROJECT="policyengine-api"
JOB1="years-20251211-110701-rbnj8p"  # 2026-2027 (2 tasks) - Clean 6750 version

while true; do
    clear
    echo "========================================"
    echo "OPTION 1 STATIC JOBS - $(date)"
    echo "========================================"
    echo ""

    echo "=== Job 1: 2026-2027 (2 tasks) ==="
    STATE1=$(gcloud batch jobs describe $JOB1 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    echo "State: $STATE1"
    if [ "$STATE1" == "RUNNING" ] || [ "$STATE1" == "SCHEDULED" ]; then
        TASKS1=$(gcloud batch tasks list --job=$JOB1 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
        SUCC1=$(echo "$TASKS1" | grep -c "SUCCEEDED" 2>/dev/null || echo "0")
        RUN1=$(echo "$TASKS1" | grep -c "RUNNING" 2>/dev/null || echo "0")
        PEND1=$(echo "$TASKS1" | grep -c "PENDING" 2>/dev/null || echo "0")
        echo "Tasks: $SUCC1/2 succeeded, $RUN1 running, $PEND1 pending"
    fi

    echo ""
    echo "=== CSV Files Saved ==="
    gsutil ls gs://crfb-ss-analysis-results/results/$JOB1/*.csv 2>/dev/null || echo "None yet"

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
