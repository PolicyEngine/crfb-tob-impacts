#!/bin/bash
# Submit option5 for 75 years (2026-2100) DYNAMIC scoring
YEARS=$(python3 -c "print(','.join(map(str, range(2026, 2101))))")
/usr/bin/python3 batch/submit_years.py \
  --years "$YEARS" \
  --reforms option5 \
  --scoring dynamic \
  --bucket crfb-ss-analysis-results 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl\|packages_distributions"
