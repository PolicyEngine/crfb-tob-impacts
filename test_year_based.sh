#!/bin/bash
# Test the year-based architecture with 2 years × 4 reforms = 2 parallel tasks
#
# Expected performance:
# - Each year task: ~26 minutes (for 8 reforms)
# - 2 years in parallel: ~26 minutes total wall time
# - Memory: ~16GB per task

cd "$(dirname "$0")"

echo "================================="
echo "TESTING YEAR-BASED ARCHITECTURE"
echo "================================="
echo ""
echo "This will submit 2 parallel tasks:"
echo "  - Task 0: Year 2026 with 4 reforms"
echo "  - Task 1: Year 2027 with 4 reforms"
echo ""
echo "Expected: ~7 minutes per year (4 reforms @ ~3.3 min each + 14s baseline)"
echo "Wall time: ~7 minutes (parallel execution)"
echo ""

python3 batch/submit_years.py \
  --years 2026,2027 \
  --reforms option1,option2,option3,option4 \
  --scoring static \
  --bucket crfb-ss-analysis-results

echo ""
echo "Monitor with:"
echo "  gcloud batch jobs list --location=us-central1"
echo "  gcloud logging read 'resource.labels.job_uid:\"years-\"' --freshness=30m --format='value(textPayload)' | grep -E '(YEAR-BASED|baseline|Reform revenue|Impact|COMPLETE)'"
