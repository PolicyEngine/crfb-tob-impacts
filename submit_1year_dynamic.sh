#!/bin/bash
# Submit 1-year dynamic test to verify code works

JOB_ID="years-$(date +%Y%m%d-%H%M%S)-$(openssl rand -hex 3)"
YEAR="2028"
REFORMS="option1 option2 option3 option4 option5 option6 option7 option8"
SCORING="dynamic"
BUCKET="crfb-ss-analysis-results"
PROJECT="policyengine-api"
REGION="us-central1"

echo "================================================================================"
echo "SUBMITTING 1-YEAR DYNAMIC SCORING TEST"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Year: 2028 (1 year only)"
echo "Reforms: option1-option8 (8 reforms)"
echo "Scoring: dynamic"
echo "Container: gcr.io/policyengine-api/ss-calculator:latest"
echo "================================================================================"
echo ""

# Create job JSON
cat > /tmp/batch_job_${JOB_ID}.json << 'EOFJ'
{
  "taskGroups": [
    {
      "taskCount": 1,
      "parallelism": 1,
      "taskSpec": {
        "runnables": [
          {
            "container": {
              "imageUri": "gcr.io/policyengine-api/ss-calculator:latest",
              "entrypoint": "/bin/bash",
              "commands": [
                "-c",
                "set -e; echo \"Computing year 2028 with 8 reforms (dynamic scoring)\"; echo \"=== Starting at $(date) ===\"; python /app/batch/compute_year.py 2028 dynamic crfb-ss-analysis-results JOBID option1 option2 option3 option4 option5 option6 option7 option8; echo \"=== Finished at $(date) ===\";"
              ]
            }
          }
        ],
        "maxRetryCount": 0,
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
      "email": "policyengine-api@appspot.gserviceaccount.com"
    }
  },
  "logsPolicy": {
    "destination": "CLOUD_LOGGING"
  },
  "labels": {
    "job_type": "year_based",
    "scoring": "dynamic",
    "test": "1year_direct"
  }
}
EOFJ

# Replace JOBID placeholder
sed -i '' "s/JOBID/$JOB_ID/g" /tmp/batch_job_${JOB_ID}.json

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
