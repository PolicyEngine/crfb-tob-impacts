#!/bin/bash

# Monitor all 8 static option jobs
declare -A JOBS_2026_2027=(
  ["option1"]="years-20251124-074653-u1alo2"
  ["option2"]="years-20251124-074807-ma4df0"
  ["option3"]="years-20251124-074842-ju2p43"
  ["option4"]="years-20251124-074923-zz8gbx"
  ["option5"]="years-20251124-074939-zxjm93"
  ["option6"]="years-20251124-074944-i82i02"
  ["option7"]="years-20251124-074949-9eamtq"
  ["option8"]="years-20251124-074955-0h29hb"
)

declare -A JOBS_2028_2100=(
  ["option1"]="years-20251124-074658-7yyiez"
  ["option2"]="years-20251124-074809-hrp7l8"
  ["option3"]="years-20251124-074845-pflh3b"
  ["option4"]="years-20251124-074926-ffmr1b"
  ["option5"]="years-20251124-074942-59n2r1"
  ["option6"]="years-20251124-074947-8vpuba"
  ["option7"]="years-20251124-074952-my8jps"
  ["option8"]="years-20251124-074957-boggn1"
)

echo "=== Monitoring All Static Options ==="
echo ""

while true; do
  clear
  echo "=== ALL STATIC OPTIONS - Job Status ==="
  echo "Last updated: $(date)"
  echo ""

  completed_count=0
  failed_count=0
  running_count=0

  for option in option1 option2 option3 option4 option5 option6 option7 option8; do
    job1="${JOBS_2026_2027[$option]}"
    job2="${JOBS_2028_2100[$option]}"

    status1=$(gcloud batch jobs describe $job1 --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null || echo "ERROR")
    status2=$(gcloud batch jobs describe $job2 --location=us-central1 --project=policyengine-api --format="value(status.state)" 2>/dev/null || echo "ERROR")

    printf "%-10s" "$option:"

    if [[ "$status1" == "SUCCEEDED" && "$status2" == "SUCCEEDED" ]]; then
      echo " ✓ COMPLETE"
      ((completed_count++))
    elif [[ "$status1" == "FAILED" || "$status2" == "FAILED" ]]; then
      echo " ✗ FAILED"
      ((failed_count++))
    elif [[ "$status1" == "RUNNING" || "$status2" == "RUNNING" ]]; then
      echo " ⟳ RUNNING ($status1 / $status2)"
      ((running_count++))
    else
      echo " ⋯ QUEUED ($status1 / $status2)"
    fi
  done

  echo ""
  echo "=== Summary ==="
  echo "Completed: $completed_count/8"
  echo "Running:   $running_count/8"
  echo "Failed:    $failed_count/8"
  echo ""

  if [[ $completed_count -eq 8 ]]; then
    echo "✓ ALL STATIC OPTIONS COMPLETE!"
    break
  elif [[ $failed_count -gt 0 ]]; then
    echo "⚠ Some jobs have failed - check logs"
  else
    echo "Jobs still running... (will refresh in 30 seconds)"
    echo "Press Ctrl+C to stop monitoring"
  fi

  sleep 30
done

echo ""
echo "Monitoring stopped."
