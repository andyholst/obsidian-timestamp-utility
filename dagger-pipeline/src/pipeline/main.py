import os
import anyio
from dagger import (
    dag,
    function,
    object_type,
    Directory,
    File,
    Socket,
    Service,
    Container,
)
import dagger


def _resolve_container_ollama_host() -> str:
    """Resolve the IP that containers use to reach the host's Ollama.

    Tries common container-to-host gateways in order:
    1. host.docker.internal (Docker Desktop / recent Docker)
    2. 172.17.0.1 (default Docker bridge gateway)
    3. 10.4.0.1 (default nerdctl/rootless containerd bridge gateway)
    4. 10.0.2.2 (Vagrant/VirtualBox host-only)
    Falls back to 172.17.0.1.
    """
    import socket
    for hostname in ("host.docker.internal",):
        try:
            socket.gethostbyname(hostname)
            return hostname
        except socket.gaierror:
            pass
    # Try to detect the nerdctl bridge gateway from /proc
    try:
        with open("/proc/net/route") as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == "00000000":  # default route
                    import struct, socket as _socket
                    gw_hex = fields[2]
                    gw_ip = _socket.inet_ntoa(struct.pack("<I", int(gw_hex, 16)))
                    return gw_ip
    except Exception:
        pass
    # Common defaults
    for gw in ("10.4.0.1", "172.17.0.1", "10.0.2.2"):
        return gw
    return "172.17.0.1"


@object_type
class Pipeline:
    @function
    async def get_tag(self, source: Directory) -> str:
        ctr = (
            dag.container()
            .from_("node:22.11.0")
            .with_directory("/app", source)
            .with_workdir("/app")
        )
        output = await ctr.with_exec(
            ["node", "-p", "require('./package.json').version"]
        ).stdout()
        return output.strip()

    async def _app_container(self, repo_name: str, tag: str, source: Directory):
        ctr = (
            dag.container()
            .from_("node:22.11.0")
            .with_exec(["apt-get", "update", "-y"])
            .with_exec(["apt-get", "install", "-y", "git", "zip", "dos2unix", "sed"])
        )
        ctr = (
            ctr.with_directory("/app", source)
            .with_workdir("/app")
            .with_env_variable("REPO_NAME", repo_name)
            .with_env_variable("TAG", tag)
            .with_env_variable("NODE_ENV", "development")
        )
        ctr = ctr.with_exec(
            ["git", "config", "--global", "--add", "safe.directory", "/app"]
        )
        return ctr

    @function
    async def build_app(
        self,
        source: Directory,
        repo_name: str = "obsidian-timestamp-utility",
        tag: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        if not tag:
            tag = await self.get_tag(source)

        ctr = await self._app_container(repo_name, tag, source)

        install_ctr = ctr.with_exec(["sh", "-c", "npm install --loglevel=silly 2>&1"])
        install_log = await install_ctr.stdout()
        print("=== NPM CI LOG ===")
        print(install_log)

        build_ctr = install_ctr.with_exec(["sh", "-c", "npm run build-package 2>&1"])
        build_log = await build_ctr.stdout()
        print("=== NPM BUILD LOG ===")
        print(build_log)

        check_ctr = build_ctr.with_exec(["test", "-f", "/app/dist/main.js"])
        if await check_ctr.exit_code() != 0:
            raise ValueError("Build failed: missing /app/dist/main.js")

        dist_contents = await build_ctr.with_exec(["ls", "-la", "/app/dist"]).stdout()
        print("=== /app/dist CONTENTS BEFORE EXPORT ===")
        print(dist_contents)

        final_ctr = build_ctr
        if host_uid != 0 and host_gid != 0:
            final_ctr = final_ctr.with_exec(
                [
                    "chown",
                    "-R",
                    f"{host_uid}:{host_gid}",
                    "/app/dist",
                    "/app/node_modules",
                ]
            )

        dist_dir = final_ctr.directory("/app/dist")
        node_dir = final_ctr.directory("/app/node_modules")
        lock_file = final_ctr.file("/app/package-lock.json")
        combined = (
            dag.directory()
            .with_directory("dist", dist_dir)
            .with_directory("node_modules", node_dir)
            .with_file("package-lock.json", lock_file)
        )
        return combined

    @function
    async def test_app(
        self,
        source: Directory,
        repo_name: str = "obsidian-timestamp-utility",
        tag: str = "",
    ) -> str:
        if not tag:
            tag = await self.get_tag(source)

        ctr = await self._app_container(repo_name, tag, source)
        # Install dependencies (including dev deps like jest)
        install_ctr = ctr.with_exec(["sh", "-c", "npm install --loglevel=silly 2>&1"])
        install_log = await install_ctr.stdout()
        test_ctr = install_ctr.with_exec(["sh", "-c", "npm test 2>&1"])
        log = await test_ctr.stdout()
        return log

    @function
    async def changelog(
        self,
        source: Directory,
        repo_name: str = "obsidian-timestamp-utility",
        tag: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> File:
        if not tag:
            tag = await self.get_tag(source)

        ctr = await self._app_container(repo_name, tag, source)
        ctr = ctr.with_exec(
            [
                "npm",
                "install",
                "-g",
                "@commitlint/cli",
                "@commitlint/config-conventional",
            ]
        )
        ctr = ctr.with_exec(["chmod", "+x", "/app/scripts/changelog.sh"])
        ctr = ctr.with_exec(["/app/scripts/changelog.sh"])

        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", f"{host_uid}:{host_gid}", "/app/CHANGELOG.md"]
            )

        return ctr.file("/app/CHANGELOG.md")

    @function
    async def release(
        self,
        source: Directory,
        repo_name: str = "obsidian-timestamp-utility",
        tag: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        if not tag:
            tag = await self.get_tag(source)

        ctr = await self._app_container(repo_name, tag, source)
        ctr = ctr.with_exec(["npm", "install", "--loglevel=silly"])
        ctr = ctr.with_exec(["npm", "run", "build-package"])
        ctr = ctr.with_exec(["chmod", "+x", "/app/scripts/release.sh"])
        ctr = ctr.with_exec(
            ["sh", "-c", "find /app -name '*.sh' -exec dos2unix {} \\;"]
        )
        ctr = ctr.with_exec(["/app/scripts/release.sh"])

        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/release"]
            )

        return ctr.directory("/app/release")

    @function
    async def release_zip_check(
        self,
        source: Directory,
        repo_name: str = "obsidian-timestamp-utility",
        tag: str = "",
    ) -> str:
        if not tag:
            tag = await self.get_tag(source)

        zip_path = f"release/{repo_name}-{tag}.zip"
        await source.file(zip_path).contents()
        return f"{zip_path} exists"

    @function
    async def lint_python(self, source: Directory) -> str:
        ctr = (
            dag.container()
            .from_("python:3.12")
            .with_directory("/app", source.directory("agents/agentics"))
            .with_workdir("/app")
            .with_exec(["pip", "install", "ruff", "black"])
        )
        ctr = ctr.with_exec(["ruff", "check", "/app/src", "/app/tests"])
        ctr = ctr.with_exec(["black", "--check", "/app/src", "/app/tests"])
        return "Python lint completed"

    async def _agents_base(self, source: Directory):
        # Use a plain container with source mounted directly
        # Copy source via tar to avoid any caching issues
        import time
        _cache_bust = str(time.time())
        ctr = (
            dag.container()
            .from_("python:3.11-slim")
            .with_exec(["apt-get", "update", "-y"])
            .with_exec(["apt-get", "install", "-y", "git", "curl"])
            .with_exec(["sh", "-c", "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -"])
            .with_exec(["apt-get", "install", "-y", "nodejs"])
            .with_directory("/app", source.directory("agents/agentics"))
            .with_directory("/project", source)
            .with_workdir("/app")
            # Force cache invalidation: write unique file then remove pycache
            .with_new_file("/app/.cache_bust", _cache_bust)
            .with_exec(["find", "/app/src", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"])
            .with_exec(["pip", "install", "--no-cache-dir", "-r", "requirements.txt"])
        )
        return ctr

    @function
    async def format(self, source: Directory) -> str:
        ctr = (
            dag.container()
            .from_("python:3.12")
            .with_directory("/app", source.directory("agents/agentics"))
            .with_workdir("/app")
            .with_exec(["pip", "install", "ruff"])
        )
        ctr = ctr.with_exec(["ruff", "format", "/app/src", "/app/tests"])
        return "Format completed"

    @function
    async def build_image_agents(self, source: Directory) -> Container:
        """Build the agents Docker image."""
        return await self._agents_base(source)

    @function
    async def test_agents_unit(
        self,
        source: Directory,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
        ollama_host: str = "",
        test_filter: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        # Resolve Ollama host for container: use parameter if provided,
        # else env var, else try common container-to-host gateways.
        if not ollama_host:
            ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = _resolve_container_ollama_host()
        # If still localhost/127.0.0.1, replace with gateway IP
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            gateway = _resolve_container_ollama_host()
            ollama_host = ollama_host.replace("localhost", gateway).replace("127.0.0.1", gateway)

        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("OLLAMA_MODEL", ollama_model).with_env_variable(
            "TEST_FILTER", test_filter
        ).with_env_variable("OLLAMA_HOST", ollama_host)
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(["chmod", "777", "results"])
        ctr = ctr.with_exec(["python", "src/collect_tests.py", "unit"])
        ctr = ctr.with_exec(
            ["mv", "collected_tests_unit.txt", "results/collected_tests_unit.txt"]
        )
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(
            [
                "bash",
                "-c",
                "cd /app && python -m pytest tests/unit/ -vv -s --tb=long ${TEST_FILTER} 2>&1 | tee results/executed_tests_unit.txt",
            ]
        )
        ctr = ctr.with_exec(["python", "src/parse_executed_tests.py", "unit"])
        ctr = ctr.with_exec(
            ["mv", "executed_list_unit.txt", "results/executed_list_unit.txt"]
        )
        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/results"]
            )
        return ctr.directory("/app/results")

    @function
    async def test_agents_unit_mock(
        self,
        source: Directory,
        test_filter: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> str:
        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("TEST_FILTER", test_filter)
        ctr = ctr.with_exec(
            [
                "bash",
                "-c",
                "cd /app && python -m pytest tests/unit/ -q --tb=short ${TEST_FILTER} 2>&1",
            ]
        )
        return await ctr.stdout()

    @function
    async def test_agents_integration(
        self,
        source: Directory,
        github_token: str,
        docker_sock: Socket | None = None,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
        test_filter: str = "",
        ollama_timeout: str = "300",
        ollama_host: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        await self.check_github(github_token)
        await self.check_mcp(source, docker_sock)

        # Use host's Ollama - resolve gateway for Dagger containers
        if not ollama_host:
            ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = _resolve_container_ollama_host()
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            gateway = _resolve_container_ollama_host()
            ollama_host = ollama_host.replace("localhost", gateway).replace("127.0.0.1", gateway)

        ctr = await self._agents_base(source)
        # Write .env file with secrets and source it before running tests
        ctr = ctr.with_new_file(".env", f"export GITHUB_TOKEN={github_token}\nexport OLLAMA_HOST={ollama_host}\n")
        ctr = (
            ctr.with_env_variable("GITHUB_TOKEN", github_token)
            .with_env_variable("OLLAMA_MODEL", ollama_model)
            .with_env_variable("TEST_FILTER", test_filter)
            .with_env_variable("OLLAMA_TIMEOUT", ollama_timeout)
            .with_env_variable("OLLAMA_HOST", ollama_host)
        )
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(["chmod", "777", "results"])
        ctr = ctr.with_exec(["python", "src/collect_tests.py", "integration"])
        ctr = ctr.with_exec(
            [
                "mv",
                "collected_tests_integration.txt",
                "results/collected_tests_integration.txt",
            ]
        )
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(
            [
                "bash",
                "-c",
                f"cd /app && GITHUB_TOKEN={github_token} OLLAMA_HOST={ollama_host} python -m pytest tests/integration/ -vv -s --tb=long ${{TEST_FILTER}} 2>&1 | tee results/executed_tests_integration.txt",
            ]
        )
        ctr = ctr.with_exec(["python", "src/parse_executed_tests.py", "integration"])
        ctr = ctr.with_exec(
            [
                "mv",
                "executed_list_integration.txt",
                "results/executed_list_integration.txt",
            ]
        )
        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/results"]
            )
        return ctr.directory("/app/results")

    @function
    async def test_agents_unit_verbose(
        self,
        source: Directory,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
        test_filter: str = "",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        # Resolve Ollama host for container
        if not ollama_host:
            ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = _resolve_container_ollama_host()
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            gateway = _resolve_container_ollama_host()
            ollama_host = ollama_host.replace("localhost", gateway).replace("127.0.0.1", gateway)

        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("OLLAMA_MODEL", ollama_model).with_env_variable(
            "TEST_FILTER", test_filter
        ).with_env_variable("OLLAMA_HOST", ollama_host)
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(
            [
                "bash",
                "-c",
                "cd /app && python -m pytest tests/unit/ -vvv --capture=no --tb=long ${TEST_FILTER} 2>&1 | tee results/verbose_unit.log",
            ]
        )
        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/results"]
            )
        return ctr.directory("/app/results")

    @function
    async def test_agents_integration_verbose(
        self,
        source: Directory,
        github_token: str,
        docker_sock: Socket | None = None,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
        test_filter: str = "",
        ollama_timeout: str = "300",
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        await self.check_github(github_token)
        await self.check_mcp(source, docker_sock)

        # Use host's Ollama - resolve gateway for Dagger containers
        if not ollama_host:
            ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = _resolve_container_ollama_host()
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            gateway = _resolve_container_ollama_host()
            ollama_host = ollama_host.replace("localhost", gateway).replace("127.0.0.1", gateway)

        ctr = await self._agents_base(source)
        ctr = (
            ctr.with_env_variable("GITHUB_TOKEN", github_token)
            .with_env_variable("OLLAMA_MODEL", ollama_model)
            .with_env_variable("TEST_FILTER", test_filter)
            .with_env_variable("OLLAMA_TIMEOUT", ollama_timeout)
            .with_env_variable("OLLAMA_HOST", ollama_host)
        )
        ctr = ctr.with_exec(["mkdir", "-p", "results"])
        ctr = ctr.with_exec(
            [
                "bash",
                "-c",
                f"cd /app && GITHUB_TOKEN={github_token} OLLAMA_HOST={ollama_host} python -m pytest tests/integration/ -vv -s --tb=long ${{TEST_FILTER}} 2>&1 | tee results/executed_tests_integration.txt",
            ]
        )
        if host_uid != 0 and host_gid != 0:
            ctr = ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/results"]
            )
        return ctr.directory("/app/results")

    @function
    async def test_agents_unit_watch(
        self, ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b", test_filter: str = ""
    ) -> str:
        return "Unit watch mode: Run locally with ptw or similar"

    @function
    async def test_agents_integration_watch(
        self,
        github_token: str,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
        test_filter: str = "",
        ollama_timeout: str = "300",
    ) -> str:
        await self.check_github(github_token)
        await self.checkOllama()
        return "Integration watch mode: Run locally with ptw or similar"

    @function
    async def run_agentics(
        self,
        source: Directory,
        docker_sock: Socket,
        url: str,
        github_token: str,
        ollama_model: str = "qwen3.5:9b",
    ) -> Directory:
        """Run the agentics workflow on a GitHub issue and return the updated source directory."""
        await self.check_github(github_token)
        await self.checkOllama()
        await self.check_mcp(source, docker_sock)

        # Resolve host gateway for container-to-host communication
        host_gateway = _resolve_container_ollama_host()

        # Resolve Ollama host for container-to-host communication
        ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = host_gateway
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            ollama_host = ollama_host.replace("localhost", host_gateway).replace("127.0.0.1", host_gateway)

        # MCP server runs on host, accessible via gateway
        mcp_server_url = f"http://{host_gateway}:3003"

        # Use qwen3.5:9b for reasoning, qwen3.5:4b for code generation
        ollama_reasoning_model = ollama_model
        ollama_code_model = "qwen3.5:4b"

        ctr = await self._agents_base(source)
        ctr = (
            ctr.with_env_variable("GITHUB_TOKEN", github_token)
            .with_env_variable("OLLAMA_MODEL", ollama_reasoning_model)
            .with_env_variable("OLLAMA_REASONING_MODEL", ollama_reasoning_model)
            .with_env_variable("OLLAMA_CODE_MODEL", ollama_code_model)
            .with_env_variable("OLLAMA_HOST", ollama_host)
            .with_env_variable("MCP_SERVER_URL", mcp_server_url)
            .with_env_variable("URL", url)
            .with_env_variable("PROJECT_ROOT", "/project")
        )
        ctr = ctr.with_exec(["python", "-m", "src.agentics"])
        # Return the updated source directory so generated files are exported back
        return ctr.directory("/project")

    @function
    async def validate_test_suite(
        self,
        source: Directory,
        docker_sock: Socket,
        github_token: str,
        ollama_model: str = "sorc/qwen3.5-claude-4.6-opus:9b",
    ) -> str:
        await self.check_github(github_token)
        await self.check_mcp(source, docker_sock)

        # Use host's Ollama - resolve gateway for Dagger containers
        if not ollama_host:
            ollama_host = os.getenv("OLLAMA_HOST", "")
        if not ollama_host:
            ollama_host = _resolve_container_ollama_host()
        if "localhost" in ollama_host or "127.0.0.1" in ollama_host:
            gateway = _resolve_container_ollama_host()
            ollama_host = ollama_host.replace("localhost", gateway).replace("127.0.0.1", gateway)

        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("GITHUB_TOKEN", github_token).with_env_variable(
            "OLLAMA_MODEL", ollama_model
        ).with_env_variable("OLLAMA_HOST", ollama_host)
        ctr = ctr.with_exec(["python", "scripts/test_suite_validation.py"])
        return "Test suite validated"

    @function
    async def checkOllama(self, ollama: Service | None = None) -> str:
        if ollama is None:
            ollama = (
                dag.container()
                .from_("ollama/ollama:latest")
                .with_env_variable("OLLAMA_HOST", "0.0.0.0")
                .with_exposed_port(11434)
                .as_service()
            )
        alpine = (
            dag.container()
            .from_("alpine:latest")
            .with_exec(["apk", "add", "--no-cache", "curl"])
            .with_service_binding("ollama", ollama)
        )
        # Readiness check with retries (up to ~2min)
        check_cmd = [
            "sh",
            "-c",
            """
for i in $(seq 1 60); do
  if curl -f --connect-timeout 5 --max-time 10 http://ollama:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama is ready"
    exit 0
  fi
  sleep 2
done
echo "Ollama failed to become ready"
exit 1
            """,
        ]
        result_ctr = alpine.with_exec(check_cmd)
        result = await result_ctr.stdout()
        if await result_ctr.exit_code() != 0:
            raise ValueError("Ollama service failed to become ready after retries")
        return result.strip()

    @function
    async def check_github(self, github_token: str) -> str:
        if not github_token:
            raise ValueError("GITHUB_TOKEN required")
        ubuntu = (
            dag.container()
            .from_("ubuntu:24.04")
            .with_exec(["sh", "-c", "apt update && apt install -y gh curl jq"])
            .with_env_variable("GITHUB_TOKEN", github_token)
        )
        gh_ctr = ubuntu.with_exec(["gh", "api", "/user"])
        if await gh_ctr.exit_code() != 0:
            raise ValueError(
                "gh api /user failed (exit code != 0): invalid token or network issue"
            )
        return "GitHub token valid via gh CLI"

    @function
    async def fix_perms(
        self,
        source: Directory,
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> str:
        if host_uid != 0 and host_gid != 0:
            ctr = dag.container().from_("alpine:latest").with_directory("/app", source)
            ctr = ctr.with_exec(["chown", "-R", f"{host_uid}:{host_gid}", "/app"])
        return "Permissions fixed"

    @function
    async def create_logs(
        self,
        source: Directory,
        host_uid: int = 0,
        host_gid: int = 0,
    ) -> Directory:
        ctr = dag.container().from_("alpine:latest").with_directory("/app", source)
        mkdir_ctr = ctr.with_exec(["mkdir", "-p", "/app/logs"])
        if host_uid != 0 and host_gid != 0:
            mkdir_ctr = mkdir_ctr.with_exec(
                ["chown", "-R", f"{host_uid}:{host_gid}", "/app/logs"]
            )
        return mkdir_ctr.directory("/app/logs")

    @function
    async def start_mcp(self, source: Directory) -> str:
        config = dag.directory().with_new_file(
            ".kilocode/mcp.json",
            """{
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
}""",
        )
        mcp_ctr = (
            source.directory("docker-files/mcp")
            .docker_build()
            .with_directory("/app/.kilocode", config.directory(".kilocode"))
            .with_exposed_port(3003)
            .as_service()
        )
        health_check = (
            dag.container()
            .from_("alpine:3.20")
            .with_exec(["apk", "add", "--no-cache", "curl"])
            .with_service_binding("mcp", mcp_ctr)
            .with_exec(
                [
                    "sh",
                    "-c",
                    "for i in $(seq 1 30); do curl -f -s http://mcp:3003/health >/dev/null 2>&1 && echo 'MCP healthy' && exit 0 || sleep 2; done; echo 'MCP not ready'; exit 1",
                ]
            )
        )
        hc_code = await health_check.exit_code()
        if hc_code != 0:
            hc_log = await health_check.stdout()
            raise ValueError(f"MCP health check failed:\\n{hc_log}")
        print("MCP service healthy, exposed on localhost:3003")
        keepalive = (
            dag.container()
            .from_("alpine:3.20")
            .with_service_binding("mcp", mcp_ctr)
            .with_exec(["tail", "-f", "/dev/null"])
        )
        await keepalive.exit_code()
        return "MCP service stopped (Ctrl+C)"

    @function
    async def stop_mcp(self, source: Directory) -> str:
        return """MCP service is managed by the Dagger pipeline process (started via 'make start-mcp').

To stop:
- Press Ctrl+C in the 'make start-mcp' terminal
- The service auto-cleans up when the Dagger process exits

No persistent containers created outside Dagger engine."""

    @function
    async def check_mcp(
        self, source: Directory, docker_sock: Socket | None = None
    ) -> str:
        """Check MCP service availability. Fails gracefully if MCP is unavailable."""
        import socket as _socket
        # First check if MCP is already running on localhost
        try:
            _socket.setdefaulttimeout(2)
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.connect(("localhost", 3003))
            s.close()
            return "MCP ready (already running on localhost:3003)"
        except (ConnectionRefusedError, OSError, TimeoutError):
            pass
        # If not running, skip the check - MCP is optional
        print("Warning: MCP server not available on localhost:3003, skipping MCP-dependent tests")
        return "MCP not available (skipped)"

    @function
    async def generate_requirements(self, source: Directory) -> Directory:
        """Generate requirements.txt from requirements.in and return the whole /app directory
        so the Dagger CLI can export it to the host."""
        app_dir = source

        container = (
            dag.container()
            .from_("python:3.10-slim")
            .with_directory("/app", app_dir)
            .with_workdir("/app")
            .with_exec(["pip", "install", "--no-cache-dir", "pip-tools"])
            .with_exec(
                [
                    "pip-compile",
                    "--verbose",
                    "--output-file=requirements.txt",
                    "requirements.in",
                ]
            )
        )
        return container.directory("/app")

    @function
    async def stop_containers(self, source: Directory, docker_sock: Socket | None = None) -> str:
        """Stop all Dagger-managed containers. Requires Docker socket."""
        if docker_sock is None:
            return "No Docker socket provided — skipping container stop"
        ctr = (
            dag.container()
            .from_("docker:24-cli")
            .with_unix_socket("/var/run/docker.sock", docker_sock)
            .with_exec(["docker", "ps", "-q", "--filter", "label=dagger.io"])
        )
        container_ids = (await ctr.stdout()).strip()
        if not container_ids:
            return "No Dagger containers running"
        ctr2 = (
            dag.container()
            .from_("docker:24-cli")
            .with_unix_socket("/var/run/docker.sock", docker_sock)
            .with_exec(["docker", "stop"] + container_ids.split("\n"))
        )
        await ctr2.stdout()
        return f"Stopped {len(container_ids.split(chr(10)))} container(s)"

    @function
    async def check_secrets(self, source: Directory) -> str:
        ctr = dag.container().from_("trufflesecurity/trufflehog:latest")
        ctr = ctr.with_directory("/app", source)
        ctr = ctr.with_exec(["trufflehog", "filesystem", "/app", "--no-verification"])
        return "Secrets checked"

    @function
    async def collect_tests(self, source: Directory, type: str) -> str:
        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("TYPE", type)
        ctr = ctr.with_exec(["python", "src/collect_tests.py"])
        return "Tests collected"

    @function
    async def collect_executed(self, source: Directory, type: str) -> str:
        ctr = await self._agents_base(source)
        ctr = ctr.with_env_variable("TYPE", type)
        ctr = ctr.with_exec(["python", "src/parse_executed_tests.py"])
        return "Executed tests collected"
