# pip-requirements resolver container (pip-compile).
FROM python:3.10-slim

RUN pip install pip-tools

WORKDIR /app

CMD ["pip-compile", "docker-files/pip-requirements/requirements.in", "-o", "docker-files/pip-requirements/requirements.txt"]
