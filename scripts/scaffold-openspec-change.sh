#!/opt/homebrew/bin/bash
# scaffold-openspec-change.sh — reproducible harness for creating OpenSpec changes.
#
# Wraps the REAL openspec CLI (durable behaviour B15: the change directory is produced by
# `openspec new change`, NEVER hand-written by this script), then seeds the conventional
# proposal.md / tasks.md / specs/<CAPABILITY>/spec.md from a template so every new
# change has the same validated shape. Finally runs `openspec validate` so the change is
# green before any implementation work begins.
#
# No git commit/push is performed (B4/B14) — only openspec/changes/<name>/ is written.
set -euo pipefail

usage() {
  cat <<'EOUSAGE'
scaffold-openspec-change.sh — reproducible harness to create an OpenSpec change

This wraps the REAL `openspec` CLI (durable behaviour B15: the change directory is
produced by `openspec new change`, never hand-written), then seeds the conventional
proposal.md / tasks.md / specs/<CAPABILITY>/spec.md from a template, and finally runs
`openspec validate` so the change is green before any implementation.

SYNOPSIS
  scripts/scaffold-openspec-change.sh --name <name> [--desc <text>] [--goal <text>] [--capability <cap>]

ARGUMENTS
  --name <name>        (REQUIRED) kebab-case change name, e.g. add-dark-mode-toggle
  --desc <text>        (optional) one-line description stored in the change README.md
  --goal <text>        (optional) goal metadata stored in .openspec.yaml
  --capability <cap>   (optional) capability name for specs/<cap>/spec.md
                        (defaults to --name when omitted)
  -h, --help           show this help and exit

EXAMPLE (direct)
  scripts/scaffold-openspec-change.sh \
    --name add-dark-mode-toggle \
    --desc "Add a dark-mode toggle command to the plugin" \
    --goal "Users can switch theme from the command palette" \
    --capability dark-mode

EXAMPLE (via Makefile — preferred)
  make openspec-new \
    NAME=add-dark-mode-toggle \
    CAPABILITY=dark-mode \
    DESC="Add a dark-mode toggle command to the plugin" \
    GOAL="Users can switch theme from the command palette"

RESULT
  Creates openspec/changes/<name>/ containing:
    .openspec.yaml        (produced by the openspec CLI)
    README.md             (produced by the openspec CLI)
    proposal.md           (seeded template — edit Why / What / Impact)
    tasks.md              (seeded checkbox plan)
    specs/<cap>/spec.md   (seeded delta-format spec: ADDED Requirements -> Scenario WHEN/THEN)
  Then prints the `openspec validate <name>` result (must be exit 0).

NOTES
  - No git commit/push is performed (B4/B14).
  - Refuses (exit 1) if NAME is empty or if the change directory already exists.
  - For Makefile usage run `make openspec-new` with no NAME to see the same usage.
EOUSAGE
}

NAME=""
DESC=""
GOAL=""
CAPABILITY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --name)       NAME="$2"; shift 2 ;;
    --desc)       DESC="$2"; shift 2 ;;
    --goal)       GOAL="$2"; shift 2 ;;
    --capability) CAPABILITY="$2"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [ -z "$NAME" ]; then
  echo "ERROR: --name is required." >&2
  echo "Run 'scripts/scaffold-openspec-change.sh --help' (or 'make openspec-new' with no NAME) for usage." >&2
  exit 1
fi
# Capability defaults to the change name when not given.
[ -z "$CAPABILITY" ] && CAPABILITY="$NAME"

# Human-readable title derived from the kebab name (e.g. my-cool-change -> "My Cool Change").
TITLE_LINE="$(echo "$NAME" | sed -E 's/(^|-)(\w)/\U\2/g')"

CHANGE_DIR="openspec/changes/$NAME"
if [ -d "$CHANGE_DIR" ]; then
  echo "ERROR: $CHANGE_DIR already exists — refusing to overwrite an existing change." >&2
  exit 1
fi

echo "[scaffold] invoking 'openspec new change $NAME' (real CLI, per B15)..."
# The canonical CLI step a human runs. We do NOT hand-write the directory shape.
OPEN_SPEC_ARGS=(new change "$NAME")
[ -n "$DESC" ] && OPEN_SPEC_ARGS+=(--description "$DESC")
[ -n "$GOAL" ] && OPEN_SPEC_ARGS+=(--goal "$GOAL")
if ! openspec "${OPEN_SPEC_ARGS[@]}"; then
  echo "ERROR: 'openspec new change' failed." >&2
  exit 1
fi

# Sanity: the CLI must have created the directory with its own .openspec.yaml.
if [ ! -f "$CHANGE_DIR/.openspec.yaml" ]; then
  echo "ERROR: CLI did not produce $CHANGE_DIR/.openspec.yaml — aborting." >&2
  exit 1
fi

SPEC_DIR="$CHANGE_DIR/specs/$CAPABILITY"
mkdir -p "$SPEC_DIR"

echo "[scaffold] seeding proposal.md / tasks.md / specs/$CAPABILITY/spec.md from template..."

cat > "$CHANGE_DIR/proposal.md" <<EOF
# Proposal: $TITLE_LINE

## Why
$TITLE_LINE
TODO: explain the motivation for this change — what problem it solves and why now.

## What Changes
TODO: describe the concrete changes (files, behaviours, commands). Keep it factual.

## Capabilities
- \`$CAPABILITY\` (new): TODO: one-line description of the capability this change introduces.

## Impact
TODO: call out side effects, dependencies, and what MUST NOT regress (loop-harness gates,
deterministic floor, no git commit/push — B4/B14).
EOF

cat > "$CHANGE_DIR/tasks.md" <<EOF
# Tasks

- [ ] 1.1 Implement the core change for \`$NAME\` (TODO: concrete, verifiable step)
- [ ] 2.1 Verify: run the relevant gate(s) — e.g. \`make build-app\` / \`make test-app\` / \`make loop-unit\`
- [ ] 2.2 TODO: add/adjust tests that prove the behaviour
- [ ] 3.1 B8-sync: update AGENTS.md + openspec-loop-harness skill if behaviour/docs changed
- [ ] 4.1 \`openspec validate $NAME\` passes
EOF

cat > "$SPEC_DIR/spec.md" <<EOF
# $CAPABILITY Specification

## ADDED Requirements

### Requirement: TODO — name the requirement
The system MUST <describe the required behaviour in imperative form>.

#### Scenario: TODO — name the scenario
- **WHEN** <condition or action>
- **THEN** <expected outcome>
EOF

echo "[scaffold] running 'openspec validate $NAME'..."
if openspec validate "$NAME"; then
  echo "[scaffold] OK: change '$NAME' created and validated at $CHANGE_DIR"
  echo "[scaffold] next: edit proposal.md / tasks.md / specs/$CAPABILITY/spec.md, then implement + verify."
  exit 0
else
  echo "ERROR: 'openspec validate $NAME' failed — review the seeded files." >&2
  exit 1
fi
