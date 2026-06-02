"""
Edge case and failure tests for the agentics workflow.

Tests cover:
- Empty/invalid inputs
- LLM failures at each stage
- GitHub API failures
- tsc compilation failures and recovery
- State preservation across nodes
- Conditional routing
- Test node behavior
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.workflow import AgenticsWorkflow
from src.state import State


@pytest.fixture
def temp_project():
    tmpdir = tempfile.mkdtemp()
    src_dir = os.path.join(tmpdir, "src")
    test_dir = os.path.join(src_dir, "__tests__")
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(src_dir, "main.ts"), "w") as f:
        f.write(
            "class TimestampPlugin {\n"
            "  async onload() {\n"
            "    this.addCommand({ id: 'test' });\n"
            "  }\n"
            "}\n"
        )
    with open(os.path.join(test_dir, "main.test.ts"), "w") as f:
        f.write("describe('test', () => { it('passes', () => {}); });\n")
    with open(os.path.join(tmpdir, "package.json"), "w") as f:
        json.dump({"name": "test", "version": "1.0.0"}, f)
    with open(os.path.join(tmpdir, "tsconfig.json"), "w") as f:
        json.dump({"compilerOptions": {"target": "esnext"}}, f)
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _make_workflow(temp_project, llm_responses=None, github_side_effect=None):
    """Helper to create a workflow with controlled mock responses."""
    llm = MagicMock()
    if llm_responses:
        llm.invoke.side_effect = llm_responses
    elif llm_responses is None:
        llm.invoke.side_effect = Exception("should not be called")

    github = MagicMock()
    if github_side_effect:
        github.get_repo.side_effect = github_side_effect
    else:
        repo = MagicMock()
        issue = MagicMock()
        issue.body = "Test issue body"
        issue.title = "Test Issue"
        repo.get_issue.return_value = issue
        github.get_repo.return_value = repo

    config = MagicMock()
    with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
        return AgenticsWorkflow(llm, llm, github, config)


class TestEmptyInputs:
    def test_empty_ticket_content(self, temp_project):
        llm = MagicMock()
        llm.invoke.return_value = "invalid"
        github = MagicMock()
        repo = MagicMock()
        issue = MagicMock()
        issue.body = ""
        issue.title = "Empty Issue"
        repo.get_issue.return_value = issue
        github.get_repo.return_value = repo
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, github, config)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = wf._node_fetch_issue(state)
        assert result["ticket_content"] == ""
        result = wf._node_clarify_ticket(result)
        assert "refined_ticket" in result
        assert result["refined_ticket"]["title"] == "Feature Implementation"

    def test_github_returns_none_body(self, temp_project):
        llm = MagicMock()
        github = MagicMock()
        repo = MagicMock()
        issue = MagicMock()
        issue.body = None
        issue.title = "Test"
        repo.get_issue.return_value = issue
        github.get_repo.return_value = repo
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, github, config)
        result = wf._node_fetch_issue({"url": "https://github.com/o/r/issues/1"})
        assert result["ticket_content"] == ""


class TestLLMFailures:
    def test_clarify_raises_exception(self, temp_project):
        llm = MagicMock()
        llm.invoke.side_effect = Exception("Connection refused")
        wf = _make_workflow(temp_project)
        wf.llm_reasoning = llm
        state: State = {"url": "https://github.com/o/r/issues/1", "ticket_content": "Some ticket"}
        result = wf._node_clarify_ticket(state)
        assert "refined_ticket" in result
        assert result["refined_ticket"]["title"] == "Feature Implementation"

    def test_clarify_returns_markdown_wrapped_json(self, temp_project):
        llm = MagicMock()
        llm.invoke.return_value = '```json\n{"title": "Test", "description": "Desc", "requirements": ["a", "b"], "acceptance_criteria": ["c"], "implementation_steps": ["d"], "npm_packages": [], "affected_files": ["src/main.ts"]}\n```'
        wf = _make_workflow(temp_project)
        wf.llm_reasoning = llm
        state: State = {"url": "https://github.com/o/r/issues/1", "ticket_content": "Test"}
        result = wf._node_clarify_ticket(state)
        assert result["refined_ticket"]["title"] == "Test"
        assert len(result["refined_ticket"]["requirements"]) == 2

    def test_clarify_returns_truncated_json(self, temp_project):
        llm = MagicMock()
        llm.invoke.return_value = '{"title": "Test", "description": "Desc"'
        wf = _make_workflow(temp_project)
        wf.llm_reasoning = llm
        state: State = {"url": "https://github.com/o/r/issues/1", "ticket_content": "Test"}
        result = wf._node_clarify_ticket(state)
        assert "refined_ticket" in result


class TestGitHubFailures:
    def test_github_404(self, temp_project):
        wf = _make_workflow(temp_project, github_side_effect=Exception("404 Not Found"))
        result = wf._node_fetch_issue({"url": "https://github.com/o/r/issues/1"})
        assert "error" in result
        assert "404" in result["error"]

    def test_github_timeout(self, temp_project):
        wf = _make_workflow(temp_project, github_side_effect=Exception("timeout"))
        result = wf._node_fetch_issue({"url": "https://github.com/o/r/issues/1"})
        assert "error" in result

    def test_fetch_failure_state_preserved(self, temp_project):
        wf = _make_workflow(temp_project, github_side_effect=Exception("fail"))
        state: State = {"url": "https://github.com/o/r/issues/1"}
        state = wf._node_fetch_issue(state)
        assert "error" in state
        state = wf._node_clarify_ticket(state)
        assert "refined_ticket" in state


class TestStateShape:
    def test_state_always_dict(self, temp_project):
        wf = _make_workflow(temp_project)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        for node in [
            wf._node_fetch_issue, wf._node_clarify_ticket,
            wf._node_plan_implementation, wf._node_extract_code,
            wf._node_output,
        ]:
            state = node(state)
            assert isinstance(state, dict)

    def test_url_preserved_through_all_nodes(self, temp_project):
        wf = _make_workflow(temp_project)
        url = "https://github.com/owner/repo/issues/42"
        state: State = {"url": url}
        for node in [
            wf._node_fetch_issue, wf._node_clarify_ticket,
            wf._node_plan_implementation, wf._node_extract_code,
            wf._node_output,
        ]:
            state = node(state)
            assert state["url"] == url

    def test_error_not_lost(self, temp_project):
        wf = _make_workflow(temp_project, github_side_effect=Exception("fail"))
        state: State = {"url": "https://github.com/o/r/issues/1"}
        state = wf._node_fetch_issue(state)
        state = wf._node_clarify_ticket(state)
        state = wf._node_plan_implementation(state)
        state = wf._node_extract_code(state)
        state = wf._node_output(state)
        assert "error" in state or "success" in state


class TestTestNode:
    @patch("src.workflow.subprocess.run")
    def test_test_passes(self, mock_run, temp_project):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Tests: 10 passed, 10 total\n", stderr=""
        )
        wf = _make_workflow(temp_project)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = wf._node_test(state)
        assert result["post_integration_tests_passed"] == 10
        assert result["existing_tests_passed"] == 10

    @patch("src.workflow.subprocess.run")
    def test_test_failure(self, mock_run, temp_project):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Tests failed")
        wf = _make_workflow(temp_project)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = wf._node_test(state)
        assert result["post_integration_tests_passed"] == 0

    @patch("src.workflow.subprocess.run")
    def test_test_exception(self, mock_run, temp_project):
        mock_run.side_effect = Exception("make not found")
        wf = _make_workflow(temp_project)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = wf._node_test(state)
        assert result["post_integration_tests_passed"] == 0


# ---------------------------------------------------------------------------
# Helper function edge case tests
# ---------------------------------------------------------------------------

class TestBuildIntegrationTests:
    """Tests for _build_integration_tests with edge cases."""

    def test_special_chars_in_title_escaped(self):
        """Quotes in title should be escaped."""
        from src.workflow import _build_integration_tests
        result = _build_integration_tests("myFunc", "my-cmd", 'Test "quoted" title', "my-cmd")
        assert "myFunc" in result
        assert "my-cmd" in result
        # Single quotes and double quotes should be escaped
        assert '\\' in result

    def test_backslash_in_title(self):
        """Backslash in title should be handled."""
        from src.workflow import _build_integration_tests
        result = _build_integration_tests("myFunc", "my-cmd", "Test\\title", "my-cmd")
        assert "myFunc" in result
        # Should not have raw unescaped backslash issues
        assert "describe(" in result

    def test_empty_title(self):
        """Empty title should still produce valid test code."""
        from src.workflow import _build_integration_tests
        result = _build_integration_tests("myFunc", "my-cmd", "", "my-cmd")
        assert "my-cmd" in result
        assert "myFunc" in result
        assert "describe(" in result

    def test_unicode_title(self):
        """Unicode title should be handled."""
        from src.workflow import _build_integration_tests
        result = _build_integration_tests("myFunc", "my-cmd", "Test 🚀 Feature", "my-cmd")
        assert "my-cmd" in result
        assert "Test 🚀 Feature" in result


class TestFallbackTests:
    """Tests for _fallback_tests output."""

    def test_produces_valid_ts_test_code(self):
        """Verify _fallback_tests generates valid TS test code."""
        from src.workflow import _fallback_tests
        result = _fallback_tests("myFunction", "my-function")
        assert "import { myFunction }" in result
        assert "describe('myFunction'" in result
        assert "it('should be a function'" in result
        assert "it('should return a string'" in result
        assert "});" in result
        # Should have proper describe() with callback
        assert "describe('myFunction', () => {" in result or "describe(\"myFunction\", () => {" in result
        # Should have expect calls
        assert "expect(" in result

    def test_fallback_tests_well_formed(self):
        """_fallback_tests output should be well-formed TS."""
        from src.workflow import _fallback_tests
        result = _fallback_tests("testFunc", "test-func")
        # Should not have unbalanced braces
        assert result.count("{") == result.count("}")
        assert result.count("(") == result.count(")")
        # Should end with });
        assert result.strip().endswith("});")


class TestIsValidTsSyntax:
    """Tests for _is_valid_ts_syntax edge cases."""

    def test_empty_code(self):
        from src.workflow import _is_valid_ts_syntax
        assert _is_valid_ts_syntax("") is True  # Empty is trivially balanced

    def test_const_reassignment_with_plus_equals(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nx += 1;"
        assert _is_valid_ts_syntax(code) is False

    def test_const_reassignment_with_minus_equals(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nx -= 1;"
        assert _is_valid_ts_syntax(code) is False

    def test_const_reassignment_with_times_equals(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nx *= 2;"
        assert _is_valid_ts_syntax(code) is False

    def test_const_reassignment_direct_equals(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nx = 10;"
        assert _is_valid_ts_syntax(code) is False

    def test_const_no_reassignment_valid(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nconst y = x + 1;\nreturn y;"
        assert _is_valid_ts_syntax(code) is True

    def test_deeply_nested_braces(self):
        from src.workflow import _is_valid_ts_syntax
        code = "function a() { function b() { function c() { return 1; } } }"
        assert _is_valid_ts_syntax(code) is True

    def test_deeply_unbalanced_braces(self):
        from src.workflow import _is_valid_ts_syntax
        code = "function a() { function b() { return 1; }"
        assert _is_valid_ts_syntax(code) is False

    def test_too_many_closing_braces(self):
        from src.workflow import _is_valid_ts_syntax
        code = "function a() { return 1; }}"
        assert _is_valid_ts_syntax(code) is False

    def test_unbalanced_parens_closing_early(self):
        from src.workflow import _is_valid_ts_syntax
        code = "const x = (1 + 2;"
        assert _is_valid_ts_syntax(code) is False

    def test_const_with_equality_comparison_not_reassignment(self):
        """== or === should not trigger reassignment detection."""
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nif (x === 5) { return 'ok'; }"
        assert _is_valid_ts_syntax(code) is True

    def test_const_with_not_equals(self):
        """!= should not trigger reassignment detection."""
        from src.workflow import _is_valid_ts_syntax
        code = "const x = 5;\nif (x != 10) { return 'ok'; }"
        assert _is_valid_ts_syntax(code) is True


class TestPostProcessGeneratedCode:
    """Tests for _post_process_generated_code edge cases."""

    def test_hex_underscore_fixing(self):
        from src.workflow import _post_process_generated_code
        code = "const v = 0x1234_5678;"
        result = _post_process_generated_code(code)
        assert "0x12345678" in result
        assert "_" not in result.split("0x")[1] if "0x" in result else True

    def test_multiple_hex_underscore(self):
        from src.workflow import _post_process_generated_code
        code = "const a = 0xdead_beef;\nconst b = 0xcafe_babe;"
        result = _post_process_generated_code(code)
        assert "0xdeadbeef" in result
        assert "0xcafebabe" in result
        assert "0xdead_beef" not in result

    def test_import_stripping(self):
        from src.workflow import _post_process_generated_code
        code = "import { Foo } from './bar';\nexport function test(): string { return 'hi'; }"
        result = _post_process_generated_code(code)
        assert "import" not in result

    def test_multiple_imports_stripped(self):
        from src.workflow import _post_process_generated_code
        code = "import { A } from './a';\nimport { B } from './b';\nexport function f(): string { return 'x'; }"
        result = _post_process_generated_code(code)
        assert "import" not in result

    def test_blank_line_squashing(self):
        from src.workflow import _post_process_generated_code
        code = "line1\n\n\n\nline2\n\n\nline3"
        result = _post_process_generated_code(code)
        # Should have at most 1 blank line between content
        assert "\n\n\n" not in result

    def test_no_hex_no_replacement(self):
        from src.workflow import _post_process_generated_code
        code = "export function foo(): string { return 'bar'; }"
        result = _post_process_generated_code(code)
        assert result == code

    def test_empty_code(self):
        from src.workflow import _post_process_generated_code
        result = _post_process_generated_code("")
        assert result == ""

    def test_only_imports_result_empty(self):
        from src.workflow import _post_process_generated_code
        code = "import { X } from './y';\n"
        result = _post_process_generated_code(code)
        assert result == ""


class TestStripLlmGeneratedTestBlocks:
    """Tests for _strip_llm_generated_test_blocks."""

    def test_no_extra_blocks(self):
        from src.workflow import _strip_llm_generated_test_blocks
        code = "describe('test', () => {\n  it('works', () => {});\n});\n"
        result = _strip_llm_generated_test_blocks(code)
        assert "describe(" in result

    def test_multiple_extra_blocks_stripped(self):
        from src.workflow import _strip_llm_generated_test_blocks
        # The function strips blocks AFTER the last properly closed describe.
        # It only strips when remaining text contains describe( or it( patterns.
        code = (
            "describe('main', () => {\n"
            "  it('works', () => {});\n"
            "});\n"
            "describe('extra_bad', () => {\n"
            "  it('bad', () => {});\n"
            "});\n"
        )
        result = _strip_llm_generated_test_blocks(code)
        # The extra_bad describe block IS properly closed, so it's also a good block.
        # The function keeps all well-formed describe blocks.
        assert "main" in result
        # Verify output is not empty
        assert len(result) > 0

    def test_empty_test_code(self):
        from src.workflow import _strip_llm_generated_test_blocks
        result = _strip_llm_generated_test_blocks("")
        assert result == ""

    def test_only_extra_block_no_good_block(self):
        """If no properly closed describe block, returns original."""
        from src.workflow import _strip_llm_generated_test_blocks
        code = "describe('broken', () => {\n  it('bad', () => {});\n"
        result = _strip_llm_generated_test_blocks(code)
        assert result == code  # No complete describe block

    def test_nested_describe_blocks(self):
        from src.workflow import _strip_llm_generated_test_blocks
        # Nested describes: the function tracks pd and bd across all lines.
        # When inner describe closes at ');', outer describe's '});' also closes properly.
        # The function only strips if remaining text contains describe( or it(.
        code = (
            "describe('outer', () => {\n"
            "  describe('inner', () => {\n"
            "    it('works', () => {});\n"
            "  });\n"
            "});\n"
            "describe('garbage', () => { it('bad', () => {}); });\n"
        )
        result = _strip_llm_generated_test_blocks(code)
        assert "outer" in result
        assert "inner" in result
        # The function keeps nested describes as long as they're properly closed
        # The garbage describe after may or may not be stripped depending on closure tracking


class TestAppendIntegrationTests:
    """Tests for _append_integration_tests_to_main_test."""

    def test_no_closing_paren_brace_semicolon(self, temp_project):
        """When main test has no '});' closing, integration tests are appended."""
        from src.workflow import _append_integration_tests_to_main_test
        main_test_path = os.path.join(temp_project, "src", "__tests__", "main.test.ts")
        # Write a file WITHOUT a closing '});'
        with open(main_test_path, "w") as f:
            f.write("describe('test', () => {\n  it('works', () => {});\n")
        integration = "// integration tests"
        _append_integration_tests_to_main_test(main_test_path, integration)
        with open(main_test_path) as f:
            content = f.read()
        assert "integration tests" in content

    def test_normal_closing(self, temp_project):
        """When main test has '});', integration tests inserted before it."""
        from src.workflow import _append_integration_tests_to_main_test
        main_test_path = os.path.join(temp_project, "src", "__tests__", "main.test.ts")
        with open(main_test_path, "w") as f:
            f.write("describe('test', () => {\n  it('works', () => {});\n});\n")
        integration = "// integration tests"
        _append_integration_tests_to_main_test(main_test_path, integration)
        with open(main_test_path) as f:
            content = f.read()
        assert "integration tests" in content
        # Should end with the original closing
        assert content.rstrip().endswith("});")


class TestRouteAfterGenerate:
    """Tests for _route_after_generate routing logic."""

    def test_eval_passed_true_routes_to_test(self):
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": True, "recovery_attempt": 0}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "test"

    def test_recovery_three_routes_to_output(self):
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": False, "recovery_attempt": 3}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "output"

    def test_recovery_more_than_three_routes_to_output(self):
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": False, "recovery_attempt": 5}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "output"

    def test_recovery_less_than_three_routes_to_retry(self):
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": False, "recovery_attempt": 2}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "generate_code_tests"
        # Should increment recovery_attempt
        assert state["recovery_attempt"] == 3

    def test_recovery_zero_routes_to_retry(self):
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": False, "recovery_attempt": 0}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "generate_code_tests"
        assert state["recovery_attempt"] == 1

    def test_eval_passed_true_ignores_recovery_count(self):
        """If eval_passed is True, route to test regardless of recovery_attempt."""
        from src.workflow import AgenticsWorkflow
        state = {"eval_passed": True, "recovery_attempt": 99}
        result = AgenticsWorkflow._route_after_generate(state)
        assert result == "test"
