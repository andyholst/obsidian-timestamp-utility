#!/usr/bin/env bash
# run_e2e_tests.sh — Standing e2e gates (ticket20 + ticket22 + greetings)
# Simple wrapper: runs pytest e2e markers in the integration-test-agents container.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "E2E: running standing e2e gates (ticket20 + ticket22 + greetings)..."

# Run the 3 standing e2e tests via the integration-test-agents compose service
if [ -t 1 ]; then
    nerdctl compose -f docker-compose-files/agents.yaml run --remove-orphans integration-test-agents python -m pytest tests/integration/test_ticket20_e2e_integration.py tests/integration/test_ticket22_e2e_integration.py tests/integration/test_greetings_e2e_integration.py -v -m e2e
else
    script -q /dev/null nerdctl compose -f docker-compose-files/agents.yaml run --remove-orphans integration-test-agents python -m pytest tests/integration/test_ticket20_e2e_integration.py tests/integration/test_ticket22_e2e_integration.py tests/integration/test_greetings_e2e_integration.py -v -m e2e
fi

echo "E2E: done."
