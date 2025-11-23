FROM node:22-slim

# Install Python for potential MCP bridge scripts
RUN apt-get update && apt-get install -y python3 python3-pip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install MCP SDK and related packages
RUN npm install -g @modelcontextprotocol/sdk

# Create app directory
WORKDIR /app

# Force cache invalidation

# Install MCP bridge dependencies
RUN pip install --no-cache-dir --break-system-packages mcp aiohttp

# Create MCP bridge script
RUN echo '#!/usr/bin/env python3\n\
import asyncio\n\
import json\n\
import os\n\
import subprocess\n\
import sys\n\
from aiohttp import web\n\
from mcp import ClientSession, StdioServerParameters\n\
from mcp.client.stdio import stdio_client\n\
\n\
async def load_mcp_config():\n\
    config_path = os.getenv("MCP_CONFIG_PATH", "/app/.kilocode/mcp.json")\n\
    with open(config_path, "r") as f:\n\
        return json.load(f)\n\
\n\
async def start_mcp_servers():\n\
    config = await load_mcp_config()\n\
    servers = {}\n\
    \n\
    for name, server_config in config.get("mcpServers", {}).items():\n\
        cmd = server_config["command"]\n\
        args = server_config.get("args", [])\n\
        env = server_config.get("env", {})\n\
        \n\
        # Merge environment variables\n\
        server_env = os.environ.copy()\n\
        server_env.update(env)\n\
        \n\
        # Start the MCP server process\n\
        process = await asyncio.create_subprocess_exec(\n\
            cmd, *args,\n\
            stdin=asyncio.subprocess.PIPE,\n\
            stdout=asyncio.subprocess.PIPE,\n\
            stderr=asyncio.subprocess.PIPE,\n\
            env=server_env\n\
        )\n\
        \n\
        servers[name] = {\n\
            "process": process,\n\
            "config": server_config\n\
        }\n\
        \n\
    return servers\n\
\n\
async def health_check(request):\n\
    return web.Response(text="OK")\n\
\n\
async def list_servers(request):\n\
    config = await load_mcp_config()\n\
    return web.json_response({\n\
        "servers": list(config.get("mcpServers", {}).keys())\n\
    })\n\
\n\
async def main():\n\
    app = web.Application()\n\
    app.router.add_get("/health", health_check)\n\
    app.router.add_get("/servers", list_servers)\n\
    \n\
    # Start MCP servers\n\
    servers = await start_mcp_servers()\n\
    print(f"Started MCP servers: {list(servers.keys())}")\n\
    \n\
    # Store servers in app for access by handlers\n\
    app["mcp_servers"] = servers\n\
    \n\
    runner = web.AppRunner(app)\n\
    await runner.setup()\n\
    site = web.TCPSite(runner, "0.0.0.0", 3000)\n\
    await site.start()\n\
    print("MCP bridge server started on port 3000")\n\
    \n\
    # Keep running\n\
    try:\n\
        while True:\n\
            await asyncio.sleep(1)\n\
    except KeyboardInterrupt:\n\
        print("Shutting down MCP servers...")\n\
        for name, server in servers.items():\n\
            server["process"].terminate()\n\
            await server["process"].wait()\n\
        await runner.cleanup()\n\
\n\
if __name__ == "__main__":\n\
    asyncio.run(main())\n\
' > mcp_bridge.py && chmod +x mcp_bridge.py

# Expose port
EXPOSE 3000

# Run the MCP bridge
CMD ["python3", "mcp_bridge.py"]