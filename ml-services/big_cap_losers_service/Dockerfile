FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

# Expose the HTTP server port
EXPOSE 8001

# Run the service with HTTP server enabled
# This allows the API gateway to trigger refreshes via HTTP
CMD ["python", "service.py", "--http"]
