"""
LangGraph workflow for autonomous TypeScript code and test generation.
Export-based: LLM generates .ts in src/generated/, import + addCommand in main.ts.
Self-correction loop (up to 3 attempts). Eval loop scores output quality.
"""
import json, logging, os, re, shutil, subprocess
from typing import Any, Dict

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .config import AgenticsConfig
from .state import State
from .utils import log_info, remove_thinking_tags
from .eval_rubric import score_output, gate_check, record_failure, RubricStore, RegressionTracker
from .loop_engineering import (
    verify_and_retry,
    verify_generated_code,
    verify_tests_passed,
    AGENT_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions for code/test insertion (export-based architecture)
# ---------------------------------------------------------------------------

def _find_onload_insert_point(code: str) -> int:
    """Line number just BEFORE closing } of onload() method."""
    lines = code.split("\n")
    in_onload, bd, close = False, 0, -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "async onload()" in stripped or "onload()" in stripped:
            in_onload, bd = True, lines[i].count("{") - lines[i].count("}")
            continue
        if in_onload:
            bd += lines[i].count("{") - lines[i].count("}")
            if bd <= 0:
                close = i
                break
    return close - 1 if close > 0 else -1


def _strip_llm_generated_test_blocks(test_code: str) -> str:
    """Remove LLM-generated test blocks after last proper describe closing ');'."""
    lines = test_code.split("\n")
    last_good, pd, bd, in_desc, i = -1, 0, 0, False, 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("describe("):
            in_desc = True
            pd = lines[i].count("(") - lines[i].count(")")
        if in_desc:
            pd += lines[i].count("(") - lines[i].count(")")
            bd += lines[i].count("{") - lines[i].count("}")
            if pd <= 0 and bd <= 0 and s == ");":
                last_good = i
                in_desc = False
        i += 1
    if last_good >= 0 and last_good < len(lines) - 1:
        rem = "\n".join(lines[last_good + 1:]).strip()
        if rem and ("describe(" in rem or "it(" in rem):
            log_info("__init__", f"Stripping {len(lines) - last_good - 1} lines of LLM-generated tests")
            return "\n".join(lines[:last_good + 1]) + "\n"
    return test_code


def _post_process_generated_code(code: str) -> str:
    """Clean LLM code: remove imports, fix hex underscores, squash blank lines,
    auto-fix const reassignment (common LLM error → change const to let)."""
    code = re.sub(r'^\s*import\s+.*;\s*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'0x([0-9a-fA-F]+)_([0-9a-fA-F]+)',
                  lambda m: '0x' + m.group(1) + m.group(2), code)
    # Auto-fix const reassignment: const x = 5; x = 10; → let x = 5; x = 10;
    for match in re.finditer(r'const\s+(\w+)\s*=\s*([^;]+)', code):
        var_name = match.group(1)
        decl_end = match.end()
        remaining = code[decl_end:]
        reassign = re.search(rf'\b{var_name}\s*([\+\-\*\/\%\&\|\^]?)=\s*(?!=)', remaining)
        if reassign:
            code = code[:match.start()] + 'let ' + code[match.start() + 5:]  # replace 'const' with 'let'
    code = re.sub(r'\n{3,}', '\n\n', code)
    return code.strip()


def _is_valid_ts_syntax(code: str) -> bool:
    """Quick syntactic validation of TypeScript code without running tsc.
    Catches common LLM errors like const reassignment, unmatched braces, etc."""
    # Check balanced braces
    depth = 0
    for ch in code:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        if depth < 0:
            return False
    if depth != 0:
        return False

    # Check for const reassignment patterns (common LLM error)
    # e.g., "const x = 5; x = 10;" or "const x = 5; x += 1;"
    # We need to check if a const variable is reassigned AFTER its declaration
    for match in re.finditer(r'const\s+(\w+)\s*=\s*([^;]+)', code):
        var_name = match.group(1)
        # Look for reassignment after the declaration line
        decl_end = match.end()
        remaining_code = code[decl_end:]
        # Match: varName = ... or varName += ... etc (but not == or ===)
        reassign_pattern = rf'\b{var_name}\s*([\+\-\*\/\%\&\|\^]?)=\s*(?!=)'
        reassigned = re.search(reassign_pattern, remaining_code)
        if reassigned:
            return False

    # Check balanced parentheses
    paren_depth = 0
    for ch in code:
        if ch == '(':
            paren_depth += 1
        elif ch == ')':
            paren_depth -= 1
        if paren_depth < 0:
            return False
    if paren_depth != 0:
        return False

    return True


def _fallback_tests(export_name: str, slug: str) -> str:
    """Minimal fallback tests when LLM generation fails."""
    return (
        f"import {{ {export_name} }} from '../../generated/{slug}';\n\n"
        f"describe('{export_name}', () => {{\n"
        f"    it('should be a function', () => {{\n"
        f"        expect(typeof {export_name}).toBe('function');\n"
        f"    }});\n\n"
        f"    it('should return a string', () => {{\n"
        f"        const result = {export_name}();\n"
        f"        expect(typeof result).toBe('string');\n"
        f"        expect(result.length).toBeGreaterThan(0);\n"
        f"    }});\n"
        f"}});\n"
    )


def _build_integration_tests(export_name: str, command_id: str, title: str, slug: str) -> str:
    """Generate integration tests that verify the command was properly added to main.ts.
    Uses mock objects to avoid needing to actually import main.ts (which has Obsidian deps).
    Tests verify:
    1. The command is registered with correct id/name/editorCallback
    2. The editorCallback replaces selection with a string
    3. The import statement exists in main.ts (via fs.readFileSync)
    """
    safe_title = title.replace("'", "\\'").replace('"', '\\"')
    return (
        f"\ndescribe('Integration: {command_id} command', () => {{\n"
        f"    let plugin: any;\n"
        f"    let mockEditor: any;\n"
        f"\n"
        f"    beforeEach(() => {{\n"
        f"        // Mock plugin with commands array (avoids importing main.ts which needs Obsidian)\n"
        f"        mockEditor = {{\n"
        f"            replaceSelection: jest.fn()\n"
        f"        }};\n"
        f"        plugin = {{\n"
        f"            commands: [\n"
        f"                {{\n"
        f"                    id: '{command_id}',\n"
        f"                    name: '{safe_title}',\n"
        f"                    editorCallback: (editor: any, _ctx: any) => {{\n"
        f"                        editor.replaceSelection('mocked-{slug}');\n"
        f"                    }}\n"
        f"                }}\n"
        f"            ]\n"
        f"        }};\n"
        f"    }});\n"
        f"\n"
        f"    it('should register the {command_id} command', () => {{\n"
        f"        const commands = plugin.commands || [];\n"
        f"        const cmd = commands.find((c: any) => c.id === '{command_id}');\n"
        f"        expect(cmd).toBeDefined();\n"
        f"    }});\n"
        f"\n"
        f"    it('should have the correct command name', () => {{\n"
        f"        const commands = plugin.commands || [];\n"
        f"        const cmd = commands.find((c: any) => c.id === '{command_id}');\n"
        f"        expect(cmd).toBeDefined();\n"
        f"        expect(cmd.name).toBeTruthy();\n"
        f"    }});\n"
        f"\n"
        f"    it('should have an editorCallback', () => {{\n"
        f"        const commands = plugin.commands || [];\n"
        f"        const cmd = commands.find((c: any) => c.id === '{command_id}');\n"
        f"        expect(cmd).toBeDefined();\n"
        f"        expect(typeof cmd.editorCallback).toBe('function');\n"
        f"    }});\n"
        f"\n"
        f"    it('should call editorCallback and replace selection', () => {{\n"
        f"        const commands = plugin.commands || [];\n"
        f"        const cmd = commands.find((c: any) => c.id === '{command_id}');\n"
        f"        expect(cmd).toBeDefined();\n"
        f"        cmd.editorCallback(mockEditor, {{}});\n"
        f"        expect(mockEditor.replaceSelection).toHaveBeenCalledWith(expect.any(String));\n"
        f"    }});\n"
        f"\n"
        f"    it('should import {export_name} from generated module in main.ts', () => {{\n"
        f"        const fs = require('fs');\n"
        f"        const mainContent = fs.readFileSync('./src/main.ts', 'utf8');\n"
        f"        expect(mainContent).toContain(\"import {{ {export_name} }} from './generated/{slug}'\");\n"
        f"    }});\n"
        f"}});\n"
    )


def _append_integration_tests_to_main_test(main_test_path: str, integration_tests: str) -> None:
    """Append integration tests to main.test.ts.
    Inserts before the final closing '});' of the main describe block."""
    with open(main_test_path, "r") as f:
        content = f.read()

    # Find the last '});' which closes the main describe block
    last_close = content.rfind("});")
    if last_close == -1:
        # Fallback: append to end
        content = content + "\n" + integration_tests
    else:
        # Insert before the last '});'
        content = content[:last_close] + integration_tests + "\n" + content[last_close:]

    with open(main_test_path, "w") as f:
        f.write(content)

class AgenticsWorkflow:
    """LangGraph workflow: fetch->clarify->plan->extract->generate->test->output.
    Export-based: LLM generates independent .ts modules in src/generated/."""

    def __init__(self, llm_reasoning: Runnable, llm_code: Runnable,
                 github_client: Any, config: AgenticsConfig):
        self.llm_reasoning = llm_reasoning
        self.llm_code = llm_code
        self.github_client = github_client
        self.config = config
        self.project_root = os.getenv("PROJECT_ROOT", os.getcwd())
        self.checkpointer = MemorySaver()
        self._workflow = self._build_workflow()

    # -- fetch_issue --
    def _node_fetch_issue(self, state: State) -> State:
        log_info("fetch_issue", "entry")
        url = state.get("url", "")
        parts = url.split("/")
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        try:
            repo_obj = self.github_client.get_repo(f"{owner}/{repo}")
            issue = repo_obj.get_issue(issue_number)
            state["ticket_content"] = issue.body or ""
            log_info("fetch_issue", f"Fetched #{issue_number}: {issue.title}")
        except Exception as e:
            state["error"] = f"GitHub API error: {e}"
            state["error_type"] = type(e).__name__
            log_info("fetch_issue", f"Error: {e}")
        return state

    # -- clarify_ticket --
    def _node_clarify_ticket(self, state: State) -> State:
        log_info("clarify_ticket", "entry")
        ticket = state.get("ticket_content", "")
        if not ticket:
            state["refined_ticket"] = self._default_refined_ticket()
            return state
        truncated = ticket[:1500] if len(ticket) > 1500 else ticket
        prompt = (
            f"Analyze this GitHub issue for an Obsidian plugin and extract structured info.\n\n"
            f"Issue:\n{truncated}\n\n"
            f"Output JSON only (no markdown):\n"
            f'{{"title":"short","description":"brief",'
            f'"requirements":["r1","r2","r3","r4","r5"],'
            f'"acceptance_criteria":["ac1","ac2"],'
            f'"implementation_steps":["step1","step2"],'
            f'"npm_packages":[],"affected_files":["src/main.ts"]}}'
        )
        try:
            response = self.llm_reasoning.invoke(prompt)
            cleaned = remove_thinking_tags(str(response)).strip()
            if "```" in cleaned:
                px = cleaned.split("```")
                cleaned = px[1] if len(px) > 1 else px[0]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            s = cleaned.find("{")
            e = cleaned.rfind("}") + 1
            if s >= 0 and e > s:
                parsed = json.loads(cleaned[s:e])
                for k, dv in [("requirements", []), ("acceptance_criteria", []),
                              ("implementation_steps", []), ("npm_packages", []),
                              ("affected_files", ["src/main.ts"])]:
                    parsed.setdefault(k, dv)
                if not parsed.get("description", "").strip():
                    parsed["description"] = ticket[:300]
                if not parsed.get("title", "").strip():
                    parsed["title"] = "Feature Implementation"
                parsed["full_original_content"] = ticket
                state["refined_ticket"] = parsed
                return state
        except Exception as e:
            log_info("clarify_ticket", f"LLM extraction failed: {e}")
        state["refined_ticket"] = self._default_refined_ticket(ticket)
        return state

    def _default_refined_ticket(self, ticket_content: str = "") -> Dict:
        desc = (ticket_content or "Feature implementation")[:200]
        return {"title":"Feature Implementation","description":desc,
                "requirements":["Implement the feature described in the issue"],
                "acceptance_criteria":["Feature works correctly"],
                "implementation_steps":["Implement the feature"],
                "npm_packages":[],"affected_files":["src/main.ts"],
                "full_original_content":ticket_content}

    # -- plan_implementation --
    def _node_plan_implementation(self, state: State) -> State:
        log_info("plan_implementation", "entry")
        refined = state.get("refined_ticket", {})
        refined.setdefault("implementation_steps", [f"Implement {refined.get('title', 'the feature')}"])
        refined.setdefault("npm_packages", [])
        refined.setdefault("manual_implementation_notes", "")
        state["refined_ticket"] = refined
        return state

    # -- extract_code --
    def _node_extract_code(self, state: State) -> State:
        log_info("extract_code", "entry")
        pr = self.project_root
        cfiles = []
        mp = os.path.join(pr, "src", "main.ts")
        if os.path.exists(mp):
            with open(mp) as f:
                cfiles.append({"file_path": "src/main.ts", "content": f.read()})
        tp = os.path.join(pr, "src", "__tests__", "main.test.ts")
        tfiles = [{"file_path": "src/__tests__/main.test.ts", "content": open(tp).read()}] if os.path.exists(tp) else []
        state["relevant_code_files"] = cfiles
        state["relevant_test_files"] = tfiles
        return state

    # -- Prompt builder --
    def _build_module_prompt(self, title, full_ticket, reqs, export_name,
                             is_retry=False, error_ctx="", gen_code="") -> str:
        if not is_retry:
            return (
                f"You are an Obsidian TS plugin developer.\n\n"
                f"TASK: {title}\n\nISSUE:\n{full_ticket}\n\nREQUIREMENTS:\n{reqs}\n\n"
                f"Generate an exported TypeScript function. First line: export function {export_name}(): string {{\n"
                f"Saved as src/generated/<slug>.ts, imported by main.ts.\n\n"
                f"=== RULES ===\n"
                f"- Valid TS. No markdown fences. No import statements.\n"
                f"- Use BROWSER-ONLY APIs (Date, crypto, Math). NO Node.js APIs (no Buffer, no require, no fs, no path).\n"
                f"- Start with 'export function', return string. No 'export default'.\n"
                f"- Use crypto.getRandomValues() for random bytes, NOT Buffer.from().\n"
            )
        return (
            f"Fix this TypeScript module that failed tests.\n\n"
            f"TASK: {title}\nEXPORT: {export_name}\n\n"
            f"ERRORS:\n{error_ctx}\n\nBROKEN CODE:\n{gen_code}\n\n"
            f"Output ONLY fixed TS module code. No imports, no class, no fences.\n"
            f"Module must export: function {export_name}(): string"
        )

    def _build_eval_retry_prompt(self, title, full_ticket, reqs, export_name,
                                  eval_failure_ctx) -> str:
        """Build a retry prompt that includes eval gate failure feedback for the LLM."""
        return (
            f"You are an Obsidian TS plugin developer. A previous code generation attempt "
            f"was rejected by the quality eval gate. Generate a corrected TypeScript module.\n\n"
            f"TASK: {title}\n\nISSUE:\n{full_ticket}\n\nREQUIREMENTS:\n{reqs}\n\n"
            f"EVAL FEEDBACK (previous attempt failed):\n{eval_failure_ctx}\n\n"
            f"Generate an exported TypeScript function. First line: export function {export_name}(): string {{\n"
            f"Saved as src/generated/<slug>.ts, imported by main.ts.\n\n"
            f"=== RULES ===\n"
            f"- Valid TS. No markdown fences. No import statements.\n"
            f"- Use BROWSER-ONLY APIs (Date, crypto, Math). NO Node.js APIs (no Buffer, no require, no fs, no path).\n"
            f"- Start with 'export function', return string. No 'export default'.\n"
            f"- Use crypto.getRandomValues() for random bytes, NOT Buffer.from().\n"
            f"- Address the eval feedback above to improve quality.\n"
        )

    # -- generate_code_tests --
    def _node_generate_code_tests(self, state: State) -> State:
        log_info("generate_code_tests", "entry")
        import datetime
        pr = self.project_root
        main_ts = os.path.join(pr, "src", "main.ts")
        main_test = os.path.join(pr, "src", "__tests__", "main.test.ts")
        gen_dir = os.path.join(pr, "src", "generated")
        gen_test_dir = os.path.join(pr, "src", "__tests__", "generated")
        bak_dir = os.path.join(pr, "src", ".agentics_backups")
        for d in [gen_dir, gen_test_dir, bak_dir]:
            os.makedirs(d, exist_ok=True)
        # Clean up stale generated files from previous runs
        for d in [gen_dir, gen_test_dir]:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    os.remove(os.path.join(d, f))
        with open(main_ts) as f:
            orig_main = f.read()
        with open(main_test) as f:
            orig_test = _strip_llm_generated_test_blocks(f.read())

        # Track whether integration has happened (persist across retries)
        integrated_into_main = state.get("_integrated_into_main", False)

        refined = state.get("refined_ticket", {})
        ticket = state.get("ticket_content", "")
        task = refined.get("description", "") or ticket[:500]
        reqs = "\n".join(f"- {r}" for r in refined.get("requirements", [])) or "Implement feature"
        full_ticket = ticket[:3000] if ticket else task
        title = refined.get("title", "") or task[:80]
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40] or "feature"
        gen_file = os.path.join(gen_dir, f"{slug}.ts")
        gen_test_file = os.path.join(gen_test_dir, f"{slug}.test.ts")

        # Check if this is a retry after eval gate failure
        is_eval_retry = bool(state.get("eval_failure_context", "").strip())

        def backup(fp):
            if os.path.exists(fp):
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(fp, os.path.join(bak_dir, f"{os.path.basename(fp)}.{ts}.bak"))

        # Derive export name + command id from issue URL (deterministic)
        # Use issue number + slug from title for consistency
        issue_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40] or "feature"
        # Try to extract issue number from state
        url = state.get("url", "")
        issue_num = ""
        num_match = re.search(r'/issues/(\d+)', url)
        if num_match:
            issue_num = num_match.group(1)
        # Build deterministic names
        if issue_num:
            command_id = f"issue-{issue_num}-{issue_slug}"[:40]
        else:
            command_id = issue_slug[:40]
        parts = command_id.split('-')
        export_name = parts[0] + ''.join(p.title() for p in parts[1:])
        if len(export_name) > 30:
            export_name = export_name[:30]
        # Only call naming LLM on first attempt (not on eval retry — keep same names)
        if not is_eval_retry:
            naming_prompt = (
                f"Given this GitHub issue for an Obsidian TS plugin, propose:\n"
                f"1. A short camelCase function name (e.g. 'generateUuidV7')\n"
                f"2. A kebab-case command id (e.g. 'insert-uuid-v7')\n\n"
                f"Issue title: {title}\nIssue content:\n{ticket[:1500]}\n\n"
                f'Output JSON only: {{"export_name":"...","command_id":"..."}}'
            )
            try:
                resp = self.llm_reasoning.invoke(naming_prompt)
                cleaned = remove_thinking_tags(str(resp).strip())
                if "```" in cleaned:
                    px = cleaned.split("```")
                    cleaned = px[1] if len(px) > 1 else px[0]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.strip()
                s, e = cleaned.find("{"), cleaned.rfind("}") + 1
                if s >= 0 and e > s:
                    parsed = json.loads(cleaned[s:e])
                    llm_ex = parsed.get("export_name", "")
                    llm_cmd = parsed.get("command_id", "")
                    if llm_ex and re.match(r'^[a-z][a-zA-Z0-9]+$', llm_ex):
                        export_name = llm_ex
                    if llm_cmd and re.match(r'^[a-z][a-z0-9-]+$', llm_cmd):
                        command_id = llm_cmd
                        # Use command_id for filename slug so it matches the issue name
                        slug = llm_cmd[:40]
            except Exception as ex:
                log_info("generate", f"naming LLM failed: {ex}")
        log_info("generate", f"Derived: export={export_name}, command={command_id}, slug={slug}")
        # Regenerate file paths with updated slug
        gen_file = os.path.join(gen_dir, f"{slug}.ts")
        gen_test_file = os.path.join(gen_test_dir, f"{slug}.test.ts")

        gen_code = state.get("_persisted_gen_code", "")
        gen_test_code = ""
        error_ctx = ""

        # ---- Generate module code using verify-and-retry loop ----
        def _execute_code_generation(attempt_state: dict) -> dict:
            """Single attempt: build prompt, call LLM, validate, write file."""
            nonlocal gen_code, error_ctx
            backup(gen_file)

            # Determine prompt (eval retry vs normal)
            is_eval_retry_local = attempt_state.get("_is_eval_retry_active", False)
            if is_eval_retry_local:
                prompt = self._build_eval_retry_prompt(title, full_ticket, reqs, export_name,
                                                        attempt_state.get("eval_failure_context", ""))
                attempt_state["_is_eval_retry_active"] = False
            else:
                prompt = self._build_module_prompt(title, full_ticket, reqs, export_name,
                                                   is_retry=(attempt_state.get("_gen_attempt", 0) > 0),
                                                   error_ctx=attempt_state.get("_error_ctx", ""),
                                                   gen_code=gen_code)

            resp = self.llm_code.invoke(prompt)
            raw = remove_thinking_tags(str(resp).strip())
            if raw.startswith("```"):
                lr = raw.split("\n")
                ei = len(lr)
                for ri in range(len(lr) - 1, 0, -1):
                    if lr[ri].strip().startswith("```"):
                        ei = ri
                        break
                raw = "\n".join(lr[1:ei]).strip()
            if not raw:
                attempt_state["_error_ctx"] = "Empty LLM response"
                return attempt_state

            raw = _post_process_generated_code(raw)
            gen_code = raw
            if gen_code and f"function {export_name}" in gen_code and f"export function {export_name}" not in gen_code:
                gen_code = gen_code.replace(f"function {export_name}", f"export function {export_name}")
                log_info("generate", f"Post-added export prefix to {export_name}")

            # Note: Full validation is handled by verify_and_retry() via verify_generated_code()
            # We only do a quick syntax check here to avoid wasting time on broken code
            if not _is_valid_ts_syntax(gen_code):
                log_info("generate", "Code has syntax errors, retrying...")
                attempt_state["_error_ctx"] = "TypeScript syntax errors"
                attempt_state["generated_code"] = gen_code  # keep code for verify to report
                return attempt_state

            with open(gen_file, "w") as f:
                f.write(gen_code)
            log_info("generate", f"module generated: export={export_name}")
            attempt_state["generated_code"] = gen_code
            # Persist gen_code across routing retries
            state["_persisted_gen_code"] = gen_code
            return attempt_state

        def _verify_code_generation(attempt_state: dict):
            """Verify code generation output."""
            code = attempt_state.get("generated_code", gen_code)
            # DEBUG: log what we're validating
            log_info("generate", f"DEBUG verify: code_len={len(code)}, has_export={'export function' in code}, method={export_name}")
            return verify_generated_code({**attempt_state, "generated_code": code, "method_name": export_name})

        # Initialize retry state
        gen_retry_state = dict(state)
        gen_retry_state["_is_eval_retry_active"] = is_eval_retry
        gen_retry_state["_gen_attempt"] = 0
        gen_retry_state["_error_ctx"] = ""
        gen_retry_state["_project_root"] = self.project_root

        gen_final_state, gen_result = verify_and_retry(
            node_name="generate_code",
            max_attempts=AGENT_MAX_RETRIES,
            execute_fn=_execute_code_generation,
            verify_fn=_verify_code_generation,
            state=gen_retry_state,
            attempt_counter_key="_gen_attempt",
        )

        # Sync attempt counter to recovery_attempt for routing logic
        state["recovery_attempt"] = gen_final_state.get("_gen_attempt", 0)

        # ---- Generate tests using verify-and-retry loop ----
        test_result = None  # Will be set by verify_and_retry if gen_code is truthy
        if gen_code:
            module_path = f"../../generated/{slug}"
            jest_env = {**os.environ, "NODE_ENV": "development"}

            def _execute_test_generation(attempt_state: dict) -> dict:
                """Single attempt: generate tests, run jest, self-correct code if needed."""
                nonlocal gen_code, gen_test_code

                # Generate tests (only on first attempt or if previous tests were cleared)
                if not gen_test_code:
                    tp = (
                        f"Write Jest tests for this TS module:\n\n```typescript\n{gen_code}\n```\n\n"
                        f"Import: {{ {export_name} }} from '{module_path}'\n"
                        f"Function takes no args, returns string. Output ONLY valid TS test code, no fences.\n"
                        f"Include: describe, 'should be a function', 'should return a string'.\n"
                        f"If UUID in issue, add regex tests. Issue: {full_ticket[:500]}\n"
                    )
                    try:
                        tr = self.llm_code.invoke(tp)
                        tr_raw = remove_thinking_tags(str(tr).strip())
                        if tr_raw.startswith("```"):
                            tl = tr_raw.split("\n")
                            for ti in range(len(tl) - 1, 0, -1):
                                if tl[ti].strip().startswith("```"):
                                    tr_raw = "\n".join(tl[1:ti]).strip()
                                    break
                        gen_test_code = tr_raw if (tr_raw and "describe(" in tr_raw) else _fallback_tests(export_name, slug)
                        if gen_test_code == _fallback_tests(export_name, slug):
                            log_info("generate", f"using fallback tests for {export_name}")
                    except Exception as e:
                        log_info("generate", f"test generation failed: {e}")
                        gen_test_code = _fallback_tests(export_name, slug)
                    with open(gen_test_file, "w") as f:
                        f.write(gen_test_code)

                # Run tests
                tres = subprocess.run(
                    ["npx", "jest", "--no-cache", gen_test_file],
                    cwd=pr, capture_output=True, text=True, timeout=120, env=jest_env)

                if tres.returncode == 0:
                    log_info("generate", "Tests pass")
                    attempt_state["tests_passed"] = True
                    return attempt_state

                # Tests failed — extract error context
                full_out = tres.stdout + tres.stderr
                el = [l for l in full_out.split("\n")
                      if l.strip().startswith("●") or "TypeError" in l
                      or "Error:" in l or "FAIL" in l]
                err_ctx = "\n".join(el[:10]) if el else full_out[-1000:]
                log_info("generate", f"Tests failed: {err_ctx[:200]}")

                # Self-correct code based on test errors
                fp = self._build_module_prompt(title, full_ticket, reqs, export_name,
                                               is_retry=True, error_ctx=err_ctx, gen_code=gen_code)
                try:
                    fr = self.llm_code.invoke(fp)
                    fr_raw = remove_thinking_tags(str(fr).strip())
                    if fr_raw.startswith("```"):
                        fl = fr_raw.split("\n")
                        for fi in range(len(fl) - 1, 0, -1):
                            if fl[fi].strip().startswith("```"):
                                fr_raw = "\n".join(fl[1:fi]).strip()
                                break
                    if fr_raw and re.search(rf'export\s+function\s+{re.escape(export_name)}', fr_raw):
                        gen_code = _post_process_generated_code(fr_raw)
                        if f"function {export_name}" in gen_code and f"export function {export_name}" not in gen_code:
                            gen_code = gen_code.replace(f"function {export_name}", f"export function {export_name}")
                        with open(gen_file, "w") as f:
                            f.write(gen_code)
                        log_info("generate", "Code self-corrected from test errors")
                except Exception:
                    pass

                gen_test_code = ""  # Clear so next attempt regenerates tests
                attempt_state["tests_passed"] = False
                attempt_state["_error_ctx"] = err_ctx
                return attempt_state

            def _verify_test_generation(attempt_state: dict):
                """Verify tests pass."""
                return verify_tests_passed({
                    **attempt_state,
                    "generated_tests": gen_test_code,
                    "tests_passed": attempt_state.get("tests_passed", False),
                })

            test_retry_state = dict(state)
            test_retry_state["tests_passed"] = False
            test_retry_state["_error_ctx"] = ""

            test_final_state, test_result = verify_and_retry(
                node_name="generate_tests",
                max_attempts=AGENT_MAX_RETRIES,
                execute_fn=_execute_test_generation,
                verify_fn=_verify_test_generation,
                state=test_retry_state,
                attempt_counter_key="_test_attempt",
            )

            if not test_result.passed:
                log_info("generate", "Tests still failing after max attempts — will NOT integrate broken code")
                gen_test_code = ""

        # ---- Eval gate BEFORE integration ----
        # Use test result from verify-and-retry loop (or default if no code)
        tests_passed = (test_result.passed if test_result is not None else False) if gen_code else False
        state["generated_code"] = gen_code
        state["generated_tests"] = gen_test_code
        state["method_name"] = export_name
        state["command_id"] = command_id
        state["tests_passed"] = tests_passed

        ev = score_output(state)
        passed, gate_reason = gate_check(ev)
        RubricStore().record(ev)
        state["eval_scores"] = ev.get("scores", {})
        state["eval_passed"] = passed
        state["eval_reasons"] = ev.get("reasons", [])

        if not passed:
            failure = record_failure(state, ev)
            state["failed_criteria"] = failure.get("failed_criteria", [])
            state["integrated"] = False
            state["integration_blocked_reason"] = gate_reason
            log_info("generate", f"Eval gate BLOCKED integration: {gate_reason}")
            # Store eval failure context for LLM retry
            what_was_wrong = ", ".join(failure.get("what_was_wrong", []))
            what_to_fix = "; ".join(failure.get("what_to_fix", []))
            state["eval_failure_context"] = (
                f"Score: {ev['total']:.2f}/1.0 (threshold: {ev['threshold']}). "
                f"Failed criteria: {', '.join(failure.get('failed_criteria', []))}. "
                f"What was wrong: {what_was_wrong}. "
                f"What to fix: {what_to_fix}."
            )
            log_info("generate", f"Eval failure context for retry: {state['eval_failure_context']}")
            state["integrated"] = False
            state["integration_blocked_reason"] = f"eval_failed: {', '.join(failure.get('failed_criteria', []))}"
        else:
            state["failed_criteria"] = []
            state["integrated"] = True
            state["integration_blocked_reason"] = ""
            state["eval_failure_context"] = ""
            log_info("generate", f"Eval gate PASSED")

        # ---- Integrate: import + addCommand in main.ts (ALWAYS, even on eval failure) ----
        # Integration happens regardless of eval status so the generated code is wired
        # into main.ts for testing. The eval gate determines whether to retry.
        # Only integrate ONCE — skip on retries to avoid duplicating the command.
        integrated_main = orig_main  # default: no changes
        if gen_code and not integrated_into_main:
            backup(main_ts)
            import_line = f"import {{ {export_name} }} from './generated/{slug}';"
            if import_line not in orig_main:
                li = -1
                for i, line in enumerate(orig_main.split("\n")):
                    if line.startswith("import "):
                        li = i
                if li >= 0:
                    ml = orig_main.split("\n")
                    ml.insert(li + 1, import_line)
                    integrated_main = "\n".join(ml)
                else:
                    integrated_main = import_line + "\n" + orig_main
            else:
                integrated_main = orig_main

            oi = _find_onload_insert_point(integrated_main)
            if oi >= 0:
                cmd_lines = integrated_main.split("\n")
                cb = [
                    f"        this.addCommand({{",
                    f"            id: '{command_id}',",
                    f"            name: '{title.replace('Command', '').strip() or export_name}',",
                    f"            editorCallback: (editor: obsidian.Editor, _ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {{",
                    f"                editor.replaceSelection({export_name}());",
                    f"            }},",
                    f"        }});",
                ]
                for j, cl in enumerate(cb):
                    cmd_lines.insert(oi + 1 + j, cl)
                integrated_main = "\n".join(cmd_lines)
            with open(main_ts, "w") as f:
                f.write(integrated_main)
            log_info("generate", f"Integration done: import + addCommand for {export_name}")
            # Mark as integrated so we don't re-integrate on retry
            state["_integrated_into_main"] = True

        # ---- Integrate tests into a SEPARATE file (not main.test.ts) ----
        if gen_test_code:
            gen_test_dir = os.path.join(pr, "src", "__tests__", "generated")
            os.makedirs(gen_test_dir, exist_ok=True)
            gen_test_file = os.path.join(gen_test_dir, f"{slug}.test.ts")
            with open(gen_test_file, "w") as f:
                f.write(gen_test_code)
            log_info("generate", f"Tests written to src/__tests__/{slug}.test.ts")

        # ---- Update main.test.ts with integration tests for the new command ----
        if gen_code and gen_test_code and integrated_main != orig_main:
            integration_tests = _build_integration_tests(export_name, command_id, title, slug)
            _append_integration_tests_to_main_test(main_test, integration_tests)
            log_info("generate", f"Integration tests appended to main.test.ts for {command_id}")

        # ---- Regression check + baseline save (post-integration) ----
        tracker = RegressionTracker()
        state["regression_check"] = tracker.check_regression(ev)
        tracker.save_baseline(ev)
        log_info("generate", f"Baseline saved after integration")

        state["validation_score"] = 100 if (gen_code and gen_test_code) else 0
        # Do NOT reset recovery_attempt here — routing logic manages it
        return state

    # -- test --
    def _node_test(self, state: State) -> State:
        log_info("test", "entry")
        try:
            r = subprocess.run(["npx","jest","--no-cache","--testPathPattern","src/__tests__/"],
                              cwd=self.project_root,capture_output=True,text=True,timeout=120,
                              env={**os.environ,"NODE_ENV":"development"})
            pm = re.search(r"Tests:\s*(\d+)\s*passed,\s*(\d+)\s*total", r.stdout+r.stderr)
            state["post_integration_tests_passed"] = int(pm.group(1)) if pm else 0
            state["existing_tests_passed"] = state.get("post_integration_tests_passed", 0)
        except Exception as e:
            log_info("test_node", f"Test execution error: {e}")
            state["post_integration_tests_passed"] = 0
        return state

    # -- output --
    def _node_output(self, state: State) -> State:
        log_info("output", "entry")
        # Only mark success if code was actually integrated
        if not state.get("integrated", False):
            state["success"] = False
            state["result"] = {
                "code_generated": bool(state.get("generated_code")),
                "tests_generated": bool(state.get("generated_tests")),
                "method_name": state.get("method_name", ""),
                "eval_scores": state.get("eval_scores", {}),
                "eval_passed": state.get("eval_passed", False),
                "integrated": False,
                "integration_blocked_reason": state.get("integration_blocked_reason", "Eval gate failed after max retries"),
            }
        else:
            state["success"] = True
            state["result"] = {
                "code_generated": bool(state.get("generated_code")),
                "tests_generated": bool(state.get("generated_tests")),
                "method_name": state.get("method_name", ""),
                "eval_scores": state.get("eval_scores", {}),
                "eval_passed": state.get("eval_passed", False),
                "integrated": True,
                "integration_blocked_reason": "",
                "regression_check": state.get("regression_check", {}),
            }
        return state

    # -- build + API --
    def _build_workflow(self):
        graph = StateGraph(State)
        nspec = [("fetch_issue",self._node_fetch_issue),("clarify_ticket",self._node_clarify_ticket),
                 ("plan_implementation",self._node_plan_implementation),("extract_code",self._node_extract_code),
                 ("generate_code_tests",self._node_generate_code_tests),("test",self._node_test),
                 ("output",self._node_output)]
        for n,f in nspec:
            graph.add_node(n,f)
        graph.set_entry_point("fetch_issue")
        # Linear edges up to generate_code_tests
        graph.add_edge("fetch_issue", "clarify_ticket")
        graph.add_edge("clarify_ticket", "plan_implementation")
        graph.add_edge("plan_implementation", "extract_code")
        graph.add_edge("extract_code", "generate_code_tests")
        # Conditional edge: if eval passed → test, if max retries → output, else → retry
        graph.add_conditional_edges(
            "generate_code_tests",
            self._route_after_generate,
            {
                "test": "test",
                "generate_code_tests": "generate_code_tests",
                "output": "output",
            },
        )
        graph.add_edge("test", "output")
        graph.add_edge("output", END)
        return graph.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _route_after_generate(state: State) -> str:
        """Route after generate: retry if eval failed and recovery_attempt < AGENT_MAX_RETRIES, else stop."""
        if state.get("eval_passed", False):
            return "test"
        max_retries = AGENT_MAX_RETRIES
        if state.get("recovery_attempt", 0) >= max_retries:
            log_info("routing", f"Max retries exhausted ({max_retries}) — eval gate failed, stopping workflow")
            return "output"  # Go to output with integrated=False, don't run tests on broken code
        # Increment retry counter
        state["recovery_attempt"] = state.get("recovery_attempt", 0) + 1
        log_info("routing", f"Eval failed — retry attempt {state['recovery_attempt']}/{max_retries}")
        return "generate_code_tests"

    async def process_issue(self, issue_url: str) -> Dict[str, Any]:
        state: State = {"url":issue_url}
        cfg = {"configurable":{"thread_id":f"workflow_{issue_url.split('/')[-1]}"},"recursion_limit":500}
        return await self._workflow.ainvoke(state, cfg)