#!/bin/bash

# Monitor Option 2 Static jobs
JOB1="years-20251124-074807-ma4df0"  # 2026-2027
JOB2="years-20251124-074809-hrp7l8"  # 2028-2100

echo "=== Monitoring Option 2 Static Jobs ==="
echo ""

while true; do
  clear
  echo "=== Option 2 Static - Job Status ==="
  echo "Last updated: $(date)"
  echo ""

  # Job 1: 2026-2027
  echo "Job 1 (2026-2027): $JOB1"
  status1=$(gcloud batch jobs describe $JOB1 --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null || echo "ERROR")
  duration1=$(gcloud batch jobs describe $JOB1 --location=us-central1 --project=policyengine-api --format="value(status.runDuration)" 2>/dev/null || echo "N/A")
  echo "  Status: $status1"
  echo "  Duration: $duration1"

  # Check for CSV files
  csv_count1=$(gsutil ls gs://crfb-ss-analysis-results/results/$JOB1/*.csv 2>/dev/null | wc -l)
  echo "  CSV files: $csv_count1"

  echo ""

  # Job 2: 2028-2100
  echo "Job 2 (2028-2100): $JOB2"
  status2=$(gcloud batch jobs describe $JOB2 --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null || echo "ERROR")
  duration2=$(gcloud batch jobs describe $JOB2 --location=us-central1 --project=policyengine-api --format="value(status.runDuration)" 2>/dev/null || echo "N/A")
  echo "  Status: $status2"
  echo "  Duration: $duration2"

  # Check for CSV files
  csv_count2=$(gsutil ls gs://crfb-ss-analysis-results/results/$JOB2/*.csv 2>/dev/null | wc -l)
  echo "  CSV files: $csv_count2"

  echo ""
  echo "=== Summary ==="
  if [[ "$status1" == "SUCCEEDED" && "$status2" == "SUCCEEDED" ]]; then
    echo "✓ Both jobs COMPLETE!"
    echo ""
    echo "Download results with:"
    echo "  gsutil -m cp gs://crfb-ss-analysis-results/results/$JOB1/*.csv results/option2_static_temp/"
    echo "  gsutil -m cp gs://crfb-ss-analysis-results/results/$JOB2/*.csv results/option2_static_temp/"
    break
  elif [[ "$status1" == "FAILED" || "$status2" == "FAILED" ]]; then
    echo "✗ One or more jobs FAILED"
    break
  else
    echo "Jobs still running... (will refresh in 30 seconds)"
    echo "Press Ctrl+C to stop monitoring"
  fi

  sleep 30
done

echo ""
echo "Monitoring stopped."
