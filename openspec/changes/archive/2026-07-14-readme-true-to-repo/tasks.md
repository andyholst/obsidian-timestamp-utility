# Tasks

- [x] 1.1 Fill the change `readme-true-to-repo` proposal.md / spec.md / tasks.md with the evidence-backed corrections
- [x] 2.1 Fix "Steps to Run the Agent": `make run-agentics CHANGE=<name>` (local OpenSpec change, no GitHub fetch); remove `build-image-agents`, `ISSUE_URL=`, `agentics.log` — keep same format
- [x] 2.2 Remove the false MCP note (localhost:3003 / `make start-mcp-persist`) from "Running Integration Tests"
- [x] 2.3 Fix test filenames reference → real `agents/agentics/tests/{unit,integration}` layout + real `make test-agents*` targets
- [x] 2.4 Correct llama model defaults to Makefile values (`qwen3.6-35b-a3b`, `LLAMA_HOST=http://localhost:11434`)
- [x] 3.1 Verify README no longer contains: MCP / localhost:3003 / start-mcp-persist / build-image-agents / ISSUE_URL= / agentics.log / test_ticket_interpreter / qwen3.5:9b / qwen3.5:4b
- [x] 4.1 B8-sync check: confirm AGENTS.md / openspec-loop-harness skill unaffected (README-only)
- [x] 5.1 VERIFICATION: `make loop-collect` + `make loop-unit` still pass
- [x] 6.1 `openspec validate readme-true-to-repo` passes
