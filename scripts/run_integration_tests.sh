#!/usr/bin/env bash
# run_integration_tests.sh — Broad agentic integration suite (B17)
# Runs the FAST subset: excludes e2e (its own stage) and slow full-pipeline tests.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "INTEGRATION: running fast integration suite (excludes e2e + slow)..."

# Run the fast integration test subset via the integration-test-agents compose service
if [ -t 1 ]; then
    nerdctl compose -f docker-compose-files/agents.yaml run --remove-orphans \
        -e GITHUB_TOKEN=${GITHUB_TOKEN:-} \
        -e "TEST_FILTER=--maxfail=1 -m 'integration and not e2e and not slow'" \
        integration-test-agents python -m pytest tests/integration/ -v
else
    script -q /dev/null nerdctl compose -f docker-compose-files/agents.yaml run --remove-orphans \
        -e GITHUB_TOKEN=${GITHUB_TOKEN:-} \
        -e "TEST_FILTER=--maxfail=1 -m 'integration and not e2e and not slow'" \
        integration-test-agents python -m pytest tests/integration/ -v
fi

echo "INTEGRATION: done."
