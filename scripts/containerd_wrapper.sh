#!/bin/bash

# Check available runtimes
if command -v nerdctl &> /dev/null; then
    runtime="nerdctl"
elif command -v docker &> /dev/null; then
    runtime="docker"
else
    echo "Error: Neither nerdctl nor docker is installed."
    exit 1
fi

# Check if it's a compose command
# Compose commands in the Makefile start with -f followed by a file in docker-compose-files/
if [ "$1" = "-f" ] && [ -n "$2" ] && [[ "$2" == docker-compose-files/* ]]; then
    # Compose command: use 'compose' subcommand
    if [ "$runtime" = "nerdctl" ]; then
        exec nerdctl compose "$@"
    else
        exec docker compose "$@"
    fi
else
    # Direct command: pass straight to nerdctl or docker
    exec "$runtime" "$@"
fi
