# Container definitions for the Obsidian Timestamp Utility project.
#
# Each container lives in its own directory under `containers/` with its own Dockerfile:
#   containers/npm/Dockerfile      - Node 22 build/test image for the plugin (npm run build / jest)
#   containers/agents/Dockerfile   - Python LangGraph agentic pipeline image
#   containers/pip/Dockerfile      - pip-compile requirements resolver
#
# These replace the previous Dagger-based execution. All build/test/lint/agentic
# Makefile targets run via `docker compose` against `docker-compose-files/*.yaml`,
# which build from these container Dockerfiles. No Dagger, no MCP.
