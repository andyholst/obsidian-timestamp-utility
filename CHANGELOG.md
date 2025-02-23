# Timestamp Plugin Changelog

This changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.

## 0.1.4

### 🐞 Bug Fixes

- **fixed commit linting for current branch**
- **fixed commit linting so only commits for the current branch is being linted**

## 0.1.3

### 🐞 Bug Fixes

- **fixed proper version tagging to comply with Obsidian plugin release policy**

## 0.1.2

### 🐞 Bug Fixes

- **publish to Obsidian community with correct version**
- **bumped the version of the Timestamp Utility to be released for the Obsidian community**

## 0.1.1

### ✨ New Features

- **add changelog log. & integrated with release**
- **added new Makefile section to generate/update CHANGELOG.md file**

### 🐞 Bug Fixes

- **updated the release script to only gen. release notes accordingly**
- **fixed the release.sh script to have proper spacing between sections and lists**
- **renamed the release timestamp artifact with proper filename**

### ⚡ Performance Improvements

- **improved the release and commit GitHub workflow actions**

### 🔧 Refactor Improvements

- **refactored the release script**
- **update release workflow action to publish the correct**

### 📝 Documentation

- **created new CHANGELOG.md file**

### 🛠️ Maintenance

- **added missings versions.json file for Obsidian plugin**

## 0.1.0

### ✨ New Features

- **implemented file renaming with timestamp prefix for filename**
- **implemented YYYYMMDDHHmmss timestamp at file cursor**
- **added Docker and Docker Compose for consistent build and test environments**
- **configured GitHub workflows for automated testing and release**

### 🐞 Bug Fixes

- **generation of changelog for pr merge (#5)**
- **resolved changelog generation errors for multi-type commits**
- **release pipeline**
- **corrected changelog release template**

### ⚡ Performance Improvements

- **improve release script efficiency for changelog categorization**

### 🔧 Refactor Improvements

- **simplified TimestampPlugin command structure in main.ts**

### 📝 Documentation

- **documented installation steps and prerequisites in README**
- **added usage instructions for timestamp commands in README**

### 🛠️ Maintenance

- **configured Jest testing suite with Obsidian API mocks**
- **added unit tests for timestamp insertion and file renaming commands**
- **added Makefile with build, test, and release tasks**
- **enable commitlint for conventional commit validation**
- **set up git-chglog for automated changelog generation**
- **remove unused mock utilities and clean up test setup**
