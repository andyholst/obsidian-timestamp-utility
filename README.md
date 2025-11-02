# Timestamp Plugin for Obsidian

This plugin enhances your Obsidian experience by adding six convenient commands for working with timestamps, date ranges, and task processing to support the Zettelkasten notes and effecient planning:

- **Insert Current Timestamp (YYYYMMDDHHMMSS)**: Inserts a timestamp at the cursor position in the format `YYYYMMDDHHMMSS` (e.g., `20250221134527` for February 21, 2025, 1:45:27 PM).
- **Rename Current File with Timestamp Prefix (YYYYMMDDHHMMSS)**: Renames the active file by adding a timestamp prefix in the format `YYYYMMDDHHMMSS_filename` (e.g., `20250221134527_notes.md`).
- **Rename Current File with Timestamp as Prefix and First Heading Title as Filename**: Renames the active file using a timestamp prefix and the first heading title from the file content in the format `YYYYMMDDHHMMSS_title` (e.g., `20250221134527_my_awesome_title.md`). If no heading is found, it uses "untitled" (e.g., `20250221134527_untitled.md`).
- **Rename Current File with the First Heading Title as Filename**: Renames the active file using the first level 1 heading (e.g., `# My Awesome Title`) as the filename (e.g., `my_awesome_title.md`). If no heading is found, it uses "untitled" (e.g., `untitled.md`).
- **Insert Dates in Range (YYYY-MM-DD, one per line)**: Opens a modal where you can input a start and end date in `YYYYMMDD` format. It then inserts a list of dates from the start to the end date (inclusive) in `YYYY-MM-DD` format, each on a new line.
- **Convert Reminders to Date-Time-Blocked Tasks**: Processes reminders in notes in a selected source folder and converts them into time-blocked tasks organized by date in a selected output folder. Reminders in the format `- [ ] Task description (@YYYY-MM-DD HH:MM)` are transformed into tasks like `- [ ] HH:MM - HH:MM Task description` and grouped into daily files to be synced with ICAL services (like `2025-01-01.md`).

## Installation

You can install the plugin either by downloading a pre-built release or by building it from source. Most users should use the **From Release** method, which does not require any additional tools. Developers who want to modify or contribute to the plugin can use the **From Source** method, which requires a container runtime (Docker or nerdctl), Make, and Git.

### From Release

1. Download the latest release from [link to releases] (e.g., a ZIP file).
2. Extract the downloaded archive to obtain the plugin files (e.g., `main.js`, `manifest.json`).
3. In your Obsidian vault, navigate to the `.obsidian/plugins` directory. If it doesn’t exist, create it.
4. Create a new folder named `timestamp-plugin` (this name should match the plugin’s ID in `manifest.json`).
5. Copy the extracted plugin files into this new folder.
6. Restart Obsidian.
7. Go to **Settings > Community plugins**, find "Timestamp Plugin", and toggle it on to enable it.

### From Source

To build the plugin from source, you will need:

- A container runtime: Either **[Docker](https://www.docker.com/)** or **[nerdctl](https://github.com/containerd/nerdctl)**. The build process will automatically use whichever is available.
- **[Make](https://www.gnu.org/software/make/)**: Required for building and running the Makefile to manage the plugin’s build process.
- A Git repository initialized in the project directory: Required for automatic versioning and tagging.

Follow these steps:

1. Clone this repository: Use the command `git clone https://github.com/andyholst/obsidian-timestamp-utility.git` to clone the repository to your local machine, then navigate to the project directory with `cd obsidian-timestamp-utility`.
2. Build the plugin: Run `make build-app` to compile the plugin. This will generate the plugin files in the `dist` folder.
3. Install the plugin: Follow steps 3-7 from the "From Release" section above, using the files from the `dist` folder.

## Usage

### Insert Current Timestamp

To insert a timestamp at the cursor position:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Insert Current Timestamp".
3. Press Enter to insert the timestamp at the cursor.

### Rename Current File with Timestamp Prefix

To rename the active file by adding a timestamp prefix:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Rename Current File with Timestamp Prefix".
3. Press Enter to rename the file.

### Rename Current File with Timestamp as Prefix and First Heading Title as Filename

To rename the active file using a timestamp prefix and the first heading title:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Rename Current File with Timestamp as Prefix and First Heading Title as Filename".
3. Press Enter to rename the file based on the first heading (e.g., `# My Awesome Title`) or "untitled" if no heading exists.

### Rename Current File with the First Heading Title as Filename

To rename the active file using the first heading title:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Rename Current File with the First Heading Title as Filename".
3. Press Enter to rename the file based on the first level 1 heading (e.g., `# My Awesome Title`) or "untitled" if no heading exists.

### Insert Dates in Range

To insert a list of dates in `YYYY-MM-DD` format between a start and end date:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Insert Dates in Range".
3. Press Enter to open a modal.
4. In the modal, enter the start date in `YYYYMMDD` format (e.g., `20250101` for January 1, 2025).
5. Enter the end date in `YYYYMMDD` format (e.g., `20250105` for January 5, 2025).
6. Click "Insert Dates" to insert the list of dates, each on a new line, at the cursor position. The output will be a list of dates in `YYYY-MM-DD` format from the start date to the end date, inclusive.

**Note**:
- The start date must be before or equal to the end date.
- Both dates must be valid and entered in `YYYYMMDD` format (e.g., `20250230` is invalid and will trigger an error message).
- If the input is invalid, a notice will appear in Obsidian (e.g., "Invalid start date. Please use YYYYMMDD and ensure it's a valid date.").

### Convert Reminders to Date-Time-Blocked Tasks

To process reminder files and convert them into organized time-blocked tasks:

1. Open the command palette (Ctrl+P or Cmd+P).
2. Search for "Convert Reminders to Date Time-Blocked Tasks".
3. Press Enter to open a folder selection modal.
4. Select the source folder containing your reminder files using the fuzzy search interface.
5. Select the output folder where processed tasks will be saved.
6. The plugin will scan all Markdown files in the source folder (recursively), extract reminders in the format `- [ ] Task description (@YYYY-MM-DD HH:MM)`, convert them to time-blocked tasks like `- [ ] HH:MM - HH:MM Task description`, and organize them into daily files (e.g., `2025-01-01.md`) in the output folder.

**Note**:
- The source and output folders must be different.
- Existing checked tasks (`- [x]`) in output files are preserved.
- Unchecked tasks are updated if they match current reminders.
- New tasks are added to existing files or new files are created as needed.

## Running the Ticket Interpreter Agent

The ticket interpreter agent is an AI-powered tool designed to process GitHub issues and extract structured information (e.g., title, description, requirements, and acceptance criteria) using LangChain and LangGraph. The output is provided in JSON format and logged to both the console and a file. The purpose is to use it for other agents to generate TypeScript code, tests and to create pull request and review the generated code tests and see it fulfills the acceptance criteria.

### Prerequisites

Before running the ticket interpreter agent, ensure you have the following:

- A container runtime: Either **[Docker](https://www.docker.com/)** or **[nerdctl](https://github.com/containerd/nerdctl)**.
- **[Make](https://www.gnu.org/software/make/)**: Required to execute the Makefile commands.
- Environment Variables:
  - GITHUB_TOKEN: A GitHub personal access token with repository access. Obtain one from [GitHub Settings](https://github.com/settings/tokens).
  - OLLAMA_HOST: The URL of your Ollama LLM service (default: http://localhost:11434).
  - OLLAMA_REASONING_MODEL: The LLM model for reasoning tasks (default: qwen2.5:14b).
  - OLLAMA_CODE_MODEL: The LLM model for code generation (default: qwen2.5-coder:14b).

Set these environment variables in your terminal:
export GITHUB_TOKEN=your_token_here
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_REASONING_MODEL=qwen2.5:14b
export OLLAMA_CODE_MODEL=qwen2.5-coder:14b

### Steps to Run the Agent

1. Build the Docker Image:
   - Build the necessary Docker image for the agent by running: make build-image-agents
   - This command uses the docker-compose-files/agents.yaml file to set up the environment.

2. Run the Agent:
   - Execute the ticket interpreter agent with a specific GitHub issue URL using the following command: make run-agentics ISSUE_URL=https://github.com/owner/repo/issues/123
   - Replace https://github.com/owner/repo/issues/123 with the URL of the GitHub issue you want to process.

3. View the Output:
   - The agent processes the issue and outputs the result in JSON format.
   - Check the console for immediate feedback.
   - Review the agentics.log file in the project directory for detailed logs, including the final JSON output.

Example:
To process issue #20 from this repository, run: make run-agentics ISSUE_URL=https://github.com/andyholst/obsidian-timestamp-utility/issues/20

## Running the Tests

The ticket interpreter agent includes unit and integration tests to verify its functionality. These tests are defined in test_ticket_interpreter.py (unit tests) and test_ticket_interpreter_integration.py (integration tests).

### Prerequisites

- A container runtime: Either **[Docker](https://www.docker.com/)** or **[nerdctl](https://github.com/containerd/nerdctl)**.
- **[Make](https://www.gnu.org/software/make/)**: Required to execute the Makefile commands.
- Environment Variables: Same as for running the agent (GITHUB_TOKEN, OLLAMA_HOST, OLLAMA_REASONING_MODEL, OLLAMA_CODE_MODEL), plus:
  - TEST_ISSUE_URL: A base GitHub repository URL (e.g., https://github.com/andyholst/obsidian-timestamp-utility) used by integration tests.

Set the additional variable:
export TEST_ISSUE_URL=https://github.com/andyholst/obsidian-timestamp-utility

### Running Unit Tests

Unit tests cover individual components, such as URL validation, issue fetching, and LLM response processing, using mocked data.

- Run the unit tests with: make test-agents-unit

### Running Integration Tests

Integration tests validate the full workflow with real GitHub API calls and LLM interactions, testing scenarios like well-structured tickets, sloppy tickets, empty tickets, and invalid inputs.

- Run the integration tests with: make test-agents-integration

### Running All Tests

To execute both unit and integration tests together: make test-agents

Notes:
- Ensure the TEST_ISSUE_URL points to a valid repository with accessible issues (e.g., issues #20, #22, #23) for integration tests to pass.
- Integration tests require a live Ollama LLM service and a valid GITHUB_TOKEN. If these are unavailable, tests may fail with appropriate error messages (e.g., GithubException or ValueError).

## Development

For those interested in contributing:

1. Clone the Repository: git clone https://github.com/andyholst/obsidian-timestamp-utility.git
2. Install Dependencies:
   - Ensure you have a container runtime (either Docker or nerdctl) and Make installed.
3. Build and Test:
   - Use the Makefile commands to build, test, and run the plugin and agent as described above.
4. Contribute:
   - Follow standard Git workflows to submit pull requests with your changes.
