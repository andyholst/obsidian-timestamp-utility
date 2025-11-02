import { addOneHour, processLine, getAllMdFiles } from '../taskProcessor';
import * as obsidian from 'obsidian';

describe('addOneHour', () => {
    test('adds one hour correctly', () => {
        expect(addOneHour('13:00')).toBe('14:00');
        expect(addOneHour('23:00')).toBe('00:00');
        expect(addOneHour('12:30')).toBe('13:30');
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
