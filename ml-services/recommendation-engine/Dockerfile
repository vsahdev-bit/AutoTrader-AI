# Recommendation Engine Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the recommendation engine source
COPY src/ /app/

# Copy streaming connectors (needed for data fetching)
COPY ../../streaming /app/streaming

# Copy vault client
COPY ../vault_client.py /app/

# Set Python path
ENV PYTHONPATH="/app:/app/streaming"

# Run the recommendation service
CMD ["python", "recommendation_flow.py"]
