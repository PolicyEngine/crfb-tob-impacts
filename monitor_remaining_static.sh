#!/bin/bash

while true; do
  clear
  echo "=== Remaining Static Jobs Status ==="
  date
  echo ""

  echo "Option 8 (2026-2027): $(gcloud batch jobs describe years-20251124-074955-0h29hb --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 8 (2028-2100): $(gcloud batch jobs describe years-20251124-074957-boggn1 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"

  status=$(gcloud batch jobs describe years-20251124-074957-boggn1 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)

  echo ""
  if [[ "$status" == "SUCCEEDED" ]]; then
    echo "✓ Option 8 COMPLETE!"
    echo ""
    echo "Download with:"
    echo "  mkdir -p results/option8_static_final"
    echo "  gsutil -m cp 'gs://crfb-ss-analysis-results/results/years-20251124-074955-0h29hb/*.csv' results/option8_static_final/"
    echo "  gsutil -m cp 'gs://crfb-ss-analysis-results/results/years-20251124-074957-boggn1/*.csv' results/option8_static_final/"
    break
  elif [[ "$status" == "FAILED" ]]; then
    echo "✗ Option 8 job FAILED"
    break
  else
    echo "Job still running... (will refresh in 30 seconds)"
    echo "Press Ctrl+C to stop monitoring"
  fi

  sleep 30
done

echo ""
echo "Monitoring stopped."
