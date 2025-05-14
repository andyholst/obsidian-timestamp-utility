FROM python:3.10-slim

WORKDIR /app

# Install Node.js 22.x and npm
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    node --version && npm --version

COPY requirements.txt .

RUN pip install -r requirements.txt
