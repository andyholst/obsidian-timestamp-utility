// Type shim for obsidian module (replaces @types/obsidian git dependency)
declare module 'obsidian' {
  export interface App {
    workspace: Workspace
    fileManager: FileManager
    vault: Vault
    metadataCache: MetadataCache
    plugins: PluginManager
    normalizePath(path: string): string
    getAvailableTags(): Promise<string[]>
    keymap: any
    scope: any
    lastEvent: string
    loadLocalStorage(name: string): Promise<any>
    saveLocalStorage(name: string, data: any): Promise<void>
    renderContext: any
    secretStorage: any
    isDarkMode: boolean
  }

  export interface Workspace {
    getActiveViewOfType<T extends View>(clazz: new (container: any) => T): T | null
    getActiveFile(): TFile | null
    leaves: Array<{ content: View }>
    on(name: string, callback: (data: any) => void): void
  }

  export interface View {
    containerEl: HTMLElement
    editor?: Editor
  }

  export interface FileManager {
    renameFile(file: TFile, newName: string): Promise<TFile>
    getNewFileParent(folder: TFolder): TFolder
    generateMarkdownLink(file: TFile, sourcePath: string): string
    trashFile(file: TFile): void
    processFrontMatter(file: TFile, callback: (frontMatter: any) => any): void
    getAvailablePathForAttachment(parent: TFolder, SuggestedName: string, extension: string): string
    promptForDeletion(file: TFile): Promise<boolean>
  }

  // Export Vault as both a namespace (for static methods) and an interface (for instance methods)
  export namespace Vault {
    export function recurseChildren(root: TFolder, callback: (child: TFolder) => void): void
  }

  export interface Vault {
    adapter: FileSystemAdapter
    getConfig(key: string): any
    setConfig(key: string, value: any): void
    getRoot(): TFolder
    on(name: string, callback: (data: any) => void): void
    getAbstractFileByPath(path: string): TFile | TFolder | null
    read(file: TFile): Promise<string>
    modify(file: TFile, callback: (content: string) => string): Promise<void>
    create(name: string, content: string): Promise<TFile>
    delete(file: TFile): Promise<void>
  }

  export interface MetadataCache {
    getTags(): Array<{ tag: string; count: number }>
  }

  export interface PluginManager {
    enabledPlugins: Set<string>
  }

  export interface FileSystemAdapter {
    basePath: string
    getFilePath(path: string): string
  }

  export abstract class Plugin {
    app: App
    manifest: PluginManifest
    constructor(app: App, manifest: PluginManifest)
    abstract onload(): void
    addCommand(cmd: Command): void
    tfileCache: Map<string, TFile>
  }

  export interface PluginManifest {
    id: string
    name: string
    version: string
    minAppVersion: string
    description: string
    author: string
    isDesktopOnly?: boolean
  }

  export interface Command {
    id: string
    name: string
    checkCallback?: (checking: boolean) => void | boolean
    callback?: () => void
    editorCallback?: (editor: Editor, view: MarkdownView) => void
  }

  export abstract class Modal {
    app: App
    contentEl: HTMLElement
    constructor(app: App)
    onOpen(): void
    onClose(): void
    open(): void
    close(): void
  }

  export interface TFile {
    basename: string
    extension: string
    parent: TFolder | null
    stat: FileStats
    vault: Vault
    path: string
    name: string
  }

  export interface FileStats {
    mtime: number
    ctime: number
    size: number
  }

  export interface TFolder {
    path: string
    name: string
    parent: TFolder | null
    children: Array<TFile | TFolder>
    isRoot: boolean
    vault: Vault
  }

  export class FuzzySuggestModal<T> extends Modal {
    constructor(app: App)
    setPlaceholder(placeholder: string): void
    getItems(): T[]
    getItemText(item: T): string
    onChooseItem(item: T): void
  }

  export class Notice {
    constructor(message: string, timeout?: number)
    setMessage(message: string): void
    hide(): void
  }

  export interface Editor {
    replaceSelection(text: string): void
    getValue(): string
    setValue(text: string): void
    getSelection(): string
    setSelection(from: { line: number; ch: number }, to: { line: number; ch: number }): void
    getRange(from: { line: number; ch: number }, to: { line: number; ch: number }): string
    getLine(line: number): string
    setLine(line: number, text: string): void
    lineCount(): number
    lastLine(): number
    offsetToPos(offset: number): { line: number; ch: number }
    posToOffset(pos: { line: number; ch: number }): number
    getCursor(): { line: number; ch: number }
    setCursor(pos: { line: number; ch: number }): void
    somethingSelected(): boolean
    exec(command: string): void
    focus(): void
    blur(): void
    hasFocus(): boolean
    getScrollInfo(): { top: number; left: number }
    scrollTo(line: number, ch: number): void
    scrollIntoView(pos: { line: number; ch: number }): void
    undo(): void
    redo(): void
    wordAt(pos: { line: number; ch: number }): any
    getDoc(): CodeMirror.Doc
    refresh(): void
    listSelections(): Array<{ anchor: { line: number; ch: number }; head: { line: number; ch: number } }>
    setSelections(anchor: any, head: any): void
    transaction(changes: any): void
    processLines(from: number, to: number, callback: (line: string) => void): void
    replaceRange(replacement: string, from: { line: number; ch: number }, to?: { line: number; ch: number }): void
  }

  export interface MarkdownView extends View {
    editor: Editor
    file?: TFile
  }

  export interface CodeMirror {
    Doc: any
  }

  // Export classes as both types and values
  export class TFolder {}
  export class TFile {}
  export class MarkdownView {}
  export class MarkdownFileInfo {}

  export interface MarkdownRenderChild {
    containerEl: HTMLElement
  }

  export interface SuggestModal<T> extends FuzzySuggestModal<T> {}

  export interface HTMLElement {
    empty(): void
    createEl<K extends keyof HTMLElementTagNameMap>(
      tag: K,
      options?: {
        text?: string
        cls?: string | string[]
        attr?: Record<string, string>
        title?: string
        href?: string
        click?: () => void
        type?: string
        placeholder?: string
      }
    ): HTMLElementTagNameMap[K] & { setText(text: string): void }
    createDiv(options?: { text?: string; cls?: string | string[]; attr?: Record<string, string> }): HTMLDivElement
    createSpan(options?: { text?: string; cls?: string | string[]; attr?: Record<string, string> }): HTMLSpanElement
    createP(options?: { text?: string; cls?: string | string[]; attr?: Record<string, string> }): HTMLParagraphElement
    createButton(options?: { text?: string; cls?: string | string[]; attr?: Record<string, string> }): HTMLButtonElement
    addEventListener(type: string, listener: (event: Event) => void): void
    setAttr(key: string, value: any): void
    toggleClass(name: string, state?: boolean): void
    hasClass(name: string): boolean
    remove(): void
    setText(text: string): void
  }

  export interface HTMLPreElement extends HTMLElement {
    setText(text: string): void
  }

  export interface MarkdownPostProcessorContext {
    sourcePath: string
    containerEl: HTMLElement
    loading: (error?: Error) => void
  }

  export function addIcon(name: string, icon: string): void

  export interface Setting {
    setHeading(): Setting
    setName(name: string): Setting
    setDesc(desc: string): Setting
    addText(callback: (text: string) => void): Setting
    addSlider(callback: (value: number) => void): Setting
    addToggle(callback: (value: boolean) => void): Setting
    addButton(callback: (button: ButtonComponent) => void): Setting
  }

  export class ButtonComponent {
    button: HTMLButtonElement
    setButtonText(text: string): ButtonComponent
    setTooltip(tooltip: string): ButtonComponent
    setClass(cls: string): ButtonComponent
    onClick(callback: () => void): ButtonComponent
  }

  export interface NoticeConstructor {
    new (message: string, timeout?: number): Notice
  }

  export const requestUrl: any
  export const request: any
  export const normalizePath: (path: string) => string
  export const sanitize: (path: string) => string
  export const decodeHTML: (text: string) => string
}
