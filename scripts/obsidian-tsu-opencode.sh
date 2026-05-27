#!/bin/zsh
set -e

WORKSPACE="$(pwd)"
OPENCODE_JSON="$WORKSPACE/opencode.json"
AUTH_JSON="$HOME/.local/share/opencode/auth.json"

if ! nerdctl images | grep -q obsidian-tsu-dev; then
  nerdctl build -t obsidian-tsu-dev -f docker-files/dev/Containerfile .
fi

nerdctl run -it --rm \
  --network=host \
  -v "$WORKSPACE:/workspace" \
  -v "$OPENCODE_JSON:/root/.config/opencode/opencode.json:ro" \
  -v "$AUTH_JSON:/root/.local/share/opencode/auth.json:ro" \
  -w /workspace \
  obsidian-tsu-dev opencode "$@"