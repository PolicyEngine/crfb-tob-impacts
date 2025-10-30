FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY batch/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (will be available when we build from parent directory)
COPY src/ /app/src/

# Copy batch worker scripts
COPY batch/compute_baseline.py batch/compute_reform.py /app/

# Make scripts executable
RUN chmod +x /app/compute_baseline.py /app/compute_reform.py

# Pre-download and cache datasets for 2026-2027 to eliminate runtime downloads
# This makes containers start INSTANTLY instead of downloading at runtime
ENV PYTHONPATH=/app/src
RUN python3 -c "import os; os.environ['POLICYENGINE_GITHUB_MICRODATA_AUTH_TOKEN']=''; from policyengine_us import Microsimulation; print('Caching datasets...'); [Microsimulation(dataset=f'hf://policyengine/test/{year}.h5') for year in [2026, 2027]]; print('Datasets cached!')"

# Set Python to run in unbuffered mode (see output in real-time)
ENV PYTHONUNBUFFERED=1

# Default command (will be overridden by Cloud Batch)
CMD ["python", "--version"]
