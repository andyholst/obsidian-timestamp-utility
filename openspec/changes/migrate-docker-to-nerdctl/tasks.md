# Tasks: Migrate from Docker to nerdctl

## 1. Rename Dockerfiles to Containerfiles
- [ ] 1.1 Rename `containers/agents/Dockerfile` → `containers/agents/Containerfile`
- [ ] 1.2 Rename `containers/npm/Dockerfile` → `containers/npm/Containerfile`
- [ ] 1.3 Rename `containers/pip/Dockerfile` → `containers/pip/Containerfile`
- [ ] 1.4 Rename `containers/gitleaks/Dockerfile` → `containers/gitleaks/Containerfile`
- [ ] 1.5 Rename `containers/gitleaks-tests/Dockerfile` → `containers/gitleaks-tests/Containerfile`

## 2. Migrate Makefile
- [ ] 2.1 Replace `docker compose -f ...` with `nerdctl compose -f ...` in all targets
- [ ] 2.2 Rename `docker_run` macro to `nerdctl_run` (or keep name, change internals)
- [ ] 2.3 Replace `docker build` references with `nerdctl build`
- [ ] 2.4 Update `stop-containers` target to use `nerdctl ps` / `nerdctl stop`
- [ ] 2.5 Update `DOCKER_SOCK` detection (nerdctl uses containerd socket)
- [ ] 2.6 Verify `make build-app` succeeds
- [ ] 2.7 Verify `make test-app` succeeds

## 3. Migrate Shell Scripts
- [ ] 3.1 Update `scripts/run-loop-harness.sh` — replace docker compose/kill/rm with nerdctl
- [ ] 3.2 Update `scripts/engine-wrapper.sh` — prefer nerdctl over docker
- [ ] 3.3 Update `scripts/stop-containers.sh` — use nerdctl commands
- [ ] 3.4 Update `scripts/release.sh` — replace docker references
- [ ] 3.5 Update `scripts/obsidian-tsu-opencode.sh` — already uses nerdctl, verify
- [ ] 3.6 Update `scripts/install_dagger.sh` — remove docker dependency
- [ ] 3.7 Update `scripts/gen_changelog.sh` — update comments

## 4. Migrate CI/CD Workflows
- [ ] 4.1 Update `.github/workflows/ci.yml` (or equivalent) — replace docker actions with nerdctl
- [ ] 4.2 Update `.github/workflows/release.yml` — replace docker actions
- [ ] 4.3 Update any other workflow files that reference docker

## 5. Migrate Documentation
- [ ] 5.1 Update `docs/openspec-engineering-loop-harness.md` — replace docker with nerdctl
- [ ] 5.2 Update `hermes/skills/openspec-loop-harness.md` — replace docker with nerdctl
- [ ] 5.3 Update `AGENTS.md` — replace docker references with nerdctl
- [ ] 5.4 Update `README.md` if it references docker setup

## 6. Migrate Test Fixtures
- [ ] 6.1 Update `tests/fixtures/check_docs_sync/in_sync_ascii/...` — replace docker refs
- [ ] 6.2 Update `tests/test_secret_scanner.py` — fix comments about docker runtime
- [ ] 6.3 Update Python source comments referencing docker compose

## 7. Verify All Changes
- [ ] 7.1 Run `make build-app` and confirm success
- [ ] 7.2 Run `make test-app` and confirm success
- [ ] 7.3 Run `grep -rn "docker" Makefile scripts/` — only comments/legacy references should remain
- [ ] 7.4 Verify no `docker compose` or `docker build` calls remain in executable code
- [ ] 7.5 Run `make format` and confirm clean
