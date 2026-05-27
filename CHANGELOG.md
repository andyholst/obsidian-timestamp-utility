# Timestamp Plugin Changelog

This changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.

## 0.4.9

### ✨ New Features

- **add task command to convert reminders to calendar tasks**
- **add new "Convert Reminders to Date Time-Blocked Tasks" command**
- **implement folder selection modal with fuzzy search interface**
- **Create taskProcessor.ts with reminder parsing and time-blocking**
- **add comprehensive unit tests for task processing functionality**
- **process reminders in format "- [ ] Task (@YYYY-MM-DD HH:MM)" to time-blocked tasks**
- **Organize tasks by date in daily files (YYYY-MM-DD.md)**
- **Preserve existing checked tasks and merge with new ones**
- **Use Obsidian's file system API for folder and file operations**

### 📝 Documentation

- **update README.md with new command documentation**

## 0.4.8

### ✨ New Features

- **refactored Makefile to run containerd**
- **Added Bash script to make system containerd migration enabled.**

### 🔧 Refactor Improvements

- **removed Docker Compose dependency since new Docker/NerdCtl has it integrated.**
- **Makefile uses containerd cmd to run and build images.**

### 📝 Documentation

- **updated README.md file based on the new containerd bash wrapper script.**

## 0.4.7

### ✨ New Features

- **implement the code integrator agent**
- **make sure code integrator preserve the existing TypeScript code with new TS code.**
- **make sure code integrator preserve existing TS tests with new tests.**

### 🔧 Refactor Improvements

- **refactored away the mocks of the LLM agents so they are being unit tested for reals.**
- **fetching GitHub tickets and writing to files has been mocked in unit tests.**
- **use qwen2.5-coder instead of qwen2.5 LLM model.**
- **added more logging to enable better troubleshooting in case of errors.**
- **made the code generator more strict to generate TS code and TS tests accordingly.**
- **simplified the code integrator to only deal with 2 files, no so much llm prompting.**
- **updated code extractor to only deal with main.ts and it's main.test.ts file.**
- **refine the llm agents to reduce halicunation.**
- **added new test asserts to cover up for refactored agents code and python code.**
- **added more real unit tests based on refactored llm agents.**
- **be able to silent the logs to debug level to give clarity for real exceptions for failure.**
- **improved the unit tests to run reall LLM agents excepty for the fetch integrator agent.**
- **get the updated unit tests running with real LM except for fetch ticket agent.**
- **added more edge unit test cases to verify that the TS code/tests is intact.**
- **refactored the integration tests to copver the new refactored LLM code.**

## 0.4.6

### ✨ New Features

- **added Code Extractor Agent**
- **added code extractor agent code and tests.**
- **updated the unit test to make make code extractor agent work with real files.**
- **added asserts of the expected real relevant files to integration tests.**
- **added corner cases for the integration test for the CodeExtractorAgent.**

### 🔧 Refactor Improvements

- **improve the build time to execute the tests with specific requirements.**
- **always run Pre Test Runner Agent first to make TS test works before creating new code.**

## 0.4.5

### ✨ New Features

- **implement clarify ticket agent**
- **the TicketClarityAgent has been implemented to clarify existing ticket.**
- **ticket with clear title, desc, requirements & acceptance criteria for coding agents.**
- **TicketClarityAgent will set better conditions to generate TS code and tests for other agents.**

## 0.4.4

### ✨ New Features

- **added Pre-Test Runner Agent**

### 🛠️ Maintenance

- **cleaned up unnessesary comments.**

## 0.4.3

### ⚡ Performance Improvements

- **added test coverage of the Obsidian plugin code**

## 0.4.2

### ✨ New Features

- **added Code Generation Agent Logic**
- **added code generation agent to create code and tests based on ticket description.**
- **added updated the tests to verify that TypeScript code/tests is generated.**
- **created State class to manage data between agents.**
- **setup LangGraph workflow to automate the analysis process.**

### 🐞 Bug Fixes

- **fixed the llm prompt operation to use the recommended operation.**

### 🔧 Refactor Improvements

- **refactored out FetchIssueAgent to fetch and validate GitHub issue content.**
- **refactored out ProcessLLMAgent to analyze ticket content using an LLM.**
- **implemented OutputResultAgent to log analysis results.**
- **updated the unit and integration tests for the system.**
- **renamed the package to agentics to make more sense.**
- **updated the Makefile and Docker Compose since the Python package has been renamed.**

### 📝 Documentation

- **updated the README.md file based on the updated Makefile.**

## 0.4.1

### ✨ New Features

- **implemented Ticket interpreter Node**
- **add python ticket interpreter to read GitHub tickets to work with other agents.**

### 📝 Documentation

- **updated the README.md file how to run the agents and test them.**

## 0.4.0

### ✨ New Features

- **added new code logic**
- **added rename filename logic to make sure filename is the same as the title.**

### 🔧 Refactor Improvements

- **reduced boiler plate code from main.ts file.**

### 📝 Documentation

- **updated the README to include the new rename filename command based on file title.**

## 0.3.1

### 🐞 Bug Fixes

- **aligned with modern Obsidian plugin standards**
- **replaced assume what file you edit code with actual file you edit on code.**

## 0.3.0

### ✨ New Features

- **added generate a list of YYYY-MM-DD dates logic**
- **implemented generate range list of dates with happy/unhappy tests.**

### 📝 Documentation

- **updated README.md file how to use the generate the date range list.**

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
