import * as obsidian from 'obsidian';

export function addOneHour(timeStr: string): string {
    const [hours, minutes] = timeStr.split(':').map(Number);
    let newHours = (hours + 1) % 24;
    return `${newHours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

export function processLine(line: string): { date: string; formatted: string } | null {
    const regex = /^\- \[\ \] (.*?) \(@(\d{4}-\d{2}-\d{2})( (\d{2}:\d{2}))?\)( ?(#\w+))?$/;
    const match = line.trim().match(regex);
    if (!match) return null;

    const text = match[1];
    const date = match[2];
    const timeGroup = match[4]; // time if present
    // Tag is captured but ignored for skipping and not added to output

    let startTime: string, endTime: string;
    if (timeGroup) {
        startTime = timeGroup.trim();
        endTime = addOneHour(startTime);
    } else {
        startTime = '13:00';
        endTime = '14:00';
    }
    const formatted = `- [ ] ${startTime} - ${endTime} ${text}`;

    return { date, formatted };
}

export function getAllMdFiles(folder: obsidian.TFolder, outputFolderPath: string): obsidian.TFile[] {
    let results: obsidian.TFile[] = [];
    if (folder.path === outputFolderPath) {
        return results; // Skip if this folder is the output folder
    }

    folder.children.forEach(child => {
        if (child instanceof obsidian.TFolder) {
            results = results.concat(getAllMdFiles(child, outputFolderPath));
        } else if (child instanceof obsidian.TFile && child.extension === 'md') {
            results.push(child);
        }
    });
    return results;
}

export async function processTasks(app: obsidian.App, sourceFolderPath: string, outputFolderPath: string): Promise<void> {
    const sourceFolder = app.vault.getAbstractFileByPath(sourceFolderPath);
    if (!(sourceFolder instanceof obsidian.TFolder)) {
        throw new Error(`Invalid source folder: ${sourceFolderPath}`);
    }

    const outputFolder = app.vault.getAbstractFileByPath(outputFolderPath);
    if (!(outputFolder instanceof obsidian.TFolder)) {
        throw new Error(`Invalid output folder: ${outputFolderPath}`);
    }

    if (sourceFolderPath === outputFolderPath) {
        throw new Error('Source folder and output folder must be different.');
    }

    const mdFiles = getAllMdFiles(sourceFolder, outputFolderPath);

    const tasksByDate = new Map<string, string[]>();

    for (const file of mdFiles) {
        const content = await app.vault.read(file);
        const lines = content.split('\n');

        lines.forEach(line => {
            const task = processLine(line);
            if (task) {
                if (!tasksByDate.has(task.date)) {
                    tasksByDate.set(task.date, []);
                }
                tasksByDate.get(task.date)!.push(task.formatted);
            }
        });
    }

    // Collect all relevant dates: from current tasks and existing output files
    const allDates = new Set(tasksByDate.keys());
    outputFolder.children.forEach(child => {
        if (child instanceof obsidian.TFile && /^\d{4}-\d{2}-\d{2}\.md$/.test(child.name)) {
            const date = child.name.slice(0, 10);
            allDates.add(date);
        }
    });

    // For each date, update the file
    for (const date of allDates) {
        const currentFormatted = new Set(tasksByDate.get(date) || []);
        const filePath = `${outputFolderPath}/${date}.md`;

        let existingTaskLines: string[] = [];
        const existingFile = app.vault.getAbstractFileByPath(filePath);
        if (existingFile instanceof obsidian.TFile) {
            const content = await app.vault.read(existingFile);
            const lines = content.split('\n');
            lines.forEach(line => {
                const trimmed = line.trim();
                if (trimmed.startsWith('- [x] ')) {
                    existingTaskLines.push(trimmed); // Keep checked
                } else if (trimmed.startsWith('- [ ] ')) {
                    if (currentFormatted.has(trimmed)) {
                        existingTaskLines.push(trimmed); // Keep unchecked only if matches current
                    }
                }
                // Ignore other lines (assumes no non-task content)
            });
        }

        // Add new formatted items not already present
        const existingSet = new Set(existingTaskLines);
        currentFormatted.forEach(fmt => {
            if (!existingSet.has(fmt)) {
                existingTaskLines.push(fmt);
            }
        });

        // Write updated content if there are tasks, else delete if file exists
        if (existingTaskLines.length > 0) {
            const header = `# ${date}\n\n`;
            const content = header + existingTaskLines.join('\n');
            await app.vault.modify(existingFile as obsidian.TFile || await app.vault.create(filePath, ''), content);
        } else if (existingFile) {
            await app.vault.delete(existingFile);
        }
    }
}
