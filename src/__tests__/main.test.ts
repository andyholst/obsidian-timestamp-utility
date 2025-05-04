import TimestampPlugin from '../main';
import * as obsidian from 'obsidian';

const mockManifest: obsidian.PluginManifest = {
    id: 'obsidian-timestamp-utility',
    name: 'Timestamp Utility',
    version: '0.4.4',
    minAppVersion: '0.15.0',
    description: 'Insert timestamps and rename files with timestamp prefixes.',
    author: 'Your Name',
    isDesktopOnly: false,
};

const mockEditor: obsidian.MarkdownView['editor'] = {
    replaceSelection: jest.fn(),
    getValue: jest.fn(() => ''),
    setValue: jest.fn(),
    getSelection: jest.fn(() => ''),
    setSelection: jest.fn(),
    getRange: jest.fn(() => ''),
    replaceRange: jest.fn(),
    getLine: jest.fn(() => ''),
    setLine: jest.fn(),
    lineCount: jest.fn(() => 1),
    lastLine: jest.fn(() => 0),
    offsetToPos: jest.fn(() => ({ line: 0, ch: 0 })),
    posToOffset: jest.fn(() => 0),
    getCursor: jest.fn(() => ({ line: 0, ch: 0 })),
    setCursor: jest.fn(),
    somethingSelected: jest.fn(() => false),
    exec: jest.fn(),
    focus: jest.fn(),
    blur: jest.fn(),
    hasFocus: jest.fn(() => false),
    getScrollInfo: jest.fn(() => ({ top: 0, left: 0 })),
    scrollTo: jest.fn(),
    scrollIntoView: jest.fn(),
    undo: jest.fn(),
    redo: jest.fn(),
    wordAt: jest.fn(() => null),
    getDoc: jest.fn(() => ({ getValue: jest.fn(() => '') } as any)),
    refresh: jest.fn(),
    listSelections: jest.fn(() => []),
    setSelections: jest.fn(),
    transaction: jest.fn(),
    processLines: jest.fn(() => 0),
};

const mockFile: obsidian.TFile = {
    basename: 'My Note',
    extension: 'md',
    parent: { path: 'folder' } as obsidian.TFolder,
    stat: {} as any,
    vault: {} as any,
    path: 'folder/My Note.md',
    name: 'My Note.md',
};

const mockView: obsidian.MarkdownView = {
    editor: mockEditor,
    file: mockFile,
} as any;

const mockApp: obsidian.App = {
    workspace: {
        getActiveViewOfType: jest.fn(() => mockView),
        getActiveFile: jest.fn(() => mockFile),
    } as any,
    fileManager: {
        renameFile: jest.fn().mockResolvedValue(undefined),
        getNewFileParent: jest.fn(),
        generateMarkdownLink: jest.fn(() => ''),
        trashFile: jest.fn(),
        processFrontMatter: jest.fn(),
        getAvailablePathForAttachment: jest.fn(() => Promise.resolve('')),
    },
    keymap: {} as any,
    scope: {} as any,
    vault: { adapter: {} as any } as any,
    metadataCache: {} as any,
    lastEvent: null as any,
    loadLocalStorage: jest.fn(() => null),
    saveLocalStorage: jest.fn(),
};

const mockCommands: { [key: string]: obsidian.Command } = {};

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

function generateDateRange(startStr: string, endStr: string): string | null {
    const startDate = parseDateString(startStr);
    if (!startDate) {
        return null;
    }
    const endDate = parseDateString(endStr);
    if (!endDate) {
        return null;
    }
    if (startDate > endDate) {
        return null;
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
    return dates.join('\n');
}

describe('TimestampPlugin', () => {
    let plugin: TimestampPlugin;

    beforeEach(() => {
        jest.clearAllMocks();
        mockFile.basename = 'My Note';
        mockFile.extension = 'md';
        mockFile.parent = { path: 'folder' } as obsidian.TFolder;
        mockFile.stat = { ctime: 0, mtime: 0, size: 0 } as obsidian.FileStats;
        mockFile.vault = { adapter: {} } as obsidian.Vault;
        mockFile.path = 'folder/My Note.md';
        mockFile.name = 'My Note.md';
        mockApp.workspace.getActiveFile = jest.fn(() => mockFile) as jest.Mock<obsidian.TFile | null>;
        mockApp.workspace.getActiveViewOfType = jest.fn(() => mockView) as <T extends obsidian.View>(
            type: new (...args: any[]) => T
        ) => T | null;
        plugin = new TimestampPlugin(mockApp, mockManifest);
        plugin.addCommand = (command: obsidian.Command): obsidian.Command => {
            if (command.editorCallback) {
                command.callback = async () => {
                    const view = mockApp.workspace.getActiveViewOfType(obsidian.MarkdownView);
                    if (view) {
                        await command.editorCallback!(view.editor, view);
                    }
                };
            }
            mockCommands[command.id] = command;
            return command;
        };
    });

    describe('generateTimestamp', () => {
        test('returns a 14-digit timestamp in YYYYMMDDHHMMSS format', () => {
            const timestamp = plugin.generateTimestamp();
            expect(timestamp).toMatch(/^\d{14}$/);
            expect(parseInt(timestamp)).toBeGreaterThan(20200101000000);
            expect(parseInt(timestamp)).toBeLessThan(20991231235959);
        });
    });

    describe('insert-timestamp command', () => {
        test('inserts timestamp into editor when editor exists', async () => {
            await plugin.onload();
            const command = mockCommands['insert-timestamp'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockEditor.replaceSelection).toHaveBeenCalledWith(expect.stringMatching(/^\d{14}$/));
            } else {
                throw new Error('insert-timestamp command is not properly defined');
            }
        });

        test('does nothing if no editor is active', async () => {
            mockApp.workspace.getActiveViewOfType = jest.fn(() => null);
            await plugin.onload();
            const command = mockCommands['insert-timestamp'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockEditor.replaceSelection).not.toHaveBeenCalled();
            } else {
                throw new Error('insert-timestamp command is not properly defined');
            }
        });
    });

    describe('rename-with-timestamp command', () => {
        test('renames file with timestamp prefix and sanitized basename', async () => {
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    expect.stringMatching(/^folder\/\d{14}_my_note\.md$/)
                );
            } else {
                throw new Error('rename-with-timestamp command is not properly defined');
            }
        });

        test('does nothing if no active file', async () => {
            mockApp.workspace.getActiveFile = jest.fn(() => null);
            mockApp.workspace.getActiveViewOfType = jest.fn(() => null);
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockApp.fileManager.renameFile).not.toHaveBeenCalled();
            } else {
                throw new Error('rename-with-timestamp command is not properly defined');
            }
        });

        test('handles spaces and case in basename', async () => {
            mockFile.basename = 'My Awesome Note';
            mockFile.name = 'My Awesome Note.md';
            mockFile.path = 'folder/My Awesome Note.md';
            mockApp.workspace.getActiveFile = jest.fn(() => mockFile);
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    expect.stringMatching(/^folder\/\d{14}_my_awesome_note\.md$/)
                );
            } else {
                throw new Error('rename-with-timestamp command is not properly defined');
            }
        });
    });

    describe('rename-with-timestamp-title command', () => {
        test('renames file with timestamp and first heading title', async () => {
            (mockEditor.getValue as jest.Mock).mockReturnValue('# My Awesome Title\nSome content');
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    expect.stringMatching(/^folder\/\d{14}_my_awesome_title\.md$/)
                );
            } else {
                throw new Error('rename-with-timestamp-title command is not properly defined');
            }
        });

        test('uses "untitled" if no heading is found', async () => {
            (mockEditor.getValue as jest.Mock).mockReturnValue('No heading here');
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    expect.stringMatching(/^folder\/\d{14}_untitled\.md$/)
                );
            } else {
                throw new Error('rename-with-timestamp-title command is not properly defined');
            }
        });

        test('does nothing if no active file or editor', async () => {
            mockApp.workspace.getActiveFile = jest.fn(() => null);
            mockApp.workspace.getActiveViewOfType = jest.fn(() => null);
            await plugin.onload();
            const command = mockCommands['rename-with-timestamp-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).not.toHaveBeenCalled();
            } else {
                throw new Error('rename-with-timestamp-title command is not properly defined');
            }
        });
    });

    describe('generateDateRange', () => {
        test('generates correct date range within the same month', () => {
            const result = generateDateRange('20250101', '20250105');
            expect(result).toBe('2025-01-01\n2025-01-02\n2025-01-03\n2025-01-04\n2025-01-05');
        });

        test('generates correct date range spanning months', () => {
            const result = generateDateRange('20250131', '20250203');
            expect(result).toBe('2025-01-31\n2025-02-01\n2025-02-02\n2025-02-03');
        });

        test('returns null for invalid start date format', () => {
            const result = generateDateRange('2025010', '20250105');
            expect(result).toBeNull();
        });

        test('returns null for invalid end date format', () => {
            const result = generateDateRange('20250101', '202502');
            expect(result).toBeNull();
        });

        test('returns null when start date is after end date', () => {
            const result = generateDateRange('20250105', '20250101');
            expect(result).toBeNull();
        });

        test('returns null for invalid start date', () => {
            const result = generateDateRange('20250230', '20250301');
            expect(result).toBeNull();
        });

        test('generates single date when start and end are the same', () => {
            const result = generateDateRange('20250101', '20250101');
            expect(result).toBe('2025-01-01');
        });

        test('generates correct date range including leap day', () => {
            const result = generateDateRange('20240228', '20240301');
            expect(result).toBe('2024-02-28\n2024-02-29\n2024-03-01');
        });
    });

    describe('rename-filename-with-title command', () => {
        test('renames file with first heading title', async () => {
            (mockEditor.getValue as jest.Mock).mockReturnValue('# My Awesome Title\nSome content');
            await plugin.onload();
            const command = mockCommands['rename-filename-with-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    'folder/my_awesome_title.md'
                );
            } else {
                throw new Error('rename-filename-with-title command is not properly defined');
            }
        });

        test('renames file to untitled if no heading is found', async () => {
            (mockEditor.getValue as jest.Mock).mockReturnValue('No heading here');
            await plugin.onload();
            const command = mockCommands['rename-filename-with-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).toHaveBeenCalledWith(
                    mockFile,
                    'folder/untitled.md'
                );
            } else {
                throw new Error('rename-filename-with-title command is not properly defined');
            }
        });

        test('does nothing if no active file', async () => {
            mockApp.workspace.getActiveViewOfType = jest.fn(() => null);
            await plugin.onload();
            const command = mockCommands['rename-filename-with-title'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                await command.callback();
                expect(mockApp.fileManager.renameFile).not.toHaveBeenCalled();
            } else {
                throw new Error('rename-filename-with-title command is not properly defined');
            }
        });
    });
});
