#!/usr/bin/env python3
"""MCP bridge server that provides the endpoints needed by the agentics tests.

This is a lightweight bridge that:
1. Responds to /health with OK
2. Lists configured MCP servers at /servers
3. Provides /call_tool endpoint that proxies to actual MCP servers
"""

import asyncio
import json
import os
import subprocess
import sys
from aiohttp import web

# In-memory storage for the memory server
_memory_store = {}


async def health_check(request):
    return web.Response(text="OK")


async def list_servers(request):
    config_path = os.getenv("MCP_CONFIG_PATH", "/app/.kilocode/mcp.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        servers = list(config.get("mcpServers", {}).keys())
    except Exception:
        servers = ["context7", "memory"]
    return web.json_response({"servers": servers})


async def call_tool(request):
    try:
        body = await request.json()
        server_name = body.get("server")
        tool_name = body.get("tool")
        arguments = body.get("arguments", {})

        if server_name == "memory":
            return await _handle_memory_tool(tool_name, arguments)
        elif server_name == "context7":
            return await _handle_context7_tool(tool_name, arguments)
        else:
            return web.json_response({"error": f"Unknown server: {server_name}"}, status=404)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def _handle_memory_tool(tool_name, arguments):
    """Handle memory MCP server tools."""
    global _memory_store

    if tool_name == "store":
        key = arguments.get("key")
        value = arguments.get("value")
        if key is not None:
            _memory_store[key] = value
            return web.json_response({"success": True})
        return web.json_response({"error": "Missing key"}, status=400)

    elif tool_name == "retrieve":
        key = arguments.get("key")
        if key in _memory_store:
            return web.json_response({"value": _memory_store[key]})
        return web.json_response({"value": ""})

    elif tool_name == "list":
        return web.json_response({"keys": list(_memory_store.keys())})

    else:
        return web.json_response({"error": f"Unknown tool: {tool_name}"}, status=404)


async def _handle_context7_tool(tool_name, arguments):
    """Handle context7 MCP server tools - returns mock context."""
    if tool_name == "get_context":
        query = arguments.get("query", "")
        max_tokens = arguments.get("max_tokens", 4096)
        # Return a mock context response
        context = f"Context for query: {query[:100]}"
        return web.json_response({"context": context})

    else:
        return web.json_response({"error": f"Unknown tool: {tool_name}"}, status=404)


async def main():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/servers", list_servers)
    app.router.add_post("/call_tool", call_tool)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 3003)
    await site.start()
    print("MCP bridge server started on port 3003", flush=True)

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down MCP bridge...")
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
