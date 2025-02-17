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

# Identify the merge base between the current branch and main
MERGE_BASE=$(git merge-base HEAD main)
if [ -z "$MERGE_BASE" ]; then
    echo "Error: Could not determine merge base with main"
    exit 1
fi
echo "Merge base with main: $MERGE_BASE"

# Get the HEAD commit hash
HEAD_COMMIT=$(git rev-parse HEAD)
echo "Validating commits with commitlint from $MERGE_BASE to $HEAD_COMMIT..."

# Validate commits using commitlint
for commit in $(git rev-list "$MERGE_BASE..$HEAD_COMMIT"); do
    git show -s --format=%B "$commit" | commitlint || {
        echo "Error: Commit $commit does not conform to conventional commit standards"
        git show -s --format=%B "$commit"
        exit 1
    }
done
echo "All commits in the current branch validated successfully"

# Apply the tag to the HEAD commit
echo "Applying tag $TAG to HEAD commit $HEAD_COMMIT..."
git tag -d "$TAG" 2>/dev/null || true
git tag -f "$TAG" || { echo "Error: Failed to create tag $TAG"; git tag -l; exit 1; }

# Generate changelog for commits from after the merge base to the tagged HEAD
echo "Generating changelog for commits from $MERGE_BASE to $TAG..."

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

# Process each commit in the range
for commit in $(git rev-list "$MERGE_BASE..$HEAD_COMMIT"); do
    # Get the full commit message (subject + body)
    full_message=$(git log -1 --pretty=format:"%B" "$commit")
    while IFS= read -r line; do
        # Skip empty lines to avoid blank entries
        [ -z "$line" ] && continue
        parse_line "$line"
    done <<< "$full_message"
done

# Build the new changelog section with actual line breaks
NEW_CHANGELOG="## $TAG\n\n"

if [ ${#FEATURES[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### ✨ New Features\n"
    for feat in "${FEATURES[@]}"; do
        NEW_CHANGELOG+="- **$feat**\n"
    done
fi

if [ ${#FIXES[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### 🐞 Bug Fixes\n"
    for fix in "${FIXES[@]}"; do
        NEW_CHANGELOG+="- **$fix**\n"
    done
fi

if [ ${#PERFS[@]} -gt 0 ]; then
    NEWCHANGELOG+="### ⚡ Performance Improvements\n"
    for perf in "${PERFS[@]}"; do
        NEW_CHANGELOG+="- **$perf**\n"
    done
fi

if [ ${#REFACTORS[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### 🔧 Refactor Improvements\n"
    for refactor in "${REFACTORS[@]}"; do
        NEW_CHANGELOG+="- **$refactor**\n"
    done
fi

if [ ${#DOCS[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### 📝 Documentation\n"
    for doc in "${DOCS[@]}"; do
        NEW_CHANGELOG+="- **$doc**\n"
    done
fi

if [ ${#CHORES[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### 🛠️ Maintenance\n"
    for chore in "${CHORES[@]}"; do
        NEW_CHANGELOG+="- **$chore**\n"
    done
fi

if [ ${#FEATURES[@]} -eq 0 ] && [ ${#FIXES[@]} -eq 0 ] && [ ${#PERFS[@]} -eq 0 ] && [ ${#REFACTORS[@]} -eq 0 ] && [ ${#DOCS[@]} -eq 0 ] && [ ${#CHORES[@]} -eq 0 ]; then
    NEW_CHANGELOG+="### 🔍 No Changes\n- No notable changes in this release.\n"
fi

# Define the changelog file path
CHANGELOG_FILE="/app/CHANGELOG.md"

# Create or update the changelog file with interpreted newlines
if [ ! -f "$CHANGELOG_FILE" ]; then
    echo "Creating new CHANGELOG.md with commits from the current branch..."
    echo -e "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n$NEW_CHANGELOG" > "$CHANGELOG_FILE"
else
    echo "Appending changelog for the current branch to existing CHANGELOG.md..."
    # Insert the new section after the header with actual newlines
    sed -i "/^# Changelog/a\\" "$CHANGELOG_FILE"
    echo -e "$NEW_CHANGELOG" >> "$CHANGELOG_FILE"
fi

# Verify that the changelog file exists
test -f "$CHANGELOG_FILE" || { echo "Error: CHANGELOG.md was not created or updated"; ls -la /app; exit 1; }

# Prepare release files
mkdir -p release
cp dist/main.js manifest.json README.md CHANGELOG.md release/ || { echo "Error: Failed to copy files to release/"; ls -la /app; exit 1; }
cd release

# Create a zip file for the release
zip -r "release-$TAG.zip" main.js manifest.json README.md CHANGELOG.md >/dev/null 2>&1 || { echo "Error: Failed to create zip file"; exit 1; }

echo "release/release-$TAG.zip created successfully"
