# Timestamp Plugin for Obsidian

This plugin enhances your Obsidian experience by adding four convenient commands for working with timestamps and date ranges to support the Zettelkasten method:

- **Insert Current Timestamp (YYYYMMDDHHMMSS)**: Inserts a timestamp at the cursor position in the format `YYYYMMDDHHMMSS` (e.g., `20250221134527` for February 21, 2025, 1:45:27 PM).
- **Rename Current File with Timestamp Prefix (YYYYMMDDHHMMSS)**: Renames the active file by adding a timestamp prefix in the format `YYYYMMDDHHMMSS_filename` (e.g., `20250221134527_notes.md`).
- **Rename Current File with Timestamp as Prefix and First Heading Title as Filename**: Renames the active file using a timestamp prefix and the first heading title from the file content in the format `YYYYMMDDHHMMSS_title` (e.g., `20250221134527_my_awesome_title.md`). If no heading is found, it uses "untitled" (e.g., `20250221134527_untitled.md`).
- **Insert Dates in Range (YYYY-MM-DD, one per line)**: Opens a modal where you can input a start and end date in `YYYYMMDD` format. It then inserts a list of dates from the start to the end date (inclusive) in `YYYY-MM-DD` format, each on a new line.

## Prerequisites

Before installing and using this plugin, ensure you have the following:

- **[Docker](https://www.docker.com/)**: Required for building and running the plugin in a containerized environment.
- **[Make](https://www.gnu.org/software/make/)**: Required for building and running the Makefile to manage the plugin's build process.
- A Git repository initialized in the project directory: Required for automatic versioning and tagging.

## Installation

Follow these steps to set up the plugin:

1. **Clone this repository**: Use the command `git clone <repository-url>` to clone the repository to your local machine, then navigate to the project directory with `cd obsidian-timestamp-utility`.
2. **Build the plugin**: Run `make build-app` to compile the plugin.
3. **Install the plugin**: Copy the `dist` folder to your Obsidian plugins directory and restart Obsidian.
4. **Use the commands**: Open the command palette (Ctrl+P or Cmd+P) and search for "Insert Current Timestamp", "Rename Current File with Timestamp Prefix", or "Insert Dates in Range".

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
- If the input is invalid, a notice will appear in Obsidian (e.g., "Invalid start date. Please use YYYYMMDD and ensure it’s a valid date.").
