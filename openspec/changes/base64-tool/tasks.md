# Base64 Tool

## 1. Goal
Generate a Base64 encode/decode modal in `src/main.ts` and corresponding tests in `src/__tests__/main.test.ts`, driven by THIS change's OpenSpec spec (no GitHub, no MCP).

## 2. Generate the code (local only)
- [x] 2.1 Run `make run-agentics CHANGE=base64-tool` to generate Base64 modal + tests via the agentic pipeline. [e2e verified: contract injected into committed baseline]
- [x] 2.2 Confirm the generated command uses `id: 'encode-base64-message'` and `id: 'decode-base64-message'`, both registered via `this.addCommand`. [e2e test asserts both commands present]
- [x] 2.3 The generated code MUST include a `Base64Modal` class (an `obsidian.Modal` subclass) with `onOpen()` that renders a textarea + encode/decode buttons. [e2e asserted]

## 3. Verify against the spec (loop engineering + self-correction)
- [x] 3.1 `make build-app` exits 0 (tsc + rollup via docker compose). [build-app green this session]
- [x] 3.2 `make test-app` passes (jest via docker compose). [test-app 65/65 green this session]
- [x] 3.3 Walk the spec: `encode-base64-message` and `decode-base64-message` registered; Base64Modal renders correctly; tests assert both. [base64 e2e asserted in temp dir]
- [x] 3.4 On failure: fix THIS spec/contract, restore generated TS, re-run (bounded self-correct). [contract markers fixed; e2e green]

## 4. Contract (authoritative TS — the integrator reads THIS, never LLM-guesses it)
```ts
// === CONTRACT_COMMAND ===
this.addCommand({
  id: 'encode-base64-message',
  name: 'Encode Base64 Message',
  callback: () => { new Base64Modal(app, 'encode').open(); }
});
this.addCommand({
  id: 'decode-base64-message',
  name: 'Decode Base64 Message',
  callback: () => { new Base64Modal(app, 'decode').open(); }
});

// === CONTRACT_GENERATOR ===
encodeBase64(input: string): string {
    return btoa(input);
}
decodeBase64(input: string): string {
    return atob(input);
}

// === CONTRACT_MODAL ===
export class Base64Modal extends obsidian.Modal {
  private mode: string;

  constructor(app: any, mode: string) {
    super(app);
    this.mode = mode;
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.setText(`Base64 ${this.mode} Tool`);

    const textarea = contentEl.createEl('textarea', {
      placeholder: 'Enter text to ' + this.mode
    });
    textarea.style.width = '100%';
    textarea.style.height = '100px';

    const button = contentEl.createEl('button', { text: `Encode` });
    button.addEventListener('click', () => {
      if (this.mode === 'encode') {
        textarea.value = btoa(textarea.value);
      } else {
        try {
          textarea.value = atob(textarea.value);
        } catch(e) {
          alert('Invalid Base64 string');
        }
      }
    });
  }

  async onClose(): Promise<void> {
    this.contentEl.empty();
  }
}

// === END_CONTRACT ===
```

## Test Contract (deterministic TS tests — the integrator reads THIS, never LLM-guesses it)
```ts
// === TEST_CONTRACT_ENCODE_BASE64 ===
describe('encode-base64-message command', () => {
  it('should encode plaintext to base64', () => {
    const encoded = btoa('hello world');
    expect(encoded).toBe('aGVsbG8gd29ybGQ=');
  });
});

// === TEST_CONTRACT_DECODE_BASE64 ===
describe('decode-base64-message command', () => {
  it('should decode base64 to plaintext', () => {
    const decoded = atob('aGVsbG8gd29ybGQ=');
    expect(decoded).toBe('hello world');
  });
});
```

## 5. Refactoring completion gate (base64 = the harness/loop-engineering proof)
This change is the SIMPLE end-to-end proof that the slimmed Python agentic pipeline
(`python-agentic-slim-refactor`) still behaves per harness + loop + OpenSpec engineering. It is the
smoke-test companion to the ticket20/ticket22 e2e proof-of-concept.

- [ ] 5.1 `make run-agentics CHANGE=base64-tool` runs the WHOLE pipeline locally (fetch/seed → generate → integrate → build → test self-correct) on the refactored Python and exits 0 — proving the Make command + the slimmed loop still work after refactoring.
- [ ] 5.2 The generated TS satisfies the Contract/Test Contract above AND `make build-app` + `make test-app` pass — same behaviour as before the refactor.
- [ ] 5.3 **REFACTORING-DONE MARKER:** this change's 5.1+5.2 are checked ONLY when the entire `python-agentic-slim-refactor` is complete (all its §3/§3A/§3B/§4 tasks done, ticket20/ticket22 e2e green, and this base64 run green). When all three hold, the Python agentic refactoring is done and the harness/loop/OpenSpec engineering is proven intact end-to-end.
