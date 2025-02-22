import * as obsidian from 'obsidian';

export default class TimestampPlugin extends obsidian.Plugin {
    async onload() {
        this.addCommand({
            id: 'insert-timestamp',
            name: 'Insert Current Timestamp (YYYYMMDDHHMMSS)',
            callback: () => {
                const view = this.app.workspace.getActiveViewOfType(obsidian.MarkdownView);
                const editor = view?.editor;
                if (editor) {
                    editor.replaceSelection(this.generateTimestamp());
                }
            }
        });

        this.addCommand({
            id: 'rename-with-timestamp',
            name: 'Rename Current File with Timestamp Prefix (YYYYMMDDHHMMSS)',
            callback: () => {
                const file = this.app.workspace.getActiveFile();
                if (file && file.parent) {
                    const directoryPath = file.parent.path;
                    const sanitizedBasename = file.basename.replace(/\s+/g, '_').toLowerCase();
                    const newName = `${directoryPath}/${this.generateTimestamp()}_${sanitizedBasename}.${file.extension}`;
                    this.app.fileManager.renameFile(file, newName);
                }
            }
        });
    }

    generateTimestamp(): string {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        return `${year}${month}${day}${hours}${minutes}${seconds}`;
    }
}
