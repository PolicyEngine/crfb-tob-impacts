#!/bin/bash

while true; do
  clear
  echo "=== Static Jobs Status ==="
  date
  echo ""

  echo "Option 1 (2026-2027): $(gcloud batch jobs describe years-20251124-074653-u1alo2 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 1 (2028-2100): $(gcloud batch jobs describe years-20251124-074658-7yyiez --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 2 (2026-2027): $(gcloud batch jobs describe years-20251124-074807-ma4df0 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 2 (2028-2100): $(gcloud batch jobs describe years-20251124-074809-hrp7l8 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 3 (2026-2027): $(gcloud batch jobs describe years-20251124-074842-ju2p43 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 3 (2028-2100): $(gcloud batch jobs describe years-20251124-074845-pflh3b --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 4 (2026-2027): $(gcloud batch jobs describe years-20251124-074923-zz8gbx --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 4 (2028-2100): $(gcloud batch jobs describe years-20251124-074926-ffmr1b --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 5 (2026-2027): $(gcloud batch jobs describe years-20251124-074939-zxjm93 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 5 (2028-2100): $(gcloud batch jobs describe years-20251124-074942-59n2r1 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 6 (2026-2027): $(gcloud batch jobs describe years-20251124-074944-i82i02 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 6 (2028-2100): $(gcloud batch jobs describe years-20251124-074947-8vpuba --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 7 (2026-2027): $(gcloud batch jobs describe years-20251124-074949-9eamtq --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 7 (2028-2100): $(gcloud batch jobs describe years-20251124-074952-my8jps --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Option 8 (2026-2027): $(gcloud batch jobs describe years-20251124-074955-0h29hb --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo "Option 8 (2028-2100): $(gcloud batch jobs describe years-20251124-074957-boggn1 --location=us-central1 --project=policyengine-api --format='value(status.state)' 2>/dev/null)"
  echo ""
  echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
  sleep 30
done
