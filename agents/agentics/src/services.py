"""Service clients and health checks for external dependencies."""

import asyncio
from typing import Optional, Callable, Dict, Any
from abc import ABC, abstractmethod

from github import Github, Auth
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

from .config import LLMConfig, get_config
from .exceptions import (
    ServiceUnavailableError,
    GitHubError,
    LLMError,
    HealthCheckError,
)
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


class LLMClient(ServiceClient):
    """Client for LLM services (llama.cpp / OpenAI-compatible API)."""

    def __init__(self, config: LLMConfig):
        super().__init__("llm")
        self.config = config
        self._client: Optional[ChatOpenAI] = None

    def _initialize_client(self) -> None:
        """Initialize the LLM client."""
        try:
            self._client = ChatOpenAI(
                model=self.config.model,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                min_p=self.config.min_p,
                request_timeout=self.config.request_timeout,
            )
        except Exception as e:
            log_info(__name__, f"Failed to initialize LLM client: {str(e)}")
            self._client = None

    @property
    def client(self) -> Optional[ChatOpenAI]:
        """Lazily initialize and return the LLM client."""
        if self._client is None:
            self._initialize_client()
        return self._client

    async def health_check(self) -> bool:
        """Check if LLM service is healthy."""
        # Use lazy client property to trigger initialization if needed
        client = self.client
        if not client:
            return False

        try:
            # Run health check in thread pool to avoid blocking
            response = await asyncio.get_event_loop().run_in_executor(
                None, client.invoke, "Hello"
            )
            return bool(response and len(str(response).strip()) > 0)
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if LLM client is available."""
        return self.client is not None and self.health_monitor.is_service_healthy(
            "llm"
        )

    def invoke(self, prompt: str) -> str:
        """Invoke the LLM with a prompt."""
        if not self.is_available():
            raise LLMError(f"LLM service ({self.config.model}) is not available")

        @self.circuit_breaker.call
        def _invoke():
            return self.client.invoke(prompt)

        return _invoke()


class GitHubClient(ServiceClient):
    """Client for GitHub API services."""

    def __init__(self, token: str):
        print(f"GitHubClient __init__ called, token: {token}")
        super().__init__("github")
        self.token = token
        self._client: Optional[Github] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the GitHub client."""
        if not self.token:
            self._client = None
            return
        print(f"GitHub _initialize_client called, token: {self.token}")
        try:
            auth = Auth.Token(self.token)
            self._client = Github(auth=auth)
            log_info(__name__, "Initialized GitHub client")
        except Exception as e:
            log_info(__name__, f"Failed to initialize GitHub client: {str(e)}")
            self._client = None
        log_info(
            __name__,
            f"GitHub client initialization complete: _client is {self._client}",
        )

    async def health_check(self) -> bool:
        if not self.token or not self._client:
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
        return self._client is not None and self.health_monitor.is_service_healthy(
            "github"
        )

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



class ServiceManager:
    """Manager for all external service clients."""

    def __init__(self, config):
        self.config = config
        self.llm_reasoning: Optional[LLMClient] = None
        self.llm_code: Optional[LLMClient] = None
        self.github: Optional[GitHubClient] = None
        self.health_monitor = get_health_monitor()

    async def initialize_services(self) -> None:
        """Initialize all service clients."""
        log_info(__name__, "Initializing service clients")

        # Initialize LLM clients
        reasoning_config = self.config.get_reasoning_llm_config()
        code_config = self.config.get_code_llm_config()

        self.llm_reasoning = LLMClient(reasoning_config)
        self.llm_code = LLMClient(code_config)

        # Initialize GitHub client
        if self.config.github_token:
            self.github = GitHubClient(self.config.github_token)

        # Register health checks
        if self.llm_reasoning:
            self.health_monitor.register_service(
                "llm_reasoning", self.llm_reasoning.health_check
            )
        if self.llm_code:
            self.health_monitor.register_service(
                "llm_code", self.llm_code.health_check
            )
        if self.github:
            self.health_monitor.register_service("github", self.github.health_check)

        log_info(__name__, "Service clients initialized")

    async def check_services_health(self) -> Dict[str, bool]:
        """Check health of all services."""
        results = {}

        services_to_check = [
            ("llm_reasoning", self.llm_reasoning),
            ("llm_code", self.llm_code),
            ("github", self.github),
        ]

        for name, service in services_to_check:
            if service:
                results[name] = self.health_monitor.is_service_healthy(name)
            else:
                results[name] = False

        return results

    async def close_services(self) -> None:
        """Close all service clients."""
        log_info(__name__, "Closing service clients")

        log_info(__name__, "Service clients closed")


# Global service manager instance
_service_manager: Optional[ServiceManager] = None


def get_service_manager() -> ServiceManager:
    """Get the global service manager instance."""
    if _service_manager is None:
        raise RuntimeError(
            "Service manager not initialized. Call init_services() first."
        )
    return _service_manager


async def init_services(config) -> ServiceManager:
    """Initialize the global service manager."""
    global _service_manager
    _service_manager = ServiceManager(config)
    await _service_manager.initialize_services()
    return _service_manager
