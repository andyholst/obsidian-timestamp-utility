FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ticket_interpreter.py .

CMD ["python", "ticket_interpreter.py"]
