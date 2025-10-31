#!/bin/bash
# Monitor option5 75-year run with detailed progress tracking

if [ -z "$1" ]; then
    echo "Usage: ./monitor_option5.sh <JOB_ID>"
    exit 1
fi

JOB_ID=$1
REGION="us-central1"
RESULTS_DIR="results/option5_75years"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING OPTION5 - 75 YEARS (2026-2100)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Region: $REGION"
echo "Reform: option5 (Eliminate cap on SS taxable maximum)"
echo "Years: 75 (2026-2100)"
echo "Scoring: static"
echo "================================================================================"
echo ""

for i in {1..120}; do
    echo "=== CHECK #$i - $(date '+%H:%M:%S') ==="

    # Get job status
    STATE=$(gcloud batch jobs describe $JOB_ID --location=$REGION --format="value(status.state)" 2>/dev/null)
    DURATION=$(gcloud batch jobs describe $JOB_ID --location=$REGION --format="value(status.runDuration)" 2>/dev/null | sed 's/s$//')

    if [ -n "$DURATION" ]; then
        MINUTES=$(echo "$DURATION" | awk '{print int($1/60)}')
        SECS=$(echo "$DURATION" | awk '{print int($1%60)}')
        echo "Job State: $STATE (${MINUTES}m ${SECS}s)"
    else
        echo "Job State: $STATE"
    fi

    # Get detailed task counts
    TASK_STATES=$(gcloud batch tasks list --location=$REGION --job=$JOB_ID --format="value(status.state)" 2>/dev/null)
    PENDING=$(echo "$TASK_STATES" | grep -c "PENDING" || echo 0)
    RUNNING=$(echo "$TASK_STATES" | grep -c "RUNNING" || echo 0)
    SUCCEEDED=$(echo "$TASK_STATES" | grep -c "SUCCEEDED" || echo 0)
    FAILED=$(echo "$TASK_STATES" | grep -c "FAILED" || echo 0)

    echo "Tasks: RUNNING=$RUNNING, SUCCEEDED=$SUCCEEDED, FAILED=$FAILED, PENDING=$PENDING (Total: 75)"

    # Download and display results
    TEMP_DIR="$RESULTS_DIR/.temp"
    mkdir -p "$TEMP_DIR"
    gsutil -m cp -n "gs://crfb-ss-analysis-results/results/${JOB_ID}/*.csv" "$TEMP_DIR/" 2>/dev/null

    # Count results
    RESULT_FILES=$(ls "$TEMP_DIR"/*_option5_static_results.csv 2>/dev/null | wc -l | tr -d ' ')

    if [ "$RESULT_FILES" -gt 0 ]; then
        # Merge and sort results
        echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$TEMP_DIR/merged.csv"
        tail -n +2 -q "$TEMP_DIR"/*_option5_static_results.csv 2>/dev/null | sort -t',' -k2 -n >> "$TEMP_DIR/merged.csv"

        # Calculate total impact
        python3 << PYEOF
import pandas as pd
try:
    df = pd.read_csv('$TEMP_DIR/merged.csv')
    if len(df) > 0:
        df = df.sort_values('year')
        total_impact = df['revenue_impact'].sum() / 1e9
        df.to_csv('$RESULTS_DIR/all_results.csv', index=False)

        print(f"Results: {len(df)}/75 years completed")
        print(f"Years: {df['year'].min()}-{df['year'].max()}")
        print(f"Cumulative 10-year impact (2026-2035): \${df[df['year'] <= 2035]['revenue_impact'].sum()/1e9:+.2f}B")
        print(f"Total 75-year impact: \${total_impact:+.2f}B")
except Exception as e:
    print(f"Results: {RESULT_FILES} files downloaded")
PYEOF

        rm -rf "$TEMP_DIR"
    else
        echo "Results: None yet (waiting for first task to complete)"
    fi

    # Show recent logs if tasks are failing
    if [ "$FAILED" -gt 0 ]; then
        echo ""
        echo "⚠️  WARNING: $FAILED tasks have failed"
        echo "Checking logs for failures..."
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID AND severity>=ERROR" --limit=5 --format="value(textPayload)" 2>/dev/null | head -10
    fi

    echo ""

    # Check if done
    if [ "$STATE" = "SUCCEEDED" ]; then
        echo "================================================================================"
        echo "✅ OPTION5 75-YEAR RUN SUCCEEDED!"
        echo "================================================================================"
        echo "Completed: $SUCCEEDED/75 years"
        echo "Failed: $FAILED/75 years"
        echo ""
        echo "Final results saved to: $RESULTS_DIR/all_results.csv"
        echo "Cloud Storage: gs://crfb-ss-analysis-results/results/${JOB_ID}/"
        echo "================================================================================"
        break
    fi

    if [ "$STATE" = "FAILED" ]; then
        echo "================================================================================"
        echo "❌ JOB FAILED"
        echo "================================================================================"
        echo "Succeeded: $SUCCEEDED/75 years"
        echo "Failed: $FAILED/75 years"
        echo ""
        echo "Partial results saved to: $RESULTS_DIR/all_results.csv"
        echo "================================================================================"
        break
    fi

    # Wait 60 seconds before next check
    sleep 60
done

echo ""
echo "Monitoring session ended at $(date)"
