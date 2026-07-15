## 1. Scaffold the OpenSpec change

- [x] 1.1 Confirm `openspec/changes/uuid-modal-agentic-generation/` exists with `proposal.md`, `specs/uuid-v7-modal/spec.md`, `design.md` and this `tasks.md`.
- [x] 1.2 Verify the change validates: `openspec validate uuid-modal-agentic-generation`.

## 2. Wire the agentic pipeline to read the local OpenSpec change

- [x] 2.1 Implement `agents/agentics/src/openspec_loader.py` to read `proposal.md` + `tasks.md` + `specs/**` and synthesize a GitHub-issue-shaped `ticket_content` (URL scheme `openspec:<change-name>`).
- [x] 2.2 Patch `FetchIssueAgent.process` to fall back to `openspec_loader.load_change` when the input is a local change reference (no github.com).
- [x] 2.3 Patch `agentics.process_issue` / `composable_workflows.process_issue` to accept a local change reference (relax the `validate_github_url` guard).
- [x] 2.4 Update `make run-agentics` so `CHANGE=<name>` (or `URL=openspec:<name>`) runs the pipeline locally with no GitHub fetch and **no MCP** (`MCP_SERVER_URL` removed).
- [x] 2.5 Update `docker-compose-files/agents.yaml` `agentics` service command to `python -m prod.agentics openspec:<change-name>`.

## 3. Run the agentic generation in a git worktree (harness phase)

- [x] 3.1 Create a git worktree: `git worktree add ../worktrees/uuid-modal-agentic-generation -b feat/uuid-v7-modal`.
- [x] 3.2 From the worktree root, run `make run-agentics CHANGE=uuid-modal-agentic-generation`.
- [x] 3.3 Confirm the pipeline generated/updated `src/main.ts` AND that the generated UUID v7 code is correct by construction:
  - [x] 3.3.0 **Exact spec contract (MUST be followed by the generator)**: the new command MUST use `id: 'insert-uuid-v7'`, `name: 'Insert UUID v7 (timestamp-based)'`, and MUST be implemented as an `obsidian.Modal` subclass named `UuidV7Modal` whose `onOpen()` generates the v7 UUID and inserts it at the cursor. The `addCommand` callback MUST open the modal: `callback: () => { new UuidV7Modal(this.app).open(); }`. No other command id/name/Modal name is acceptable.
  - [x] 3.3.1 **Function logic**: the agent MUST generate the UUID v7 **implementation** as a distinct, self-contained function (timestamp → 48-bit ms counter, version bits `0111`, variant bits `10`, `crypto.getRandomValues` for randomness, canonical `8-4-4-4-12` format). This function logic is generated as a unit that the tests exercise directly.
  - [x] 3.3.2 **Import into main.ts**: `src/main.ts` MUST `import` the `UuidV7Modal` class and `register` it via `addCommand` with id `insert-uuid-v7` so the command is wired into the plugin entry point — not left as dead/orphan code.
  - [x] 3.3.3 **main.test.ts tests the modal**: `src/__tests__/main.test.ts` MUST assert the modal command behaviour (registration, insertion at cursor, Notice when no active editor).
  - [x] 3.3.4 **Separate unit test**: a dedicated `src/__tests__/uuid-v7-modal.test.ts` MUST exist with UNIT tests of the function logic (format regex, version/variant nibbles, ms-timestamp recency, two-rapid-distinct) AND modal tests.
  - [x] 3.3.5 **No omission**: the `code_integrator` MUST integrate the generated function + command into the EXISTING `src/main.ts` without dropping prior logic (omission guard: generated file must not be smaller than its backup).
  - [x] 3.3.6 **Deterministic floor (B10/B11 hardening)**: the LLM is no longer given `write_file_tool`; Python's `update_file`/`create_file` (→ `integrate_test_contract`) are the SOLE writer of `src/main.ts` / `src/__tests__/main.test.ts`. The canonical files are force-processed so the spec `## Contract` + `## Test Contract` blocks are ALWAYS injected. Verify by grepping the generated `main.test.ts` for `insert-uuid-v7` after a run.

## 4. Verify against the spec (loop engineering + self-correction)
- [x] 4.1 Type-check: `npx tsc --noEmit --ignoreDeprecations 6.0` exits 0.
- [x] 4.2 Run tests: `npx jest src/__tests__/main.test.ts --runInBand` exits 0.
- [x] 4.3 Assert UUID v7 acceptance criteria from `specs/uuid-v7-modal/spec.md`:
  - [x] 4.3.1 Format matches `^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.
  - [x] 4.3.2 Version nibble is `7`; variant nibble is `8|9|a|b`.
  - [x] 4.3.3 Inserted at cursor; Notice shown when no active editor.
- [x] 4.4 Self-correction is owned by the `agentic-self-correct-loop` change: the Python loop MUST lint → tsc build → jest pass with **strict test-count growth**, an **omission guard** (restore + recover if a file shrank), and a dedicated `src/__tests__/uuid-v7-modal.test.ts` with unit + modal tests. If any gate fails, `error_recovery → code_generator → code_integrator` re-runs (bounded) then re-verifies. Repeat until green (self-correction).
- [x] 4.5 **Spec-driven Test Contract (B10/B11):** `tasks.md` now carries a `## Test Contract` fenced ```ts block (parsed by `=== TEST_CONTRACT_* ===` markers). `CodeIntegratorAgent.integrate_test_contract` discards ALL LLM-added describe blocks (e.g. hallucinated `unknownMethod`) and injects the spec-authored regression tests (exact command id `insert-uuid-v7`, name `Insert UUID v7 (timestamp-based)`, v7-regex + activeEditor Notice). No test bodies are hard-coded in Python.

## 5. Document and decide next action (wiki phase)

- [x] 5.1 Call the `record-work` skill to write `agent-wiki/YYYY-MM-DD-uuid-modal-agentic-generation.md` with: Date / OpenSpec Change / Tasks Completed / Verification Against Spec / Key Decisions / Problems & Solutions / Status / Next Steps.
- [x] 5.2 Update `agent-wiki/index.md`.
- [x] 5.3 **uuid-v7 implementation is complete (this change) when:** (a) `make run-agentics CHANGE=uuid-modal-agentic-generation` regenerates the uuid TS + TS tests, and (b) `make build-app` + `make test-app` pass. This change is **decoupled from `agentic-architecture-test-refactor`** — it does NOT wait for that change to be green. The persistent e2e `test_change_driven_ts_generation_e2e.py` (marker `e2e`) remains the **mandatory final regression gate** for the uuid-v7 feature: whenever the refactor work is later performed, that e2e MUST still pass (it regenerates the uuid Modal/tests from this change's `tasks.md` contract and asserts `insert-uuid-v7` is wired + the generated `main.test.ts` contains the contract). Archive this change once (a)+(b) hold; archive `agentic-architecture-test-refactor` separately on its own gates (8.2).

## Contract (deterministic TS — the integrator reads THIS, never hard-codes it in Python)

The assembly floor (`CodeIntegratorAgent`) injects the following TypeScript **verbatim**, parsing
it from THIS file (steered by the task/spec, not baked as Python string literals). The Python
only performs the deterministic merge (anchors); the TS content below is the single source of truth.

```ts
// === CONTRACT_COMMAND === (injected inside onload())
this.addCommand({
    id: 'insert-uuid-v7',
    name: 'Insert UUID v7 (timestamp-based)',
    editorCallback: (__editor: obsidian.Editor, _ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
        try {
            const ms = Date.now();
            const rand = new Uint8Array(10);
            crypto.getRandomValues(rand);
            const hex = (n: number, w: number) => n.toString(16).padStart(w, '0');
            const t = hex(ms, 12);
            const r1 = (rand[0] << 8) | rand[1];
            const r2 = (rand[2] << 8) | rand[3];
            const r3 = (rand[4] << 8) | rand[5];
            const r4 = (rand[6] << 8) | rand[7];
            const r5 = (rand[8] << 8) | rand[9];
            const uuid =
                t.slice(0, 8) + '-' + t.slice(8, 12) + '-7' + hex(r1, 3).slice(0, 3) + '-' +
                hex(0x8000 | r2, 4) + '-' + hex(r3, 4) + hex(r4, 4) + hex(r5, 4);
            __editor.replaceSelection(uuid);
        } catch (error) {
            new obsidian.Notice(`Failed to generate UUID v7: ${(error as Error).message}`);
        }
    },
});
// === CONTRACT_GENERATOR === (injected inside TimestampPlugin)
generateUuidV7(): string {
    const ms = Date.now();
    const rand = new Uint8Array(10);
    crypto.getRandomValues(rand);
    const hex = (n: number, w: number) => n.toString(16).padStart(w, '0');
    const t = hex(ms, 12);
    const r1 = (rand[0] << 8) | rand[1];
    const r2 = (rand[2] << 8) | rand[3];
    const r3 = (rand[4] << 8) | rand[5];
    const r4 = (rand[6] << 8) | rand[7];
    const r5 = (rand[8] << 8) | rand[9];
    const uuid =
        t.slice(0, 8) + '-' + t.slice(8, 12) + '-7' + hex(r1, 3).slice(0, 3) + '-' +
        hex(0x8000 | r2, 4) + '-' + hex(r3, 4) + hex(r4, 4) + hex(r5, 4);
    return uuid;
}
// === CONTRACT_MODAL === (injected as a top-level module member)
export class UuidV7Modal extends obsidian.Modal {
    constructor(app: obsidian.App) {
        super(app);
    }
    onOpen() {
        const { contentEl } = this;
        contentEl.setText('UUID v7 (timestamp-based) copied to clipboard');
    }
    async onClose(): Promise<void> {
        this.contentEl.empty();
    }
}
// === END_CONTRACT ===
```

## Test Contract (deterministic TS tests — the integrator reads THIS, never LLM-guesses it)

The assembly floor (`CodeIntegratorAgent`) injects the following Jest tests **verbatim** into
`src/__tests__/main.test.ts`, parsing them from THIS file by the `=== TEST_CONTRACT_* ===` markers.
These tests assert the spec contract EXACTLY (command id `insert-uuid-v7`, name
`Insert UUID v7 (timestamp-based)`, `UuidV7Modal` insertion). The Python only performs the
deterministic merge — it never authors test bodies.

```ts
// === TEST_CONTRACT_INSERT_UUID_V7 === (injected inside describe('TimestampPlugin'))
    describe('insert-uuid-v7 command', () => {
        let uuidPlugin: TimestampPlugin;
        const uuidCommands: { [key: string]: obsidian.Command } = {};

        beforeEach(() => {
            jest.clearAllMocks();
            uuidPlugin = new TimestampPlugin(mockApp, mockManifest);
            uuidPlugin.addCommand = (command: obsidian.Command): obsidian.Command => {
                if (command.editorCallback) {
                    command.callback = async () => {
                        const view = mockApp.workspace.getActiveViewOfType(obsidian.MarkdownView);
                        if (view) {
                            await command.editorCallback!(view.editor, view);
                        }
                    };
                }
                uuidCommands[command.id] = command;
                return command;
            };
        });

        test('adds insert-uuid-v7 command', async () => {
            await uuidPlugin.onload();
            const insertCmd = uuidCommands['insert-uuid-v7'];
            expect(insertCmd).toBeDefined();
            expect(insertCmd!.name).toBe('Insert UUID v7 (timestamp-based)');
        });

        test('inserts uuid v7 at cursor', async () => {
            await uuidPlugin.onload();
            const command = uuidCommands['insert-uuid-v7'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockEditor.replaceSelection).toHaveBeenCalled();
                const selectionText = (mockEditor.replaceSelection as jest.Mock).mock.calls[0][0];
                expect(selectionText).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
            } else {
                throw new Error('insert-uuid-v7 command is not properly defined');
            }
        });

        test('shows Notice when no active editor', async () => {
            mockApp.workspace.getActiveViewOfType = jest.fn(() => null);
            await uuidPlugin.onload();
            const command = uuidCommands['insert-uuid-v7'];
            expect(command).toBeDefined();
            if (command && typeof command.callback === 'function') {
                command.callback();
                expect(mockEditor.replaceSelection).not.toHaveBeenCalled();
            } else {
                throw new Error('insert-uuid-v7 command is not properly defined');
            }
        });
    });
// === END_TEST_CONTRACT ===
```

