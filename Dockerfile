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

# Copy local policyengine-us with TOB variables and install from source
COPY policyengine-us/ /app/policyengine-us/
RUN pip install --no-cache-dir /app/policyengine-us/

# Copy source code (will be available when we build from parent directory)
COPY src/ /app/src/

# Copy data files (for Option 13 HI expenditures, etc.)
COPY data/ /app/data/

# Copy batch worker scripts
COPY batch/compute_year.py /app/batch/

# Make scripts executable
RUN chmod +x /app/batch/compute_year.py

# Set PYTHONPATH for imports
ENV PYTHONPATH=/app/src

# NOTE: Dataset pre-caching was causing OOM issues in cloud (28GB+ RAM usage)
# even though local execution only uses 0.9GB. Letting datasets download at runtime instead.
# Each dataset download adds ~30-60 seconds but avoids the memory issue.

# Set Python to run in unbuffered mode (see output in real-time)
ENV PYTHONUNBUFFERED=1

# Default command (will be overridden by Cloud Batch)
CMD ["python", "--version"]
