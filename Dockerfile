FROM python:3.10-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Set up virtual environment and install dependencies
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install wheel setuptools && \
    /opt/venv/bin/pip install -v --no-cache-dir -r requirements.txt

# Second stage to reduce image size
FROM python:3.10-slim

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Make sure we use the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Make run script executable
RUN chmod +x run.sh

EXPOSE 8000

CMD ["./run.sh"]
