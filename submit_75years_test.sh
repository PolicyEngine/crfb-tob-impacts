#!/bin/bash
# Test year-parallel with 75 years, 1 reform only
YEARS=$(seq -s',' 2026 2100)
/usr/bin/python3 batch/submit_years.py \
  --years "$YEARS" \
  --reforms option1 \
  --scoring static \
  --bucket crfb-ss-analysis-results 2>&1 | grep -v "FutureWarning\|NotOpenSSLWarning\|urllib3\|warnings\|ssl\|packages_distributions"
