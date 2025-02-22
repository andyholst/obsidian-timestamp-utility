# Timestamp Plugin for Obsidian

This plugin enhances your Obsidian experience by adding two convenient commands for setting timestamp in file and for filename as a prefix to support Zettlekasten method:

- **Insert Current Timestamp (YYYYMMDDHHMMSS)**: Inserts a timestamp at the cursor position in the format `YYYYMMDDHHMMSS` (e.g., `20250221134527` for February 21, 2025, 1:45:27 PM).
- **Rename Current File with Timestamp Prefix (YYYYMMDDHHMMSS)**: Renames the active file by adding a timestamp prefix in the format `YYYYMMDDHHMMSS_filename` (e.g., `20250221134527_notes.md`).

## Prerequisites

Before installing and using this plugin, ensure you have the following:

- **[Docker](https://www.docker.com/)**: Required for building and running the plugin in a containerized environment.
- **[Node.js](https://nodejs.org/)** and **[npm](https://www.npmjs.com/)**: Optional, only needed for local development outside of Docker.
- **[Make](https://www.gnu.org/software/make/)**: Required for building and running the Makefile to manage the plugin's build process.
- A Git repository initialized in the project directory: Required for automatic versioning and tagging.

## Installation

Follow these steps to set up the plugin:

1. **Clone this repository**:
   ```bash
   git clone <repository-url>
   cd obsidian-timestamp-utility
   ```

2. **Build the plugin**:
   ```bash
   make build-app
   ```

3. **Install the plugin**:
   - Copy the `dist` folder to your Obsidian plugins directory.
   - Restart Obsidian.

4. **Use the commands**:
   - Open the command palette (Ctrl+P or Cmd+P) and search for "Insert Current Timestamp" or "Rename Current File with Timestamp Prefix".

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
