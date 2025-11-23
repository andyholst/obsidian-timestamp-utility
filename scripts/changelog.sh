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

# Get the latest tag (excluding the current $TAG)
LATEST_TAG=$(git tag --sort=-creatordate | grep -v "$TAG" | head -n 1)
if [ -z "$LATEST_TAG" ]; then
    echo "No previous tags found, processing all commits up to HEAD"
    COMMIT_RANGE="HEAD"
else
    echo "Latest tag: $LATEST_TAG"
    # Get the commit hash of the latest tag
    LATEST_TAG_COMMIT=$(git rev-list -n 1 "$LATEST_TAG")
    COMMIT_RANGE="$LATEST_TAG_COMMIT..HEAD"
fi

# Validate commits in the range with commitlint
echo "Validating commits with commitlint from $COMMIT_RANGE..."
COMMITS_FOUND=false
for commit in $(git rev-list --no-merges "$COMMIT_RANGE"); do
    # Skip the commit that created the latest tag itself
    if [ -n "$LATEST_TAG_COMMIT" ] && [ "$commit" = "$LATEST_TAG_COMMIT" ]; then
        continue
    fi
    COMMITS_FOUND=true
    git show -s --format=%B "$commit" | commitlint || {
        echo "Error: Commit $commit does not conform to conventional commit standards"
        git show -s --format=%B "$commit"
        exit 1
    }
done
if [ "$COMMITS_FOUND" = false ]; then
    echo "No new commits found since $LATEST_TAG"
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

# Arrays to store changes for the new $TAG
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

# Process commits in the range
echo "Generating changelog for commits in range $COMMIT_RANGE..."
for commit in $(git rev-list --no-merges "$COMMIT_RANGE"); do
    # Skip the commit that created the latest tag itself
    if [ -n "$LATEST_TAG_COMMIT" ] && [ "$commit" = "$LATEST_TAG_COMMIT" ]; then
        continue
    fi
    FULL_MESSAGE=$(git log -1 --pretty=format:"%B" "$commit")
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        parse_line "$line"
    done <<< "$FULL_MESSAGE"
done

# Build the new changelog section for $TAG with proper spacing
NEW_CHANGELOG="\n\n## $TAG\n\n"
FIRST_SUBSECTION=true

if [ ${#FEATURES[@]} -gt 0 ]; then
    NEW_CHANGELOG+="### ✨ New Features\n\n"
    for feat in "${FEATURES[@]}"; do
        NEW_CHANGELOG+="- **$feat**\n"
    done
    FIRST_SUBSECTION=false
fi

if [ ${#FIXES[@]} -gt 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### 🐞 Bug Fixes\n\n"
        FIRST_SUBSECTION=false
    else
        NEW_CHANGELOG+="\n### 🐞 Bug Fixes\n\n"
    fi
    for fix in "${FIXES[@]}"; do
        NEW_CHANGELOG+="- **$fix**\n"
    done
fi

if [ ${#PERFS[@]} -gt 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### ⚡ Performance Improvements\n\n"
        FIRST_SUBSECTION=false
    else
        NEW_CHANGELOG+="\n### ⚡ Performance Improvements\n\n"
    fi
    for perf in "${PERFS[@]}"; do
        NEW_CHANGELOG+="- **$perf**\n"
    done
fi

if [ ${#REFACTORS[@]} -gt 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### 🔧 Refactor Improvements\n\n"
        FIRST_SUBSECTION=false
    else
        NEW_CHANGELOG+="\n### 🔧 Refactor Improvements\n\n"
    fi
    for refactor in "${REFACTORS[@]}"; do
        NEW_CHANGELOG+="- **$refactor**\n"
    done
fi

if [ ${#DOCS[@]} -gt 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### 📝 Documentation\n\n"
        FIRST_SUBSECTION=false
    else
        NEW_CHANGELOG+="\n### 📝 Documentation\n\n"
    fi
    for doc in "${DOCS[@]}"; do
        NEW_CHANGELOG+="- **$doc**\n"
    done
fi

if [ ${#CHORES[@]} -gt 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### 🛠️ Maintenance\n\n"
        FIRST_SUBSECTION=false
    else
        NEW_CHANGELOG+="\n### 🛠️ Maintenance\n\n"
    fi
    for chore in "${CHORES[@]}"; do
        NEW_CHANGELOG+="- **$chore**\n"
    done
fi

if [ ${#FEATURES[@]} -eq 0 ] && [ ${#FIXES[@]} -eq 0 ] && [ ${#PERFS[@]} -eq 0 ] && [ ${#REFACTORS[@]} -eq 0 ] && [ ${#DOCS[@]} -eq 0 ] && [ ${#CHORES[@]} -eq 0 ]; then
    if [ "$FIRST_SUBSECTION" = true ]; then
        NEW_CHANGELOG+="### 🔍 No Changes\n\n"
    else
        NEW_CHANGELOG+="\n### 🔍 No Changes\n\n"
    fi
    NEW_CHANGELOG+="- No notable changes in this release.\n"
fi

# Add a single newline to separate from the next version
NEW_CHANGELOG+="\n"

# Define the changelog file path
CHANGELOG_FILE="/app/CHANGELOG.md"

# If no existing file, create it with just the header and new section
if [ ! -f "$CHANGELOG_FILE" ]; then
    FULL_CHANGELOG="# Timestamp Plugin Changelog\n\nThis changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.\n$NEW_CHANGELOG"
else
    # Read the existing changelog content
    EXISTING_CONTENT=$(cat "$CHANGELOG_FILE")
    # Extract the header (up to but not including the first ## section)
    HEADER=$(echo "$EXISTING_CONTENT" | sed -n '1,/^## /{p; /^## /q}' | sed '$d')
    # Extract the existing sections starting from the first ## (latest tag section) without modification
    if [ -n "$LATEST_TAG" ]; then
        OLD_SECTIONS=$(echo "$EXISTING_CONTENT" | sed -n "/^## /,\$p")
    else
        OLD_SECTIONS=""
    fi
    # Build the full changelog: header, new section, unchanged old sections
    FULL_CHANGELOG="$HEADER$NEW_CHANGELOG"
    if [ -n "$OLD_SECTIONS" ]; then
        FULL_CHANGELOG+="$OLD_SECTIONS"
    fi
fi

# Write the full changelog, overwriting the existing file
echo "Amending CHANGELOG.md with new $TAG section after header and before latest tag section..."
echo -e "$FULL_CHANGELOG" > "$CHANGELOG_FILE"

# Verify that the changelog file exists
test -f "$CHANGELOG_FILE" || { echo "Error: CHANGELOG.md was not created"; ls -la /app; exit 1; }

echo "Amended CHANGELOG.md with commits from $COMMIT_RANGE inserted after header"
