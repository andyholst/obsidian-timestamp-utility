# Python agentic pipeline container (LangGraph code-generation workflow).
# Restored from the last working version (commit 2f5e08e): python:3.10-slim base,
# not the nvidia/cuda base that introduced a pip resolution conflict.
# Build context is the repo root.
FROM python:3.10-slim AS base

# Install Node.js 22.x and npm
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs git && \
    node --version && npm --version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install TypeScript globally for use by agents that require it
RUN npm install -g typescript

# Install git-chglog (used by `make changelog` / `make release-flow` to regenerate CHANGELOG.md).
# Must be present in THIS image because the changelog target runs in unit-test-agents (image `agentics`).
RUN curl -sL --retry 3 -o git-chglog.tar.gz https://github.com/git-chglog/git-chglog/releases/download/v0.15.4/git-chglog_0.15.4_linux_amd64.tar.gz || { echo "curl failed to download git-chglog"; exit 1; } && \
    [ $(stat -c %s git-chglog.tar.gz) -gt 1000000 ] || { echo "git-chglog.tar.gz too small, likely corrupted"; ls -l git-chglog.tar.gz; exit 1; } && \
    tar xzf git-chglog.tar.gz || { echo "tar failed to extract git-chglog.tar.gz"; exit 1; } && \
    mv git-chglog /usr/local/bin/ && \
    chmod +x /usr/local/bin/git-chglog && \
    rm git-chglog.tar.gz && \
    git-chglog --version || { echo "git-chglog install failed"; exit 1; }


FROM base

ARG HOST_UID=1000
ARG HOST_GID=1000

# Copy and install Python requirements
COPY agents/agentics/requirements.txt ./agents/agentics/requirements.txt
RUN pip install --no-cache-dir -r agents/agentics/requirements.txt && \
    rm -rf ~/.cache/pip && \
    mkdir -p /tmp/.cache/huggingface && \
    chown -R ${HOST_UID}:${HOST_GID} /tmp/.cache/huggingface
ENV HF_HOME=/tmp/.cache/huggingface
ENV TRANSFORMERS_CACHE=/tmp/.cache/huggingface

WORKDIR /app

# Create non-root user with home directory
RUN groupadd -r appgroup -g ${HOST_GID} && useradd -r -u ${HOST_UID} -g appgroup -m -d /home/appuser appuser

# Set ownership of /app and home to appuser
RUN chown -R appuser:appgroup /app /home/appuser

# HOME=/home/appuser for proper environment setup
ENV HOME=/home/appuser

# Switch to non-root user
USER appuser
