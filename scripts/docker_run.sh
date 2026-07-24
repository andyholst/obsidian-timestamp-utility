#!/opt/homebrew/bin/bash
#
# docker_run.sh — PTY-aware wrapper for nerdctl compose run.
#
set -uo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <compose-file> <extra-flags> <service> <cmd...>" >&2
    exit 1
fi

COMPOSE_FILE="$1"
shift

# Detect runtime
if command -v nerdctl >/dev/null 2>&1; then
    RUNTIME="nerdctl"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
else
    echo "ERROR: Neither nerdctl nor docker found" >&2
    exit 1
fi

# Build arguments
ARGS=()
CMD_ARGS=()
SERVICE=""
FOUND_SERVICE=0

for arg in "$@"; do
    if [ "$FOUND_SERVICE" -eq 0 ]; then
        case "$arg" in
            -*) ARGS+=("$arg") ;;
            *) SERVICE="$arg"; FOUND_SERVICE=1 ;;
        esac
    else
        CMD_ARGS+=("$arg")
    fi
done

# Handle "bash -c" commands — keep as-is so nerdctl gets ["bash", "-c", "..."]
# Stripping to just ["-c", "..."] caused: exec: "-c": executable file not found in $PATH
if [ ${#CMD_ARGS[@]} -ge 1 ]; then
    case "${CMD_ARGS[0]}" in
        bash\ -c*)
            # Reconstruct as separate args: ["bash", "-c", "<cmd>"]
            BASH_C_CMD="${CMD_ARGS[0]#bash -c }"
            CMD_ARGS=("bash" "-c" "$BASH_C_CMD")
            ;;
    esac
fi

if [ -z "$SERVICE" ]; then
    echo "ERROR: Could not determine service name" >&2
    exit 1
fi

# Verbose logging
LOG_ARGS="${ARGS[*]:-}"
LOG_CMD="${CMD_ARGS[*]:-}"
echo "DOCKER_RUN: $RUNTIME run $LOG_ARGS $SERVICE $LOG_CMD" >&2

if [ "$RUNTIME" = "nerdctl" ]; then
    # nerdctl compose run on macOS requires a real TTY — use script to allocate one.
    # The command's output goes to the PTY which bypasses stdout pipes (tee).
    # We use a FIFO pipe: redirect script's stdout to the FIFO, then cat it
    # to stderr (which IS captured by the pipe in run-loop-harness.sh).
    # --remove-orphans (after run): cleans up stale containers from aborted runs.
    _FIFO="/tmp/docker_run_fifo_$$"
    rm -f "$_FIFO"
    mkfifo "$_FIFO"

    if [ ${#ARGS[@]} -gt 0 ] && [ ${#CMD_ARGS[@]} -gt 0 ]; then
        script -q /dev/null nerdctl compose -f "$COMPOSE_FILE" run --remove-orphans "${ARGS[@]}" "$SERVICE" "${CMD_ARGS[@]}" > "$_FIFO" &
        _SCRIPT_PID=$!
        cat "$_FIFO" >&2
        wait "$_SCRIPT_PID" 2>/dev/null || true
    elif [ ${#ARGS[@]} -gt 0 ]; then
        script -q /dev/null nerdctl compose -f "$COMPOSE_FILE" run --remove-orphans "${ARGS[@]}" "$SERVICE" > "$_FIFO" &
        _SCRIPT_PID=$!
        cat "$_FIFO" >&2
        wait "$_SCRIPT_PID" 2>/dev/null || true
    elif [ ${#CMD_ARGS[@]} -gt 0 ]; then
        script -q /dev/null nerdctl compose -f "$COMPOSE_FILE" run --remove-orphans "$SERVICE" "${CMD_ARGS[@]}" > "$_FIFO" &
        _SCRIPT_PID=$!
        cat "$_FIFO" >&2
        wait "$_SCRIPT_PID" 2>/dev/null || true
    else
        script -q /dev/null nerdctl compose -f "$COMPOSE_FILE" run --remove-orphans "$SERVICE" > "$_FIFO" &
        _SCRIPT_PID=$!
        cat "$_FIFO" >&2
        wait "$_SCRIPT_PID" 2>/dev/null || true
    fi

    rm -f "$_FIFO"
else
    # docker compose
    if [ ${#ARGS[@]} -gt 0 ] && [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec docker -f "$COMPOSE_FILE" run --rm "${ARGS[@]}" "$SERVICE" "${CMD_ARGS[@]}"
    elif [ ${#ARGS[@]} -gt 0 ]; then
        exec docker -f "$COMPOSE_FILE" run --rm "${ARGS[@]}" "$SERVICE"
    elif [ ${#CMD_ARGS[@]} -gt 0 ]; then
        exec docker -f "$COMPOSE_FILE" run --rm "$SERVICE" "${CMD_ARGS[@]}"
    else
        exec docker -f "$COMPOSE_FILE" run --rm "$SERVICE"
    fi
fi
