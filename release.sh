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

# Use provided COMMIT_RANGE if set (e.g., from GitHub Actions), otherwise compute it
if [ -n "$COMMIT_RANGE" ]; then
    echo "Using provided COMMIT_RANGE: $COMMIT_RANGE"
else
    # Fallback logic for local runs
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "Current branch: $CURRENT_BRANCH"
    MAIN_BRANCH="main"
    git fetch origin "$MAIN_BRANCH" >/dev/null 2>&1 || { echo "Error: Failed to fetch $MAIN_BRANCH"; exit 1; }
    MERGE_BASE=$(git merge-base "origin/$MAIN_BRANCH" "$CURRENT_BRANCH")
    if [ -z "$MERGE_BASE" ]; then
        echo "Error: Could not determine merge base between $CURRENT_BRANCH and $MAIN_BRANCH"
        exit 1
    fi
    COMMIT_RANGE="$MERGE_BASE..HEAD"
    echo "Computed COMMIT_RANGE: $COMMIT_RANGE"
fi

# Validate commits in the range with commitlint
echo "Validating commits with commitlint from $COMMIT_RANGE..."
COMMITS_FOUND=false
for commit in $(git rev-list --no-merges "$COMMIT_RANGE"); do
    COMMITS_FOUND=true
    git show -s --format=%B "$commit" | commitlint || {
        echo "Error: Commit $commit does not conform to conventional commit standards"
        git show -s --format=%B "$commit"
        exit 1
    }
done
if [ "$COMMITS_FOUND" = false ]; then
    echo "No new commits found in range $COMMIT_RANGE"
else
    echo "Commits validated successfully"
fi

# Function to trim leading and trailing whitespace
trim() {
    local var="$1"
    var="${var#"${var%%[![:space:]]*}"}"
    var="${var%"${var##*[![:space:]]}"}"
    echo -n "$var"
}

# Initialize changelog sections as arrays
declare -a FEATURES
declare -a FIXES
declare -a PERFS
declare -a REFACTORS
declare -a DOCS
declare -a CHORES

# Function to parse a line and add to the appropriate category array
parse_line() {
    local line="$1"
    local description
    case "$line" in
        feat:*)
            description=$(trim "${line#feat:}")
            [ -n "$description" ] && FEATURES+=("$description")
            ;;
        fix:*)
            description=$(trim "${line#fix:}")
            [ -n "$description" ] && FIXES+=("$description")
            ;;
        perf:*)
            description=$(trim "${line#perf:}")
            [ -n "$description" ] && PERFS+=("$description")
            ;;
        refactor:*)
            description=$(trim "${line#refactor:}")
            [ -n "$description" ] && REFACTORS+=("$description")
            ;;
        docs:*)
            description=$(trim "${line#docs:}")
            [ -n "$description" ] && DOCS+=("$description")
            ;;
        chore:*)
            description=$(trim "${line#chore:}")
            [ -n "$description" ] && CHORES+=("$description")
            ;;
        *)
            # Ignore lines that don't match a recognized change type
            ;;
    esac
}

# Process commits from the specified range
echo "Generating release notes for commits in range $COMMIT_RANGE..."
for commit in $(git rev-list --no-merges "$COMMIT_RANGE"); do
    COMMIT_MESSAGE=$(git log -1 --pretty=format:"%B" "$commit")
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        parse_line "$line"
    done <<< "$COMMIT_MESSAGE"
done

# Build the release notes section with proper spacing
RELEASE_NOTES="## $TAG\n\n"

if [ ${#FEATURES[@]} -gt 0 ]; then
    RELEASE_NOTES+="### ✨ New Features\n\n"
    for feat in "${FEATURES[@]}"; do
        RELEASE_NOTES+="- **$feat**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#FIXES[@]} -gt 0 ]; then
    RELEASE_NOTES+="### 🐞 Bug Fixes\n\n"
    for fix in "${FIXES[@]}"; do
        RELEASE_NOTES+="- **$fix**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#PERFS[@]} -gt 0 ]; then
    RELEASE_NOTES+="### ⚡ Performance Improvements\n\n"
    for perf in "${PERFS[@]}"; do
        RELEASE_NOTES+="- **$perf**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#REFACTORS[@]} -gt 0 ]; then
    RELEASE_NOTES+="### 🔧 Refactor Improvements\n\n"
    for refactor in "${REFACTORS[@]}"; do
        RELEASE_NOTES+="- **$refactor**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#DOCS[@]} -gt 0 ]; then
    RELEASE_NOTES+="### 📝 Documentation\n\n"
    for doc in "${DOCS[@]}"; do
        RELEASE_NOTES+="- **$doc**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#CHORES[@]} -gt 0 ]; then
    RELEASE_NOTES+="### 🛠️ Maintenance\n\n"
    for chore in "${CHORES[@]}"; do
        RELEASE_NOTES+="- **$chore**\n"
    done
    RELEASE_NOTES+="\n"
fi

if [ ${#FEATURES[@]} -eq 0 ] && [ ${#FIXES[@]} -eq 0 ] && [ ${#PERFS[@]} -eq 0 ] && [ ${#REFACTORS[@]} -eq 0 ] && [ ${#DOCS[@]} -eq 0 ] && [ ${#CHORES[@]} -eq 0 ]; then
    RELEASE_NOTES+="### 🔍 No Changes\n\n- No notable changes in this release.\n"
fi

# Trim trailing newlines and ensure proper formatting
RELEASE_NOTES=$(printf "%b" "$RELEASE_NOTES" | sed -e :a -e '/^\n*$/{$d;N;ba}')$'\n'

# Define the release notes file path
RELEASE_NOTES_FILE="/app/release_notes.md"

# Create or overwrite the release notes file with proper newlines
echo "Creating release_notes.md with commits from $COMMIT_RANGE..."
printf "%b" "$RELEASE_NOTES" > "$RELEASE_NOTES_FILE"

# Verify that the release notes file exists
test -f "$RELEASE_NOTES_FILE" || { echo "Error: release_notes.md was not created"; ls -la /app; exit 1; }

# Prepare release files
mkdir -p release
cp dist/main.js CHANGELOG.md manifest.json README.md release_notes.md release/ || { echo "Error: Failed to copy files to release/"; ls -la /app; exit 1; }
cd release

# Create a zip file for the release
zip -r "release-timestamp-utility-$TAG.zip" main.js manifest.json README.md release_notes.md >/dev/null 2>&1 || { echo "Error: Failed to create zip file"; exit 1; }

echo "release/release-timestamp-utility-$TAG.zip created successfully"
