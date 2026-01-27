# Jim Cramer Advice Service Dockerfile
# Runs daily at 9 AM PST to crawl and analyze Jim Cramer content

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared ML services dependencies
COPY ../requirements.txt /app/ml-requirements.txt
RUN pip install --no-cache-dir -r /app/ml-requirements.txt || true

# Copy service code
COPY . /app/jim_cramer_service/

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default to scheduled mode
CMD ["python", "-m", "jim_cramer_service.service", "--schedule"]
