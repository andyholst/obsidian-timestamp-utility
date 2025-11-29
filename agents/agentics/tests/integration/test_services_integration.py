import pytest
import asyncio
from src.services import MCPClient


class TestMCPClientIntegration:
    """Integration tests for MCPClient using real services."""

    @pytest.mark.asyncio
    async def test_mcp_client_initialize_success(self):
        """Test MCPClient initialize success."""
        client = MCPClient()

        await client.initialize()

        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_mcp_client_health_check_success(self):
        """Test MCPClient health check success."""
        client = MCPClient()
        await client.initialize()

        result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_mcp_client_is_available(self):
        """Test MCPClient is_available method."""
        client = MCPClient()
        await client.initialize()

        result = client.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_mcp_client_get_context_success(self):
        """Test MCPClient get_context success."""
        client = MCPClient()
        await client.initialize()

        result = await client.get_context("test query", 4096)

        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_client_store_memory_success(self):
        """Test MCPClient store_memory success."""
        client = MCPClient()
        await client.initialize()

        await client.store_memory("key", "value")

        # No assertion needed, just ensure no exception

    @pytest.mark.asyncio
    async def test_mcp_client_retrieve_memory_success(self):
        """Test MCPClient retrieve_memory success."""
        client = MCPClient()
        await client.initialize()

        result = await client.retrieve_memory("key")

        assert result is not None

    def test_mcp_client_get_tools(self):
        """Test MCPClient get_tools method."""
        client = MCPClient()

        tools = client.get_tools()

        assert len(tools) == 3
        assert client._tools == tools