#!/bin/bash
JOB_ID="years-20251031-142557-af0153"
RESULTS_DIR="results/1year_diagnostic"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING 1-YEAR DYNAMIC TEST WITH COMPREHENSIVE DIAGNOSTIC LOGGING"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Year: 2028 (single year)"
echo "Reforms: option1-option8 (8 reforms)"
echo "Container: Latest with comprehensive diagnostic logging"
echo "Check interval: 20 seconds"
echo "================================================================================"
echo ""

for i in {1..25}; do
    echo "=== CHECK #$i - $(date '+%H:%M:%S') ==="
    
    # Get job status
    STATE=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.state)" 2>/dev/null)
    DURATION=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.runDuration)" 2>/dev/null | sed 's/s$//')
    
    if [ -n "$DURATION" ]; then
        MINUTES=$(echo "$DURATION" | awk '{print int($1/60)}')
        SECS=$(echo "$DURATION" | awk '{print int($1%60)}')
        echo "Job State: $STATE (${MINUTES}m ${SECS}s)"
        
        # Highlight when we pass 2-minute mark (previous 1-year test failed at 1m 56s)
        if [ "$MINUTES" -ge 2 ]; then
            echo "✅ PASSED 2-minute mark (previous 1-year test failed at 1m 56s)"
        fi
    else
        echo "Job State: $STATE"
    fi
    
    # Get task state
    TASK_STATE=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | head -1)
    echo "Task State: $TASK_STATE"
    
    # Try to get diagnostic logs
    echo "--- Fetching diagnostic logs ---"
    LOGS=$(gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=200 --format="value(textPayload)" --freshness=10m 2>/dev/null | grep -v "^$")
    
    if [ -n "$LOGS" ]; then
        echo "$LOGS" | tail -30
        # Save full logs to file
        echo "$LOGS" > "$RESULTS_DIR/logs_check_${i}.txt"
        echo "✓ Logs saved to $RESULTS_DIR/logs_check_${i}.txt"
    else
        echo "No logs captured yet"
    fi
    
    # Check for results
    HAS_RESULTS=$(gsutil ls "gs://crfb-ss-analysis-results/results/$JOB_ID/" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$HAS_RESULTS" -gt 0 ]; then
        echo "✓ Results file exists"
        gsutil -m cp -n "gs://crfb-ss-analysis-results/results/$JOB_ID/*.csv" "$RESULTS_DIR/" 2>/dev/null
    fi
    
    echo ""
    
    # Check if done
    if [ "$STATE" = "SUCCEEDED" ]; then
        echo "================================================================================"
        echo "✅ JOB SUCCEEDED!"
        echo "================================================================================"
        
        # Get final logs
        echo ""
        echo "=== FINAL DIAGNOSTIC LOGS ==="
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=500 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$" | tee "$RESULTS_DIR/final_logs.txt"
        break
    fi
    
    if [ "$STATE" = "FAILED" ]; then
        echo "================================================================================"
        echo "❌ JOB FAILED"
        echo "================================================================================"
        
        # Get final logs with all attempts
        echo ""
        echo "=== FINAL DIAGNOSTIC LOGS (ALL ATTEMPTS) ==="
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=1000 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$" | tee "$RESULTS_DIR/failure_logs.txt"
        
        # Also try task-level logs
        echo ""
        echo "=== TASK-LEVEL LOGS ==="
        TASK_NAME=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(name)" 2>/dev/null | head -1)
        if [ -n "$TASK_NAME" ]; then
            gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.task_uid=$TASK_NAME" --limit=1000 --format="json" --freshness=15m 2>/dev/null | tee "$RESULTS_DIR/task_logs.json"
        fi
        break
    fi
    
    # Wait 20 seconds
    sleep 20
done

echo ""
echo "Results saved to: $RESULTS_DIR/"
