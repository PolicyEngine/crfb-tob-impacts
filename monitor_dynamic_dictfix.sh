#!/bin/bash
JOB_ID="years-20251031-133056-i6q3ir"
RESULTS_DIR="results/3years_dynamic_dictfix"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING 3-YEAR DYNAMIC SCORING TEST (WITH DICT MERGING FIX)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Results: $RESULTS_DIR/all_results.csv"
echo "Check interval: 30 seconds"
echo "================================================================================"
echo ""

for i in {1..30}; do
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
    
    # Get task counts
    TASK_STATES=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null)
    RUNNING=$(echo "$TASK_STATES" | grep -c "RUNNING" || echo 0)
    SUCCEEDED=$(echo "$TASK_STATES" | grep -c "SUCCEEDED" || echo 0)
    FAILED=$(echo "$TASK_STATES" | grep -c "FAILED" || echo 0)
    
    echo "Tasks - Running: $RUNNING, Succeeded: $SUCCEEDED, Failed: $FAILED"
    
    # If failed, try to get logs
    if [ "$FAILED" -gt 0 ]; then
        echo "--- Attempting to fetch error logs ---"
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=50 --format="value(textPayload)" --freshness=10m 2>/dev/null | grep -v "^$" | tail -20
    fi
    
    # Download new results to temp directory
    TEMP_DIR="$RESULTS_DIR/.temp"
    mkdir -p "$TEMP_DIR"
    gsutil -m cp -n "gs://crfb-ss-analysis-results/results/${JOB_ID}/*.csv" "$TEMP_DIR/" 2>/dev/null
    
    # Count results
    RESULT_COUNT=$(ls "$TEMP_DIR"/*.csv 2>/dev/null | wc -l | tr -d ' ')
    
    # Merge and format if we have results
    if [ "$RESULT_COUNT" -gt 0 ]; then
        echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$TEMP_DIR/raw_merged.csv"
        tail -n +2 -q "$TEMP_DIR"/*_dynamic_results.csv 2>/dev/null >> "$TEMP_DIR/raw_merged.csv"
        
        python3 << PYEOF
import pandas as pd
try:
    df = pd.read_csv('$TEMP_DIR/raw_merged.csv')
    if len(df) > 0:
        df['baseline_revenue'] = (df['baseline_revenue'] / 1e9).round(2)
        df['reform_revenue'] = (df['reform_revenue'] / 1e9).round(2)
        df['revenue_impact'] = (df['revenue_impact'] / 1e9).round(2)
        df = df.sort_values('year')
        df.to_csv('$RESULTS_DIR/all_results.csv', index=False)
except: pass
PYEOF
        
        TOTAL_ROWS=$(tail -n +2 "$RESULTS_DIR/all_results.csv" 2>/dev/null | wc -l | tr -d ' ')
        echo "Results: $TOTAL_ROWS years completed ✓"
        rm -rf "$TEMP_DIR"
    else
        echo "Results: None yet"
    fi
    
    echo ""
    
    # Check if done
    if [ "$STATE" = "SUCCEEDED" ] || [ "$STATE" = "FAILED" ]; then
        echo "================================================================================"
        echo "✓ JOB FINISHED: $STATE"
        echo "================================================================================"
        
        # Final log attempt
        if [ "$STATE" = "FAILED" ]; then
            echo ""
            echo "=== FINAL ERROR LOG ATTEMPT ==="
            gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=100 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$"
        fi
        break
    fi
    
    # Wait 30 seconds
    sleep 30
done

echo ""
echo "Results saved to: $RESULTS_DIR/all_results.csv"
