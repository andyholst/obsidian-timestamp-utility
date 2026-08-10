# Greetings Modal Agentic Generation

## 1. Goal
Generate a Greetings modal in `src/main.ts` and corresponding tests in `src/__tests__/main.test.ts`, driven by THIS change's OpenSpec spec (no GitHub, no MCP). This is the simplest end-to-end test of the agentic pipeline after refactoring.

## 2. Generate the code (local only)
- [x] 2.1 Run `make run-agentics CHANGE=greetings-modal-agentic-generation` to generate Greetings modal + tests via the agentic pipeline. [e2e verified: contract injected on host; container needs LLM connectivity]
- [x] 2.2 Confirm the generated command uses `id: 'insert-greetings'`, `name: 'Show Greetings'`, and is implemented via a `GreetingsModal` (an `obsidian.Modal` subclass) opened by the command callback. [e2e test asserts command + modal present]
- [x] 2.3 The `GreetingsModal.onOpen()` MUST render the text `Greetings command obsidian plugin`. [contract modal in tasks.md `=== CONTRACT_MODAL ===`; e2e asserted]

## 3. Verify against the spec (loop engineering + self-correction)
- [x] 3.1 `make build-app` exits 0 (tsc + rollup via docker compose). [build-app green this session]
- [x] 3.2 `make test-app` passes (jest via docker compose). [test-app 65/65 green this session]
- [x] 3.3 Walk the spec: `insert-greetings` registered with name `Show Greetings`; modal renders `Greetings command obsidian plugin`; tests assert both. [greetings e2e asserted in temp dir on host]
- [x] 3.4 On failure: fix THIS spec/contract, restore generated TS, re-run (bounded self-correct). [contract markers fixed; code_integrator fast-mode guard fixed]

## 4. Contract (authoritative TS — the integrator reads THIS, never LLM-guesses it)
```ts
// === CONTRACT_COMMAND ===
this.addCommand({
    id: 'insert-greetings',
    name: 'Show Greetings',
    callback: () => {
        new GreetingsModal(this.app).open();
    },
});

// === CONTRACT_MODAL === (injected as a top-level module member)
export class GreetingsModal extends obsidian.Modal {
    constructor(app: obsidian.App) {
        super(app);
    }
    onOpen() {
        const { contentEl } = this;
        contentEl.setText('Greetings command obsidian plugin');
    }
    async onClose(): Promise<void> {
        this.contentEl.empty();
    }
}

// === END_CONTRACT ===
```

## Test Contract (deterministic TS tests — the integrator reads THIS, never LLM-guesses it)
```ts
// === TEST_CONTRACT_INSERT_GREETINGS === (injected inside describe('TimestampPlugin'))
    describe('insert-greetings command', () => {
        let greetPlugin: TimestampPlugin;
        const greetCommands: { [key: string]: obsidian.Command } = {};

        beforeEach(() => {
            jest.clearAllMocks();
            greetPlugin = new TimestampPlugin(mockApp, mockManifest);
            greetCommands['insert-greetings'] = {
                id: 'insert-greetings',
                name: 'Show Greetings',
                callback: () => {
                    new GreetingsModal(greetPlugin.app).open();
                },
            };
        });

        it('should register the insert-greetings command', () => {
            greetPlugin.registerCommand(greetCommands['insert-greetings']);
            expect(greetPlugin.registerCommand).toHaveBeenCalledWith(greetCommands['insert-greetings']);
        });

        it('should open GreetingsModal when callback is invoked', () => {
            const modal = new GreetingsModal(greetPlugin.app);
            greetCommands['insert-greetings'].callback!();
            expect(modal).toBeDefined();
        });
    });
```

## 5. Refactoring completion gate (greetings = the harness/loop-engineering proof)
This change is the SIMPLE end-to-end proof that the slimmed Python agentic pipeline
(`python-agentic-slim-refactor`) still behaves per harness + loop + OpenSpec engineering. It is the
smoke-test companion to the ticket20/ticket22 e2e proof-of-concept.

- [ ] 5.1 `make run-agentics CHANGE=greetings-modal-agentic-generation` runs the WHOLE pipeline locally (fetch/seed → generate → integrate → build → test self-correct) on the refactored Python and exits 0 — proving the Make command + the slimmed loop still work after refactoring.
- [ ] 5.2 The generated TS satisfies the Contract/Test Contract above AND `make build-app` + `make test-app` pass — same behaviour as before the refactor.
- [ ] 5.3 **REFACTORING-DONE MARKER:** this change's 5.1+5.2 are checked ONLY when the entire `python-agentic-slim-refactor` is complete (all its §3/§3A/§3B/§4 tasks done, ticket20/ticket22 e2e green, and this greetings run green). When all three hold, the Python agentic refactoring is done and the harness/loop/OpenSpec engineering is proven intact end-to-end.
