import TimestampPlugin from '../main';
import * as obsidian from 'obsidian';

// Mock manifest
const mockManifest: obsidian.PluginManifest = {
    id: 'obsidian-timestamp-utility',
    name: 'Timestamp Utility',
    version: '0.2.0',
    minAppVersion: '0.15.0',
    description: 'Insert timestamps and rename files with timestamp prefixes.',
    author: 'Your Name',
    isDesktopOnly: false,
};

// Mock editor
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

// Mock MarkdownView
const mockView: obsidian.MarkdownView = {
    editor: mockEditor,
} as any;

// Mock file
const mockFile: obsidian.TFile = {
    basename: 'My Note',
    extension: 'md',
    parent: { path: 'folder' } as obsidian.TFolder,
    stat: {} as any,
    vault: {} as any,
    path: 'folder/My Note.md',
    name: 'My Note.md',
};

// Mock App
const mockApp: obsidian.App = {
    workspace: {
        getActiveViewOfType: jest.fn(() => mockView),
        getActiveFile: jest.fn(() => mockFile),
    } as any,
    fileManager: {
        renameFile: jest.fn(),
        getNewFileParent: jest.fn(),
        generateMarkdownLink: jest.fn(() => ''),
        trashFile: jest.fn(),
        processFrontMatter: jest.fn(),
        getAvailablePathForAttachment: jest.fn(() => Promise.resolve(''))
    },
    keymap: {} as any,
    scope: {} as any,
    vault: { adapter: {} as any } as any,
    metadataCache: {} as any,
    lastEvent: null as any,
    loadLocalStorage: jest.fn(() => null),
    saveLocalStorage: jest.fn()
};

// Mock commands
const mockCommands: { [key: string]: obsidian.Command } = {};

describe('TimestampPlugin', () => {
    let plugin: TimestampPlugin;

    beforeEach(() => {
        jest.clearAllMocks();
        // Reset mockFile to its initial state with proper typing
        mockFile.basename = 'My Note';
        mockFile.extension = 'md';
        mockFile.parent = { path: 'folder' } as obsidian.TFolder;
        mockFile.stat = { ctime: 0, mtime: 0, size: 0 } as obsidian.FileStats;
        mockFile.vault = { adapter: {} } as obsidian.Vault;
        mockFile.path = 'folder/My Note.md';
        mockFile.name = 'My Note.md';
        // Reset mocks with proper type assertions
        mockApp.workspace.getActiveFile = jest.fn(() => mockFile) as jest.Mock<obsidian.TFile | null>;
        mockApp.workspace.getActiveViewOfType = jest.fn(() => mockView) as <T extends obsidian.View>(type: new (...args: any[]) => T) => T | null;
        plugin = new TimestampPlugin(mockApp, mockManifest);

        // Mock addCommand
        plugin.addCommand = (command: obsidian.Command): obsidian.Command => {
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
});
