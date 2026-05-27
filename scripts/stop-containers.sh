#!/bin/bash

set -euo pipefail

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

PRUNE_OPTS="--all --force --volumes"

stop_containers() {
  echo "Stopping and removing all containers using $CONTAINER_CMD..."
  ids=$($CONTAINER_CMD ps -aq)
  if [ -n "$ids" ]; then
    $CONTAINER_CMD rm -f $ids
  fi
  pkill -f 'containerd-shim.*dagger' || true
  echo "All containers removed."
}

clean_images() {
  echo "Pruning all unused images, networks, volumes, and cache using $CONTAINER_CMD..."
  $CONTAINER_CMD system prune $PRUNE_OPTS
  echo "OCI cleanup complete."
}

case "${1:-all}" in
  stop)
    stop_containers
    ;;
  clean)
    clean_images
    ;;
  all|*)
    stop_containers
    clean_images
    ;;
esac
