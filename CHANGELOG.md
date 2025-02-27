# Timestamp Plugin Changelog

This changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.

## 0.2.0

### ✨ New Features

- **add rename file with timestamp & heading**
- **Implemented the new command to rename specific file with timestamp prefix & title as filename**

### 📝 Documentation

- **updated README.md file how to use the new rename command with timestamp & title as filename**

## 0.1.8

### 🐞 Bug Fixes

- **forgot to push the simplified release.sh**

### 📝 Documentation

- **forgot to push the simplified release.sh file to generate latest tag release notes**

## 0.1.7

### 🐞 Bug Fixes

- **fixed automatic release for pr merge**
- **simplified the release.sh to generate release notes based on CHANGELOG.md file**

## 0.1.6

### 🐞 Bug Fixes

- **updated release workflow and release script**
- **the release workflow didn't see any commit changes, so no proper release notes was created**
- **updated make to update package-lock accordingly**

## 0.1.5

### 🐞 Bug Fixes

- **did a tag release for Obsidian plugin release**
- **the release script should work as supposed to**

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
