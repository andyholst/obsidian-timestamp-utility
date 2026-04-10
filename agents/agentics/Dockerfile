FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04 AS base

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    gnupg && ln -sf /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs git && \
    node --version && npm --version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*



# Install TypeScript globally for use agents that require it
RUN npm install -g typescript

FROM base

ARG HOST_UID=1000
ARG HOST_GID=1000
ARG CACHE_BUST=1

# Copy and install Python requirements
COPY requirements.txt .
RUN echo "Cache bust: ${CACHE_BUST}" && pip install --no-cache-dir -r requirements.txt && \
    rm -rf ~/.cache/pip && \
    mkdir -p /tmp/.cache/huggingface && \
    chown -R ${HOST_UID}:${HOST_GID} /tmp/.cache/huggingface
ENV HF_HOME=/tmp/.cache/huggingface
ENV TRANSFORMERS_CACHE=/tmp/.cache/huggingface

WORKDIR /app
# CACHE_BUST must be declared before COPY to invalidate the COPY layer when it changes
ARG CACHE_BUST
RUN echo "Source cache bust: ${CACHE_BUST}"
COPY . /app/

# Create non-root user
RUN groupadd -r appgroup -g ${HOST_GID} && useradd -r -u ${HOST_UID} -g appgroup appuser

# Set ownership of /app to appuser
RUN chown -R appuser:appgroup /app && mkdir -p /home/appuser/.npm && chown -R appuser:appgroup /home/appuser/.npm

# Switch to non-root user

USER appuser
