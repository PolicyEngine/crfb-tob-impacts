#!/bin/bash
JOB_ID="years-20251031-143409-4e5vco"

echo "Monitoring 1-year dynamic test (submitted via Python API - same as working static)"
echo "Job ID: $JOB_ID"
echo ""

for i in {1..15}; do
  echo "=== CHECK #$i - $(date '+%H:%M:%S') ==="
  STATE=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.state)" 2>/dev/null)
  DURATION=$(gcloud batch jobs describe $JOB_ID --location=us-central1 --format="value(status.runDuration)" 2>/dev/null | sed 's/s$//')
  TASK_STATE=$(gcloud batch tasks list --location=us-central1 --job=$JOB_ID --format="value(status.state)" 2>/dev/null | head -1)
  
  if [ -n "$DURATION" ]; then
    MINUTES=$(echo "$DURATION" | awk '{print int($1/60)}')
    SECS=$(echo "$DURATION" | awk '{print int($1%60)}')
    echo "Job: $STATE (${MINUTES}m ${SECS}s) | Task: $TASK_STATE"
  else
    echo "Job: $STATE | Task: $TASK_STATE"
  fi
  
  gsutil ls "gs://crfb-ss-analysis-results/results/$JOB_ID/" 2>/dev/null && echo "✓ Results file exists!"
  
  echo ""
  
  if [ "$STATE" = "SUCCEEDED" ] || [ "$STATE" = "FAILED" ]; then
    echo "✓ JOB FINISHED: $STATE"
    if [ "$STATE" = "SUCCEEDED" ]; then
      echo "Downloading results..."
      gsutil cp "gs://crfb-ss-analysis-results/results/$JOB_ID/*.csv" . 2>/dev/null
    else
      echo "Fetching logs..."
      gcloud logging read "resource.type=batch.googleapis.com/Job AND resource.labels.job_uid=$JOB_ID" --limit=100 --format="value(textPayload)" --freshness=15m 2>/dev/null | grep -v "^$"
    fi
    break
  fi
  
  sleep 20
done
