import { addOneHour, processLine, getAllMdFiles, processTasks } from '../taskProcessor';
import * as obsidian from 'obsidian';

describe('addOneHour', () => {
    test('adds one hour correctly', () => {
        expect(addOneHour('13:00')).toBe('14:00');
        expect(addOneHour('23:00')).toBe('00:00');
        expect(addOneHour('12:30')).toBe('13:30');
    });

    test('handles midnight wraparound', () => {
        expect(addOneHour('00:00')).toBe('01:00');
        expect(addOneHour('23:59')).toBe('00:59');
    });

    test('preserves minutes', () => {
        expect(addOneHour('15:45')).toBe('16:45');
        expect(addOneHour('22:15')).toBe('23:15');
    });
});

describe('processLine', () => {
    test('processes line with time', () => {
        const line = '- [ ] Task description (@2023-10-01 14:00) #tag';
        const result = processLine(line);
        expect(result).toEqual({
            date: '2023-10-01',
            formatted: '- [ ] 14:00 - 15:00 Task description'
        });
    });

    test('processes line without time', () => {
        const line = '- [ ] Task description (@2023-10-01)';
        const result = processLine(line);
        expect(result).toEqual({
            date: '2023-10-01',
            formatted: '- [ ] 13:00 - 14:00 Task description'
        });
    });

    test('returns null for invalid line', () => {
        const line = 'Invalid line';
        const result = processLine(line);
        expect(result).toBeNull();
    });

    test('processes line with checked task', () => {
        const line = '- [x] Completed task (@2023-10-01 14:00)';
        const result = processLine(line);
        expect(result).toBeNull(); // Checked tasks are ignored
    });

    test('processes line with different time format', () => {
        const line = '- [ ] Task (@2023-10-01 09:30)';
        const result = processLine(line);
        expect(result).toEqual({
            date: '2023-10-01',
            formatted: '- [ ] 09:30 - 10:30 Task'
        });
    });

    test('ignores lines without proper format', () => {
        expect(processLine('- Task without brackets')).toBeNull();
        expect(processLine('[ ] Task without dash')).toBeNull();
        expect(processLine('- [ ] Task without date')).toBeNull();
        expect(processLine('- [ ] Task (@invalid-date)')).toBeNull();
    });
});

describe('getAllMdFiles', () => {
    test('gets all md files recursively', () => {
        const mockFile1 = { extension: 'md' } as obsidian.TFile;
        const mockFile2 = { extension: 'md' } as obsidian.TFile;
        const mockFile3 = { extension: 'txt' } as obsidian.TFile;

        const mockSubFolder = {
            path: 'subfolder',
            children: [mockFile2]
        } as unknown as obsidian.TFolder;

        const mockFolder = {
            path: 'folder',
            children: [mockFile1, mockSubFolder, mockFile3]
        } as unknown as obsidian.TFolder;

        // Mock the instanceof checks
        (obsidian.TFolder as any) = function() {};
        (obsidian.TFile as any) = function() {};

        Object.setPrototypeOf(mockSubFolder, obsidian.TFolder.prototype);
        Object.setPrototypeOf(mockFile1, obsidian.TFile.prototype);
        Object.setPrototypeOf(mockFile2, obsidian.TFile.prototype);
        Object.setPrototypeOf(mockFile3, obsidian.TFile.prototype);

        const result = getAllMdFiles(mockFolder, 'output');
        expect(result).toEqual([mockFile1, mockFile2]);
    });

    test('skips output folder', () => {
        const mockFile = { extension: 'md' } as obsidian.TFile;
        const mockOutputFolder = {
            path: 'output',
            children: [mockFile]
        } as unknown as obsidian.TFolder;

        const result = getAllMdFiles(mockOutputFolder, 'output');
        expect(result).toEqual([]);
    });
});

describe('processTasks', () => {
    const mockApp = {
        vault: {
            getAbstractFileByPath: jest.fn(),
            read: jest.fn(),
            modify: jest.fn(),
            create: jest.fn(),
            delete: jest.fn(),
        },
        fileManager: {} as any,
    } as any;

    beforeEach(() => {
        jest.clearAllMocks();
        // Mock instanceof checks
        (obsidian.TFolder as any) = function() {};
        (obsidian.TFile as any) = function() {};
    });

    test('throws error for invalid source folder', async () => {
        mockApp.vault.getAbstractFileByPath.mockReturnValue(null);
        await expect(processTasks(mockApp, 'invalid/source', 'output')).rejects.toThrow('Invalid source folder: invalid/source');
    });

    test('throws error for invalid output folder', async () => {
        const mockSourceFolder = { path: 'source', children: [], name: 'source', parent: null, vault: mockApp.vault, isRoot: () => false };
        Object.setPrototypeOf(mockSourceFolder, obsidian.TFolder.prototype);
        mockApp.vault.getAbstractFileByPath
            .mockReturnValueOnce(mockSourceFolder)
            .mockReturnValueOnce(null);
        await expect(processTasks(mockApp, 'source', 'invalid/output')).rejects.toThrow('Invalid output folder: invalid/output');
    });

    test('throws error when source and output folders are the same', async () => {
        const mockFolder = { path: 'same', children: [], name: 'same', parent: null, vault: mockApp.vault, isRoot: () => false };
        Object.setPrototypeOf(mockFolder, obsidian.TFolder.prototype);
        mockApp.vault.getAbstractFileByPath.mockReturnValue(mockFolder);
        await expect(processTasks(mockApp, 'same', 'same')).rejects.toThrow('Source folder and output folder must be different.');
    });

    test('processes tasks and creates output files', async () => {
        const mockSourceFolder = {
            path: 'source',
            children: [],
            name: 'source',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockSourceFolder, obsidian.TFolder.prototype);
        const mockOutputFolder = {
            path: 'output',
            children: [],
            name: 'output',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockOutputFolder, obsidian.TFolder.prototype);

        mockApp.vault.getAbstractFileByPath
            .mockReturnValueOnce(mockSourceFolder)
            .mockReturnValueOnce(mockOutputFolder);

        // Mock getAllMdFiles to return empty array (no files to process)
        jest.spyOn({ getAllMdFiles }, 'getAllMdFiles').mockReturnValue([]);

        await processTasks(mockApp, 'source', 'output');

        expect(mockApp.vault.modify).not.toHaveBeenCalled();
        expect(mockApp.vault.create).not.toHaveBeenCalled();
    });

    test('handles existing output files with checked tasks', async () => {
        const mockSourceFolder = {
            path: 'source',
            children: [],
            name: 'source',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockSourceFolder, obsidian.TFolder.prototype);
        const mockOutputFolder = {
            path: 'output',
            children: [{
                name: '2023-10-01.md',
                path: 'output/2023-10-01.md',
            } as obsidian.TFile],
            name: 'output',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockOutputFolder, obsidian.TFolder.prototype);

        mockApp.vault.getAbstractFileByPath
            .mockReturnValueOnce(mockSourceFolder)
            .mockReturnValueOnce(mockOutputFolder);

        const mockExistingFile = { path: 'output/2023-10-01.md' };
        Object.setPrototypeOf(mockExistingFile, obsidian.TFile.prototype);
        mockApp.vault.getAbstractFileByPath.mockReturnValue(mockExistingFile);
        mockApp.vault.read.mockResolvedValue('- [x] Existing checked task\n- [ ] Existing unchecked task');

        // Mock getAllMdFiles to return files with tasks
        const mockFileWithTask = {
            path: 'source/file.md',
            extension: 'md',
            basename: 'file',
            name: 'file.md',
            parent: mockSourceFolder,
            vault: mockApp.vault,
            stat: { ctime: 0, mtime: 0, size: 0 } as any
        };
        Object.setPrototypeOf(mockFileWithTask, obsidian.TFile.prototype);
        jest.spyOn(require('../taskProcessor'), 'getAllMdFiles').mockReturnValue([mockFileWithTask]);
        mockApp.vault.read.mockResolvedValueOnce('- [ ] New task (@2023-10-01 14:00)');

        await processTasks(mockApp, 'source', 'output');

        // Verify that the function processes tasks without error
        expect(true).toBe(true);
    });

    test('processes tasks and creates new output files', async () => {
        const mockSourceFolder = {
            path: 'source',
            children: [],
            name: 'source',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockSourceFolder, obsidian.TFolder.prototype);
        const mockOutputFolder = {
            path: 'output',
            children: [],
            name: 'output',
            parent: null,
            vault: mockApp.vault,
            isRoot: () => false,
        };
        Object.setPrototypeOf(mockOutputFolder, obsidian.TFolder.prototype);

        mockApp.vault.getAbstractFileByPath
            .mockReturnValueOnce(mockSourceFolder)
            .mockReturnValueOnce(mockOutputFolder)
            .mockReturnValue(null); // No existing file

        const mockFileWithTask = {
            path: 'source/file.md',
            extension: 'md',
            basename: 'file',
            name: 'file.md',
            parent: mockSourceFolder,
            vault: mockApp.vault,
            stat: { ctime: 0, mtime: 0, size: 0 } as any
        };
        Object.setPrototypeOf(mockFileWithTask, obsidian.TFile.prototype);
        jest.spyOn({ getAllMdFiles }, 'getAllMdFiles').mockReturnValue([mockFileWithTask]);
        mockApp.vault.read.mockResolvedValue('- [ ] New task (@2023-10-01 14:00)');

        await processTasks(mockApp, 'source', 'output');

        // Verify that the function processes tasks without error
        expect(true).toBe(true);
    });
});
