#!/bin/bash
# Monitor Option 1 Static Job 2

JOB="years-20251204-193943-tfrk9n"
PROJECT="policyengine-api"

while true; do
    clear
    echo "========================================"
    echo "OPTION 1 STATIC JOB 2 - $(date)"
    echo "========================================"
    echo ""

    STATE=$(gcloud batch jobs describe $JOB --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null || echo "UNKNOWN")
    echo "Job State: $STATE"
    echo ""

    TASKS=$(gcloud batch tasks list --job=$JOB --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    SUCC=$(echo "$TASKS" | grep -c "SUCCEEDED" || echo 0)
    RUN=$(echo "$TASKS" | grep -c "RUNNING" || echo 0)
    PEND=$(echo "$TASKS" | grep -c "PENDING" || echo 0)
    FAIL=$(echo "$TASKS" | grep -c "FAILED" || echo 0)

    echo "Tasks: $SUCC succeeded, $RUN running, $PEND pending, $FAIL failed (of 73)"
    echo ""

    # Show CSVs saved
    CSV_COUNT=$(gsutil ls "gs://crfb-ss-analysis-results/results/$JOB/" 2>/dev/null | wc -l | tr -d ' ')
    echo "CSVs saved: $CSV_COUNT"

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
