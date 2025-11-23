# MCP Integration for Agentic System

## Overview

MCP (Model Context Protocol) servers are fully integrated with your LangChain and Ollama agents, providing enhanced context and memory capabilities:

- **context7**: Contextual information retrieval that enhances LLM understanding of development tasks
- **memory**: Persistent key-value storage for agent feedback and learning

### Integration Points

- **ProcessLLMAgent**: Uses context7 to retrieve relevant context before LLM processing
- **FeedbackAgent**: Stores metrics in memory server for continuous improvement
- **LangChain Tools**: MCP tools available for advanced agent capabilities

## Configuration

The MCP servers are configured in `.kilocode/mcp.json`:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {
        "DEFAULT_MINIMUM_TOKENS": "128000"
      }
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

## Usage

MCP servers auto-start if not running. They stay running continuously for efficiency:

```bash
# Just run agents/tests - MCP starts automatically if needed
make run-agentics          # ✅ Auto-starts MCP if needed
make test-agents-unit      # ✅ Auto-starts MCP if needed
make test-agents-integration # ✅ Auto-starts MCP if needed

# Manual control still available
make start-mcp       # Start explicitly
make check-mcp       # Check status only
make check-mcp-start # Check and auto-start if needed
make stop-mcp        # Stop when done
```

**MCP Lifecycle**: Lazy initialization - starts when first needed, stays running for efficiency, manually stopped when done.

## Architecture

- **MCP Bridge**: A Python service (built from `docker-files/mcp/Dockerfile`) that manages MCP server processes and exposes them via HTTP API
- **MCP Client**: Python client (`agents/agentics/src/mcp_client.py`) that connects to the bridge and provides high-level methods
- **Agent Integration**: Agents actively use MCP services for enhanced context and memory management
- **Docker Integration**: MCP servers run as persistent background services in Docker containers with `restart: unless-stopped`

## Troubleshooting

- **MCP not starting automatically**: Check docker-compose logs: `docker-compose -f docker-compose-files/agents.yaml logs mcp-bridge`
- **MCP health check fails**: Wait a few seconds after auto-start, or run `make check-mcp` to verify
- **MCP stays running**: This is normal - it persists across operations for efficiency
- Check logs in the MCP bridge container
- Verify `.kilocode/mcp.json` configuration is correct
- Ensure network connectivity between containers

## Dependencies

Added to `requirements.in`:
- `aiohttp`: For HTTP client functionality
- `mcp`: Model Context Protocol Python SDK
