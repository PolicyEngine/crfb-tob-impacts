#!/bin/bash
JOB_ID="years-20251031-121429-x1squs"
RESULTS_DIR="results/75years_dynamic_fixed"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING 75-YEAR DYNAMIC SCORING JOB (WITH FIX)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Results: $RESULTS_DIR/all_results.csv"
echo "Check interval: 60 seconds"
echo "================================================================================"
echo ""

for i in {1..60}; do
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
    RUNNING=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | grep -c "RUNNING" || echo 0)
    SUCCEEDED=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | grep -c "SUCCEEDED" || echo 0)
    FAILED=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | grep -c "FAILED" || echo 0)
    
    echo "Tasks - Running: $RUNNING, Succeeded: $SUCCEEDED, Failed: $FAILED"
    
    # Download new results to temp directory
    TEMP_DIR="$RESULTS_DIR/.temp"
    mkdir -p "$TEMP_DIR"
    gsutil -m cp -n "gs://crfb-ss-analysis-results/results/${JOB_ID}/*.csv" "$TEMP_DIR/" 2>/dev/null
    
    # Count results
    RESULT_COUNT=$(ls "$TEMP_DIR"/*.csv 2>/dev/null | wc -l | tr -d ' ')
    
    # Merge and format if we have results
    if [ "$RESULT_COUNT" -gt 0 ]; then
        # Create temporary merged file with raw data
        echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$TEMP_DIR/raw_merged.csv"
        tail -n +2 -q "$TEMP_DIR"/*_dynamic_results.csv 2>/dev/null >> "$TEMP_DIR/raw_merged.csv"
        
        # Format to billions using Python
        python3 << PYEOF
import pandas as pd
import sys
try:
    df = pd.read_csv('$TEMP_DIR/raw_merged.csv')
    if len(df) > 0:
        df['baseline_revenue'] = (df['baseline_revenue'] / 1e9).round(2)
        df['reform_revenue'] = (df['reform_revenue'] / 1e9).round(2)
        df['revenue_impact'] = (df['revenue_impact'] / 1e9).round(2)
        df = df.sort_values('year')
        df.to_csv('$RESULTS_DIR/all_results.csv', index=False)
except Exception as e:
    print(f"Error formatting: {e}", file=sys.stderr)
PYEOF
        
        TOTAL_ROWS=$(tail -n +2 "$RESULTS_DIR/all_results.csv" 2>/dev/null | wc -l | tr -d ' ')
        echo "Results: $TOTAL_ROWS years completed"
        
        # Clean up temp directory
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
        break
    fi
    
    # Wait 1 minute
    sleep 60
done

echo ""
echo "Final results saved to: $RESULTS_DIR/all_results.csv"
echo "Revenue values are in billions (rounded to 2 decimals)"
