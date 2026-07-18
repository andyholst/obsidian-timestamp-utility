## ADDED Requirements

### Requirement: Makefile docker-backed targets run through the background host
Every Makefile target that invokes a container runtime (any docker, nerdctl, or *compose* binary
via $(call docker_run, ...)) MUST be executed through the Hermes terminal(background=true) channel,
which runs on the REAL HOST that owns the docker/nerdctl daemon and the live Ollama. The foreground
sandbox (/workspace) has no container runtime and MUST NOT be used for these targets.

#### Scenario: long-running verification targets use background
- **WHEN** make run-agentics, make build-app, make test-app, make loop-harness, make loop-e2e,
  make deliver-change, make phase7-archive, or make release-flow is run
- **THEN** it is launched via terminal(background=true) and executes on the real host (docker
  available), never in the foreground sandbox

#### Scenario: any container-backed target uses background
- **WHEN** any Makefile target that resolves a docker/nerdctl/compose binary is run (including short
  ones such as make loop-collect, make loop-ts-floor, make loop-unit, make test-agents-unit,
  make test-agents-integration)
- **THEN** it is launched via terminal(background=true) so it reaches the host daemon instead of
  failing with docker: command not found in the foreground sandbox

#### Scenario: foreground sandbox is not a substitute
- **WHEN** a make <docker-backed-target> command would be issued from the foreground terminal
- **THEN** the agent routes it through terminal(background=true) instead, and does not report
  "can't run from here" as a blocker — the host runs make for it

### Requirement: Background execution MUST be the default, not an opt-in
The background-host channel MUST be the MANDATORY DEFAULT for all container-backed make targets (standing
behaviour B31). It is not advisory and not limited to "long-running" steps.

#### Scenario: no docker in foreground sandbox
- **WHEN** the agent checks the foreground sandbox for a docker/nerdctl binary
- **THEN** it finds none, and concludes the only supported path to the daemon is terminal(background=true)

#### Scenario: B8 sync set records the behaviour
- **WHEN** the B8 doc-sync files (AGENTS.md, hermes/skills/openspec-loop-harness.md,
  docs/openspec-engineering-loop-harness.md, Makefile, scripts/run-loop-harness.sh) are grepped for
  the B-behaviour range
- **THEN** each states B1-B31 so check-docs-sync still PASSES
