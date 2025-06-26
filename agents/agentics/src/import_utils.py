import re
from typing import List, Dict, Optional, Tuple

def clean_code_body(code: str) -> str:
    """Remove comments and string literals from code to prevent false symbol usage detection."""
    # Remove block comments (/* ... */)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Remove line comments (// ...)
    code = re.sub(r'//.*', '', code)
    # Remove string literals (simplified: single and double quotes, no escaped quotes)
    code = re.sub(r"'[^']*'", "", code)
    code = re.sub(r'"[^"]*"', "", code)
    return code

def parse_import(line: str) -> Optional[Dict]:
    """Parse a TypeScript import statement, normalizing whitespace."""
    line = line.strip()  # Remove leading/trailing whitespace
    # Default import: e.g., import Plugin from 'obsidian';
    match = re.match(r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"];", line)
    if match:
        return {'type': 'default', 'module': match.group(2), 'symbol': match.group(1)}
    
    # Named import: e.g., import { App, Plugin as MyPlugin } from 'obsidian';
    match = re.match(r"import\s+\{\s*([\w,\s]+)\s*\}\s+from\s+['\"]([^'\"]+)['\"];", line)
    if match:
        symbols_str = match.group(1)
        module = match.group(2)
        symbols = []
        for sym in re.finditer(r"(\w+)(?:\s+as\s+(\w+))?", symbols_str):
            original = sym.group(1)
            alias = sym.group(2)
            symbols.append({'original': original, 'alias': alias})
        return {'type': 'named', 'module': module, 'symbols': symbols}
    
    # Namespace import: e.g., import * as obsidian from 'obsidian';
    match = re.match(r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"];", line)
    if match:
        return {'type': 'namespace', 'module': match.group(2), 'symbol': match.group(1)}
    
    # Side-effect import: e.g., import 'module';
    match = re.match(r"import\s+['\"]([^'\"]+)['\"];", line)
    if match:
        return {'type': 'side-effect', 'module': match.group(1)}
    
    return None

def is_symbol_used(symbol: str, code_body: str, is_namespace: bool = False) -> bool:
    """Check if a symbol is used in the code body, excluding strings and comments."""
    cleaned_code = clean_code_body(code_body)
    pattern = r"\b" + re.escape(symbol) + r"\.\w+" if is_namespace else r"\b" + re.escape(symbol) + r"\b"
    return bool(re.search(pattern, cleaned_code))

def reconstruct_import(imp: Dict) -> str:
    """Reconstruct an import statement with standardized spacing."""
    if imp['type'] == 'side-effect':
        return f"import '{imp['module']}';"
    elif imp['type'] == 'default':
        return f"import {imp['symbol']} from '{imp['module']}';"
    elif imp['type'] == 'namespace':
        return f"import * as {imp['symbol']} from '{imp['module']}';"
    elif imp['type'] == 'named':
        symbols_str = ', '.join(
            f"{sym['original']} as {sym['alias']}" if sym['alias'] else sym['original']
            for sym in imp['symbols']
        )
        return f"import {{ {symbols_str} }} from '{imp['module']}';"

def filter_imports(code: str) -> Tuple[str, List[str]]:
    """Filter unused imports from the code and track new modules, excluding comments from code body."""
    lines = code.split('\n')
    import_lines = []
    code_body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import'):
            parsed = parse_import(line)
            if parsed:
                import_lines.append(line)
            else:
                code_body_lines.append(line)
        elif not stripped.startswith('//'):  # Exclude standalone comment lines
            code_body_lines.append(line)
    code_body = '\n'.join(code_body_lines)

    imports = [parse_import(line) for line in import_lines if parse_import(line)]
    filtered_imports = []
    new_modules = set()

    for imp in imports:
        if imp['type'] == 'side-effect':
            filtered_imports.append(imp)
            new_modules.add(imp['module'])
        elif imp['type'] == 'default':
            if is_symbol_used(imp['symbol'], code_body):
                filtered_imports.append(imp)
                new_modules.add(imp['module'])
        elif imp['type'] == 'namespace':
            if is_symbol_used(imp['symbol'], code_body, is_namespace=True):
                filtered_imports.append(imp)
                new_modules.add(imp['module'])
        elif imp['type'] == 'named':
            used_symbols = [
                sym for sym in imp['symbols']
                if is_symbol_used(sym['alias'] or sym['original'], code_body)
            ]
            if used_symbols:
                filtered_imports.append({'type': 'named', 'module': imp['module'], 'symbols': used_symbols})
                new_modules.add(imp['module'])

    filtered_import_lines = [reconstruct_import(imp) for imp in filtered_imports]
    filtered_code = '\n'.join(filtered_import_lines + code_body_lines)
    return filtered_code, list(new_modules)
