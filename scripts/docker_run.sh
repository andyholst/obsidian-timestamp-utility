#!/usr/bin/env bash
#
# docker_run.sh — PTY-aware wrapper for docker/nerdctl compose run.
#
# nerdctl compose run on macOS requires a TTY (gives "provided file is not a console" otherwise).
# docker compose does not need it. nerdctl compose run does NOT support --rm (auto-removed).
# This script detects the runtime and allocates a PTY for nerdctl.
# Verbose logging prints the full command before executing.
#
# Usage: scripts/docker_run.sh <compose-file> <extra-flags> <service> <cmd...>
# Example: scripts/docker_run.sh docker-compose-files/tools.yaml -e TAG=v0.1.0 app npm run build
#
# NOTE: All args after compose-file are passed as-is to compose (no quoting/word-splitting).
# The service name and command are the last positional args.
#
# bash 3.2 compatible (macOS default): no associative arrays, no [[ ]].
# Uses ${arr[@]+...} idiom to handle empty arrays safely with set -u.

set -uo pipefail

if [ $# -lt 3 ]; then
    echo "Usage: $0 <compose-file> <extra-flags> <service> <cmd...>" >&2
    echo "Example: $0 docker-compose-files/tools.yaml -e TAG=v0.1.0 app npm run build" >&2
    exit 1
fi

COMPOSE_FILE="$1"
shift

# Detect runtime
if command -v nerdctl >/dev/null 2>&1; then
    RUNTIME="nerdctl"
    DOCKER_CMD="nerdctl compose"
else
    RUNTIME="docker"
    DOCKER_CMD="docker compose"
fi

# Build the compose run arguments
# Everything until the service name are flags (--rm, -e, etc.)
# The service name and everything after is the command

# Use arrays for proper quoting preservation
ARGS=()
CMD_ARGS=()
SERVICE=""
FOUND_SERVICE=0

for arg in "$@"; do
    if [ "$FOUND_SERVICE" -eq 0 ]; then
        case "$arg" in
            -*)
                ARGS+=("$arg")
                ;;
            *)
                SERVICE="$arg"
                FOUND_SERVICE=1
                ;;
        esac
    else
        CMD_ARGS+=("$arg")
    fi
done

if [ -z "$SERVICE" ]; then
    echo "ERROR: Could not determine service name" >&2
    exit 1
fi

# Verbose logging (safe for empty arrays in bash 3.2)
LOG_ARGS=""
if [ ${#ARGS[@]} -gt 0 ]; then
    LOG_ARGS="${ARGS[*]}"
fi
LOG_CMD=""
if [ ${#CMD_ARGS[@]} -gt 0 ]; then
    LOG_CMD="${CMD_ARGS[*]}"
fi
echo "DOCKER_RUN: $DOCKER_CMD -f $COMPOSE_FILE run $LOG_ARGS $SERVICE $LOG_CMD" >&2

if [ "$RUNTIME" = "nerdctl" ]; then
    # nerdctl requires TTY — use macOS script to allocate PTY
    # macOS script: script [-q] /dev/null command args...
    # This allocates a PTY and runs the command, discarding output to /dev/null
    # Use explicit if-else to avoid ${arr[@]+"${arr[@]}"} bash 3.2 issues
    if [ ${#ARGS[@]} -gt 0 ] && [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec script -q /dev/null $DOCKER_CMD -f $COMPOSE_FILE run "${ARGS[@]}" $SERVICE "${CMD_ARGS[@]}"
    elif [ ${#ARGS[@]} -gt 0 ]; then
        exec script -q /dev/null $DOCKER_CMD -f $COMPOSE_FILE run "${ARGS[@]}" $SERVICE
    elif [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec script -q /dev/null $DOCKER_CMD -f $COMPOSE_FILE run $SERVICE "${CMD_ARGS[@]}"
    else
        exec script -q /dev/null $DOCKER_CMD -f $COMPOSE_FILE run $SERVICE
    fi
else
    # docker compose supports --rm and doesn't require TTY
    if [ ${#ARGS[@]} -gt 0 ] && [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec $DOCKER_CMD -f "$COMPOSE_FILE" run --rm "${ARGS[@]}" "$SERVICE" "${CMD_ARGS[@]}"
    elif [ ${#ARGS[@]} -gt 0 ]; then
        exec $DOCKER_CMD -f "$COMPOSE_FILE" run --rm "${ARGS[@]}" "$SERVICE"
    elif [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec $DOCKER_CMD -f "$COMPOSE_FILE" run --rm "$SERVICE" "${CMD_ARGS[@]}"
    else
        exec $DOCKER_CMD -f "$COMPOSE_FILE" run --rm "$SERVICE"
    fi
fi
