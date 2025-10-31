#!/bin/bash
# General-purpose monitoring script for any Cloud Batch job
JOB_ID="$1"
REFORM="$2"
SCORING="$3"
REGION="${4:-us-central1}"

if [ -z "$JOB_ID" ] || [ -z "$REFORM" ] || [ -z "$SCORING" ]; then
    echo "Usage: $0 <job_id> <reform> <scoring> [region]"
    echo "Example: $0 years-20251031-123456-abc123 option5 dynamic us-central1"
    exit 1
fi

RESULTS_DIR="results/${REFORM}_75years_${SCORING}"
mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING CLOUD BATCH JOB"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Region: $REGION"
echo "Reform: $REFORM"
echo "Scoring: $SCORING"
echo "Results: $RESULTS_DIR"
echo "================================================================================"
echo ""

for i in {1..120}; do
    echo "=== CHECK #$i - $(date '+%H:%M:%S') ==="

    STATE=$(gcloud batch jobs describe $JOB_ID --location=$REGION --format="value(status.state)" 2>/dev/null)
    DURATION=$(gcloud batch jobs describe $JOB_ID --location=$REGION --format="value(status.runDuration)" 2>/dev/null | sed 's/s$//')

    if [ -n "$DURATION" ]; then
        MINUTES=$(echo "$DURATION" | awk '{print int($1/60)}')
        SECS=$(echo "$DURATION" | awk '{print int($1%60)}')
        echo "Job State: $STATE (${MINUTES}m ${SECS}s)"
    else
        echo "Job State: $STATE"
    fi

    TASK_STATES=$(gcloud batch tasks list --location=$REGION --job=$JOB_ID --format="value(status.state)" 2>/dev/null)
    PENDING=$(echo "$TASK_STATES" | grep -c "PENDING" || echo 0)
    RUNNING=$(echo "$TASK_STATES" | grep -c "RUNNING" || echo 0)
    SUCCEEDED=$(echo "$TASK_STATES" | grep -c "SUCCEEDED" || echo 0)
    FAILED=$(echo "$TASK_STATES" | grep -c "FAILED" || echo 0)

    echo "Tasks: RUNNING=$RUNNING, SUCCEEDED=$SUCCEEDED, FAILED=$FAILED, PENDING=$PENDING"

    TEMP_DIR="$RESULTS_DIR/.temp"
    mkdir -p "$TEMP_DIR"
    gsutil -m cp -n "gs://crfb-ss-analysis-results/results/${JOB_ID}/*.csv" "$TEMP_DIR/" 2>/dev/null

    RESULT_FILES=$(ls "$TEMP_DIR"/*_${REFORM}_${SCORING}_results.csv 2>/dev/null | wc -l | tr -d ' ')

    if [ "$RESULT_FILES" -gt 0 ]; then
        echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$TEMP_DIR/merged.csv"
        tail -n +2 -q "$TEMP_DIR"/*_${REFORM}_${SCORING}_results.csv 2>/dev/null | sort -t',' -k2 -n >> "$TEMP_DIR/merged.csv"

        python3 << PYEOF
import pandas as pd
try:
    df = pd.read_csv('$TEMP_DIR/merged.csv')
    if len(df) > 0:
        df = df.sort_values('year')
        # Convert to billions
        df['baseline_revenue'] = (df['baseline_revenue'] / 1e9).round(2)
        df['reform_revenue'] = (df['reform_revenue'] / 1e9).round(2)
        df['revenue_impact'] = (df['revenue_impact'] / 1e9).round(2)

        total_impact = df['revenue_impact'].sum()
        df.to_csv('$RESULTS_DIR/all_results.csv', index=False)

        print(f"Results: {len(df)} years completed")
        print(f"Years: {df['year'].min()}-{df['year'].max()}")
        if len(df[df['year'] <= 2035]) > 0:
            print(f"10-year impact (2026-2035): \${df[df['year'] <= 2035]['revenue_impact'].sum():+.2f}B")
        print(f"Total impact: \${total_impact:+.2f}B")
except Exception as e:
    print(f"Results: {RESULT_FILES} files downloaded")
PYEOF

        rm -rf "$TEMP_DIR"
    else
        echo "Results: None yet"
    fi

    if [ "$FAILED" -gt 0 ]; then
        echo "⚠️  WARNING: $FAILED tasks failed"
    fi

    echo ""

    if [ "$STATE" = "SUCCEEDED" ]; then
        echo "✅ JOB COMPLETED! ($SUCCEEDED succeeded, $FAILED failed)"
        break
    fi

    if [ "$STATE" = "FAILED" ]; then
        echo "❌ JOB FAILED ($SUCCEEDED succeeded, $FAILED failed)"
        break
    fi

    sleep 60
done

echo "Final results: $RESULTS_DIR/all_results.csv"
