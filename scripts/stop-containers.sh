#!/bin/bash

set -euo pipefail

if ! command -v nerdctl >/dev/null 2>&1; then
  echo "nerdctl is required but not found on PATH." >&2
  exit 1
fi

PRUNE_OPTS="--all --force --volumes"

stop_containers() {
  echo "Stopping and removing all containers using nerdctl..."
  ids=$(nerdctl ps -aq)
  if [ -n "$ids" ]; then
    nerdctl rm -f $ids
  fi
  pkill -f 'containerd-shim.*dagger' || true
  echo "All containers removed."
}

clean_images() {
  echo "Pruning all unused images, networks, volumes, and cache using nerdctl..."
  nerdctl system prune $PRUNE_OPTS
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
