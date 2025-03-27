import * as obsidian from 'obsidian';

// Parses a date string in YYYYMMDD format and validates it
function parseDateString(dateStr: string): Date | null {
    if (!/^\d{8}$/.test(dateStr)) {
        return null;
    }
    const year = parseInt(dateStr.slice(0, 4));
    const month = parseInt(dateStr.slice(4, 6)) - 1;
    const day = parseInt(dateStr.slice(6, 8));
    const date = new Date(year, month, day);
    if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) {
        return null;
    }
    return date;
}

class DateRangeModal extends obsidian.Modal {
    onSubmit: (rangeText: string) => void;

    constructor(app: obsidian.App, onSubmit: (rangeText: string) => void) {
        super(app);
        this.onSubmit = onSubmit;
    }

    onOpen() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.createEl('h2', { text: 'Enter Date Range' });

        const startInput = contentEl.createEl('input', {
            type: 'text',
            placeholder: 'Start date (YYYYMMDD)',
        });

        const endInput = contentEl.createEl('input', {
            type: 'text',
            placeholder: 'End date (YYYYMMDD)',
        });

        const submitButton = contentEl.createEl('button', { text: 'Insert Dates' });
        submitButton.addEventListener('click', () => {
            const startStr = startInput.value.trim();
            const endStr = endInput.value.trim();

            const startDate = parseDateString(startStr);
            if (!startDate) {
                new obsidian.Notice('Invalid start date. Please use YYYYMMDD and ensure it’s a valid date.');
                return;
            }

            const endDate = parseDateString(endStr);
            if (!endDate) {
                new obsidian.Notice('Invalid end date. Please use YYYYMMDD and ensure it’s a valid date.');
                return;
            }

            if (startDate > endDate) {
                new obsidian.Notice('Start date must be before or equal to end date.');
                return;
            }

            const dates: string[] = [];
            let currentDate = new Date(startDate);
            while (currentDate <= endDate) {
                const year = currentDate.getFullYear().toString();
                const month = String(currentDate.getMonth() + 1).padStart(2, '0');
                const day = String(currentDate.getDate()).padStart(2, '0');
                dates.push(`${year}-${month}-${day}`);
                currentDate.setDate(currentDate.getDate() + 1);
            }

            const rangeText = dates.join('\n');
            this.onSubmit(rangeText);
            this.close();
        });

        startInput.focus();
    }

    onClose() {
        const { contentEl } = this;
        contentEl.empty();
    }
}

export default class TimestampPlugin extends obsidian.Plugin {
    async onload() {
        this.addCommand({
            id: 'insert-timestamp',
            name: 'Insert Current Timestamp (YYYYMMDDHHMMSS)',
            editorCallback: (editor: obsidian.Editor, _ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
                editor.replaceSelection(this.generateTimestamp());
            },
        });

        this.addCommand({
            id: 'rename-with-timestamp',
            name: 'Rename Current File with Timestamp Prefix (YYYYMMDDHHMMSS)',
            editorCallback: (_editor: obsidian.Editor, ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
                if ('file' in ctx && ctx.file) {
                    const file = ctx.file;
                    if (file && file.parent) {
                        const directoryPath = file.parent.path;
                        const sanitizedBasename = file.basename.replace(/\s+/g, '_').toLowerCase();
                        const newName = `${directoryPath}/${this.generateTimestamp()}_${sanitizedBasename}.${file.extension}`;
                        this.app.fileManager.renameFile(file, newName);
                    }
                } else {
                    new obsidian.Notice('This command requires an active Markdown view.');
                }
            },
        });

        this.addCommand({
            id: 'rename-with-timestamp-title',
            name: 'Rename Current File with Timestamp as prefix and with First Heading Title as filename',
            editorCallback: async (editor: obsidian.Editor, ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
                if ('file' in ctx && ctx.file) {
                    const file = ctx.file;
                    if (file && file.parent) {
                        const content = editor.getValue();
                        const titleMatch = content.match(/^#\s+(.+)$/m);
                        let newBasename = 'untitled';

                        if (titleMatch && titleMatch[1]) {
                            newBasename = titleMatch[1].trim().replace(/\s+/g, '_').toLowerCase();
                        }

                        const directoryPath = file.parent.path;
                        const newName = `${directoryPath}/${this.generateTimestamp()}_${newBasename}.${file.extension}`;
                        await this.app.fileManager.renameFile(file, newName);
                    }
                } else {
                    new obsidian.Notice('This command requires an active Markdown view.');
                }
            },
        });

        this.addCommand({
            id: 'insert-date-range',
            name: 'Insert Dates in Range (YYYY-MM-DD, one per line)',
            editorCallback: (editor: obsidian.Editor, _ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
                const modal = new DateRangeModal(this.app, (rangeText) => {
                    editor.replaceSelection(rangeText);
                });
                modal.open();
            },
        });
    }

    // Generates a timestamp in YYYYMMDDHHMMSS format
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
