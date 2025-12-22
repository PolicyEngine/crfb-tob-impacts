#!/bin/bash
# Monitor Option 4 static and dynamic jobs

STATIC_JOB="years-20251222-133740-7o34f4"
DYNAMIC_JOB="years-20251222-133748-f7rvh8"
REGION="us-central1"
PROJECT="policyengine-api"

echo "Monitoring Option 4 jobs..."
echo "Static:  $STATIC_JOB"
echo "Dynamic: $DYNAMIC_JOB"
echo ""

while true; do
    clear
    echo "=========================================="
    echo "Option 4 Job Monitor - $(date)"
    echo "=========================================="
    echo ""

    # Static job status
    echo "=== STATIC JOB: $STATIC_JOB ==="
    STATIC_INFO=$(gcloud batch jobs describe $STATIC_JOB --location=$REGION --project=$PROJECT --format="value(status.state,status.taskGroups.group0.counts)" 2>/dev/null)
    STATIC_STATUS=$(echo "$STATIC_INFO" | head -1)
    STATIC_COUNTS=$(echo "$STATIC_INFO" | tail -1)

    echo "State: $STATIC_STATUS"
    echo "Tasks: $STATIC_COUNTS"
    echo ""

    # Dynamic job status
    echo "=== DYNAMIC JOB: $DYNAMIC_JOB ==="
    DYNAMIC_INFO=$(gcloud batch jobs describe $DYNAMIC_JOB --location=$REGION --project=$PROJECT --format="value(status.state,status.taskGroups.group0.counts)" 2>/dev/null)
    DYNAMIC_STATUS=$(echo "$DYNAMIC_INFO" | head -1)
    DYNAMIC_COUNTS=$(echo "$DYNAMIC_INFO" | tail -1)

    echo "State: $DYNAMIC_STATUS"
    echo "Tasks: $DYNAMIC_COUNTS"
    echo ""

    # Check results
    echo "=== RESULTS ==="
    STATIC_FILES=$(gsutil ls gs://crfb-ss-analysis-results/results/$STATIC_JOB/*.csv 2>/dev/null | wc -l | tr -d ' ')
    DYNAMIC_FILES=$(gsutil ls gs://crfb-ss-analysis-results/results/$DYNAMIC_JOB/*.csv 2>/dev/null | wc -l | tr -d ' ')
    echo "Static CSVs:  $STATIC_FILES / 75"
    echo "Dynamic CSVs: $DYNAMIC_FILES / 75"
    echo ""

    # Check if both complete
    if [[ "$STATIC_STATUS" == "SUCCEEDED" && "$DYNAMIC_STATUS" == "SUCCEEDED" ]]; then
        echo "=========================================="
        echo "BOTH JOBS COMPLETED SUCCESSFULLY!"
        echo "=========================================="
        echo ""
        echo "Download results:"
        echo "  gsutil -m cp gs://crfb-ss-analysis-results/results/$STATIC_JOB/*.csv ./results/option4_static/"
        echo "  gsutil -m cp gs://crfb-ss-analysis-results/results/$DYNAMIC_JOB/*.csv ./results/option4_dynamic/"
        break
    fi

    if [[ "$STATIC_STATUS" == "FAILED" || "$DYNAMIC_STATUS" == "FAILED" ]]; then
        echo "=========================================="
        echo "WARNING: ONE OR MORE JOBS FAILED"
        echo "=========================================="
        echo "Check logs in Cloud Console"
        break
    fi

    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
