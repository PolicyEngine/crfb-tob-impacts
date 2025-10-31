#!/bin/bash
# Submit 75-year static scoring for ALL options (1-8) - MAIN PRODUCTION RUN

YEARS=$(python3 -c "print(','.join(map(str, range(2026, 2101))))")
/usr/bin/python3 batch/submit_years.py \
  --years "$YEARS" \
  --reforms option1,option2,option3,option4,option5,option6,option7,option8 \
  --scoring static \
  --bucket crfb-ss-analysis-results 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl\|packages_distributions"
