import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .utils import log_info
from .monitoring import structured_log

class MCPClient:
    def __init__(self, bridge_url: str = "http://localhost:3000"):
        self.bridge_url = bridge_url
        self.logger = logging.getLogger("MCPClient")
        self.monitor.logger.setLevel(logging.INFO)
        self.session: Optional[aiohttp.ClientSession] = None
        log_info(self.logger, f"Initialized MCP client with bridge URL: {bridge_url}")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    async def check_health(self) -> bool:
        """Check if MCP bridge is healthy."""
        try:
            async with self.session.get(f"{self.bridge_url}/health") as response:
                return response.status == 200
        except Exception as e:
            log_info(self.logger, f"Health check failed: {str(e)}")
            raise

    async def list_servers(self) -> list:
        """List available MCP servers."""
        try:
            async with self.session.get(f"{self.bridge_url}/servers") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("servers", [])
                else:
                    log_info(self.logger, f"Failed to list servers: {response.status}")
                    return []
        except Exception as e:
            log_info(self.logger, f"Failed to list servers: {str(e)}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server."""
        payload = {
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments
        }
        async with self.session.post(f"{self.bridge_url}/call_tool", json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                log_info(self.logger, f"Tool call failed: {response.status} - {error_text}")
                raise Exception(f"HTTP {response.status}: {error_text}")

    async def get_context(self, query: str, max_tokens: int = 128000) -> str:
        """Get context from the context7 MCP server."""
        result = await self.call_tool("context7", "get_context", {
            "query": query,
            "max_tokens": max_tokens
        })
        if "error" in result:
            log_info(self.logger, f"Context retrieval failed: {result['error']}")
            return ""
        return result.get("context", "")

    async def store_memory(self, key: str, value: str) -> bool:
        """Store a key-value pair in the memory MCP server."""
        result = await self.call_tool("memory", "store", {
            "key": key,
            "value": value
        })
        if "error" in result:
            log_info(self.logger, f"Memory store failed: {result['error']}")
            return False
        return result.get("success", False)

    async def retrieve_memory(self, key: str) -> str:
        """Retrieve a value from the memory MCP server."""
        result = await self.call_tool("memory", "retrieve", {
            "key": key
        })
        if "error" in result:
            log_info(self.logger, f"Memory retrieval failed: {result['error']}")
            return ""
        return result.get("value", "")

# Global MCP client instance
_mcp_client = None

def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client

async def init_mcp_client():
    """Initialize the MCP client session."""
    client = get_mcp_client()
    return await client.__aenter__()

async def close_mcp_client():
    """Close the MCP client session."""
    client = get_mcp_client()
    await client.__aexit__(None, None, None)
