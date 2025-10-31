#!/bin/bash
# Submit 3-year dynamic test with reform chaining

JOB_ID="years-$(date +%Y%m%d-%H%M%S)-$(openssl rand -hex 3)"
YEARS="2028 2029 2030"
REFORMS="option1 option2 option3 option4 option5 option6 option7 option8"
SCORING="dynamic"
BUCKET="crfb-ss-analysis-results"
PROJECT="policyengine-api"
REGION="us-central1"

echo "================================================================================"
echo "SUBMITTING 3-YEAR DYNAMIC SCORING TEST (WITH REFORM CHAINING)"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Years: 2028, 2029, 2030 (3 years)"
echo "Reforms: option1-option8 (8 reforms)"
echo "Scoring: dynamic"
echo "Container: gcr.io/policyengine-api/ss-calculator:latest"
echo "================================================================================"
echo ""

# Create job JSON
cat > /tmp/batch_job_${JOB_ID}.json << EOF
{
  "taskGroups": [
    {
      "taskCount": 3,
      "parallelism": 3,
      "taskSpec": {
        "runnables": [
          {
            "container": {
              "imageUri": "gcr.io/policyengine-api/ss-calculator:latest",
              "entrypoint": "/bin/bash",
              "commands": [
                "-c",
                "set -e; YEARS=($YEARS); YEAR=\${YEARS[\$BATCH_TASK_INDEX]}; echo \"Task \$BATCH_TASK_INDEX processing year \$YEAR with 8 reforms\"; echo \"=== Starting computation at \$(date) ===\"; python /app/batch/compute_year.py \$YEAR $SCORING $BUCKET $JOB_ID $REFORMS; echo \"=== Finished at \$(date) ===\";"
              ]
            }
          }
        ],
        "maxRetryCount": 1,
        "maxRunDuration": "3600s",
        "computeResource": {
          "cpuMilli": 4000,
          "memoryMib": 32768
        }
      }
    }
  ],
  "allocationPolicy": {
    "instances": [
      {
        "policy": {
          "provisioningModel": "STANDARD",
          "machineType": "e2-highmem-4"
        }
      }
    ],
    "serviceAccount": {
      "email": "${PROJECT}@appspot.gserviceaccount.com"
    }
  },
  "logsPolicy": {
    "destination": "CLOUD_LOGGING"
  },
  "labels": {
    "job_type": "year_based",
    "scoring": "dynamic",
    "test": "reform_chaining"
  }
}
EOF

# Submit the job
echo "Submitting job to Cloud Batch..."
gcloud batch jobs submit $JOB_ID \
  --location=$REGION \
  --config=/tmp/batch_job_${JOB_ID}.json

echo ""
echo "================================================================================"
echo "✓ JOB SUBMITTED"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo ""
echo "Monitor: gcloud batch jobs describe $JOB_ID --location=$REGION"
echo "Results: gs://$BUCKET/results/$JOB_ID/"
echo "================================================================================"
echo ""

# Clean up temp file
rm /tmp/batch_job_${JOB_ID}.json

# Return job ID for monitoring
echo $JOB_ID
