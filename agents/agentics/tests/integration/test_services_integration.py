"""
Integration tests for MCPClient.
Tests are skipped when MCP server is not available.
"""

import pytest
import os


class TestMCPClientIntegration:
    """Integration tests for MCPClient - skipped when MCP unavailable."""

    @pytest.fixture(autouse=True)
    def skip_if_no_mcp(self):
        """Skip all MCP tests when MCP server is not available."""
        mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:3003")
        import socket
        try:
            host = mcp_url.split("//")[1].split(":")[0] if "//" in mcp_url else "localhost"
            port = int(mcp_url.split(":")[-1]) if ":" in mcp_url else 3003
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((host, port))
            s.close()
        except (ConnectionRefusedError, OSError, socket.timeout, IndexError):
            pytest.skip(f"MCP server not available at {mcp_url}")

    @pytest.mark.asyncio
    async def test_mcp_client_initialize_success(self):
        """Test MCPClient initialize success."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_mcp_client_health_check_success(self):
        """Test MCPClient health check success."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_mcp_client_is_available(self):
        """Test MCPClient is_available method."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        result = client.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_mcp_client_get_context_success(self):
        """Test MCPClient get_context success."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        result = await client.get_context("test query", 4096)
        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_client_store_memory_success(self):
        """Test MCPClient store_memory success."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        await client.store_memory("key", "value")

    @pytest.mark.asyncio
    async def test_mcp_client_retrieve_memory_success(self):
        """Test MCPClient retrieve_memory success."""
        from src.services import MCPClient
        client = MCPClient()
        await client.initialize()
        result = await client.retrieve_memory("key")
        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_client_get_tools(self):
        """Test MCPClient get_tools method."""
        from src.services import MCPClient
        client = MCPClient()
        tools = await client.get_tools()
        assert len(tools) > 0
