FROM python:3.10-slim AS base

# Install Node.js 22.x and npm
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    node --version && npm --version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

FROM base

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf ~/.cache/pip

WORKDIR /app
