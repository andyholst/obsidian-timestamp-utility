#!/bin/bash
set -e

# Ensure the repository is safe for Git operations
git config --global --add safe.directory /app

# Validate required environment variables
if [ -z "$TAG" ]; then
    echo "Error: TAG environment variable is not set"
    exit 1
fi

if [ -z "$REPO_NAME" ]; then
    echo "Error: REPO_NAME environment variable is not set"
    exit 1
fi

echo "TAG=$TAG"
echo "REPO_NAME=$REPO_NAME"

# Define paths
CHANGELOG_FILE="/app/CHANGELOG.md"
RELEASE_NOTES_FILE="/app/release_notes.md"

# Check if CHANGELOG.md exists
if [ ! -f "$CHANGELOG_FILE" ]; then
    echo "Error: $CHANGELOG_FILE not found"
    exit 1
fi

# Extract the first section from CHANGELOG.md (from first ## to next ##)
echo "Extracting the first section from $CHANGELOG_FILE..."
RELEASE_NOTES=$(sed -n '/^## /{p; :a; n; /^## /q; p; ba}' "$CHANGELOG_FILE")

# Check if we found a section
if [ -z "$RELEASE_NOTES" ]; then
    echo "Error: No sections found in $CHANGELOG_FILE"
    echo "Available content in CHANGELOG.md (first 10 lines):"
    head -n 10 "$CHANGELOG_FILE"
    exit 1
fi

# Trim trailing newlines and ensure proper formatting
RELEASE_NOTES=$(printf "%b" "$RELEASE_NOTES" | sed -e :a -e '/^\n*$/{$d;N;ba}')$'\n'

# Create or overwrite the release notes file with proper newlines
echo "Creating $RELEASE_NOTES_FILE with first section from $CHANGELOG_FILE..."
printf "%b" "$RELEASE_NOTES" > "$RELEASE_NOTES_FILE"

# Verify that the release notes file exists
test -f "$RELEASE_NOTES_FILE" || { echo "Error: $RELEASE_NOTES_FILE was not created"; ls -la /app; exit 1; }

# Prepare release files
mkdir -p release
cp dist/main.js CHANGELOG.md manifest.json README.md release_notes.md release/ || { echo "Error: Failed to copy files to release/"; ls -la /app; exit 1; }
cd release

# Create a zip file for the release
zip -r "release-timestamp-utility-$TAG.zip" main.js manifest.json README.md release_notes.md >/dev/null 2>&1 || { echo "Error: Failed to create zip file"; exit 1; }

echo "release/release-timestamp-utility-$TAG.zip created successfully"
