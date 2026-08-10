FROM python:3.10-slim

RUN pip install pip-tools typing_extensions langgraph langchain-openai openspec-cli

WORKDIR /app

CMD ["pip-compile", "docker-files/pip-requirements/requirements.in", "-o", "agents/agentics/requirements.txt"]
