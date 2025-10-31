#!/bin/bash
JOB_ID="years-20251031-160435-l6kukz"
RESULTS_DIR="results/75years_options2to8_static"

mkdir -p "$RESULTS_DIR"

echo "================================================================================"
echo "MONITORING OPTIONS 2-8 STATIC SCORING (MAIN PRODUCTION RUN)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Years: 2026-2100 (75 years)"
echo "Reforms: option2, option3, option4, option5, option6, option7, option8 (7 reforms)"
echo "Total reform-years: 525 (75 × 7)"
echo "Scoring: static"
echo "Expected duration: ~14-21 minutes"
echo "Check interval: 30 seconds"
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
    TASK_STATES=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null)
    RUNNING=$(echo "$TASK_STATES" | grep -c "RUNNING" || echo 0)
    SUCCEEDED=$(echo "$TASK_STATES" | grep -c "SUCCEEDED" || echo 0)
    FAILED=$(echo "$TASK_STATES" | grep -c "FAILED" || echo 0)

    echo "Tasks - Running: $RUNNING, Succeeded: $SUCCEEDED, Failed: $FAILED (Total: 75 years)"

    # Download new results to temp directory
    TEMP_DIR="$RESULTS_DIR/.temp"
    mkdir -p "$TEMP_DIR"
    gsutil -m cp -n "gs://crfb-ss-analysis-results/results/${JOB_ID}/*.csv" "$TEMP_DIR/" 2>/dev/null

    # Count results
    RESULT_COUNT=$(ls "$TEMP_DIR"/*.csv 2>/dev/null | wc -l | tr -d ' ')

    # Merge and format if we have results
    if [ "$RESULT_COUNT" -gt 0 ]; then
        echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$TEMP_DIR/raw_merged.csv"
        tail -n +2 -q "$TEMP_DIR"/*_static_results.csv 2>/dev/null >> "$TEMP_DIR/raw_merged.csv"

        python3 << 'PYEOF'
import pandas as pd
import sys
try:
    df = pd.read_csv('$TEMP_DIR/raw_merged.csv')
    if len(df) > 0:
        df['baseline_revenue'] = (df['baseline_revenue'] / 1e9).round(2)
        df['reform_revenue'] = (df['reform_revenue'] / 1e9).round(2)
        df['revenue_impact'] = (df['revenue_impact'] / 1e9).round(2)
        df = df.sort_values(['reform_name', 'year'])
        df.to_csv('$RESULTS_DIR/all_results.csv', index=False)
except Exception as e:
    pass
PYEOF

        TOTAL_ROWS=$(tail -n +2 "$RESULTS_DIR/all_results.csv" 2>/dev/null | wc -l | tr -d ' ')
        EXPECTED=525
        if [ -n "$TOTAL_ROWS" ] && [ "$TOTAL_ROWS" -gt 0 ]; then
            PERCENT=$((TOTAL_ROWS * 100 / EXPECTED))
            echo "Results: $TOTAL_ROWS/$EXPECTED reform-years completed ($PERCENT%) ✓"

            # Show progress by reform
            echo ""
            echo "Progress by reform:"
            python3 << 'PYEOF'
import pandas as pd
try:
    df = pd.read_csv('$RESULTS_DIR/all_results.csv')
    counts = df.groupby('reform_name').size()
    for reform, count in counts.items():
        pct = int(count * 100 / 75)
        bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
        print(f"  {reform}: {count}/75 years [{bar}] {pct}%")
except: pass
PYEOF
        else
            echo "Results: Processing..."
        fi
        rm -rf "$TEMP_DIR"
    else
        echo "Results: None yet"
    fi

    echo ""

    # Check if done
    if [ "$STATE" = "SUCCEEDED" ]; then
        echo "================================================================================"
        echo "✅ OPTIONS 2-8 STATIC SCORING SUCCESSFULLY COMPLETED!"
        echo "================================================================================"

        # Download final results
        gsutil -m cp "gs://crfb-ss-analysis-results/results/$JOB_ID/*.csv" "$RESULTS_DIR/" 2>/dev/null

        echo ""
        echo "Final summary:"
        python3 << 'PYEOF'
import pandas as pd
try:
    df = pd.read_csv('$RESULTS_DIR/all_results.csv')
    print(f"\nTotal reform-years computed: {len(df)}")
    print(f"\nResults by reform:")
    summary = df.groupby('reform_name').agg({
        'revenue_impact': ['count', 'sum', 'mean']
    }).round(2)
    print(summary)
    print(f"\nResults saved to: $RESULTS_DIR/all_results.csv")
except: pass
PYEOF

        break
    fi

    if [ "$STATE" = "FAILED" ]; then
        echo "================================================================================"
        echo "❌ JOB FAILED"
        echo "================================================================================"
        echo "Checking logs..."
        gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=100 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$" | tail -50
        break
    fi

    # Wait 30 seconds
    sleep 30
done

echo ""
echo "Results saved to: $RESULTS_DIR/all_results.csv"
