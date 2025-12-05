#!/bin/bash

while true; do
  clear
  echo "=== Option 8 Dynamic Jobs Status ==="
  date
  echo ""

  echo "Option 8 (2026-2027): $(gcloud batch jobs describe years-20251124-081529-gc3tg3 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 8 (2028-2100): $(gcloud batch jobs describe years-20251124-081532-w1qplp --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"

  status=$(gcloud batch jobs describe years-20251124-081532-w1qplp --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)

  echo ""
  if [[ "$status" == "SUCCEEDED" ]]; then
    echo "✓ Option 8 Dynamic COMPLETE!"
    echo ""
    echo "Download with:"
    echo "  mkdir -p results/option8_dynamic_temp"
    echo "  gsutil -m cp 'gs://crfb-ss-analysis-results/results/years-20251124-081529-gc3tg3/*.csv' results/option8_dynamic_temp/"
    echo "  gsutil -m cp 'gs://crfb-ss-analysis-results/results/years-20251124-081532-w1qplp/*.csv' results/option8_dynamic_temp/"
    break
  elif [[ "$status" == "FAILED" ]]; then
    echo "✗ Option 8 Dynamic job FAILED"
    break
  else
    echo "Job still running... (will refresh in 30 seconds)"
    echo "Press Ctrl+C to stop monitoring"
  fi

  sleep 30
done

echo ""
echo "Monitoring stopped."
