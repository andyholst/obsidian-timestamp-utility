"""Service clients and health checks for external dependencies."""

import asyncio
from typing import Optional, Callable, Dict, Any
from abc import ABC, abstractmethod

from github import Github, Auth
from langchain_ollama import OllamaLLM
from langchain.tools import Tool

from .config import LLMConfig, get_config
from .exceptions import ServiceUnavailableError, GitHubError, OllamaError, MCPError, HealthCheckError
from .mcp_client import get_mcp_client, init_mcp_client, close_mcp_client
from .circuit_breaker import get_circuit_breaker, get_health_monitor
from .utils import log_info


class ServiceClient(ABC):
    """Abstract base class for service clients."""

    def __init__(self, name: str):
        self.name = name
        self.circuit_breaker = get_circuit_breaker(name)
        self.health_monitor = get_health_monitor()

    @abstractmethod
    async def health_check(self) -> bool:
        """Perform health check for the service."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the service is currently available."""
        pass


class OllamaClient(ServiceClient):
    """Client for Ollama LLM services."""

    def __init__(self, config: LLMConfig):
        super().__init__("ollama")
        self.config = config
        self._client: Optional[OllamaLLM] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Ollama client."""
        try:
            self._client = OllamaLLM(
                model=self.config.model,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                min_p=self.config.min_p,
                extra_params={
                    "presence_penalty": self.config.presence_penalty,
                    "num_ctx": self.config.num_ctx,
                    "num_predict": self.config.num_predict
                }
            )
            log_info(__name__, f"Initialized Ollama client for model {self.config.model}")
        except Exception as e:
            log_info(__name__, f"Failed to initialize Ollama client: {str(e)}")
            self._client = None

    async def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        if not self._client:
            return False

        try:
            # Run health check in thread pool to avoid blocking
            response = await asyncio.get_event_loop().run_in_executor(
                None, self._client.invoke, "Hello"
            )
            return bool(response and len(response.strip()) > 0)
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if Ollama client is available."""
        return self._client is not None and self.health_monitor.is_service_healthy("ollama")

    def invoke(self, prompt: str) -> str:
        """Invoke the LLM with a prompt."""
        if not self.is_available():
            raise OllamaError(f"Ollama service ({self.config.model}) is not available")

        @self.circuit_breaker.call
        def _invoke():
            return self._client.invoke(prompt)

        return _invoke()


class GitHubClient(ServiceClient):
    """Client for GitHub API services."""

    def __init__(self, token: str):
        super().__init__("github")
        self.token = token
        self._client: Optional[Github] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the GitHub client."""
        try:
            auth = Auth.Token(self.token)
            self._client = Github(auth=auth)
            log_info(__name__, "Initialized GitHub client")
        except Exception as e:
            log_info(__name__, f"Failed to initialize GitHub client: {str(e)}")
            self._client = None

    async def health_check(self) -> bool:
        """Check if GitHub API is accessible."""
        if not self._client:
            return False

        try:
            user = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_user
            )
            return user is not None
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if GitHub client is available."""
        return self._client is not None and self.health_monitor.is_service_healthy("github")

    def get_user(self):
        """Get authenticated user."""
        if not self.is_available():
            raise GitHubError("GitHub service is not available")

        @self.circuit_breaker.call
        def _get_user():
            return self._client.get_user()

        return _get_user()

    def get_repo(self, repo_name: str):
        """Get repository object."""
        if not self.is_available():
            raise GitHubError("GitHub service is not available")

        @self.circuit_breaker.call
        def _get_repo():
            return self._client.get_repo(repo_name)

        return _get_repo()


class MCPClient(ServiceClient):
    """Client for MCP services."""

    def __init__(self):
        super().__init__("mcp")
        self._initialized = False
        self._tools: list = []

    async def initialize(self) -> None:
        """Initialize MCP client."""
        try:
            await asyncio.get_event_loop().run_in_executor(None, init_mcp_client)
            self._initialized = True
            log_info(__name__, "Initialized MCP client")
        except Exception as e:
            log_info(__name__, f"Failed to initialize MCP client: {str(e)}")
            self._initialized = False

    async def health_check(self) -> bool:
        """Check if MCP service is healthy."""
        if not self._initialized:
            return False
        try:
            client = get_mcp_client()
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if MCP client is available."""
        return self._initialized and self.health_monitor.is_service_healthy("mcp")

    async def get_context(self, query: str, max_tokens: int = 4096) -> str:
        """Get context from MCP."""
        if not self.is_available():
            raise MCPError("MCP service is not available")

        @self.circuit_breaker.call
        def _get_context():
            return get_mcp_client().get_context(query, max_tokens)

        return await asyncio.get_event_loop().run_in_executor(None, _get_context)

    async def store_memory(self, key: str, value: str) -> None:
        """Store memory in MCP."""
        if not self.is_available():
            raise MCPError("MCP service is not available")

        @self.circuit_breaker.call
        def _store_memory():
            return get_mcp_client().store_memory(key, value)

        await asyncio.get_event_loop().run_in_executor(None, _store_memory)

    async def retrieve_memory(self, key: str) -> str:
        """Retrieve memory from MCP."""
        if not self.is_available():
            raise MCPError("MCP service is not available")

        @self.circuit_breaker.call
        def _retrieve_memory():
            return get_mcp_client().retrieve_memory(key)

        return await asyncio.get_event_loop().run_in_executor(None, _retrieve_memory)

    def get_tools(self) -> list:
        """Get MCP tools for LangChain integration."""
        if not self.is_available():
            return []

        if not self._tools:
            try:
                client = get_mcp_client()
                self._tools = [
                    Tool.from_function(
                        func=lambda query: asyncio.run(self.get_context(query, max_tokens=4096)),
                        name="mcp_context_search",
                        description="Search for contextual information using MCP context server"
                    ),
                    Tool.from_function(
                        func=lambda key, value: asyncio.run(self.store_memory(key, value)),
                        name="mcp_memory_store",
                        description="Store key-value pairs in MCP memory server"
                    ),
                    Tool.from_function(
                        func=lambda key: asyncio.run(self.retrieve_memory(key)),
                        name="mcp_memory_retrieve",
                        description="Retrieve stored values from MCP memory server"
                    )
                ]
            except Exception as e:
                log_info(__name__, f"Failed to create MCP tools: {str(e)}")
                self._tools = []

        return self._tools

    async def close(self) -> None:
        """Close MCP client."""
        if self._initialized:
            try:
                await asyncio.get_event_loop().run_in_executor(None, close_mcp_client)
                self._initialized = False
                log_info(__name__, "Closed MCP client")
            except Exception as e:
                log_info(__name__, f"Failed to close MCP client: {str(e)}")


class ServiceManager:
    """Manager for all external service clients."""

    def __init__(self, config):
        self.config = config
        self.ollama_reasoning: Optional[OllamaClient] = None
        self.ollama_code: Optional[OllamaClient] = None
        self.github: Optional[GitHubClient] = None
        self.mcp: Optional[MCPClient] = None
        self.health_monitor = get_health_monitor()

    async def initialize_services(self) -> None:
        """Initialize all service clients."""
        log_info(__name__, "Initializing service clients")

        # Initialize Ollama clients
        reasoning_config = self.config.get_reasoning_llm_config()
        code_config = self.config.get_code_llm_config()

        self.ollama_reasoning = OllamaClient(reasoning_config)
        self.ollama_code = OllamaClient(code_config)

        # Initialize GitHub client
        if self.config.github_token:
            self.github = GitHubClient(self.config.github_token)

        # Initialize MCP client
        self.mcp = MCPClient()

        # Register health checks
        if self.ollama_reasoning:
            self.health_monitor.register_service("ollama_reasoning", self.ollama_reasoning.health_check)
        if self.ollama_code:
            self.health_monitor.register_service("ollama_code", self.ollama_code.health_check)
        if self.github:
            self.health_monitor.register_service("github", self.github.health_check)
        if self.mcp:
            self.health_monitor.register_service("mcp", self.mcp.health_check)

        log_info(__name__, "Service clients initialized")

    async def check_services_health(self) -> Dict[str, bool]:
        """Check health of all services."""
        results = {}

        services_to_check = [
            ("ollama_reasoning", self.ollama_reasoning),
            ("ollama_code", self.ollama_code),
            ("github", self.github),
            ("mcp", self.mcp)
        ]

        for name, service in services_to_check:
            if service:
                try:
                    results[name] = await service.health_check()
                except Exception:
                    results[name] = False
            else:
                results[name] = False

        return results

    async def close_services(self) -> None:
        """Close all service clients."""
        log_info(__name__, "Closing service clients")

        if self.mcp:
            await self.mcp.close()

        log_info(__name__, "Service clients closed")


# Global service manager instance
_service_manager: Optional[ServiceManager] = None


def get_service_manager() -> ServiceManager:
    """Get the global service manager instance."""
    if _service_manager is None:
        raise RuntimeError("Service manager not initialized. Call init_services() first.")
    return _service_manager


async def init_services(config) -> ServiceManager:
    """Initialize the global service manager."""
    global _service_manager
    _service_manager = ServiceManager(config)
    await _service_manager.initialize_services()
    return _service_manager