"""
Line Repair

Restores lines to a python file based on syntactic pattern-matching.

Example Usage:
    python3 src_repair.py path/to/myfile.py --missing foobar

That will restore any lines of codewith imports, classes or functions named
`foobar`.

How it Works:
1. The on-disk file is read, and the `type:name` labels for each line are stored
    as the `allowed_patterns`.
2. The `--missing` command line argument is used to add a new allowed pattern.
3. The git-version of the file is read to get the original code.
4. Each line of the original code is annotated, and those annotations are
    compared to the allowed_patterns.
5. If a line of the original code doesn't match the patterned, it is excluded.
6. All included lines are written to disk.

Note:
One nuance is that lines of code can have nested contexts for the syntax labels.
For example, a class `Foo` might define a method `do_bar`. During parsing,
do_bar is reported as a function and given the label `function:do_bar`. If only
the lines associated with `function:do_bar` are restored, but not the definition
of the surrounding class `Foo`, it may result in invalid python syntax due to
indentation.

To account for this, the annotations for each line are a nested list.
When determining if a line should be included, all layers of the nesting must
match at least one pattern in the allowed_patterns.

So the `do_bar` method would not be written to disk unless the `class:Foo` and
`function:do_bar` patterns are defined in the allowed_patterns.
"""

import argparse
import os
import re
import subprocess
import sys
import typing as T

# Add pipeline to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from src.pipeline.utils import is_verbose


def pattern_match(
    patterns: T.Set[str], labels: T.List[str]
) -> T.Optional[T.Tuple[str, str]]:
    """Compare a set of regex patterns to a list of labels and return if any match"""
    for label in labels:
        for pattern in patterns:
            if re.match(pattern, label):
                return (pattern, label)
    return None


def _annotate(code: str, lang: str) -> T.List[T.List[str]]:
    if lang == "python":
        return get_python_code_annotations(code)
    if lang == "c":
        return get_c_code_annotations(code)
    return []


def get_labels(code: str, lang: str) -> T.Set[str]:
    """Return all the annotations in the code"""
    all_labels = set()
    for line_annotations in _annotate(code, lang):
        for label in line_annotations:
            all_labels.add(label)
    return all_labels


def _get_relative_path(file_path: str) -> str:
    current_dir = os.path.abspath(os.curdir)
    return os.path.relpath(file_path, current_dir)


def get_codes(filename: str, commit: str) -> T.Tuple[str, str]:
    """Return the on-disk and git-version of the given file"""
    repo_path = _get_relative_path(filename)
    if os.path.exists(filename):
        with open(filename) as sourcefile:
            index_code = sourcefile.read()
    else:
        if is_verbose():
            print(f"No file: {filename}")
        # restore with git so folders and permissions are correct
        r = subprocess.run(["git", "checkout", repo_path])
        if r.returncode != 0:
            raise RuntimeError(f"failed to restore {repo_path}")

        # clear it out
        with open(filename, "w") as x:
            pass

        index_code = ""

    r = subprocess.run(["git", "show", f"{commit}:{repo_path}"], capture_output=True)
    if r.returncode == 0:
        git_code = r.stdout.decode("utf-8")
    else:
        if is_verbose():
            print("err:", r.stderr)
            print(r)
        raise ValueError("failed to get repo code for {filename}")
    return index_code, git_code


def get_python_code_annotations(code_str) -> T.List[T.List[str]]:
    import json
    import tempfile

    # Initialize annotations list based on number of lines in code
    lines = code_str.splitlines()
    annotations = [[] for _ in range(len(lines))]

    # Write code to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code_str)
        temp_filename = f.name

    try:
        # Run tree_print to get AST as JSON
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        tree_print_path = os.path.join(repo_root, "print-tree", "tree_print")
        result = subprocess.run(
            [tree_print_path, "--json", temp_filename],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            if is_verbose():
                print(f"tree_print failed: {result.stderr}")
            return annotations

        # Parse JSON output
        ast_data = json.loads(result.stdout)

        # Walk the AST and annotate lines
        def walk_ast(node, parent_labels=None):
            if parent_labels is None:
                parent_labels = []

            node_type = node.get("type", "")

            # Handle import statements: import os, import bar as baz
            if node_type == "import_statement":
                # Find imported names and aliases
                for child in node.get("children", []):
                    if child.get("type") == "dotted_name":
                        # Simple import: import os
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "identifier":
                                import_name = subchild.get("text", "")
                                # Annotate all lines in this import statement
                                start_line = node.get("start", {}).get("row", 0)
                                end_line = node.get("end", {}).get("row", 0)
                                for lineno in range(start_line, end_line + 1):
                                    if 0 <= lineno < len(annotations):
                                        annotations[lineno].append(f"import:{import_name}")
                    elif child.get("type") == "aliased_import":
                        # Aliased import: import bar as baz
                        import_name = None
                        alias_name = None
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "dotted_name":
                                # Get the original import name
                                for subsubchild in subchild.get("children", []):
                                    if subsubchild.get("type") == "identifier":
                                        import_name = subsubchild.get("text", "")
                            elif subchild.get("type") == "identifier":
                                # This is the alias (comes after 'as')
                                alias_name = subchild.get("text", "")

                        # Annotate with both import and alias
                        start_line = node.get("start", {}).get("row", 0)
                        end_line = node.get("end", {}).get("row", 0)
                        for lineno in range(start_line, end_line + 1):
                            if 0 <= lineno < len(annotations):
                                if import_name:
                                    annotations[lineno].append(f"import:{import_name}")
                                if alias_name:
                                    annotations[lineno].append(f"alias:{alias_name}")

            # Handle from...import statements: from typing import List, from pkg import mod as alias
            elif node_type == "import_from_statement":
                # Track if we've seen the "import" keyword
                seen_import_keyword = False
                import_labels = []

                for child in node.get("children", []):
                    if child.get("type") == "import":
                        seen_import_keyword = True
                        continue

                    # Only process items after "import" keyword
                    if not seen_import_keyword:
                        continue

                    # Handle simple imports: from pkg import name
                    if child.get("type") == "dotted_name":
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "identifier":
                                import_labels.append(f"import:{subchild.get('text', '')}")

                    # Handle aliased imports: from pkg import name as alias
                    elif child.get("type") == "aliased_import":
                        import_name = None
                        alias_name = None
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "dotted_name":
                                # Get the imported name
                                for subsubchild in subchild.get("children", []):
                                    if subsubchild.get("type") == "identifier":
                                        import_name = subsubchild.get("text", "")
                            elif subchild.get("type") == "identifier":
                                # This is the alias (comes after 'as')
                                alias_name = subchild.get("text", "")

                        if import_name:
                            import_labels.append(f"import:{import_name}")
                        if alias_name:
                            import_labels.append(f"alias:{alias_name}")

                # Annotate all lines
                start_line = node.get("start", {}).get("row", 0)
                end_line = node.get("end", {}).get("row", 0)
                for lineno in range(start_line, end_line + 1):
                    if 0 <= lineno < len(annotations):
                        annotations[lineno].extend(import_labels)

            # Handle class definitions
            elif node_type == "class_definition":
                class_name = None
                # Find the class name
                for child in node.get("children", []):
                    if child.get("type") == "identifier":
                        class_name = child.get("text", "")
                        break

                if class_name:
                    # Annotate all lines in this class definition
                    start_line = node.get("start", {}).get("row", 0)
                    end_line = node.get("end", {}).get("row", 0)
                    for lineno in range(start_line, end_line + 1):
                        if 0 <= lineno < len(annotations):
                            annotations[lineno].append(f"class:{class_name}")

                    # Recursively walk with class context
                    for child in node.get("children", []):
                        walk_ast(child, parent_labels + [f"class:{class_name}"])
                    return  # Don't walk children again

            # Handle function definitions
            elif node_type == "function_definition":
                func_name = None
                # Find the function name
                for child in node.get("children", []):
                    if child.get("type") == "identifier":
                        func_name = child.get("text", "")
                        break

                if func_name:
                    # Annotate all lines in this function definition
                    start_line = node.get("start", {}).get("row", 0)
                    end_line = node.get("end", {}).get("row", 0)
                    for lineno in range(start_line, end_line + 1):
                        if 0 <= lineno < len(annotations):
                            annotations[lineno].append(f"function:{func_name}")

            # Handle decorated definitions (decorators on classes/functions)
            elif node_type == "decorated_definition":
                # Find decorators and the definition
                decorators = []
                decorated_func_or_class = None
                func_or_class_name = None
                func_or_class_type = None

                for child in node.get("children", []):
                    if child.get("type") == "decorator":
                        # Extract decorator name
                        decorator_name = extract_decorator_name(child)
                        if decorator_name:
                            decorators.append(decorator_name)
                    elif child.get("type") in ("function_definition", "class_definition"):
                        decorated_func_or_class = child
                        func_or_class_type = child.get("type")
                        # Get the name of the function/class
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "identifier":
                                func_or_class_name = subchild.get("text", "")
                                break

                # Annotate decorator lines with both the decorator and the function/class
                for decorator_node in [c for c in node.get("children", []) if c.get("type") == "decorator"]:
                    decorator_name = extract_decorator_name(decorator_node)
                    if decorator_name:
                        start_line = decorator_node.get("start", {}).get("row", 0)
                        end_line = decorator_node.get("end", {}).get("row", 0)
                        for lineno in range(start_line, end_line + 1):
                            if 0 <= lineno < len(annotations):
                                # Add function:name or class:name label
                                if func_or_class_name:
                                    if func_or_class_type == "function_definition":
                                        annotations[lineno].append(f"function:{func_or_class_name}")
                                    elif func_or_class_type == "class_definition":
                                        annotations[lineno].append(f"class:{func_or_class_name}")
                                # Add decorator label
                                annotations[lineno].append(f"decorator:{decorator_name}")

                # Walk the decorated definition
                if decorated_func_or_class:
                    walk_ast(decorated_func_or_class, parent_labels)
                return  # Don't walk children again

            # Recursively walk children
            for child in node.get("children", []):
                walk_ast(child, parent_labels)

        def extract_decorator_name(decorator_node):
            """Extract the decorator name from a decorator node"""
            # Look for identifier or attribute nodes
            for child in decorator_node.get("children", []):
                if child.get("type") == "identifier":
                    return child.get("text", "")
                elif child.get("type") == "attribute":
                    # Handle @foo.bar style decorators
                    parts = []
                    extract_attribute_parts(child, parts)
                    return ".".join(parts)
                elif child.get("type") == "call":
                    # Handle @decorator() style - extract the function name
                    for subchild in child.get("children", []):
                        if subchild.get("type") == "identifier":
                            return subchild.get("text", "")
                        elif subchild.get("type") == "attribute":
                            parts = []
                            extract_attribute_parts(subchild, parts)
                            return ".".join(parts)
            return None

        def extract_attribute_parts(attr_node, parts):
            """Recursively extract parts of an attribute (e.g., foo.bar.baz)"""
            for child in attr_node.get("children", []):
                if child.get("type") == "identifier":
                    parts.append(child.get("text", ""))
                elif child.get("type") == "attribute":
                    extract_attribute_parts(child, parts)

        # Start walking from root
        walk_ast(ast_data)

    finally:
        # Clean up temporary file
        os.unlink(temp_filename)

    return annotations


def get_c_code_annotations(code_str) -> T.List[T.List[str]]:
    import json
    import tempfile

    # Initialize annotations list based on number of lines in code
    lines = code_str.splitlines()
    annotations = [[] for _ in range(len(lines))]

    # Write code to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
        f.write(code_str)
        temp_filename = f.name

    try:
        # Run tree_print to get AST as JSON
        # print-tree is in the repository root, not in src/ or src/tools/
        # Since we're now in src/tools/, go up two directories to get to repo root
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        tree_print_path = os.path.join(repo_root, "print-tree", "tree_print")
        result = subprocess.run(
            [tree_print_path, "--json", temp_filename],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            if is_verbose():
                print(f"tree_print failed: {result.stderr}")
            return annotations

        # Parse JSON output
        ast_data = json.loads(result.stdout)

        # Walk the AST and annotate lines
        def walk_ast(node):
            node_type = node.get("type", "")

            # Handle #include statements
            if node_type == "preproc_include":
                # Find the include name from children
                include_name = None
                for child in node.get("children", []):
                    child_type = child.get("type", "")
                    if child_type == "system_lib_string":
                        # Extract name from <stdio.h> format
                        text = child.get("text", "")
                        include_name = text.strip("<>")
                    elif child_type == "string_literal":
                        # Extract name from "something.h" format
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "string_content":
                                include_name = subchild.get("text", "")

                if include_name:
                    # Annotate all lines in this include statement
                    # Tree-sitter uses 0-indexed rows, end row/column is exclusive
                    start_line = node.get("start", {}).get("row", 0)
                    end_line = node.get("end", {}).get("row", 0)
                    # If end column is 0, it means the previous line is the last line
                    end_col = node.get("end", {}).get("column", 0)
                    if end_col == 0 and end_line > 0:
                        end_line -= 1
                    for lineno in range(start_line, end_line + 1):
                        if 0 <= lineno < len(annotations):
                            annotations[lineno].append(f"include:{include_name}")

            # Handle function definitions
            elif node_type == "function_definition":
                # Find the function name from the function_declarator
                func_name = None
                for child in node.get("children", []):
                    if child.get("type") == "function_declarator":
                        # Direct function declarator
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "identifier":
                                func_name = subchild.get("text", "")
                    elif child.get("type") == "pointer_declarator":
                        # Pointer return type (e.g., char* foo())
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "function_declarator":
                                for subsubchild in subchild.get("children", []):
                                    if subsubchild.get("type") == "identifier":
                                        func_name = subsubchild.get("text", "")

                if func_name:
                    # Annotate all lines in this function definition
                    # Tree-sitter uses 0-indexed rows, end row/column is exclusive
                    start_line = node.get("start", {}).get("row", 0)
                    end_line = node.get("end", {}).get("row", 0)
                    # If end column is 0, it means the previous line is the last line
                    end_col = node.get("end", {}).get("column", 0)
                    if end_col == 0 and end_line > 0:
                        end_line -= 1
                    for lineno in range(start_line, end_line + 1):
                        if 0 <= lineno < len(annotations):
                            annotations[lineno].append(f"function:{func_name}")

            # Recursively walk children
            for child in node.get("children", []):
                walk_ast(child)

        # Start walking from root
        walk_ast(ast_data)

    finally:
        # Clean up temporary file
        os.unlink(temp_filename)

    return annotations


def filter_code(
        code: str, patterns: T.Set[str], verbose: bool = False, lang: str = "python"
) -> T.Generator[str, None, None]:
    """Remove lines from code that doesn't match the set of syntactic patterns"""
    annotations = _annotate(code, lang)
    for lineno, (line, labels) in enumerate(
        zip(code.splitlines(), annotations), start=1
    ):
        # include any line without tags.
        include = True
        if not labels:
            match = None
            include = True
        else:
            match = pattern_match(patterns, labels)
            include = bool(match)
        label = "+" if include else "-"
        if verbose:
            print(f" {label} {lineno}: {match} = {labels} -> {line}")
        if include:
            yield line


def _infer_language(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if ext == ".py":
        return "python"
    elif ext in (".h", ".c"):
        # *might* be c
        return "c"
    else:
        raise ValueError(filename, ext)

def repair(
    filename: str, commit: str, missing: T.Optional[str] = None, verbose: bool = False
) -> None:
    """Restore deleted lines to a file that match the `missing` pattern."""
    if is_verbose():
        print(f"repairing {filename} from {commit} missing {missing}")
    lang = _infer_language(filename)
    index_code, git_code = get_codes(filename, commit)
    raw_labels = get_labels(index_code, lang)
    allowed_patterns = {x for x in raw_labels if not x.startswith("decorator:")}
    if missing is not None:
        if ":" not in missing:
            # Assume this is just a name, and match types that introduce names.
            if lang == "python":
                missing = "(class|function|import|alias):" + missing
            elif lang == "c":
                missing = "(function|include):" + missing
            else:
                raise ValueError(lang)
        allowed_patterns.add(missing)
    lines = list(filter_code(git_code, allowed_patterns, verbose=verbose, lang=lang))
    with open(filename, "w") as f:
        for line in lines:
            f.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename")
    parser.add_argument("--commit")
    parser.add_argument("--missing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    repair(args.filename, args.commit, args.missing, args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
