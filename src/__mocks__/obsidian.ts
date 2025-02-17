// __mocks__/obsidian.ts
export class Plugin {
  app: any;
  manifest: any;
  constructor(app: any, manifest: any) {
      this.app = app;
      this.manifest = manifest; // Use the parameter
  }
  async onload() {}
  addCommand(command: any) {
      return command;
  }
}

export class MarkdownView {
  editor: any;
  constructor() {
      this.editor = {
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
          getDoc: jest.fn(() => ({ getValue: jest.fn(() => '') })),
          refresh: jest.fn(),
          listSelections: jest.fn(() => []),
          setSelections: jest.fn(),
          transaction: jest.fn(),
          processLines: jest.fn(() => 0),
      };
  }
}

export class TFile {
  basename: string = '';
  extension: string = '';
  parent: any = { path: '' };
  stat: any = {};
  vault: any = {};
  path: string = '';
  name: string = '';
}

export class Workspace {
  getActiveViewOfType = jest.fn();
  getActiveFile = jest.fn();
}

export class App {
  workspace: Workspace = new Workspace();
  fileManager: any = {
      renameFile: jest.fn(),
      getNewFileParent: jest.fn(),
      generateMarkdownLink: jest.fn(() => ''),
  };
}
