# Proposal: Migrate from Docker to nerdctl

## Why

Docker Desktop is a heavy dependency requiring a GUI app, license on newer macOS versions, and significant disk/memory. The project already uses rootless `nerdctl` for all container operations — every `docker compose` call in the Makefile actually routes through `nerdctl` under the hood. We should make this explicit: use `nerdctl compose` directly, eliminating Docker Desktop as a dependency entirely.

## What Changes

- Replace all `docker compose` invocations with `nerdctl compose` in the Makefile and shell scripts
- Rename `containers/<name>/Dockerfile` → `containers/<name>/Containerfile` (nerdctl convention)
- Update docker-compose YAML files to work with nerdctl compose (no Docker-specific extensions)
- Update shell scripts (`run-loop-harness.sh`, `release.sh`, `stop-containers.sh`, etc.)
- Update CI/CD workflows (`.github/workflows/*.yml`)
- Update documentation to reference nerdctl instead of Docker
- Update test fixtures that reference docker
- Remove Docker Desktop dependency from setup instructions

## Capabilities

- `migrate-docker-to-nerdctl` — Replace all Docker references with nerdctl equivalents across the project

## Impact

- **Makefile**: ~20+ occurrences of `docker compose` → `nerdctl compose`
- **Shell scripts**: ~10+ files need updates
- **CI/CD**: GitHub Actions workflows need updates
- **Dockerfiles**: Rename to Containerfiles per nerdctl convention
- **Docs**: ~15+ documentation references to update
