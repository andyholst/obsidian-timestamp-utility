import * as obsidian from 'obsidian';
import { processTasks } from './taskProcessor';

class FolderSuggestModal extends obsidian.FuzzySuggestModal<obsidian.TFolder> {
    private onSelect: (folder: obsidian.TFolder) => void;

    constructor(app: obsidian.App, onSelect: (folder: obsidian.TFolder) => void) {
        super(app);
        this.onSelect = onSelect;
        this.setPlaceholder('Select a folder...');
    }

    getItems(): obsidian.TFolder[] {
        const folders: obsidian.TFolder[] = [];
        obsidian.Vault.recurseChildren(this.app.vault.getRoot(), (child) => {
            if (child instanceof obsidian.TFolder) {
                folders.push(child);
            }
        });
        return folders;
    }

    getItemText(folder: obsidian.TFolder): string {
        return folder.path;
    }

    onChooseItem(folder: obsidian.TFolder): void {
        this.onSelect(folder);
    }
}

export class FolderSelectorModal extends obsidian.Modal {
    private sourceFolder: obsidian.TFolder | null = null;
    private outputFolder: obsidian.TFolder | null = null;

    constructor(app: obsidian.App) {
        super(app);
    }

    onOpen() {
        this.showSourceSelection();
    }

    private showSourceSelection() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.createEl('h2', { text: 'Select Source Folder' });
        contentEl.createEl('p', {
            text: 'Choose the folder containing your reminder files to process.'
        });

        const selectButton = contentEl.createEl('button', {
            text: 'Select Source Folder',
            cls: 'mod-cta'
        });

        selectButton.addEventListener('click', () => {
            const modal = new FolderSuggestModal(this.app, (folder) => {
                this.sourceFolder = folder;
                this.showOutputSelection();
            });
            modal.open();
        });
    }

    private showOutputSelection() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.createEl('h2', { text: 'Select Output Folder' });
        contentEl.createEl('p', {
            text: `Source: ${this.sourceFolder!.path}`
        });
        contentEl.createEl('p', {
            text: 'Choose the folder where processed tasks will be saved.'
        });

        const selectButton = contentEl.createEl('button', {
            text: 'Select Output Folder',
            cls: 'mod-cta'
        });

        const backButton = contentEl.createEl('button', {
            text: 'Back',
            cls: 'mod-secondary'
        });

        selectButton.addEventListener('click', () => {
            const modal = new FolderSuggestModal(this.app, async (folder) => {
                this.outputFolder = folder;

                if (this.sourceFolder!.path === this.outputFolder!.path) {
                    new obsidian.Notice('Source and output folders must be different.');
                    return;
                }

                try {
                    await processTasks(this.app, this.sourceFolder!.path, this.outputFolder!.path);
                    new obsidian.Notice('Task processing completed successfully.');
                    this.close();
                } catch (error) {
                    new obsidian.Notice(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
                }
            });
            modal.open();
        });

        backButton.addEventListener('click', () => {
            this.showSourceSelection();
        });
    }

    onClose() {
        const { contentEl } = this;
        contentEl.empty();
    }
}
