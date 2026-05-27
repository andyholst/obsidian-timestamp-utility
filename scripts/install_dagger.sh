#!/bin/bash

set -euo pipefail
DAGGER_VERSION="v0.20.1"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
if ! command_exists curl; then
    echo "Error: curl is required but not installed. Please install curl and retry."
    exit 1
fi

if ! command_exists docker && ! command_exists podman && ! command_exists nerdctl; then
    echo "Error: A container runtime (Docker, Podman, or Nerdctl) is required but not found."
    echo "Install one (Docker recommended) before proceeding."
    exit 1
fi

# Check if runtime is running/accessible
if command_exists docker; then
    docker info >/dev/null 2>&1 || { echo "Error: Docker is installed but not running or inaccessible."; exit 1; }
elif command_exists nerdctl; then
    nerdctl info >/dev/null 2>&1 || { echo "Error: Nerdctl is installed but not running or inaccessible."; exit 1; }
elif command_exists podman; then
    podman info >/dev/null 2>&1 || { echo "Error: Podman is installed but not running or inaccessible."; exit 1; }
fi

mkdir -p bin

if [ -x "./bin/dagger" ] && ./bin/dagger version | cut -d" " -f2 | grep -q "^${DAGGER_VERSION}$"; then
    echo "Local Dagger CLI (${DAGGER_VERSION}) already installed at ./bin/dagger"
    ./bin/dagger version
    exit 0
fi

echo "Installing Dagger CLI ${DAGGER_VERSION} to ./bin/dagger..."

curl -L "https://github.com/dagger/dagger/releases/download/${DAGGER_VERSION}/dagger_${DAGGER_VERSION}_linux_amd64.tar.gz" | tar xz -C ./bin

chmod +x ./bin/dagger

echo "Dagger CLI ${DAGGER_VERSION} installed successfully!"
./bin/dagger version

echo "Installation complete! Use ./bin/dagger for commands."
rm -rf tempbin/
