import { FolderSelectorModal } from '../folderSelectorModal';
import * as obsidian from 'obsidian';

const mockApp: obsidian.App = {
    workspace: {} as any,
    vault: {
        getRoot: jest.fn(() => ({ path: '/', children: [], name: '/', parent: null, vault: {} as any, isRoot: () => true } as obsidian.TFolder)),
        getAbstractFileByPath: jest.fn(),
    } as any,
} as obsidian.App;

const mockFolder: obsidian.TFolder = {
    path: 'test/folder',
    name: 'folder',
    children: [],
    parent: null as any,
    vault: mockApp.vault,
    isRoot: jest.fn(() => false),
};

describe('FolderSelectorModal', () => {
    let modal: FolderSelectorModal;

    beforeEach(() => {
        modal = new FolderSelectorModal(mockApp);
        // Mock contentEl to avoid DOM issues
        (modal as any).contentEl = {
            empty: jest.fn(),
            createEl: jest.fn(() => ({
                addEventListener: jest.fn(),
            })),
        };
    });

    test('creates modal instance', () => {
        expect(modal).toBeInstanceOf(FolderSelectorModal);
    });

    test('onOpen calls showSourceSelection', () => {
        const spy = jest.spyOn(modal as any, 'showSourceSelection');
        modal.onOpen();
        expect(spy).toHaveBeenCalled();
    });

    test('onClose empties contentEl', () => {
        modal.onClose();
        expect((modal as any).contentEl.empty).toHaveBeenCalled();
    });

    test('showSourceSelection sets up UI elements', () => {
        const createElSpy = jest.spyOn((modal as any).contentEl, 'createEl');
        (modal as any).showSourceSelection();
        expect((modal as any).contentEl.empty).toHaveBeenCalled();
        expect(createElSpy).toHaveBeenCalledWith('h2', { text: 'Select Source Folder' });
        expect(createElSpy).toHaveBeenCalledWith('p', expect.any(Object));
    });

    test('showOutputSelection sets up UI elements', () => {
        (modal as any).sourceFolder = mockFolder;
        const createElSpy = jest.spyOn((modal as any).contentEl, 'createEl');
        (modal as any).showOutputSelection();
        expect((modal as any).contentEl.empty).toHaveBeenCalled();
        expect(createElSpy).toHaveBeenCalledWith('h2', { text: 'Select Output Folder' });
        expect(createElSpy).toHaveBeenCalledWith('p', { text: `Source: test/folder` });
    });

    test('showSourceSelection creates select button', () => {
        const createElSpy = jest.spyOn((modal as any).contentEl, 'createEl');
        (modal as any).showSourceSelection();
        expect(createElSpy).toHaveBeenCalledWith('button', { text: 'Select Source Folder', cls: 'mod-cta' });
    });

    test('showOutputSelection creates select and back buttons', () => {
        (modal as any).sourceFolder = mockFolder;
        const createElSpy = jest.spyOn((modal as any).contentEl, 'createEl');
        (modal as any).showOutputSelection();
        expect(createElSpy).toHaveBeenCalledWith('button', { text: 'Select Output Folder', cls: 'mod-cta' });
        expect(createElSpy).toHaveBeenCalledWith('button', { text: 'Back', cls: 'mod-secondary' });
    });
});
