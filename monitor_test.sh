#!/bin/bash
# Monitor single test task with detailed logging

JOB_ID=$1
REGION=${2:-us-central1}

if [ -z "$JOB_ID" ]; then
    echo "Usage: $0 <job_id> [region]"
    exit 1
fi

echo "================================================================================"
echo "MONITORING TEST JOB: $JOB_ID"
echo "================================================================================"
echo ""

CHECK=0
MAX_CHECKS=40  # 20 minutes max

while [ $CHECK -lt $MAX_CHECKS ]; do
    CHECK=$((CHECK + 1))
    echo "=== CHECK #$CHECK - $(date '+%H:%M:%S') ==="

    # Get job state
    STATE=$(gcloud batch jobs describe $JOB_ID --location=$REGION --format="value(status.state,status.runDuration)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl")
    STATUS=$(echo "$STATE" | awk '{print $1}')
    RUNTIME=$(echo "$STATE" | awk '{print $2}' | sed 's/s$//')
    RUNTIME_SEC=${RUNTIME:-0}

    echo "Job Status: $STATUS (${RUNTIME}s)"

    # Get task state
    TASK_STATE=$(gcloud batch tasks list --location=$REGION --job=$JOB_ID --format="value(status.state)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl")
    echo "Task State: $TASK_STATE"

    # Show recent logs if task is running
    if [[ "$TASK_STATE" == "RUNNING" ]] || [[ "$TASK_STATE" == "FAILED" ]]; then
        echo ""
        echo "Recent logs:"
        gcloud logging read "resource.labels.job_uid=$JOB_ID" --limit=50 --format="value(textPayload)" --freshness=2m 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl" | tail -20
    fi

    echo ""

    # Check if complete
    if [[ "$STATUS" == "SUCCEEDED" ]]; then
        echo "✓ JOB SUCCEEDED!"
        echo ""
        echo "Checking for output file..."
        gsutil ls gs://crfb-ss-analysis-results/results/$JOB_ID/ 2>&1 | grep -v "FutureWarning"
        echo ""
        exit 0
    fi

    if [[ "$STATUS" == "FAILED" ]]; then
        echo "✗ JOB FAILED"
        echo ""
        echo "Full error logs:"
        gcloud logging read "resource.labels.job_uid=$JOB_ID" --limit=200 --format="value(textPayload)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl" | tail -50
        echo ""
        exit 1
    fi

    sleep 30
done

echo "Monitoring timeout reached"
