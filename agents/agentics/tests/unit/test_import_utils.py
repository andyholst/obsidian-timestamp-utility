import pytest
from src.import_utils import filter_imports, parse_import, is_symbol_used, reconstruct_import

# Fixture to normalize code strings by stripping whitespace and ensuring consistent newlines
@pytest.fixture
def normalize_code():
    def _normalize(code):
        return "\n".join(line.strip() for line in code.splitlines() if line.strip())
    return _normalize

# Test cases for filter_imports function
@pytest.mark.parametrize("code, expected_code, expected_modules", [
    # Default Import - Used in Pure Function
    (
        "import Plugin from 'obsidian';\nfunction init() { return new Plugin(); }",
        "import Plugin from 'obsidian';\nfunction init() { return new Plugin(); }",
        ['obsidian']
    ),
    # Default Import - Not Used
    (
        "import Plugin from 'obsidian';\nfunction init() { return 'Hello'; }",
        "function init() { return 'Hello'; }",
        []
    ),
    # Default Import - Used in Class
    (
        "import Plugin from 'obsidian';\nclass MyPlugin extends Plugin { onload() {} }",
        "import Plugin from 'obsidian';\nclass MyPlugin extends Plugin { onload() {} }",
        ['obsidian']
    ),
    # Named Import - Single Symbol Used
    (
        "import { App } from 'obsidian';\nconst app = new App();",
        "import { App } from 'obsidian';\nconst app = new App();",
        ['obsidian']
    ),
    # Named Import - Multiple Symbols, Some Used
    (
        "import { App, Plugin } from 'obsidian';\nconst plugin = new Plugin();",
        "import { Plugin } from 'obsidian';\nconst plugin = new Plugin();",
        ['obsidian']
    ),
    # Named Import - With Alias
    (
        "import { Plugin as MyPlugin } from 'obsidian';\nconst p = new MyPlugin();",
        "import { Plugin as MyPlugin } from 'obsidian';\nconst p = new MyPlugin();",
        ['obsidian']
    ),
    # Named Import - Used in Class Constructor
    (
        "import { App } from 'obsidian';\nclass MyClass { constructor(app: App) {} }",
        "import { App } from 'obsidian';\nclass MyClass { constructor(app: App) {} }",
        ['obsidian']
    ),
    # Namespace Import - Used
    (
        "import * as obsidian from 'obsidian';\nconst p = new obsidian.Plugin();",
        "import * as obsidian from 'obsidian';\nconst p = new obsidian.Plugin();",
        ['obsidian']
    ),
    # Namespace Import - Not Used
    (
        "import * as obsidian from 'obsidian';\nconsole.log('Hello');",
        "console.log('Hello');",
        []
    ),
    # Side-Effect Import
    (
        "import 'side-effect';\nconsole.log('Hello');",
        "import 'side-effect';\nconsole.log('Hello');",
        ['side-effect']
    ),
    # Mixed Imports
    (
        "import Plugin from 'obsidian';\nimport { App } from 'obsidian';\nimport * as utils from './utils';\nimport 'side-effect';\nconst p = new Plugin();\nutils.doSomething();",
        "import Plugin from 'obsidian';\nimport * as utils from './utils';\nimport 'side-effect';\nconst p = new Plugin();\nutils.doSomething();",
        ['obsidian', './utils', 'side-effect']
    ),
    # No Imports
    (
        "function hello() { return 'world'; }",
        "function hello() { return 'world'; }",
        []
    ),
    # Symbol in String Literal (Should not retain import)
    (
        "import Plugin from 'obsidian';\nconsole.log('Plugin is here');",
        "console.log('Plugin is here');",
        []
    ),
    # Symbol in Comment (Should not retain import)
    (
        "import Plugin from 'obsidian';\n// Use Plugin here\nconsole.log('Hello');",
        "console.log('Hello');",
        []
    ),
    # Multiple Imports Same Symbol
    (
        "import { Plugin } from 'module1';\nimport { Plugin } from 'module2';\nconst p = new Plugin();",
        "import { Plugin } from 'module1';\nimport { Plugin } from 'module2';\nconst p = new Plugin();",
        ['module1', 'module2']
    ),
    # Multiline Class with Import
    (
        """
        import Plugin from 'obsidian';
        class MyPlugin extends Plugin {
            onload() {
                console.log('Loaded');
            }
        }
        """,
        """
        import Plugin from 'obsidian';
        class MyPlugin extends Plugin {
            onload() {
                console.log('Loaded');
            }
        }
        """,
        ['obsidian']
    ),
    # Pure Arrow Function with Import
    (
        "import { utils } from './utils';\nconst fn = () => utils.doSomething();",
        "import { utils } from './utils';\nconst fn = () => utils.doSomething();",
        ['./utils']
    ),
    # Malformed Import (Treated as code body)
    (
        "import Plugin from 'obsidian'\nconst p = new Plugin();",
        "import Plugin from 'obsidian'\nconst p = new Plugin();",
        []
    ),
    # New Test: Import Used in Nested Function
    (
        "import { utils } from './utils';\nfunction outer() { function inner() { utils.doSomething(); } }",
        "import { utils } from './utils';\nfunction outer() { function inner() { utils.doSomething(); } }",
        ['./utils']
    ),
    # New Test: Import Used in Class Method
    (
        "import { App } from 'obsidian';\nclass MyClass { method() { const app = new App(); } }",
        "import { App } from 'obsidian';\nclass MyClass { method() { const app = new App(); } }",
        ['obsidian']
    ),
    # New Test: Import with Alias Not Used
    (
        "import { Plugin as MyPlugin } from 'obsidian';\nconsole.log('Hello');",
        "console.log('Hello');",
        []
    ),
    # New Test: Empty Code
    (
        "",
        "",
        []
    ),
    # New Test: Code with Only Comments
    (
        "// This is a comment\n// Another comment",
        "// This is a comment\n// Another comment",
        []
    ),
    # New Test: Import with Multiple Aliases
    (
        "import { App as MyApp, Plugin as MyPlugin } from 'obsidian';\nconst app = new MyApp();\nconst plugin = new MyPlugin();",
        "import { App as MyApp, Plugin as MyPlugin } from 'obsidian';\nconst app = new MyApp();\nconst plugin = new MyPlugin();",
        ['obsidian']
    ),
    # New Test: Import with Partial Alias Usage
    (
        "import { App as MyApp, Plugin } from 'obsidian';\nconst app = new MyApp();",
        "import { App as MyApp } from 'obsidian';\nconst app = new MyApp();",
        ['obsidian']
    ),
    # New Test: Import with Whitespace Variations
    (
        "import   {  App  }   from   'obsidian'  ;\nconst app = new App();",
        "import { App } from 'obsidian';\nconst app = new App();",
        ['obsidian']
    ),
    # New Test: Namespace Import with Multiple Uses
    (
        "import * as obsidian from 'obsidian';\nconst p = obsidian.Plugin;\nconst a = obsidian.App;",
        "import * as obsidian from 'obsidian';\nconst p = obsidian.Plugin;\nconst a = obsidian.App;",
        ['obsidian']
    ),
    # New Test: Import with Trailing Comments
    (
        "import Plugin from 'obsidian'; // This is a plugin\nconst p = new Plugin();",
        "import Plugin from 'obsidian';\nconst p = new Plugin();",
        ['obsidian']
    ),
], ids=[
    "default_used_pure_function",
    "default_not_used",
    "default_used_class",
    "named_single_used",
    "named_partial_used",
    "named_with_alias",
    "named_in_class_constructor",
    "namespace_used",
    "namespace_not_used",
    "side_effect",
    "mixed_imports",
    "no_imports",
    "symbol_in_string",
    "symbol_in_comment",
    "multiple_imports_same_symbol",
    "multiline_class",
    "arrow_function",
    "malformed_import",
    "nested_function",
    "class_method",
    "alias_not_used",
    "empty_code",
    "only_comments",
    "multiple_aliases",
    "partial_alias_usage",
    "whitespace_variations",
    "namespace_multiple_uses",
    "trailing_comments"
])
def test_filter_imports(code, expected_code, expected_modules, normalize_code):
    result_code, result_modules = filter_imports(code)
    assert normalize_code(result_code) == normalize_code(expected_code), f"Expected code:\n{expected_code}\nGot:\n{result_code}"
    assert sorted(result_modules) == sorted(expected_modules), f"Expected modules: {expected_modules}, Got: {result_modules}"

# Tests for individual helper functions
def test_parse_default_import():
    line = "import Plugin from 'obsidian';"
    result = parse_import(line)
    assert result == {'type': 'default', 'module': 'obsidian', 'symbol': 'Plugin'}

def test_parse_named_import():
    line = "import { App, Plugin as MyPlugin } from 'obsidian';"
    result = parse_import(line)
    assert result == {
        'type': 'named',
        'module': 'obsidian',
        'symbols': [
            {'original': 'App', 'alias': None},
            {'original': 'Plugin', 'alias': 'MyPlugin'}
        ]
    }

def test_parse_namespace_import():
    line = "import * as obsidian from 'obsidian';"
    result = parse_import(line)
    assert result == {'type': 'namespace', 'module': 'obsidian', 'symbol': 'obsidian'}

def test_parse_side_effect_import():
    line = "import 'side-effect';"
    result = parse_import(line)
    assert result == {'type': 'side-effect', 'module': 'side-effect'}

def test_is_symbol_used():
    code_body = "const p = new Plugin();"
    assert is_symbol_used("Plugin", code_body) is True
    assert is_symbol_used("App", code_body) is False

def test_is_symbol_used_namespace():
    code_body = "const p = obsidian.Plugin;"
    assert is_symbol_used("obsidian", code_body, is_namespace=True) is True
    assert is_symbol_used("utils", code_body, is_namespace=True) is False

def test_reconstruct_named_import():
    imp = {
        'type': 'named',
        'module': 'obsidian',
        'symbols': [{'original': 'App', 'alias': None}, {'original': 'Plugin', 'alias': 'MyPlugin'}]
    }
    assert reconstruct_import(imp) == "import { App, Plugin as MyPlugin } from 'obsidian';"
