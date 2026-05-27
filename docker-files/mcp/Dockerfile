FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir aiohttp

WORKDIR /app

COPY mcp_bridge.py /app/mcp_bridge.py
RUN chmod +x /app/mcp_bridge.py

EXPOSE 3003

CMD ["python3", "/app/mcp_bridge.py"]
