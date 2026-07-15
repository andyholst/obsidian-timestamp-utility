import os
import logging
import re
import json
import subprocess
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import (
    read_file_tool,
    check_file_exists_tool,
    write_file_tool,
    npm_install_tool,
)
from .state import State
from .utils import safe_json_dumps, remove_thinking_tags, log_info
from .prompts import ModularPrompts


class CodeIntegratorAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        # B11 hardening: the LLM is NOT given write_file_tool. The deterministic harness
        # (self.update_file / self.create_file -> integrate_test_contract) is the SOLE writer
        # of generated TypeScript (src/main.ts, src/__tests__/main.test.ts). This guarantees
        # the OpenSpec spec contract (## Contract / ## Test Contract) is always injected and
        # no LLM-authored TS bypasses the merge floor. Python still uses write_file_tool
        # internally for non-generated config (package.json) at line ~77.
        super().__init__(
            llm_client,
            [read_file_tool, check_file_exists_tool],
            "CodeIntegrator",
        )
        # Configurable project root and file extensions
        project_root = os.getenv("PROJECT_ROOT", "/project")
        self.project_root = project_root
        self.code_ext = os.getenv("CODE_FILE_EXTENSION", ".ts")
        self.test_ext = os.getenv("TEST_FILE_EXTENSION", ".test.ts")
        self.llm = llm_client
        self.monitor.info(
            "agent_initialized",
            data={
                "project_root": self.project_root,
                "code_ext": self.code_ext,
                "test_ext": self.test_ext,
            },
        )

    def process(self, state: State) -> State:
        """
        Integrate generated code and tests into project files based on relevant code and test files.
        Updates existing files if present, otherwise creates new ones under src/ and src/__tests__/.
        """
        log_info(
            self.name,
            f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}",
        )
        log_info(self.name, "Starting code integration process")
        try:
            # Handle proposed JS dependencies first
            proposed_js_deps = state.get("proposed_js_deps", [])
            installed_deps = []
            if proposed_js_deps:
                log_info(
                    self.name,
                    f"Found {len(proposed_js_deps)} proposed JS deps: {proposed_js_deps}",
                )
                package_json_path = os.path.join(self.project_root, "package.json")
                if check_file_exists_tool(package_json_path):
                    package_json_str = read_file_tool(package_json_path)
                    try:
                        package_json = json.loads(package_json_str)
                        dependencies = package_json.setdefault("dependencies", {})
                        added_deps = []
                        for pkg in proposed_js_deps:
                            if pkg not in dependencies:
                                dependencies[pkg] = "*"
                                added_deps.append(pkg)
                                log_info(
                                    self.name,
                                    f"Added {pkg} to package.json dependencies",
                                )
                        if added_deps:
                            package_json["dependencies"] = dependencies
                            new_package_json_str = json.dumps(package_json, indent=2)
                            write_file_tool(package_json_path, new_package_json_str)
                            log_info(
                                self.name,
                                f"Updated package.json with new deps: {added_deps}",
                            )
                        # Install the proposed deps
                        for pkg in proposed_js_deps:
                            try:
                                npm_install_tool(
                                    package_name=pkg,
                                    is_dev=False,
                                    save_exact=True,
                                    cwd=self.project_root,
                                )
                                installed_deps.append(pkg)
                                log_info(self.name, f"Installed {pkg}")
                            except Exception as e:
                                log_info(
                                    self.name, f"Failed to install {pkg}: {str(e)}"
                                )
                    except json.JSONDecodeError as e:
                        log_info(self.name, f"Invalid package.json: {str(e)}")
                    except Exception as e:
                        log_info(self.name, f"Error handling deps: {str(e)}")
                else:
                    log_info(
                        self.name,
                        f"package.json not found at {package_json_path}, skipping deps install",
                    )
                state["installed_deps"] = installed_deps
                log_info(
                    self.name,
                    f"Dependency handling complete. Installed: {installed_deps}",
                )

            task_details = state["result"]
            relevant_code_files = state.get("relevant_code_files", [])
            relevant_test_files = state.get("relevant_test_files", [])

            # B11 hardening: this plugin's generated TS MUST land in the canonical files
            # (src/main.ts and src/__tests__/main.test.ts). Force them into the relevant
            # lists whenever they exist on disk, so the deterministic merge floor
            # (generate_updated_code_file / integrate_test_contract) ALWAYS processes them —
            # even if the LLM fails to flag them as relevant. This guarantees the OpenSpec
            # spec contract (## Contract / ## Test Contract) is always injected into the
            # real plugin files, never into a stray new file.
            canonical_code = os.path.join(self.project_root, "src", "main.ts")
            canonical_test = os.path.join(
                self.project_root, "src", "__tests__", "main.test.ts"
            )
            if check_file_exists_tool(canonical_code):
                if not any(
                    f["file_path"].endswith("src/main.ts") for f in relevant_code_files
                ):
                    relevant_code_files.append(
                        {
                            "file_path": os.path.relpath(
                                canonical_code, self.project_root
                            ),
                            "content": read_file_tool(canonical_code),
                        }
                    )
            if check_file_exists_tool(canonical_test):
                if not any(
                    f["file_path"].endswith("src/__tests__/main.test.ts")
                    for f in relevant_test_files
                ):
                    relevant_test_files.append(
                        {
                            "file_path": os.path.relpath(
                                canonical_test, self.project_root
                            ),
                            "content": read_file_tool(canonical_test),
                        }
                    )

            # If no generated code/tests, skip integration
            if not state.get("generated_code") or not state.get("generated_tests"):
                log_info(self.name, "No generated code/tests; skipping integration")
                return state
            log_info(
                self.name,
                f"Task details received: {json.dumps(task_details, indent=2)}",
            )
            log_info(
                self.name,
                f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}",
            )
            log_info(
                self.name,
                f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}",
            )

            # Extract code and tests (raw text)
            log_info(
                self.name, "Extracting code and test content from generated output"
            )
            code_content = self.extract_content(state["generated_code"])
            test_content = self.extract_content(state["generated_tests"])
            log_info(self.name, f"Extracted code content length: {len(code_content)}")
            log_info(self.name, f"Extracted code content: {code_content}")
            log_info(self.name, f"Extracted test content length: {len(test_content)}")
            log_info(self.name, f"Extracted test content: {test_content}")

            # Remove any lines containing "typescript" or "javascript"
            code_content = self.remove_unwanted_lines(code_content)
            test_content = self.remove_unwanted_lines(test_content)
            log_info(
                self.name,
                f"Code content length after removing unwanted lines: {len(code_content)}",
            )
            log_info(
                self.name, f"Code content after removing unwanted lines: {code_content}"
            )
            log_info(
                self.name,
                f"Test content length after removing unwanted lines: {len(test_content)}",
            )
            log_info(
                self.name, f"Test content after removing unwanted lines: {test_content}"
            )

            if not code_content or not test_content:
                self.monitor.error("content_empty", data={"type": "code_or_test"})
                raise ValueError("Code or test content is empty")

            if relevant_code_files or relevant_test_files:
                log_info(self.name, "Processing existing files for update")
                # Update existing code files
                for file_data in relevant_code_files:
                    rel_file_path = file_data["file_path"]
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data["content"]
                    log_info(self.name, f"Processing code file: {rel_file_path}")
                    log_info(
                        self.name, f"Existing content length: {len(existing_content)}"
                    )
                    log_info(self.name, f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_code_file(
                        existing_content, code_content,
                        self._expected_contract_for_change(os.getenv("CHANGE")),
                    )
                    log_info(
                        self.name,
                        f"Generated updated content length: {len(updated_content)}",
                    )
                    log_info(self.name, f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
                # Update existing test files
                for file_data in relevant_test_files:
                    rel_file_path = file_data["file_path"]
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data["content"]
                    log_info(self.name, f"Processing test file: {rel_file_path}")
                    log_info(
                        self.name, f"Existing content length: {len(existing_content)}"
                    )
                    log_info(self.name, f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_test_file(
                        existing_content, test_content
                    )
                    # B11/B10: apply the SPEC-DRIVEN test contract deterministically.
                    # The spec owns the regression tests; the LLM test output is only a
                    # fallback. This guarantees the generated main.test.ts asserts the
                    # exact spec contract (no hallucinated `unknownMethod`, no wrong name).
                    # `existing_content` is the TRUE baseline, so LLM-added describe blocks
                    # are discarded before the spec tests are injected.
                    updated_content = self.integrate_test_contract(
                        updated_content,
                        self._expected_contract_for_change(os.getenv("CHANGE")),
                        baseline_content=existing_content,
                    )
                    log_info(
                        self.name,
                        f"Generated updated content length: {len(updated_content)}",
                    )
                    log_info(self.name, f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
            else:
                log_info(self.name, "No relevant files found; creating new files")
                # B11 hardening: even the create-new path MUST write the canonical plugin
                # files (src/main.ts, src/__tests__/main.test.ts), never a stray derived
                # filename. This keeps the deterministic merge floor and spec-contract
                # injection applied to the real plugin entrypoint files.
                new_code_file = os.path.join(self.project_root, "src", "main.ts")
                new_test_file = os.path.join(
                    self.project_root, "src", "__tests__", "main.test.ts"
                )
                log_info(self.name, f"New code file path: {new_code_file}")
                log_info(self.name, f"New test file path: {new_test_file}")

                # B11/B10: the CODE file MUST also go through the deterministic contract
                # assembly (generate_updated_code_file -> _assemble_contract_features) so the
                # spec `## Contract` (command id/name/Modal/generator) is ALWAYS injected, even
                # when no existing file was flagged as relevant and we take the create-new path.
                # Use the existing on-disk file (or empty) as the baseline to merge into.
                existing_code = (
                    read_file_tool(new_code_file)
                    if check_file_exists_tool(new_code_file)
                    else ""
                )
                assembled_code = self.generate_updated_code_file(
                    existing_code,
                    code_content,
                    self._expected_contract_for_change(os.getenv("CHANGE")),
                )
                self.create_file(new_code_file, assembled_code)
                self.create_file(new_test_file, test_content)
                # B11/B10: even when the pipeline creates a NEW test file, apply the
                # SPEC-DRIVEN test contract deterministically so the generated tests assert
                # the exact spec (no LLM hallucination). There is no baseline to diff against
                # here, so baseline_content is omitted (all LLM describe blocks are kept, but
                # the spec contract is always injected).
                contract = self._expected_contract_for_change(os.getenv("CHANGE"))
                if contract:
                    test_content = self.integrate_test_contract(
                        test_content, contract
                    )
                    self.create_file(new_test_file, test_content)
                state["relevant_code_files"] = [
                    {
                        "file_path": os.path.relpath(new_code_file, self.project_root),
                        "content": code_content,
                    }
                ]
                state["relevant_test_files"] = [
                    {
                        "file_path": os.path.relpath(new_test_file, self.project_root),
                        "content": test_content,
                    }
                ]
                log_info(self.name, "Updated state with new file details")

            log_info(self.name, "Code integration process completed successfully")
            log_info(
                self.name,
                f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}",
            )
            return state

        except Exception as e:
            self.monitor.error("integration_error", data={"error": str(e)})
            raise

    @staticmethod
    def _expected_contract_for_change(change: str | None) -> dict | None:
        """Parse the OpenSpec-mandated command contract from the change's spec/tasks.

        Looks for lines like:  `id: 'insert-uuid-v7'`, `name: 'Insert UUID v7 ...'`,
        `class <X>Modal` in the change's `specs/<change>/spec.md` or `tasks.md`. Returns
        None when nothing is pinned, so generation stays free-form for unconstrained changes.
        This is how 'the OpenSpec spec always wins' is enforced on the generated command.
        """
        if not change:
            return None
        # Primary: PROJECT_ROOT (the worktree) openspec; fallback: git toplevel openspec
        # (the worktree may lag the main tree's uncommitted tasks.md edits).
        roots = []
        proj = os.getenv("PROJECT_ROOT", "/project")
        # Search active changes first, then archived changes (openspec archive moves the
        # dir to openspec/changes/archive/<name> once a change ships). Mirrors
        # openspec_loader.find_change_dir so contract tests stay valid after archiving
        # (otherwise they become dead tests pointing at a now-archived dir — B17).
        change_roots = [
            os.path.join(proj, "openspec", "changes"),
            os.path.join(proj, "openspec", "changes", "archive"),
        ]
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=proj, capture_output=True, text=True,
            )
            if top.returncode == 0 and top.stdout.strip():
                top_root = top.stdout.strip()
                change_roots.extend([
                    os.path.join(top_root, "openspec", "changes"),
                    os.path.join(top_root, "openspec", "changes", "archive"),
                ])
        except Exception:
            pass
        candidates = []
        for r in change_roots:
            candidates.append(os.path.join(r, change, "specs", change, "spec.md"))
            candidates.append(os.path.join(r, change, "tasks.md"))
        # Date-prefixed archived variants (openspec archive renames the dir
        # YYYY-MM-DD-<change>): <archive>/<date>-<change>/{specs/<change>/spec.md,tasks.md}
        import glob as _glob
        for r in change_roots:
            archive_root = os.path.join(r, "archive") if os.path.basename(r) != "archive" else r
            for dated in _glob.glob(os.path.join(archive_root, "*-" + change)):
                if os.path.isdir(dated):
                    candidates.append(os.path.join(dated, "specs", change, "spec.md"))
                    candidates.append(os.path.join(dated, "tasks.md"))
        text = ""
        for p in candidates:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    text += f.read() + "\n"
        if not text:
            return None
        contract: dict = {}
        # Exact contract lines in tasks.md look like:
        #   id: 'insert-uuid-v7'  /  name: 'Insert UUID v7 (timestamp-based)'
        #   and a Modal class named `UuidV7Modal` / `UuidV7Modal`.
        # command_id: the authoritative `id: '...'` of the contract command. Anchor to the
        # CONTRACT_COMMAND block (the spec-authored source of truth) so ANY command id is
        # captured — not just ones prefixed `insert-`. (Previously this hard-coded
        # `insert-[^']+`, which broke non-insert commands like `encode-base64-message` /
        # `decode-base64-message`, leaving command_id unset and crashing the assembly floor
        # with a KeyError -> 0-byte main.ts. The contract TS itself is the single source of
        # truth, so we read the id the spec actually pins.)
        cmd_block = re.search(
            r"// === CONTRACT_COMMAND ===.*?// === (?:END_CONTRACT|CONTRACT_)",
            text,
            re.DOTALL,
        )
        if cmd_block:
            m = re.search(r"id:\s*'([^']+)'", cmd_block.group(0))
            if m:
                contract["command_id"] = m.group(1)
        # Fallback: any `id: '...'` in the text (covers spec prose that pins the id).
        if "command_id" not in contract:
            m = re.search(r"id:\s*'([^']+)'", text)
            if m:
                contract["command_id"] = m.group(1)
        # Also accept spec-style backtick: command (id `encode-...`)
        if "command_id" not in contract:
            m = re.search(r"command \(id `([^`]+)`", text)
            if m:
                contract["command_id"] = m.group(1)
        # command_name: the `name: '...'` paired with the contract command. Generic across
        # features (uuid, greetings, ...) — the OpenSpec spec's exact name wins, not a
        # feature-specific keyword. Prefer a name inside the CONTRACT_COMMAND block; else any.
        m = None
        cmd_block = re.search(
            r"// === CONTRACT_COMMAND ===.*?// === (?:END_CONTRACT|CONTRACT_)",
            text,
            re.DOTALL,
        )
        if cmd_block:
            m = re.search(r"name:\s*'([^']+)'", cmd_block.group(0))
        if not m:
            m = re.search(r"name:\s*'([^']+)'", text)
        if m:
            contract["command_name"] = m.group(1)
        if "command_name" not in contract:
            m = re.search(r"name `([^`]+)`", text)
            if m:
                contract["command_name"] = m.group(1)
        # Modal class: `UuidV7Modal` or `class UuidV7Modal` / `XxxModal`.
        m = re.search(r"`([A-Z]\w*Modal)`", text)
        if m:
            contract["modal_class"] = m.group(1)
        if "modal_class" not in contract:
            m = re.search(r"class\s+(\w*Modal)\b", text)
            if m:
                contract["modal_class"] = m.group(1)
        # generator_kind: derived from SPEC TEXT (not a hardcoded command name), so the
        # deterministic assembly floor picks the right generator for whatever the spec
        # describes. e.g. any spec mentioning "UUID v7" -> uuidv7 generator.
        if re.search(r"uuid\s*v7", text, re.I):
            contract["generator_kind"] = "uuidv7"
        elif re.search(r"uuid", text, re.I):
            contract["generator_kind"] = "uuid"
        elif re.search(r"timestamp", text, re.I):
            contract["generator_kind"] = "timestamp"
        # The deterministic assembly floor reads the SPEC CONTRACT TS from THIS change file
        # (never hard-coded Python literals). Extract the fenced ```ts block under the
        # "## Contract" heading so the integrator injects the exact TS the spec authors.
        # Extract the SPEC CONTRACT TS directly from the unambiguous `=== CONTRACT_* ===`
        # markers (never from the fragile `## Contract` fence, which breaks when intro text
        # sits between the heading and the ```ts fence). This guarantees contract_ts contains
        # ALL markers (COMMAND / GENERATOR / MODAL) so the deterministic floor always injects.
        cblocks = re.findall(
            r"// === CONTRACT_(?:COMMAND|GENERATOR|MODAL) ===[^\n]*\n.*?(?=// === |$)",
            text,
            re.DOTALL,
        )
        if cblocks:
            contract["contract_ts"] = "\n".join(b.strip() for b in cblocks)
        # Also parse the SPEC-AUTHORED TEST CONTRACT into the same dict so the integrator
        # can inject regression tests without a second fragile file-read / CHANGE-env lookup.
        # This is what makes the test contract deterministic (B10/B11) and resilient.
        mt = re.search(r"(?m)^##\s+Test Contract\b.*?```ts\s*(.*?)```", text, re.DOTALL)
        if mt:
            contract["test_contract_ts"] = mt.group(1).strip()
        return contract or None

    def generate_updated_code_file(
        self, existing_content: str, new_code: str, expected_contract: dict | None = None
    ) -> str:
        """Integrate new code into the existing file MERGING (never replacing).

        Uses a deterministic, string-based merge so existing logic can never be
        dropped (omission guard). Falls back to the LLM merge only if the
        deterministic merge yields no change AND existing imports/classes are missing.

        `expected_contract` (optional) is the spec-mandated command contract, e.g.
        {"command_id": "insert-uuid-v7", "command_name": "Insert UUID v7 (timestamp-based)",
         "modal_class": "UuidV7Modal"}. When provided, the generated `new_code` is forced to
        honor it BEFORE merging (so the injected command uses the exact id/name/Modal class the
        OpenSpec spec mandates -- OpenSpec spec always wins over LLM naming).
        """
        try:
            merged_new = new_code
            if expected_contract:
                # When the OpenSpec spec mandates a contract, `_assemble_contract_features`
                # is the SOLE authoritative source of the command/Modal/generator (spec wins
                # over LLM under-delivery). We do NOT normalize the LLM block here -- that
                # would duplicate the authoritative injection. Strip happens inside assembly.
                merged = self._assemble_contract_features(existing_content, new_code, expected_contract)
            else:
                merged_new = self._normalize_to_contract(new_code, expected_contract) if expected_contract else new_code
                merged = self.integrate_code_deterministic(existing_content, merged_new)
            # When the OpenSpec spec mandates a contract, the deterministic assembly is the
            # SOLE authoritative source (B13/B11): it MUST win unconditionally, regardless of
            # output size. The assembled file can be legitimately SMALLER than the existing
            # baseline (e.g. greetings strips the LLM's dead modal noise), so the old
            # `len(merged) >= len(existing_content)` guard wrongly discarded the good output
            # and fell back to the LLM — which (during the docker run, empty new_code) wrote
            # a 0-byte main.ts. Never fall back to the LLM when a contract is present.
            if expected_contract:
                merged = self._ensure_contract_present(merged, expected_contract)
                return merged
            # No contract: size-based fallback to LLM only if deterministic merge shrank.
            if len(merged) >= len(existing_content):
                # B11 hardening: UNCONDITIONAL guarantee. The spec contract (Modal class,
                # generator method, command) MUST be present in the merged output regardless
                # of how the LLM's raw output interacted with the merge. This removes the
                # per-run non-determinism: if any contract piece is missing, append it.
                merged = self._ensure_contract_present(merged, expected_contract)
                return merged
            log_info(
                self.name,
                "Deterministic merge smaller than existing; falling back to LLM merge",
            )
        except Exception as e:
            log_info(self.name, f"Deterministic merge failed ({e}); using LLM merge")
        return self.integrate_code_with_llm(existing_content, new_code)

    @staticmethod
    def _ensure_contract_present(content: str, contract: dict | None) -> str:
        """Unconditionally guarantee the spec contract pieces are present in `content`.

        Idempotent: appends ONLY the pieces that are absent (by string check), so re-runs
        never duplicate. This is the deterministic floor's safety net — it makes the uuid
        Modal / generator / command injection independent of the LLM's variable raw output,
        which previously caused flaky per-run generation (command landed, Modal didn't).
        Relies on the SPEC-authored TS parsed into `contract_ts` (never Python literals).
        """
        if not contract:
            return content
        raw = contract.get("contract_ts") or ""
        if not raw:
            return content

        def _slice(marker: str) -> str:
            m = re.search(
                rf"// === {re.escape(marker)} ===[^\n]*\n\s*(.*?)(?=// === |\\Z)",
                raw,
                re.DOTALL,
            )
            return m.group(1).strip() if m else ""

        command_body = _slice("CONTRACT_COMMAND")
        generator_fn = _slice("CONTRACT_GENERATOR")
        modal_class = _slice("CONTRACT_MODAL")
        cid = contract.get("command_id", "")
        modal = contract.get("modal_class", "")

        result = content
        # 1) Command: ensure the contract command id is present inside onload().
        if cid and f"id: '{cid}'" not in result:
            # Insert just before the closing brace of onload()/TimestampPlugin; simplest:
            # append inside the last `async onload()` block's closing. Fallback: append at
            # end of the plugin class. We inject before the plugin class closing brace.
            insert_at = result.rfind("}")
            if insert_at != -1:
                result = result[:insert_at] + "\n" + command_body + "\n" + result[insert_at:]
        # 2) Generator method inside TimestampPlugin. Idempotent: skip if the method name
        # token is ALREADY present anywhere (covers both the assembled and the guaranteed
        # form, regardless of indentation), so re-runs never duplicate the method.
        if generator_fn and "generateUuidV7" in generator_fn and "generateUuidV7" not in result:
            # Insert before the TimestampPlugin class closing brace.
            lines = result.split("\n")
            open_idx = None
            for i, ln in enumerate(lines):
                if re.search(r"class\s+TimestampPlugin\b", ln):
                    open_idx = i
                    break
            insert_idx = len(lines)
            if open_idx is not None:
                depth = 0
                inside = False
                for j in range(open_idx, len(lines)):
                    depth += lines[j].count("{") - lines[j].count("}")
                    if "{" in lines[j]:
                        inside = True
                    if inside and depth <= 0:
                        insert_idx = j
                        break
            lines = (
                lines[:insert_idx]
                + [""]
                + generator_fn.rstrip("\n").split("\n")
                + lines[insert_idx:]
            )
            result = "\n".join(lines)
        # 3) Modal class as a TOP-LEVEL module member (never nested).
        if modal and f"class {modal} extends obsidian.Modal" not in result:
            result = result.rstrip("\n") + "\n\n" + modal_class.rstrip("\n") + "\n"
        return result

    @staticmethod
    def _normalize_to_contract(content: str, contract: dict) -> str:
        """Force the generated command to honor the OpenSpec-mandated contract.

        - Renames the (first) `this.addCommand({ id: '...', name: '...' })` block to the
          spec's `command_id` / `command_name` when present.
        - Renames the generated Modal class to the spec's `modal_class` (and updates the
          `new <ModalClass>(this.app).open()` call site) when present.
        This guarantees the OpenSpec spec wins even if the LLM picked a different name.
        """
        cid = contract.get("command_id")
        cname = contract.get("command_name")
        modal = contract.get("modal_class")
        if not (cid or cname or modal):
            return content
        lines = content.split("\n")
        # 1) Force command id + name on the first addCommand block.
        if cid or cname:
            in_cmd = False
            depth = 0
            for i, ln in enumerate(lines):
                if ln.strip().startswith("this.addCommand("):
                    in_cmd = True
                if in_cmd:
                    if cid and re.search(r"id:\s*'[^']*'", ln):
                        lines[i] = re.sub(r"id:\s*'[^']*'", f"id: '{cid}'", ln)
                    if cname and re.search(r"name:\s*'[^']*'", ln):
                        lines[i] = re.sub(r"name:\s*'[^']*'", f"name: '{cname}'", ln)
                if in_cmd:
                    depth += ln.count("{") - ln.count("}")
                    if depth <= 0 and "}" in ln:
                        in_cmd = False
        # 2) Rename Modal class + its open() call site.
        if modal:
            # class XxxModal -> modal
            for i, ln in enumerate(lines):
                m = re.match(r"(export\s+)?class\s+(\w*Modal)\b", ln)
                if m:
                    lines[i] = ln.replace(m.group(2), modal)
                    break
            # new <OldModal>(this.app).open() -> new modal(this.app).open()
            for i, ln in enumerate(lines):
                m = re.search(r"new\s+(\w*Modal)\(this\.app\)\.open\(\)", ln)
                if m:
                    lines[i] = ln.replace(f"new {m.group(1)}(this.app).open()",
                                          f"new {modal}(this.app).open()")
                    break
        return "\n".join(lines)

    @staticmethod
    def _spec_driven_feature_for_contract(contract: dict) -> dict:
        """Deterministic SPEC-DRIVEN assembly floor (OpenSpec spec always wins).

        The TypeScript content is NEVER hard-coded in Python. It is read from the OpenSpec
        change's ``## Contract`` fenced ```ts block (parsed by ``_expected_contract_for_change``
        into ``contract["contract_ts"]``). This method only SPLITS that block into the three
        pieces the merge needs (command / generator / modal) using the `=== CONTRACT_* ===`
        markers the spec author wrote. If no contract TS is present, returns {} and the plain
        merge is used instead.

        This is the safety net that guarantees `make test-app` / `build-app` pass even when the
        LLM under-delivers — the injected TS comes from the spec, not from Python literals.
        """
        raw = (contract or {}).get("contract_ts")
        if not raw:
            return {}
        # Split the contract block by the marker comments the spec author wrote.
        def _slice(marker: str) -> str:
            m = re.search(
                rf"// === {re.escape(marker)} ===[^\n]*\n\s*(.*?)(?=// === |\Z)",
                raw,
                re.DOTALL,
            )
            return m.group(1).strip() if m else ""

        command_body = _slice("CONTRACT_COMMAND")
        generator_fn = _slice("CONTRACT_GENERATOR")
        modal_class = _slice("CONTRACT_MODAL")
        # A valid contract needs a command + a modal. The GENERATOR is OPTIONAL: simple
        # features (e.g. a Greetings modal) have no algorithmic body, so they omit the
        # `// === CONTRACT_GENERATOR ===` marker. Requiring it here previously made the whole
        # deterministic contract-injection path fall back to a plain LLM merge for
        # generator-less features — which let the LLM's duplicate/non-contract Modal survive
        # (greetings bug 6.1). Only bail when the essential command+modal are missing.
        if not (command_body and modal_class):
            # Malformed contract block — fall back to plain merge rather than injecting garbage.
            return {}
        return {
            "generator_fn": generator_fn,
            "modal_class": modal_class,
            "command_body": command_body,
        }

    def _assemble_contract_features(
        self, existing_content: str, new_code: str, contract: dict
    ) -> str:
        """Merge existing code with the SPEC-CONTRACT-feature, deterministically.

        The OpenSpec spec is the source of truth: when `expected_contract` is present we
        DO NOT trust the LLM's generated command body at all. We build the injected code
        from the contract itself:
          - the spec-synthesized command body (exact id/name, calls the spec generator),
          - the spec-synthesized Modal subclass (if the LLM didn't emit an equivalent one),
          - the spec generator function (if it isn't already in the file).
        Any `this.addCommand(...)` the LLM generated that is NOT the contract command is
        dropped (it would otherwise duplicate / conflict). Existing commands in `main.ts`
        are preserved. No LLM, no omission of existing logic.
        """
        feat = self._spec_driven_feature_for_contract(contract)
        if not feat:
            return self.integrate_code_deterministic(existing_content, new_code)
        cid = contract["command_id"]
        modal = contract["modal_class"]
        # Build the injected CODE from the contract: ONLY the authoritative command body is
        # injected into onload(). The Modal class + generator are appended AFTER the merge
        # (idempotent: only if not already present).
        injected = feat["command_body"].rstrip("\n")

        # B13 — SPEC IS THE SOLE SOURCE OF TRUTH for contract features. Rebuild from the
        # COMMITTED baseline (git HEAD) and inject ONLY the contract pieces. The LLM's
        # `new_code` is DISCARDED entirely: it has repeatedly leaked broken helpers (e.g.
        # `generateUuidV7Internal` with an unterminated template literal) that survive the
        # balanced-block strippers and break `tsc`/rollup non-deterministically. Discarding
        # it makes output valid + deterministic (the spec contract is self-contained: the
        # CONTRACT_COMMAND body is inline and CONTRACT_GENERATOR supplies generateUuidV7).
        base_src = existing_content
        proj = os.getenv("PROJECT_ROOT", "/project")
        try:
            import subprocess as _sp
            # Under rootless nerdctl the container uid (1000) does not own the bind-mounted
            # repo, so plain `git` aborts with "dubious ownership". Pass `-c safe.directory=*`
            # (and neutralize global/system gitconfig) so the committed-read works.
            head = _sp.run(
                ["git", "-c", "safe.directory=*", "-C", proj, "show", "HEAD:src/main.ts"],
                capture_output=True, text=True,
                env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
            )
            if head.returncode == 0 and head.stdout.strip():
                base_src = head.stdout
        except Exception:
            pass

        # Clean the committed baseline so idempotent re-runs never duplicate the contract
        # command / modal / generator (none are present in a fresh baseline, but this guards
        # re-runs against any stale state).
        cleaned_existing = base_src
        for blk in self._extract_balanced_blocks(cleaned_existing, "this.addCommand("):
            if re.search(rf"id:\s*'{re.escape(cid)}'", blk):
                cleaned_existing = cleaned_existing.replace(blk, "")
        for blk in self._extract_balanced_blocks(cleaned_existing, "class "):
            if re.search(rf"\b{re.escape(modal)}\b", blk):
                cleaned_existing = cleaned_existing.replace(blk, "")
        # STRIP any existing generator-method definition from the baseline so the authoritative
        # spec generator is the ONLY one present. Derive the method name(s) from the spec's
        # `generator_fn` (name-agnostic -- not hard-coded to `generateUuidV7`, so base64's
        # `encodeBase64`/`decodeBase64` and any future generator are handled too). Match the
        # method DEFINITION line (`<name>(` at line start) -- never the call site
        # `this.<name>()` -- so call sites are preserved. This removes any stale/wrong variant
        # and makes the spec authoritative.
        _gen_names = re.findall(r"^\s*(\w+)\s*\(", feat.get("generator_fn", ""), re.MULTILINE)
        for _gname in _gen_names:
            for blk in self._extract_balanced_blocks(cleaned_existing, f"{_gname}("):
                cleaned_existing = cleaned_existing.replace(blk, "")

        # Merge: baseline + the authoritative contract command ONLY (no LLM code).
        merged = self.integrate_code_deterministic(cleaned_existing, injected)
        # The generated Modal MUST be a TOP-LEVEL class (not nested inside TimestampPlugin).
        # It is appended at the very END of the file (idempotent: only if absent).
        if f"class {modal} extends obsidian.Modal" not in merged:
            merged = merged.rstrip("\n") + "\n\n" + feat["modal_class"].rstrip("\n") + "\n"
        # Guarantee a SINGLE authoritative contract command: if the (fragile) strippers above
        # missed an LLM-emitted duplicate of id `cid`, keep only the FIRST such command block
        # and drop the rest. This prevents a late-registered LLM command from shadowing the
        # spec-injected one (which would make the uuid tests non-deterministic).
        _cmd_count = 0
        for blk in self._extract_balanced_blocks(merged, "this.addCommand("):
            if re.search(rf"id:\s*'{re.escape(cid)}'", blk):
                if _cmd_count == 0:
                    _cmd_count = 1
                else:
                    merged = merged.replace(blk, "")
        # The spec generator MUST be a METHOD INSIDE TimestampPlugin and it MUST be the
        # authoritative spec version. We already stripped any LLM-generated definition above,
        # so inject the spec's verbatim generator UNCONDITIONALLY (never skip when "present",
        # never trust the LLM's body). The spec is the single source of truth -- the TS body
        # comes from the change's `## Contract` fenced block, never a Python literal.
        # Inject the spec generator UNCONDITIONALLY whenever the contract defines one
        # (name-agnostic -- not hard-coded to `generateUuidV7`, so base64's
        # `encodeBase64`/`decodeBase64` and any future generator are handled too). The
        # baseline was already stripped of any stale generator above, so re-injection is
        # idempotent and the spec's verbatim generator is the ONLY one present.
        if feat.get("generator_fn"):
            lines = merged.split("\n")
            # Insert the generator INSIDE the TimestampPlugin class: find the opening
            # `class TimestampPlugin` and brace-match to its closing '}'.
            open_idx = None
            for i, ln in enumerate(lines):
                if re.search(r"class\s+TimestampPlugin\b", ln):
                    open_idx = i
                    break
            insert_idx = len(lines)
            if open_idx is not None:
                depth = 0
                inside = False
                for j in range(open_idx, len(lines)):
                    depth += lines[j].count("{") - lines[j].count("}")
                    if "{" in lines[j]:
                        inside = True
                    if inside and depth <= 0:
                        insert_idx = j
                        break
            else:
                # fallback: last top-level '}'
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == "}":
                        insert_idx = i
                        break
            lines = (
                lines[:insert_idx]
                + [""]
                + feat["generator_fn"].rstrip("\n").split("\n")
                + lines[insert_idx:]
            )
            merged = "\n".join(lines)
        return merged

    @staticmethod
    def _extract_balanced_blocks(text: str, prefix: str) -> list:
        """Extract balanced-brace blocks whose source line starts with `prefix`.

        Returns list of block strings (including the leading line up to and including
        the matching closing brace). Used to pull `this.addCommand({...})` and
        `class ... {...}` out of generated code without LLM rewriting.

        The block is captured from the START OF THE LINE that contains `prefix` (so leading
        modifiers like `export ` are preserved -- otherwise stripping a `class X` block would
        leave an orphan `export ` behind and corrupt the file).
        """
        blocks: list = []
        i = 0
        n = len(text)
        while i < n:
            idx = text.find(prefix, i)
            if idx == -1:
                break
            # Back up to the start of the line containing the prefix so leading modifiers
            # (e.g. `export`) are included in the captured block.
            line_start = text.rfind("\n", 0, idx) + 1
            # Find the matching opening brace after the prefix line
            brace_start = text.find("{", idx)
            if brace_start == -1:
                i = idx + len(prefix)
                continue
            depth = 0
            j = brace_start
            while j < n:
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            # Capture from the START OF THE LINE (incl. leading `export `) through the
            # matching close brace, plus any trailing `;`.
            end = j + 1
            k = end
            while k < n and text[k] in " \t\n":
                k += 1
            if k < n and text[k] == ";":
                end = k + 1
            elif k < n and text[k] == ")":
                end = k + 1
                if end < n and text[end] == ";":
                    end += 1
            blocks.append(text[line_start:end])
            i = end
            continue
        return blocks

    def integrate_code_deterministic(self, existing_content: str, new_code: str) -> str:
        """Merge generated code into existing main.ts by string manipulation only.

        Guarantees:
        - existing imports/classes/commands are preserved (no omission),
        - new imports are added if missing,
        - new class definitions are appended,
        - new `this.addCommand({...})` blocks are injected into `onload`.
        """
        log_info(self.name, "Starting deterministic code integration (no LLM)")
        existing_lines = existing_content.split("\n")

        # --- imports ---
        new_imports = [
            ln for ln in new_code.split("\n") if ln.strip().startswith("import")
        ]
        existing_import_set = set(
            ln.strip()
            for ln in existing_lines
            if ln.strip().startswith("import")
        )
        unique_new_imports = [
            imp for imp in new_imports if imp.strip() not in existing_import_set
        ]
        import_end = 0
        for i, ln in enumerate(existing_lines):
            if ln.strip() and not ln.strip().startswith("import"):
                import_end = i
                break
        if unique_new_imports:
            existing_lines = (
                existing_lines[:import_end]
                + unique_new_imports
                + [""]
                + existing_lines[import_end:]
            )

        # --- import hygiene (deterministic) ---
        # If `import * as obsidian` is present and the merged code references the
        # namespace form `obsidian.Notice` (NOT the bare `Notice`), then any
        # `import { Notice } from 'obsidian';` that the LLM phase may have added is
        # redundant -> drop it so tsc does not flag TS6133 (unused import). The
        # authoritative usage comes from the spec contract (`obsidian.Notice`).
        merged_so_far = "\n".join(existing_lines)
        if "import * as obsidian" in merged_so_far and re.search(
            r"\bobsidian\.Notice\b", merged_so_far
        ):
            existing_lines = [
                ln
                for ln in existing_lines
                if not re.match(r"\s*import\s*\{\s*Notice\s*\}\s*from\s*['\"]obsidian['\"];", ln)
            ]

        # Drop a *wholly unused* `import * as obsidian from 'obsidian'` so the
        # lint gate (eslint / tsc noUnusedLocals -> TS6133) does not fail on
        # generated code whose feature does not reference the obsidian namespace
        # at all (e.g. a plain command with no Modal). This is deterministic merge
        # hygiene, not hand-editing generated bodies.
        merged_so_far = "\n".join(existing_lines)
        if re.search(r"\bimport\s+\*\s+as\s+obsidian\b", merged_so_far) and not re.search(
            r"\bobsidian\.\w", merged_so_far
        ):
            existing_lines = [
                ln
                for ln in existing_lines
                if not re.search(r"\bimport\s+\*\s+as\s+obsidian\b", ln)
            ]

        # --- class definitions (append at end) ---
        classes = self._extract_balanced_blocks(new_code, "export class")
        # also catch `class X` without export
        for blk in self._extract_balanced_blocks(new_code, "class "):
            if not blk.startswith("export class") and blk not in classes:
                classes.append(blk)
        if classes:
            existing_lines = existing_lines + ["", ""] + classes

        # --- command registrations (inject into onload) ---
        commands = self._extract_balanced_blocks(new_code, "this.addCommand(")
        if commands:
            # locate onload body: the last existing addCommand block, else after `onload() {`
            last_cmd_idx = -1
            for k in range(len(existing_lines) - 1, -1, -1):
                if existing_lines[k].strip().startswith("this.addCommand("):
                    # find start of that block (balance backwards)
                    depth = 0
                    s = k
                    while s >= 0:
                        for ch in existing_lines[s]:
                            if ch == "}":
                                depth += 1
                            elif ch == "{":
                                depth -= 1
                        if depth <= 0 and "{" in existing_lines[s]:
                            break
                        s -= 1
                    last_cmd_idx = s
                    break
            insert_at = len(existing_lines)
            if last_cmd_idx != -1:
                insert_at = last_cmd_idx
            else:
                for k, ln in enumerate(existing_lines):
                    if ln.strip().startswith("onload()") or ln.strip().startswith(
                        "async onload()"
                    ):
                        insert_at = k + 1
                        break
            indented_cmds = []
            for cmd in commands:
                for cl in cmd.split("\n"):
                    indented_cmds.append("    " + cl if cl.strip() else cl)
            existing_lines = (
                existing_lines[:insert_at]
                + [""]
                + indented_cmds
                + [""]
                + existing_lines[insert_at:]
            )

        updated = "\n".join(existing_lines)
        log_info(
            self.name,
            f"Deterministic merge complete: {len(existing_content)} -> {len(updated)} bytes",
        )
        return updated

    def generate_updated_test_file(self, existing_content: str, new_tests: str) -> str:
        """Manually integrate new tests into the existing test file by handling imports and placing describe blocks at the top."""
        return self.integrate_tests_manually(existing_content, new_tests)

    def integrate_test_contract(
        self, existing_content: str, expected_contract: dict | None, baseline_content: str | None = None
    ) -> str:
        """B10/B11: deterministically inject the SPEC-OWNED regression tests from the change's
        `## Test Contract` block into `main.test.ts`.

        The spec (tasks.md) authors the exact Jest tests for the contract command; the LLM test
        output is only a fallback. This guarantees the generated test file asserts the exact spec
        contract (no hallucinated `unknownMethod`, correct command name). Python only merges; it
        never authors test bodies.

        - Parses the `## Test Contract` fenced ```ts block by `=== TEST_CONTRACT_* ===` markers.
        - Replaces any existing `insert-<id>` describe block in the file (so stale/LLM tests are
          removed), then injects the spec tests inside the top-level `describe('TimestampPlugin')`.
        - Returns the content unchanged if there is no spec test contract.
        """
        if not expected_contract or not expected_contract.get("contract_ts"):
            return existing_content
        # Use the spec test contract parsed directly from the contract dict (B10/B11): this
        # avoids a second fragile file-read / CHANGE-env lookup that could silently return empty.
        test_ts = expected_contract.get("test_contract_ts", "")
        if not test_ts:
            return existing_content

        m = re.search(
            r"// === TEST_CONTRACT_[A-Z0-9_]+ ===[^\n]*\n\s*(.*?)(?=// === END_TEST_CONTRACT|// === TEST_CONTRACT_|\Z)",
            test_ts,
            re.DOTALL,
        )
        if not m:
            return existing_content
        test_body = m.group(1).rstrip()

        # B11: the spec Test Contract is the SOLE source of truth for regression tests.
        # The LLM test output is only a fallback and is DISCARDED entirely here — otherwise
        # the LLM's own `describe('TimestampPlugin', ...)` wrapper (which shares the baseline
        # header name) survives alongside the spec injection and produces unbalanced braces
        # (TS1005 '}' expected). We rebuild the file from the committed BASELINE only, then
        # inject the spec contract inside the baseline's top-level describe. No LLM-authored
        # test bodies survive.
        # Prefer the COMMITTED test file as the structural source. The LLM output (passed in as
        # `baseline_content`/`existing_content`) sometimes double-wraps the uuid block in its own
        # `describe('TimestampPlugin')`, which produces unbalanced braces (TS1005 '}' expected)
        # non-deterministically. Rebuilding from the committed file makes the injection stable.
        proj = os.getenv("PROJECT_ROOT", "/project")
        # ALWAYS rebuild from the COMMITTED baseline (`git show HEAD`), never the on-disk file:
        # the on-disk test file may be DIRTY from a previous (failed) run and would feed its own
        # broken braces back into the assembler. Reading HEAD guarantees a clean, deterministic
        # structural shell. Fall back to the on-disk file only if git is unavailable.
        # NOTE: under rootless nerdctl the container uid (1000) does NOT own the bind-mounted
        # repo, so plain `git` aborts with "dubious ownership". Pass `-c safe.directory=*`
        # (and env GIT_CONFIG_GLOBAL=/dev/null) so the committed-read works inside the container.
        baseline_src = baseline_content if baseline_content is not None else existing_content
        _committed_src = None
        try:
            _g = subprocess.run(
                ["git", "-c", "safe.directory=*", "-C", proj, "show", "HEAD:src/__tests__/main.test.ts"],
                capture_output=True, text=True,
                env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
            )
            if _g.returncode == 0 and _g.stdout.strip():
                _committed_src = _g.stdout
        except Exception:
            pass
        if _committed_src is None:
            committed_file = os.path.join(proj, "src", "__tests__", "main.test.ts")
            if os.path.isfile(committed_file):
                try:
                    with open(committed_file, "r", encoding="utf-8") as _fh:
                        _committed_src = _fh.read()
                except Exception:
                    pass
        if _committed_src is not None:
            baseline_src = _committed_src

        # Idempotency: strip any pre-existing `insert-uuid-v7` describe block so a re-run does
        # not duplicate the contract tests.
        baseline_lines = baseline_src.split("\n")

        # Regex-literal-aware brace counter. Naive `line.count("{")-line.count("}")`
        # mis-counts braces that appear INSIDE a regex literal (e.g. the uuid tests contain
        # `/^[0-9a-f]{8}-...{12}$/`), which breaks the brace-balanced block strippers below
        # (they stop one `}` early and drop the real closing brace -> TS1005 '}' expected,
        # bug 6.6). Strip regex literals before counting braces.
        def _brace_delta(line: str) -> int:
            # Drop JS regex literals BEFORE counting braces (bug 6.6): the uuid tests contain
            # `toMatch(/^[0-9a-f]{8}-...{12}$/)` whose `{8}`/`{12}`/`{3}` quantifiers look like
            # code braces and break naive counting. Use a tolerant regex-literal stripper that
            # also handles an optional trailing flags group (g/i/m/s/u/y).
            s = re.sub(r"/[^/\n]*?(?:\\.[^/\n]*?)*/[a-z]*", "", line)
            # Also drop template literals (backtick) for safety.
            s = re.sub(r"`[^`]*`", "", s)
            return s.count("{") - s.count("}")

        stripped = []
        i = 0
        while i < len(baseline_lines):
            line = baseline_lines[i]
            hdr = re.search(r"describe\(\s*['\"]([^'\"]+)['\"]", line)
            if hdr and "insert-uuid-v7" in hdr.group(1):
                depth = 0
                j = i
                while j < len(baseline_lines):
                    depth += _brace_delta(baseline_lines[j])
                    if j > i and depth <= 0 and baseline_lines[j].strip() in ("}", "});"):
                        i = j + 1
                        break
                    j += 1
                else:
                    i = j + 1
                continue
            stripped.append(line)
            i += 1
        cleaned = stripped

        # Collapse to EXACTLY ONE top-level `describe('TimestampPlugin')`. The LLM output or
        # `generate_updated_test_file` sometimes emits a duplicate/second `describe('TimestampPlugin')`
        # shell (which double-opens and breaks braces -> TS1005 '}' expected, non-deterministically).
        # Keep the FIRST such block; remove every subsequent one (open -> matching close) so the
        # structural shell is always unique and balanced.
        tp_opens = [
            i for i, l in enumerate(cleaned)
            if l.strip().startswith("describe('TimestampPlugin',")
        ]
        if len(tp_opens) > 1:
            remove_ranges = []
            for open_idx in tp_opens[1:]:
                depth = 0
                for j in range(open_idx, len(cleaned)):
                    depth += _brace_delta(cleaned[j])
                    if j > open_idx and depth <= 0 and cleaned[j].strip() in ("}", "});"):
                        remove_ranges.append((open_idx, j))
                        break
            for a, b in sorted(remove_ranges, reverse=True):
                cleaned = cleaned[:a] + cleaned[b + 1:]

        # Locate the single top-level `describe('TimestampPlugin')` (the committed baseline has
        # exactly one; this is our structural shell).
        top_open_idx = None
        for idx, line in enumerate(cleaned):
            if line.strip().startswith("describe('TimestampPlugin',"):
                top_open_idx = idx
                break

        # Normalize the spec body to a 4-space base indent (sibling level inside the describe).
        body_lines = test_body.strip("\n").split("\n")
        indents = [len(l) - len(l.lstrip()) for l in body_lines if l.strip()]
        min_ind = min(indents) if indents else 0
        indented_body = "\n".join(
            ("    " + l[min_ind:]) if l.strip() else "" for l in body_lines
        )

        if top_open_idx is None:
            # No existing top-level describe -- emit a single fresh one (rare/idempotent).
            out = list(cleaned)
            out.append("")
            out.append("describe('TimestampPlugin', () => {")
            out.extend([("    " + bl) for bl in test_body.strip("\n").split("\n")])
            out.append("});")
            return "\n".join(out)

        # Find the closing brace of the top-level describe by scanning BACKWARD from EOF:
        # the outermost `describe('TimestampPlugin')` closes LAST in a well-formed file, so the
        # first `}`/`});` we meet scanning from the end is its close. (A naive forward
        # brace-count mis-fires on interior object-literal `}` lines and drops the real close,
        # producing TS1005 '}' expected.)
        top_close_idx = None
        for j in range(len(cleaned) - 1, top_open_idx, -1):
            if cleaned[j].strip() in ("}", "});"):
                top_close_idx = j
                break
        if top_close_idx is None:
            top_close_idx = len(cleaned) - 1

        # Rebuild: keep ONLY the first describe('TimestampPlugin') shell; inject the spec uuid
        # block INSIDE its closing `});`. Everything after that close (stray duplicate describes
        # the LLM may have emitted) is dropped. Guarantees exactly one balanced describe.
        inner = cleaned[top_open_idx + 1 : top_close_idx]
        out = (
            cleaned[: top_open_idx + 1]
            + inner
            + [""]
            + [("    " + bl) for bl in test_body.strip("\n").split("\n")]
            + [""]
            + cleaned[top_close_idx : top_close_idx + 1]
        )
        return "\n".join(out)

    def _extract_test_contract(self, change: str) -> str:
        """Parse the `## Test Contract` fenced ```ts block from the change's tasks.md/spec.md."""
        if not change:
            return ""
        roots = []
        proj = os.getenv("PROJECT_ROOT", "/project")
        roots.append(os.path.join(proj, "openspec", "changes"))
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=proj, capture_output=True, text=True,
            )
            if top.returncode == 0 and top.stdout.strip():
                roots.append(os.path.join(top.stdout.strip(), "openspec", "changes"))
        except Exception:
            pass
        text = ""
        for r in roots:
            for p in (
                os.path.join(r, change, "tasks.md"),
                os.path.join(r, change, "specs", change, "spec.md"),
            ):
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        text += f.read() + "\n"
        m = re.search(r"(?m)^##\s+Test Contract\b.*?```ts\s*(.*?)```", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    def integrate_code_with_llm(self, existing_content: str, new_code: str) -> str:
        """
        Use LLM to generate updated code by integrating new code into the existing TimestampPlugin class.
        """
        tool_instructions = (
            ModularPrompts.get_tool_instructions_for_code_integrator_agent()
        )
        prompt = (
            "/think\n"
            f"You are integrating new TypeScript code into an existing Obsidian plugin file (`main{self.code_ext}`). "
            "The new code must be added to the `TimestampPlugin` class without modifying any existing code. "
            "Follow these instructions carefully:\n\n"
            "1. **Existing Code:**\n"
            f"{existing_content}\n\n"
            "2. **New Code to Integrate:**\n"
            f"{new_code}\n\n"
            "3. **Integration Rules:**\n"
            "   **CRITICAL: Integrate EXACT new code from section 2 VERBATIM into TimestampPlugin class (methods) or onload (commands). Do NOT change it.**\n"
            "   - Generate precise integrated code:\n"
            "   - Valid TS syntax, no unterminated template literals/strings.\n"
            "   - Obsidian API: TFile.extension (not .ext), mock Notice/Plugin as in __mocks__/obsidian.ts.\n"
            "     - Mock functions: use jest.fn().\n"
            "     - No unused variables/imports.\n"
            "     - Preserve existing code structure.\n"
            "   - Add new methods or properties to the `TimestampPlugin` class.\n"
            "   - Add new commands within the `onload` method using `this.addCommand`.\n"
            "   - Preserve all existing imports, methods, and commands.\n"
            "   - Add only necessary new imports that are not already present.\n"
            "   - Ensure the code is properly formatted and uses TypeScript syntax.\n"
            "   - Do not remove or alter any existing code.\n   3.5 **Repair TS Errors:** Fix editorCallback sig (Editor+ctx:MarkdownView|MarkdownFileInfo; cast view=ctx as MarkdownView; use 'editor'; no unused; string/number;\n\n"
            f"{tool_instructions}\n\n"
            "4. **Output Instructions:**\n"
            "   - Your response must contain only the updated TypeScript code for `main{self.code_ext}`.\n"
            "   - The code should start with the import statements and end with the closing brace of the class.\n"
            "   - Do not include any comments, explanations, or additional text outside the code itself.\n"
            "   - Do not add any markers or comments indicating the start or end of the updated code.\n"
            "   - Do not include any lines containing the word 'typescript'.\n"
            "   - The response must consist solely of the code, with no additional lines or text before or after.\n"
            "   - The first line of your response should be a TypeScript import statement or the beginning of the class.\n\n"
            "5. **Output:**\n"
            "   - Provide the complete updated TypeScript code for `main{self.code_ext}` with the new code integrated."
        )
        log_info(self.name, f"Code integration prompt length: {len(prompt)}")
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        updated_content = self.remove_unwanted_lines(clean_response.strip())
        log_info(
            self.name,
            f"LLM response for code integration after removing unwanted lines, length: {len(updated_content)}",
        )
        log_info(self.name, f"Updated code content: {updated_content}")
        return updated_content

    def integrate_tests_manually(self, existing_content: str, new_tests: str) -> str:
        """
        Manually integrate new tests into the existing test file by handling imports and placing describe blocks inside existing describe.
        Always use '../main' import for TimestampPlugin.
        """
        log_info(self.name, "Starting manual test integration")
        existing_lines = existing_content.split("\n")

        # LLMs sometimes emit literal "\\n"/"\\t" escape sequences instead of real newlines,
        # which corrupts the test file (TS1005/Unterminated string). Normalize them so the
        # test merge / jest parse is clean. Matches the code-side normalization.
        new_tests = new_tests.replace("\\n", "\n").replace("\\t", "\t")
        # Remove any lines containing "typescript" or "javascript" from new test content
        new_test_lines = [
            line
            for line in new_tests.split("\n")
            if "typescript" not in line.lower() and "javascript" not in line.lower()
        ]
        new_tests = "\n".join(new_test_lines)
        log_info(
            self.name,
            f"New test lines after removing unwanted lines: {len(new_test_lines)}",
        )
        log_info(self.name, f"Filtered new test lines: {new_test_lines}")

        # Strip outer describe('TimestampPlugin') if present to avoid duplicates
        match = re.search(
            r"describe\('TimestampPlugin',\s*\(\)\s*=>\s*\{(.*)\}\);\s*$",
            new_tests,
            re.DOTALL,
        )
        if match:
            new_tests = match.group(1).strip()
            log_info(self.name, "Stripped outer describe block from new tests")

        # Extract import lines from new test content
        new_imports = [
            line for line in new_tests.split("\n") if line.strip().startswith("import")
        ]
        log_info(
            self.name,
            f"Extracted {len(new_imports)} import lines from new tests: {new_imports}",
        )

        # Force TimestampPlugin import to '../main'
        for i, imp in enumerate(new_imports):
            if "TimestampPlugin" in imp:
                new_imports[i] = "import TimestampPlugin from '../main';"

        # Find the end of the import section in existing content
        import_end_idx = 0
        for i, line in enumerate(existing_lines):
            if not line.strip().startswith("import") and line.strip():
                import_end_idx = i
                break
        log_info(self.name, f"Import section ends at index: {import_end_idx}")

        # Find unique new imports not already present
        existing_imports_set = set(
            line.strip()
            for line in existing_lines[:import_end_idx]
            if line.strip().startswith("import")
        )
        unique_new_imports = [
            imp for imp in new_imports if imp.strip() not in existing_imports_set
        ]
        log_info(
            self.name,
            f"Unique new imports to add: {len(unique_new_imports)}: {unique_new_imports}",
        )

        # Insert new imports after existing imports if any
        if unique_new_imports:
            existing_lines = (
                existing_lines[:import_end_idx]
                + unique_new_imports
                + [""]
                + existing_lines[import_end_idx:]
            )

        # Prepare new describe blocks (inner content)
        describe_blocks = [
            line
            for line in new_tests.split("\n")
            if not line.strip().startswith("import")
        ]

        # Try to find the start of the top-level describe block
        describe_start_idx = -1
        for i, line in enumerate(existing_lines):
            if line.strip().startswith("describe('TimestampPlugin', "):
                describe_start_idx = i
                break

        if describe_start_idx != -1:
            log_info(
                self.name,
                f"Top-level describe block starts at index: {describe_start_idx}",
            )
            # Find the position just after the opening of the describe block
            insert_idx = describe_start_idx + 1
            while (
                insert_idx < len(existing_lines)
                and not existing_lines[insert_idx].strip()
            ):
                insert_idx += 1
            log_info(self.name, f"Insert position for new tests: {insert_idx}")

            # Prepare new describe blocks with proper indentation (4 spaces)
            if describe_blocks:
                indented_describe_blocks = ["    " + line for line in describe_blocks]
                # Insert a blank line and new tests at the top of the describe block
                existing_lines = (
                    existing_lines[:insert_idx]
                    + indented_describe_blocks
                    + [""]
                    + existing_lines[insert_idx:]
                )
                log_info(
                    self.name,
                    f"Inserted {len(describe_blocks)} new test lines: {indented_describe_blocks}",
                )
        else:
            # No existing describe block, append new tests at the end
            if describe_blocks:
                existing_lines.extend([""] + describe_blocks)
                log_info(
                    self.name,
                    f"Appended {len(describe_blocks)} new test lines at the end",
                )

        updated_content = "\n".join(existing_lines)
        log_info(self.name, f"Updated test file content length: {len(updated_content)}")
        log_info(self.name, f"Updated test file content: {updated_content}")
        return updated_content

    def remove_unwanted_lines(self, content: str) -> str:
        """Remove lines containing 'typescript'/'javascript' (case-insens.) or only '```'."""
        lines = content.split("\n")
        filtered_lines = [
            line
            for line in lines
            if "typescript" not in line.lower()
            and "javascript" not in line.lower()
            and line.strip() != "```"
        ]
        removed_count = len(lines) - len(filtered_lines)
        log_info(
            self.name, f"Removed {removed_count} unwanted lines (typescript/js/```)"
        )
        filtered_content = "\n".join(filtered_lines)
        log_info(self.name, f"Filtered content: {filtered_content}")
        return filtered_content

    def strip_markdown_blocks(self, content: str) -> str:
        """Remove markdown code blocks like ```typescript ... ```"""
        pattern = r"```(?:typescript|javascript|js)?\\s*\\n[\\s\\S]*?\\n```"
        cleaned = re.sub(
            pattern, "", content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        return cleaned

    def extract_content(self, text: str) -> str:
        """Extract code content: strip thinking tags, markdown blocks, trim."""
        log_info(self.name, "Extracting content from raw text")
        log_info(self.name, f"Input text length: {len(text)}")
        log_info(self.name, f"Input text: {text}")
        clean_text = remove_thinking_tags(text)
        clean_text = self.strip_markdown_blocks(clean_text)
        log_info(self.name, f"Extracted content length: {len(clean_text)}")
        log_info(self.name, f"Extracted content: {clean_text}")
        return clean_text.strip()

    def update_file(self, file_path: str, new_content: str):
        """Update an existing file with new content, creating it if it doesn't exist."""
        log_info(self.name, f"Updating file: {file_path}")
        log_info(self.name, f"New content length: {len(new_content)}")
        log_info(self.name, f"New content: {new_content}")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            log_info(self.name, f"File updated successfully: {file_path}")
        except Exception as e:
            self.monitor.error(
                "file_update_failed", data={"file_path": file_path, "error": str(e)}
            )
            raise

    def create_file(self, file_path: str, content: str):
        """Create a new file with the given content."""
        log_info(self.name, f"Creating new file: {file_path}")
        log_info(self.name, f"Content length: {len(content)}")
        log_info(self.name, f"Content: {content}")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_info(self.name, f"File created successfully: {file_path}")
        except Exception as e:
            self.monitor.error(
                "file_creation_failed", data={"file_path": file_path, "error": str(e)}
            )
            raise
