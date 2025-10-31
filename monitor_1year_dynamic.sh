#!/bin/bash
JOB_ID="years-20251031-150413-aiogr3"
RESULTS_DIR="results/1year_dynamic"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING 1-YEAR DYNAMIC TEST (PARAMETER PATH FIX VERIFICATION)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Year: 2028 (single year)"
echo "Reform: option1"
echo "Scoring: DYNAMIC (with parameter path fix: .income.all)"
echo "Container: Latest with parameter path fix"
echo "Check interval: 20 seconds"
echo "================================================================================"
echo ""

for i in {1..20}; do
    echo "=== CHECK #$i - $(date '+%H:%M:%S') ==="
    
    # Get job status
    STATE=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.state)" 2>/dev/null)
    DURATION=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.runDuration)" 2>/dev/null | sed 's/s$//')
    
    if [ -n "$DURATION" ]; then
        MINUTES=$(echo "$DURATION" | awk '{print int($1/60)}')
        SECS=$(echo "$DURATION" | awk '{print int($1%60)}')
        echo "Job State: $STATE (${MINUTES}m ${SECS}s)"
    else
        echo "Job State: $STATE"
    fi
    
    # Get task state
    TASK_STATE=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | head -1)
    echo "Task State: $TASK_STATE"
    
    # Try to get diagnostic logs
    if [ "$TASK_STATE" = "RUNNING" ] || [ "$TASK_STATE" = "FAILED" ]; then
        echo "--- Latest logs ---"
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=30 --format="value(textPayload)" --freshness=5m 2>/dev/null | grep -v "^$" | tail -10
    fi
    
    # Check for results
    HAS_RESULTS=$(gsutil ls "gs://crfb-ss-analysis-results/results/$JOB_ID/" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$HAS_RESULTS" -gt 0 ]; then
        echo "✅ Results file exists!"
        gsutil -m cp -n "gs://crfb-ss-analysis-results/results/$JOB_ID/*.csv" "$RESULTS_DIR/" 2>/dev/null
    fi
    
    echo ""
    
    # Check if done
    if [ "$STATE" = "SUCCEEDED" ]; then
        echo "================================================================================"
        echo "✅✅✅ 1-YEAR DYNAMIC TEST SUCCEEDED! ✅✅✅"
        echo "================================================================================"
        echo ""
        echo "The parameter path fix (.income.all) is WORKING!"
        echo "Ready to proceed with 75-year dynamic test for option1."
        echo ""
        
        # Download and display results
        gsutil cp "gs://crfb-ss-analysis-results/results/$JOB_ID/*.csv" "$RESULTS_DIR/" 2>/dev/null
        echo "Results:"
        cat "$RESULTS_DIR"/*.csv | head -10
        break
    fi
    
    if [ "$STATE" = "FAILED" ]; then
        echo "================================================================================"
        echo "❌ 1-YEAR DYNAMIC TEST FAILED"
        echo "================================================================================"
        echo ""
        echo "=== FULL ERROR LOGS ==="
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=200 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$"
        break
    fi
    
    # Wait 20 seconds
    sleep 20
done

echo ""
echo "Results directory: $RESULTS_DIR/"
