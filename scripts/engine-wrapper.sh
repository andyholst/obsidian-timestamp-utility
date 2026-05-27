#!/bin/bash

if command -v nerdctl >/dev/null 2>&1; then
  CONTAINER_CMD=nerdctl
elif command -v podman >/dev/null 2>&1; then
  CONTAINER_CMD=podman
elif command -v docker >/dev/null 2>&1; then
  CONTAINER_CMD=docker
else
  echo "No supported container runtime found (nerdctl, podman, or docker)." >&2
  exit 1
fi

DAGGER_ENGINE_NAME="dagger-engine-v0.20.1"

case "$1" in
  check)
    if $CONTAINER_CMD ps --filter status=running --format '{{.Names}}' | grep -q "$DAGGER_ENGINE_NAME"; then
      exit 0
    else
      echo "Dagger engine not running" >&2
      exit 1
    fi
    ;;
  start)
    if $CONTAINER_CMD ps --filter status=running --format '{{.Names}}' | grep -q "$DAGGER_ENGINE_NAME"; then
      echo "Dagger engine already running."
      exit 0
    fi
    echo "Starting Dagger engine (ensuring single instance)..."
    # Clean any old dagger engines first (prevents duplicates from CLI auto-start)
    ENGINES=( $($CONTAINER_CMD ps -a --format '{{.Names}}' | grep -E 'dagger-engine' || true) )
    for e in "${ENGINES[@]}"; do
      echo "Removing old/stopped engine container: $e"
      $CONTAINER_CMD rm -f "$e" 2>/dev/null || true
    done
    $CONTAINER_CMD run -d --privileged \
      --name "$DAGGER_ENGINE_NAME" \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v /var/lib/containerd:/var/lib/containerd \
      -p 1234:1234 \
      registry.dagger.io/engine:v0.20.1 >/dev/null
    echo "Dagger engine started successfully."

    echo "Waiting for engine to be ready (up to 30s)..."
    for i in {1..30}; do
      if $CONTAINER_CMD ps --filter status=running --format '{{.Names}}' | grep -q "$DAGGER_ENGINE_NAME" && \
         timeout 1 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/1234' 2>/dev/null; then
        echo "Dagger engine ready on port 1234."
        break
      fi
      sleep 1
    done
    ;;
  stop)
    ENGINES=( $($CONTAINER_CMD ps -a --format '{{.Names}}' | grep -E 'dagger-engine' || true) )
    for e in "${ENGINES[@]}"; do
      echo "Stopping and removing: $e"
      $CONTAINER_CMD rm -f "$e" 2>/dev/null || true
    done
    ;;
  *)
    echo "Usage: $0 {check|start|stop}" >&2
    exit 1
    ;;
esac
