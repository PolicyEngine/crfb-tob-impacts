#!/bin/bash
#
# Combine all year CSVs into 2 final files (static and dynamic)
#
# Usage: ./combine_results.sh <reform_name> <job_ids...>
# Example: ./combine_results.sh option3 years-20251101-010116-uwtkfv years-20251101-010118-sxyrk4

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <reform_name> <job_id1> [job_id2] [job_id3] ..."
    echo ""
    echo "Example:"
    echo "  $0 option3 years-20251101-010116-uwtkfv years-20251101-010118-sxyrk4"
    echo ""
    echo "This will download and combine all CSVs from the specified jobs"
    echo "into 2 final files: {reform}_static_results.csv and {reform}_dynamic_results.csv"
    exit 1
fi

REFORM=$1
shift
JOB_IDS=("$@")

BUCKET="gs://crfb-ss-analysis-results"
TEMP_DIR="temp_results_$$"

echo "================================================================================"
echo "COMBINING RESULTS FOR $REFORM"
echo "================================================================================"
echo "Job IDs: ${JOB_IDS[@]}"
echo "Bucket: $BUCKET"
echo "================================================================================"
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"

# Download all CSVs from all job IDs
echo "📥 Downloading CSVs from Cloud Storage..."
for JOB_ID in "${JOB_IDS[@]}"; do
    echo "  Downloading from $JOB_ID..."
    gsutil -m cp -r "$BUCKET/results/$JOB_ID/*.csv" "$TEMP_DIR/" 2>/dev/null || echo "    (No files found for $JOB_ID)"
done
echo ""

# Combine static results
STATIC_FILE="${REFORM}_static_results.csv"
if ls "$TEMP_DIR"/*_${REFORM}_static_results.csv 1> /dev/null 2>&1; then
    echo "📊 Combining static scoring results..."

    # Write header
    echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$STATIC_FILE"

    # Append all data (skip headers)
    for file in "$TEMP_DIR"/*_${REFORM}_static_results.csv; do
        tail -n +2 "$file" >> "$STATIC_FILE"
    done

    # Sort by year
    (head -n 1 "$STATIC_FILE" && tail -n +2 "$STATIC_FILE" | sort -t',' -k2 -n) > "${STATIC_FILE}.tmp"
    mv "${STATIC_FILE}.tmp" "$STATIC_FILE"

    STATIC_COUNT=$(tail -n +2 "$STATIC_FILE" | wc -l | tr -d ' ')
    echo "  ✓ Combined $STATIC_COUNT years into $STATIC_FILE"
else
    echo "  ℹ️  No static results found"
fi
echo ""

# Combine dynamic results
DYNAMIC_FILE="${REFORM}_dynamic_results.csv"
if ls "$TEMP_DIR"/*_${REFORM}_dynamic_results.csv 1> /dev/null 2>&1; then
    echo "📊 Combining dynamic scoring results..."

    # Write header
    echo "reform_name,year,baseline_revenue,reform_revenue,revenue_impact,scoring_type" > "$DYNAMIC_FILE"

    # Append all data (skip headers)
    for file in "$TEMP_DIR"/*_${REFORM}_dynamic_results.csv; do
        tail -n +2 "$file" >> "$DYNAMIC_FILE"
    done

    # Sort by year
    (head -n 1 "$DYNAMIC_FILE" && tail -n +2 "$DYNAMIC_FILE" | sort -t',' -k2 -n) > "${DYNAMIC_FILE}.tmp"
    mv "${DYNAMIC_FILE}.tmp" "$DYNAMIC_FILE"

    DYNAMIC_COUNT=$(tail -n +2 "$DYNAMIC_FILE" | wc -l | tr -d ' ')
    echo "  ✓ Combined $DYNAMIC_COUNT years into $DYNAMIC_FILE"
else
    echo "  ℹ️  No dynamic results found"
fi
echo ""

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "================================================================================"
echo "✅ RESULTS COMBINED"
echo "================================================================================"
if [ -f "$STATIC_FILE" ]; then
    echo "Static:  $STATIC_FILE ($STATIC_COUNT years)"
fi
if [ -f "$DYNAMIC_FILE" ]; then
    echo "Dynamic: $DYNAMIC_FILE ($DYNAMIC_COUNT years)"
fi
echo "================================================================================"
