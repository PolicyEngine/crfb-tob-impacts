#!/bin/bash
# Test memory limits by trying different numbers of reforms per task

echo "================================================================================"
echo "MEMORY LIMIT TESTING"
echo "================================================================================"
echo "Goal: Find maximum reforms per year that fits in 16GB RAM"
echo ""
echo "Known:"
echo "  ✗ 1 reform/year = OOM (just tested)"
echo "  ✓ 8 reforms/year = Works (proven)"
echo ""
echo "Testing: 2, 4 reforms/year to find the boundary"
echo "================================================================================"
echo ""

# Test 4 reforms/year (midpoint)
echo "=== TEST 1: 4 reforms (option1-4) ==="
/usr/bin/python3 batch/test_single_task.py 2026 "option1 option2 option3 option4" static 2>&1 | grep -v "FutureWarning\|ssl\|packages_distributions" | grep "Job ID\|✓"

# Wait a bit for job to queue
sleep 5

# Get the job ID from the log
JOB_ID_4=$(grep "Job ID:" /tmp/test_submission.log 2>/dev/null | tail -1 | awk '{print $3}')

echo ""
echo "Job submitted: $JOB_ID_4"
echo "This will take ~5-10 minutes to complete or fail"
echo ""
echo "Monitor with: ./monitor_test.sh $JOB_ID_4"
echo ""
echo "After this test completes, we'll know if 4 reforms fits in 16GB."
echo "Then we can test 2 or 6 reforms depending on the result."
