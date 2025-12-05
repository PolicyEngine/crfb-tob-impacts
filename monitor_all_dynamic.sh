#!/bin/bash

while true; do
  clear
  echo "=== Dynamic Jobs Status ==="
  date
  echo ""

  echo "Option 1 (2026-2027): $(gcloud batch jobs describe years-20251124-081439-odpypb --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 1 (2028-2100): $(gcloud batch jobs describe years-20251124-081442-kgm5qv --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 2 (2026-2027): $(gcloud batch jobs describe years-20251124-081445-s7oyhq --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 2 (2028-2100): $(gcloud batch jobs describe years-20251124-081448-h0mv2b --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 3 (2026-2027): $(gcloud batch jobs describe years-20251124-081451-b0q0ho --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 3 (2028-2100): $(gcloud batch jobs describe years-20251124-081453-hqtq05 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 4 (2026-2027): $(gcloud batch jobs describe years-20251124-081456-n47wg4 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 4 (2028-2100): $(gcloud batch jobs describe years-20251124-081459-rzr6wo --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 5 (2026-2027): $(gcloud batch jobs describe years-20251124-081514-bhhttd --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 5 (2028-2100): $(gcloud batch jobs describe years-20251124-081516-8fios5 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 6 (2026-2027): $(gcloud batch jobs describe years-20251124-081519-0f0l3i --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 6 (2028-2100): $(gcloud batch jobs describe years-20251124-081521-05661s --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 7 (2026-2027): $(gcloud batch jobs describe years-20251124-081524-ka672b --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 7 (2028-2100): $(gcloud batch jobs describe years-20251124-081526-brf4ur --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 8 (2026-2027): $(gcloud batch jobs describe years-20251124-081529-gc3tg3 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 8 (2028-2100): $(gcloud batch jobs describe years-20251124-081532-w1qplp --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
  sleep 30
done
