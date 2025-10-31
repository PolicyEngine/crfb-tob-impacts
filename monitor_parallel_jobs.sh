#!/bin/bash
# Monitor two parallel jobs (static and dynamic) with comprehensive real-time updates

STATIC_JOB_ID=$1
DYNAMIC_JOB_ID=$2
STATIC_REGION=${3:-us-central1}
DYNAMIC_REGION=${4:-us-east1}
BUCKET="crfb-ss-analysis-results"
LOCAL_DIR="results/parallel_run"
OUTPUT_CSV="$LOCAL_DIR/all_results.csv"

if [ -z "$STATIC_JOB_ID" ] || [ -z "$DYNAMIC_JOB_ID" ]; then
    echo "Usage: $0 <static_job_id> <dynamic_job_id> [static_region] [dynamic_region]"
    exit 1
fi

# Create local directory
mkdir -p "$LOCAL_DIR"

echo "================================================================================"
echo "MONITORING FULLY PARALLELIZED JOBS (STATIC + DYNAMIC)"
echo "================================================================================"
echo "Static Job ID: $STATIC_JOB_ID (region: $STATIC_REGION)"
echo "Dynamic Job ID: $DYNAMIC_JOB_ID (region: $DYNAMIC_REGION)"
echo "Total reform-years: 1200 (600 static + 600 dynamic)"
echo "Expected duration: ~15-20 minutes for both to complete"
echo "Check interval: 20 seconds"
echo "Results: $OUTPUT_CSV"
echo "================================================================================"
echo ""

CHECK_NUM=0
MAX_CHECKS=100  # ~33 minutes of monitoring

while [ $CHECK_NUM -lt $MAX_CHECKS ]; do
    CHECK_NUM=$((CHECK_NUM + 1))
    echo "=== CHECK #$CHECK_NUM - $(date '+%H:%M:%S') ==="

    # Get job states
    STATIC_STATE=$(gcloud batch jobs describe $STATIC_JOB_ID --location=$STATIC_REGION --format="value(status.state,status.runDuration)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl")
    DYNAMIC_STATE=$(gcloud batch jobs describe $DYNAMIC_JOB_ID --location=$DYNAMIC_REGION --format="value(status.state,status.runDuration)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl")

    # Parse states
    STATIC_STATUS=$(echo "$STATIC_STATE" | awk '{print $1}')
    STATIC_RUNTIME=$(echo "$STATIC_STATE" | awk '{print $2}' | sed 's/s$//')
    STATIC_RUNTIME_MIN=$(echo "scale=1; $STATIC_RUNTIME / 60" | bc 2>/dev/null || echo "0")

    DYNAMIC_STATUS=$(echo "$DYNAMIC_STATE" | awk '{print $1}')
    DYNAMIC_RUNTIME=$(echo "$DYNAMIC_STATE" | awk '{print $2}' | sed 's/s$//')
    DYNAMIC_RUNTIME_MIN=$(echo "scale=1; $DYNAMIC_RUNTIME / 60" | bc 2>/dev/null || echo "0")

    echo "Static Job:  $STATIC_STATUS (${STATIC_RUNTIME_MIN}m)"
    echo "Dynamic Job: $DYNAMIC_STATUS (${DYNAMIC_RUNTIME_MIN}m)"
    echo ""

    # Get task counts
    echo "Task Status:"
    STATIC_TASKS=$(gcloud batch tasks list --location=$STATIC_REGION --job=$STATIC_JOB_ID --format="value(status.state)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl" | sort | uniq -c)
    DYNAMIC_TASKS=$(gcloud batch tasks list --location=$DYNAMIC_REGION --job=$DYNAMIC_JOB_ID --format="value(status.state)" 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl" | sort | uniq -c)
    echo "  Static:  $STATIC_TASKS"
    echo "  Dynamic: $DYNAMIC_TASKS"
    echo ""

    # Download and merge all CSVs
    echo "Downloading results..."

    # Download static results
    gsutil -m cp -n "gs://$BUCKET/results/$STATIC_JOB_ID/*.csv" "$LOCAL_DIR/" 2>&1 | grep -v "Copying\|Skipping\|Operation completed" | head -3

    # Download dynamic results
    gsutil -m cp -n "gs://$BUCKET/results/$DYNAMIC_JOB_ID/*.csv" "$LOCAL_DIR/" 2>&1 | grep -v "Copying\|Skipping\|Operation completed" | head -3

    # Merge and analyze with Python
    python3 << 'PYTHON_EOF'
import pandas as pd
import os
from datetime import datetime

local_dir = "results/parallel_run"
output_csv = os.path.join(local_dir, "all_results.csv")

# Find all CSV files
csv_files = [f for f in os.listdir(local_dir) if f.endswith('_results.csv') and f != 'all_results.csv']

if csv_files:
    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(os.path.join(local_dir, csv_file))
            dfs.append(df)
        except Exception as e:
            pass

    if dfs:
        merged = pd.concat(dfs, ignore_index=True)
        merged = merged.drop_duplicates()
        merged = merged.sort_values(['scoring_type', 'reform_name', 'year'])
        merged.to_csv(output_csv, index=False)

        # Analyze progress
        total = len(merged)
        print(f"\n{'='*80}")
        print(f"PROGRESS: {total}/1200 reform-years completed ({100*total/1200:.1f}%)")
        print(f"{'='*80}\n")

        # Break down by scoring type and reform
        for scoring in ['static', 'dynamic']:
            scoring_data = merged[merged['scoring_type'] == scoring]
            count = len(scoring_data)
            pct = 100 * count / 600
            print(f"{scoring.upper()}: {count}/600 reform-years ({pct:.1f}%)")

            for reform in ['option1', 'option2', 'option3', 'option4', 'option5', 'option6', 'option7', 'option8']:
                reform_data = scoring_data[scoring_data['reform_name'] == reform]
                reform_count = len(reform_data)
                reform_pct = 100 * reform_count / 75
                bar_length = int(reform_pct / 2)
                bar = '█' * bar_length + '░' * (50 - bar_length)
                print(f"  {reform}: [{bar}] {reform_count}/75 years ({reform_pct:.0f}%)")
            print()

        # Show recent completions (last 10)
        recent = merged.tail(10)
        print("Recent completions:")
        for _, row in recent.iterrows():
            print(f"  ✓ {row['reform_name']} {row['year']} ({row['scoring_type']}) - ${row['revenue_impact']/1e9:.1f}B impact")
        print()
else:
    print("\nNo results yet...\n")
PYTHON_EOF

    echo "================================================================================"
    echo ""

    # Check if both jobs are complete
    if [[ "$STATIC_STATUS" == "SUCCEEDED" ]] && [[ "$DYNAMIC_STATUS" == "SUCCEEDED" ]]; then
        echo "✓ BOTH JOBS COMPLETED SUCCESSFULLY!"
        echo ""
        echo "Final results saved to: $OUTPUT_CSV"
        echo ""
        break
    fi

    # Check if either job failed
    if [[ "$STATIC_STATUS" == "FAILED" ]]; then
        echo "✗ Static job FAILED"
    fi
    if [[ "$DYNAMIC_STATUS" == "FAILED" ]]; then
        echo "✗ Dynamic job FAILED"
    fi

    if [[ "$STATIC_STATUS" == "FAILED" ]] || [[ "$DYNAMIC_STATUS" == "FAILED" ]]; then
        echo ""
        echo "One or both jobs failed. Check logs:"
        echo "  gcloud logging read \"resource.type=batch_job\" --limit=100"
        break
    fi

    sleep 20
done

if [ $CHECK_NUM -ge $MAX_CHECKS ]; then
    echo "Monitoring limit reached. Jobs may still be running."
    echo "Check status manually:"
    echo "  gcloud batch jobs describe $STATIC_JOB_ID --location=us-central1"
    echo "  gcloud batch jobs describe $DYNAMIC_JOB_ID --location=us-central1"
fi
