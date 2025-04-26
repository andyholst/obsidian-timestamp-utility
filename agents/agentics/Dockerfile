FROM python:3.10-slim AS builder

RUN pip install pip-tools

WORKDIR /app

COPY requirements.in .

RUN pip-compile requirements.in -o requirements.txt

FROM python:3.10-slim

WORKDIR /app

COPY --from=builder /app/requirements.txt .

RUN pip install -r requirements.txt

COPY src/agentics.py .

CMD ["python", "agentics.py"]
