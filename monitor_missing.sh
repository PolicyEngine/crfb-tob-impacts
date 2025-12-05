#!/bin/bash
# Monitor missing years jobs

PROJECT="policyengine-api"
OPT6_JOB="years-20251205-122208-41agnf"
OPT7_JOB="years-20251205-122537-881xpc"
OPT8_JOB="years-20251205-122839-sm37ih"

while true; do
    clear
    echo "========================================"
    echo "MISSING YEARS JOBS - $(date)"
    echo "========================================"
    echo ""

    echo "=== Option 6 (62 years) ==="
    TASKS6=$(gcloud batch tasks list --job=$OPT6_JOB --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    SUCC6=$(echo "$TASKS6" | grep -c "SUCCEEDED" 2>/dev/null || echo "0")
    RUN6=$(echo "$TASKS6" | grep -c "RUNNING" 2>/dev/null || echo "0")
    PEND6=$(echo "$TASKS6" | grep -c "PENDING" 2>/dev/null || echo "0")
    FAIL6=$(echo "$TASKS6" | grep -c "FAILED" 2>/dev/null || echo "0")
    echo "Tasks: $SUCC6 succ, $RUN6 run, $PEND6 pend, $FAIL6 fail"

    echo ""
    echo "=== Option 7 (66 years) ==="
    TASKS7=$(gcloud batch tasks list --job=$OPT7_JOB --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    SUCC7=$(echo "$TASKS7" | grep -c "SUCCEEDED" 2>/dev/null || echo "0")
    RUN7=$(echo "$TASKS7" | grep -c "RUNNING" 2>/dev/null || echo "0")
    PEND7=$(echo "$TASKS7" | grep -c "PENDING" 2>/dev/null || echo "0")
    FAIL7=$(echo "$TASKS7" | grep -c "FAILED" 2>/dev/null || echo "0")
    echo "Tasks: $SUCC7 succ, $RUN7 run, $PEND7 pend, $FAIL7 fail"

    echo ""
    echo "=== Option 8 (62 years) ==="
    TASKS8=$(gcloud batch tasks list --job=$OPT8_JOB --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
    SUCC8=$(echo "$TASKS8" | grep -c "SUCCEEDED" 2>/dev/null || echo "0")
    RUN8=$(echo "$TASKS8" | grep -c "RUNNING" 2>/dev/null || echo "0")
    PEND8=$(echo "$TASKS8" | grep -c "PENDING" 2>/dev/null || echo "0")
    FAIL8=$(echo "$TASKS8" | grep -c "FAILED" 2>/dev/null || echo "0")
    echo "Tasks: $SUCC8 succ, $RUN8 run, $PEND8 pend, $FAIL8 fail"

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
