"""
Line Repair

Restores lines to a python file based on syntactic pattern-matching.

Example Usage:
    python3 py_repair.py path/to/myfile.py --missing foobar

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
import ast
import os
import re
import subprocess
import sys
import typing as T


# TODO(matt): add decorator support for functions and classes
# T0DO(matt): annotate global constatnts
class LineAnnotator(ast.NodeVisitor):
    def __init__(self, code):
        self.code = code.splitlines()  # Split code into individual lines
        self.annotations = [[] for _ in range(len(self.code))]

    def annotate(self):
        tree = ast.parse("\n".join(self.code))
        self.visit(tree)  # Visit each node in the AST
        return self.annotations

    def annotate_lines(self, node, labels):
        start_line = node.lineno - 1
        end_line = getattr(node, "end_lineno", node.lineno) - 1
        for lineno in range(start_line, end_line + 1):
            self.annotations[lineno].append(labels)

    # TODO(matt): handle import aliases, with `import typing as T`

    def visit_Import(self, node):
        first = node.names[0]
        print(f"import {first.name} as {first.asname}")
        labels = []
        for name in node.names:
            if name.asname is not None:
                labels.append(f"import:{name.name} as {name.asname}")
            else:
                labels.append(f"import:{name.name}")
        self.annotate_lines(node, labels)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        print(f"from import {dir(node)}")
        self.annotate_lines(node, [f"import:{n.name}" for n in node.names])
        self.generic_visit(node)

    def get_decorator_name(self, n):
        if hasattr(n, "attr"):
            # this is an attribute
            return self.get_decorator_name(n.value) + "." + n.attr
        else:
            return n.id

    def visit_FunctionDef(self, node):
        self.annotate_lines(node, [f"function:{node.name}"])
        for decorator in node.decorator_list:
            name = self.get_decorator_name(decorator)
            self.annotate_lines(decorator, [f"function:{node.name}", f"decorator:{name}"])
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.annotate_lines(node, [f"class:{node.name}"])
        for decorator in node.decorator_list:
            name = self.get_decorator_name(decorator)
            self.annotate_lines(decorator, [f"class:{node.name}", f"decorator:{name}"])
        self.generic_visit(node)


EXAMPLE_PATTERNS = {"function:my_function", "import:path", "class:MyClass"}
EXAMPLE_CODE = """
import os
from sys import (
    path, argv
)

def foo(): pass

class MyClass:
    # this is a comment
    def my_function(self):
        "some string"
        # another comment
        print("Hello, World!")
        def inner_func(): pass
        x = 1
        return fart
    VAR = 2
# cool
x = 1
"""


def pattern_match(patterns: T.Set[str], labels: T.List[str]) -> bool:
    """Return True if any label matches any pattern"""
    for label in labels:
        for pattern in patterns:
            if re.match(pattern, label):
                return (pattern, label)
    return None


def get_labels(code):
    """Return all the annotations in the code"""
    annotator = LineAnnotator(code)
    annotations = annotator.annotate()
    all_labels = set()
    for line_annotations in annotations:
        for labels in line_annotations:
            for label in labels:
                all_labels.add(label)
    return all_labels


def _get_relative_path(file_path: str) -> str:
    current_dir = os.path.abspath(os.curdir)
    return os.path.relpath(file_path, current_dir)


def get_codes(filename):
    """Return the on-disk and git-version of the given file"""
    repo_path = _get_relative_path(filename)
    if os.path.exists(filename):
        print(f"found {filename}")
        with open(filename) as sourcefile:
            index_code = sourcefile.read()
    else:
        print("no file")
        # restore with git so folders and permissions are correct
        r = subprocess.run(["git", "checkout", repo_path])
        if r.returncode != 0:
            raise RuntimeError(f"failed to restore {repo_path}")

        # clear it out
        with open(filename, "w") as x:
            pass

        index_code = ""

    print("relative path: ", repo_path)
    r = subprocess.run(["git", "show", f":{repo_path}"], capture_output=True)
    if r.returncode == 0:
        git_code = r.stdout.decode("utf-8")
    else:
        print("err:", r.stderr)
        print(r)
        raise ValueError("failed to get repo code for {filename}")
    return index_code, git_code


def filter_code(code, patterns, verbose=False):
    """Remove lines from code that doesn't match the set of syntactic patterns"""
    annotator = LineAnnotator(code)
    annotations = annotator.annotate()
    for lineno, (line, annotations) in enumerate(
        zip(code.splitlines(), annotations), start=1
    ):
        # include any line without tags.
        include = True
        match = None
        for labels in annotations:
            match = pattern_match(patterns, labels)
            # fail on the first mismatch
            if not match:
                include = False
                break
        label = "+" if include else "-"
        if verbose:
            print(f" {label} {lineno}: {match} = {annotations} -> {line}")
        if include:
            yield line


def repair(filename: str, missing=None, verbose=False):
    """Restore deleted lines to a file that match the `missing` pattern."""
    index_code, git_code = get_codes(filename)
    allowed_patterns = get_labels(index_code)
    if missing is not None:
        if ":" not in missing:
            # assume this is just a name, and match any type.
            missing = ".*:" + missing
        print(f"adding {missing}")
        allowed_patterns.add(missing)
    print(f"{allowed_patterns=}")
    with open(filename, "w") as f:
        for line in filter_code(git_code, allowed_patterns, verbose=verbose):
            f.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename")
    parser.add_argument("--missing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    repair(args.filename, args.missing, args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
