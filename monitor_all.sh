#!/bin/bash
# Monitor all running batch jobs - refreshes every 30 seconds

JOBS=(
    "years-20251217-224620-nvy2t9"
)
# COMPLETED: Option 5 static 75/75, Option 7 dynamic 75/75, Option 8 dynamic 75/75

while true; do
    clear
    echo "================================================================================"
    echo "CRFB Batch Jobs Monitor - $(date)"
    echo "================================================================================"
    echo ""

    for job_id in "${JOBS[@]}"; do
        # Get job state and duration
        result=$(gcloud batch jobs describe "$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state,status.runDuration)" 2>/dev/null)

        if [ -z "$result" ]; then
            echo ">>> $job_id"
            echo "    ✗ Job not found"
            echo ""
            continue
        fi

        state=$(echo "$result" | cut -f1)
        duration_raw=$(echo "$result" | cut -f2)

        # Convert duration to minutes
        duration_sec=$(echo "$duration_raw" | sed 's/s$//' | cut -d'.' -f1)
        if [ -n "$duration_sec" ] && [ "$duration_sec" -gt 0 ] 2>/dev/null; then
            duration_min=$(awk "BEGIN {printf \"%.1f\", $duration_sec/60}")
        else
            duration_min="0.0"
        fi

        # Get task counts
        pending=$(gcloud batch tasks list --job="$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null | grep -c "PENDING" || echo 0)
        running=$(gcloud batch tasks list --job="$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null | grep -c "RUNNING" || echo 0)
        done_count=$(gcloud batch tasks list --job="$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null | grep -c "SUCCEEDED" || echo 0)
        failed=$(gcloud batch tasks list --job="$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null | grep -c "FAILED" || echo 0)

        # Choose symbol based on state
        case "$state" in
            "SUCCEEDED") symbol="✓" ;;
            "RUNNING") symbol="►" ;;
            "FAILED") symbol="✗" ;;
            "QUEUED"|"SCHEDULED") symbol="◷" ;;
            *) symbol="○" ;;
        esac

        printf ">>> %s\n" "$job_id"
        printf "    %s State: %-13s | Runtime: %6.1f min | Pending: %2d | Running: %2d | Done: %2d | Failed: %2d\n" \
            "$symbol" "$state" "$duration_min" "$pending" "$running" "$done_count" "$failed"
        echo ""
    done

    echo "================================================================================"
    echo "Refreshing in 30 seconds... (Ctrl+C to exit)"
    echo "================================================================================"
    sleep 30
done
