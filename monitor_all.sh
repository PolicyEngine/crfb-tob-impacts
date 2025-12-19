#!/bin/bash
# Monitor all running batch jobs - refreshes every 30 seconds
# Only shows RUNNING/SCHEDULED/QUEUED jobs, skips SUCCEEDED/FAILED

JOBS=(
    # Options 3,4,6,7,8 - 10 years each (2026,2030,2040,2050,2060,2070,2080,2090,2095,2100)
    "years-20251218-174929-8lc1s0:Option3-2026"
    "years-20251218-174930-jtbyh5:Option3-rest"
    "years-20251218-174933-pbfj1z:Option4-2026"
    "years-20251218-174934-4frgsx:Option4-rest"
    "years-20251218-174941-obhdzi:Option6-2026"
    "years-20251218-174942-dmu8l7:Option6-rest"
    "years-20251218-174945-2e9vkk:Option7-2026"
    "years-20251218-174946-frsuta:Option7-rest"
    "years-20251218-174949-a3ztma:Option8-2026"
    "years-20251218-174950-y9swaf:Option8-rest"
    # Options 1,2,5 - 10 NEW years each (2028,2033,2038,2043,2048,2053,2058,2063,2085,2095)
    "years-20251218-180133-borbau:Option1-new"
    "years-20251218-180134-7fbolw:Option2-new"
    "years-20251218-180135-k6jej3:Option5-new"
    # Option 1 - remaining 50 years (all 75 years complete)
    "years-20251218-192027-p96n66:Option1-50yrs"
    # Option 2 - remaining 56 years (all 75 years complete)
    "years-20251218-192522-biik5k:Option2-56yrs"
    # Option 3 - remaining 65 years (all 75 years complete)
    "years-20251218-192807-8ri66o:Option3-65yrs"
    # Option 4 - remaining 65 years (all 75 years complete)
    "years-20251218-193249-b30jin:Option4-65yrs"
    # Option 2 - missing year 2045
    "years-20251218-202000-amr4e0:Option2-2045"
    # Option 5 - remaining 60 years (all 75 years complete)
    "years-20251218-202050-yr65vh:Option5-60yrs"
    # Option 6 - remaining 65 years (all 75 years complete)
    "years-20251218-202051-y3c4fg:Option6-65yrs"
    # Option 7 - remaining 65 years (all 75 years complete)
    "years-20251218-202052-f7dncw:Option7-65yrs"
    # Option 8 - remaining 65 years (all 75 years complete)
    "years-20251218-202054-7qpqqw:Option8-65yrs"
    # Dynamic scoring - Options 1-4 (75 years each)
    "years-20251218-221445-hjhfp6:Option1-dyn"
    "years-20251218-221450-thsgeh:Option2-dyn"
    "years-20251218-221455-f1xff9:Option3-dyn"
    "years-20251218-221458-lpf1rv:Option4-dyn"
    # Dynamic scoring - Options 5-8 (75 years each)
    "years-20251219-094048-v55a04:Option5-dyn"
    "years-20251219-094052-db1o22:Option6-dyn"
    "years-20251219-094055-r5koh6:Option7-dyn"
    "years-20251219-094058-vw22re:Option8-dyn"
)
# no-h6 datasets test run

completed=0
running_jobs=0

while true; do
    clear
    echo "================================================================================"
    echo "CRFB Batch Jobs Monitor - $(date)"
    echo "================================================================================"
    echo ""

    completed=0
    running_jobs=0
    failed_jobs=0

    for entry in "${JOBS[@]}"; do
        job_id="${entry%%:*}"
        job_name="${entry##*:}"

        # Get job state and duration
        result=$(gcloud batch jobs describe "$job_id" --location=us-central1 --project=policyengine-api --format="value(status.state,status.runDuration)" 2>/dev/null)

        if [ -z "$result" ]; then
            echo ">>> $job_name ($job_id)"
            echo "    ✗ Job not found"
            echo ""
            continue
        fi

        state=$(echo "$result" | cut -f1)
        duration_raw=$(echo "$result" | cut -f2)

        # Count completed/failed jobs
        if [ "$state" = "SUCCEEDED" ]; then
            completed=$((completed + 1))
            continue  # Skip showing completed jobs
        elif [ "$state" = "FAILED" ]; then
            failed_jobs=$((failed_jobs + 1))
        fi

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

        running_jobs=$((running_jobs + 1))

        # Choose symbol based on state
        case "$state" in
            "RUNNING") symbol="►" ;;
            "FAILED") symbol="✗" ;;
            "QUEUED"|"SCHEDULED") symbol="◷" ;;
            *) symbol="○" ;;
        esac

        printf ">>> %-15s %s\n" "$job_name" "$job_id"
        printf "    %s State: %-13s | Runtime: %6.1f min | Pending: %2d | Running: %2d | Done: %2d | Failed: %2d\n" \
            "$symbol" "$state" "$duration_min" "$pending" "$running" "$done_count" "$failed"
        echo ""
    done

    echo "================================================================================"
    echo "Summary: $completed completed | $running_jobs active | $failed_jobs failed"
    if [ "$running_jobs" -eq 0 ]; then
        echo "All jobs finished! Run: cd results/no_h6_test && ./download_and_combine.sh"
    else
        echo "Refreshing in 30 seconds... (Ctrl+C to exit)"
    fi
    echo "================================================================================"

    [ "$running_jobs" -eq 0 ] && break
    sleep 30
done
