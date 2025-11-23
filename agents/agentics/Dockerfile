FROM python:3.10-slim AS base

# Install Node.js 22.x and npm
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    node --version && npm --version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install TypeScript globally for use agents that require it
RUN npm install -g typescript

FROM base

ARG HOST_UID=1000
ARG HOST_GID=1000

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf ~/.cache/pip

WORKDIR /app

# Create non-root user
RUN groupadd -r appgroup -g ${HOST_GID} && useradd -r -u ${HOST_UID} -g appgroup appuser

# Set ownership of /app to appuser
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser
