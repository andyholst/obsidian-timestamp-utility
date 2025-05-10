FROM python:3.10-slim

RUN pip install pip-tools

WORKDIR /app

CMD ["pip-compile", "requirements.in", "-o", "requirements.txt"]
