#!/bin/bash
# Submit static scoring with full parallelization for all options (1-8)
# Uses us-central1 region

YEARS=$(python3 -c "print(','.join(map(str, range(2026, 2101))))")
/usr/bin/python3 batch/submit_years_parallel.py \
  --years "$YEARS" \
  --reforms option1,option2,option3,option4,option5,option6,option7,option8 \
  --scoring static \
  --region us-central1 \
  --bucket crfb-ss-analysis-results 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl\|packages_distributions"
