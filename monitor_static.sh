#!/bin/bash
# Monitor Option 1-8 Static jobs

PROJECT="policyengine-api"

# Option 1
OPT1_JOB1="years-20251204-164800-hopzx8"
OPT1_JOB2="years-20251204-172759-ut2sgo"

# Option 2
OPT2_JOB1="years-20251204-165124-9sqy9i"
OPT2_JOB2="years-20251204-172808-6ffmj8"

# Option 3
OPT3_JOB1="years-20251204-165236-ftreu4"
OPT3_JOB2="years-20251204-172953-siqhuq"

# Option 4
OPT4_JOB1="years-20251204-165350-cok8dp"
OPT4_JOB2="years-20251204-173011-lff1g4"

# Option 5
OPT5_JOB1="years-20251204-165401-e3vxdb"
OPT5_JOB2="years-20251204-173020-sp1q5s"

# Option 6
OPT6_JOB1="years-20251204-165410-7qdmdv"
OPT6_JOB2="years-20251204-173028-bx80mr"

# Option 7
OPT7_JOB1="years-20251204-165420-dbkued"
OPT7_JOB2="years-20251204-173036-l7kt6f"

# Option 8
OPT8_JOB1="years-20251204-165428-2nkz6y"
OPT8_JOB2="years-20251204-173044-d9c3vc"

while true; do
    clear
    echo "========================================"
    echo "STATIC JOBS - $(date)"
    echo "========================================"

    for OPT in 1 2 3 4 5 6 7 8; do
        eval "JOB1=\$OPT${OPT}_JOB1"
        eval "JOB2=\$OPT${OPT}_JOB2"
        
        echo ""
        echo "=== OPTION $OPT ==="
        STATE1=$(gcloud batch jobs describe $JOB1 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null || echo "UNKNOWN")
        STATE2=$(gcloud batch jobs describe $JOB2 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null || echo "UNKNOWN")
        
        TASKS1=$(gcloud batch tasks list --job=$JOB1 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
        SUCC1=$(echo "$TASKS1" | grep -c "SUCCEEDED" || echo 0)
        RUN1=$(echo "$TASKS1" | grep -c "RUNNING" || echo 0)
        FAIL1=$(echo "$TASKS1" | grep -c "FAILED" || echo 0)
        
        TASKS2=$(gcloud batch tasks list --job=$JOB2 --location=us-central1 --project=$PROJECT --format="value(status.state)" 2>/dev/null)
        SUCC2=$(echo "$TASKS2" | grep -c "SUCCEEDED" || echo 0)
        RUN2=$(echo "$TASKS2" | grep -c "RUNNING" || echo 0)
        FAIL2=$(echo "$TASKS2" | grep -c "FAILED" || echo 0)
        
        echo "  Job1 (2026-27, 64GB): $STATE1 | $SUCC1 succ, $RUN1 run, $FAIL1 fail (of 2)"
        echo "  Job2 (2028-2100, 64GB): $STATE2 | $SUCC2 succ, $RUN2 run, $FAIL2 fail (of 73)"
    done

    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
