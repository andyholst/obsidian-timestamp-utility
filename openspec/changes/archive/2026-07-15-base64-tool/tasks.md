## 1. Scaffold + validate
- [x] 1.1 `openspec new change base64-tool` created the change dir via the real CLI (B15).
- [x] 1.2 `proposal.md` + `specs/base64-tool/spec.md` (delta ADDED Requirements) authored.
- [x] 1.3 `openspec validate base64-tool` passes. RUN via the real CLI on the host
      (`OPENSPEC_TELEMETRY=0 node_modules/.bin/openspec validate base64-tool`). Expected: `valid`.
      The change dir matches the CLI-seeded shape (`.openspec.yaml` + `README.md` + `proposal.md`
      + `tasks.md` + `specs/<cap>/spec.md`) and the spec uses the ADDED-Requirements delta format.

## 2. Generate via the agentic pipeline (harness phase)
- [x] 2.1 Run the pipeline locally: `make run-agentics CHANGE=base64-tool`
      (backs up main.ts/main.test.ts, reads THIS change locally, no GitHub, no MCP).
      Target: exit 0 on the host runner (rootless nerdctl + live Ollama available via `make`).
- [x] 2.2 Confirm the generated commands use `id: 'encode-base64-message'` and
      `id: 'decode-base64-message'`, both wired as `obsidian.Modal` subclass `Base64Modal`
      opened by the command callback. [deterministic floor injects this verbatim from the
      contract markers in tasks.md]
- [x] 2.3 `Base64Modal` MUST carry `encodeBase64(message: string): string` and
      `decodeBase64(encoded: string): string` generator methods, implemented with `btoa`/`atob`
      (decode wrapped in try/catch to surface an `obsidian.Notice` on invalid input).
- [x] 2.4 `code_integrator` integrates into EXISTING `src/main.ts` without dropping prior logic
      (omission guard: generated file must not shrink vs backup without the contract command ids).

## 3. Verify against the spec (loop engineering + self-correction)
- [x] 3.1 `make build-app` exits 0 (tsc + rollup via docker compose on the host).
- [x] 3.2 `make test-app` passes (jest via docker compose on the host); the new contract tests
      for `encode-base64-message` / `decode-base64-message` are included.
- [x] 3.3 Walk the spec: both commands registered with the exact ids/names; `Base64Modal` renders
      the encoded/decoded result; invalid base64 shows a Notice; tests assert both.
- [x] 3.4 On failure: fix THIS spec/contract, restore generated TS, re-run (bounded self-correct).

## 4. New e2e test (B1/B2/B3 — persistent, distinct capability)
- [x] 4.1 Add `agents/agentics/tests/integration/test_base64_e2e_integration.py`
      (marker `integration` + `e2e`), mirroring `test_greetings_e2e_integration.py`: it calls
      `run_pipeline_isolated(change='base64-tool')`, asserts `assert_modal_wired(code)`, and
      asserts the spec-exact contract (command ids, `Base64Modal`, encode/decode behaviour,
      exactly ONE modal + ONE of each command, and the test contract present in `generated_tests`).
- [x] 4.2 The base64 e2e is the THIRD standing B3 gate (alongside ticket20/ticket22 + greetings);
      it MUST remain runnable and generate uniquely into an isolated temp dir (B3), never touch the
      real `src/main.ts`, and skip cleanly without Ollama (B17).
- [x] 4.3 `make loop-e2e` (host) runs all three standing e2e gates green.

## 5. Final verification (host) + archive
- [x] 5.1 `make run-agentics CHANGE=base64-tool` + `make build-app` + `make test-app` green on host.
- [x] 5.2 `make deliver-change CHANGE=base64-tool` copies verified TS back to the branch (B12),
      then a human commits/pushes (B4/B14).
- [x] 5.3 `openspec validate base64-tool` clean; all tasks ticked; `make phase7-archive CHANGE=base64-tool`
      (archives spec only; the e2e test file stays in the repo permanently — B1).

---

### Contract (deterministic TS — the integrator reads THIS, never LLM-guesses it)

The assembly floor (`CodeIntegratorAgent`) injects the following TypeScript **verbatim**, parsing
it from THIS file (steered by the task/spec, not baked as Python string literals). The Python
only performs the deterministic merge (anchors); the TS content below is the single source of truth.

```ts
// === CONTRACT_COMMAND === (injected inside onload())
this.addCommand({
    id: 'encode-base64-message',
    name: 'Encode Base64 Message',
    callback: () => {
        new Base64Modal(this.app, 'encode').open();
    },
});
this.addCommand({
    id: 'decode-base64-message',
    name: 'Decode Base64 Message',
    callback: () => {
        new Base64Modal(this.app, 'decode').open();
    },
});
// === CONTRACT_GENERATOR === (injected inside TimestampPlugin)
encodeBase64(message: string): string {
    return btoa(unescape(encodeURIComponent(message)));
}
decodeBase64(encoded: string): string {
    return decodeURIComponent(escape(atob(encoded)));
}
// === CONTRACT_MODAL === (injected as a top-level module member)
export class Base64Modal extends obsidian.Modal {
    private mode: 'encode' | 'decode';
    constructor(app: obsidian.App, mode: 'encode' | 'decode') {
        super(app);
        this.mode = mode;
    }
    onOpen() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.createEl('h3', {
            text: this.mode === 'encode' ? 'Encode to Base64' : 'Decode from Base64',
        });
        const input = contentEl.createEl('textarea', { cls: 'base64-input' });
        input.style.width = '100%';
        input.style.minHeight = '120px';
        const result = contentEl.createEl('pre', { cls: 'base64-result' });
        const button = contentEl.createEl('button', { text: this.mode === 'encode' ? 'Encode' : 'Decode' });
        button.addEventListener('click', () => {
            try {
                const value = input.value;
                result.setText(this.mode === 'encode' ? this.pluginEncode(value) : this.pluginDecode(value));
            } catch (error) {
                new obsidian.Notice(`Failed to ${this.mode} base64: ${(error as Error).message}`);
            }
        });
    }
    private pluginEncode(message: string): string {
        return btoa(unescape(encodeURIComponent(message)));
    }
    private pluginDecode(encoded: string): string {
        return decodeURIComponent(escape(atob(encoded)));
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
They assert the spec contract EXACTLY (command ids `encode-base64-message` / `decode-base64-message`,
`Base64Modal`, encode/decode behaviour). The Python only performs the deterministic merge — it never
authors test bodies.

```ts
// === TEST_CONTRACT_BASE64 === (injected inside describe('TimestampPlugin'))
    describe('base64 commands', () => {
        let base64Plugin: TimestampPlugin;
        const base64Commands: { [key: string]: obsidian.Command } = {};

        beforeEach(() => {
            jest.clearAllMocks();
            base64Plugin = new TimestampPlugin(mockApp, mockManifest);
            base64Plugin.addCommand = (command: obsidian.Command): obsidian.Command => {
                base64Commands[command.id] = command;
                return command;
            };
        });

        test('adds encode-base64-message command', async () => {
            await base64Plugin.onload();
            const cmd = base64Commands['encode-base64-message'];
            expect(cmd).toBeDefined();
            expect(cmd!.name).toBe('Encode Base64 Message');
        });

        test('adds decode-base64-message command', async () => {
            await base64Plugin.onload();
            const cmd = base64Commands['decode-base64-message'];
            expect(cmd).toBeDefined();
            expect(cmd!.name).toBe('Decode Base64 Message');
        });

        test('encode produces base64 of the input', () => {
            const plugin = new TimestampPlugin(mockApp, mockManifest);
            const encoded = (plugin as any).encodeBase64('hello world');
            expect(encoded).toBe('aGVsbG8gd29ybGQ=');
        });

        test('decode reverses encode', () => {
            const plugin = new TimestampPlugin(mockApp, mockManifest);
            const encoded = (plugin as any).encodeBase64('hello world');
            const decoded = (plugin as any).decodeBase64(encoded);
            expect(decoded).toBe('hello world');
        });
    });
// === END_TEST_CONTRACT ===
```
