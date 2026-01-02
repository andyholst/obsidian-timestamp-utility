import os
import ast
import re

src_dir = 'agents/agentics/src/'

def get_py_files(src_dir):
    files = []
    for root, dirs, files_in_dir in os.walk(src_dir):
        for file in files_in_dir:
            if file.endswith('.py') and file not in ['__init__.py', 'analyze_usage.py']:
                files.append(os.path.join(root, file))
    return files

def get_module_and_classes(filepath):
    module = os.path.basename(filepath)[:-3]
    classes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
        except SyntaxError:
            pass  # Skip files with syntax errors
    return module, classes

def search_references(other_files, module, classes):
    references = []
    for file in other_files:
        if 'test' in file.lower():  # Exclude test files
            continue
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for relative import from .module
                if re.search(r'from \.' + re.escape(module) + r'\s+import', content):
                    references.append(file)
                    continue
                # Check for class name references
                for cls in classes:
                    if cls in content:
                        references.append(file)
                        break
        except UnicodeDecodeError:
            pass  # Skip binary or non-utf8 files
    return references

def main():
    py_files = get_py_files(src_dir)
    results = {}
    for file in py_files:
        module, classes = get_module_and_classes(file)
        other_files = [f for f in py_files if f != file]
        refs = search_references(other_files, module, classes)
        if not refs:
            results[file] = 'No references'
        else:
            results[file] = refs

    print("Files with no references:")
    no_refs = [file for file, status in results.items() if status == 'No references']
    if no_refs:
        for file in no_refs:
            print(file)
    else:
        print("All files have references.")

if __name__ == '__main__':
    main()