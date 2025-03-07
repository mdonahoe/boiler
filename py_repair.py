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


# T0DO(matt): annotate global constatnts
class LineAnnotator(ast.NodeVisitor):
    """
    Attempt to label every line of code.
    Currently supports the following:
    * class
    * function
    * decorator
    * import / alias

    Each line of code will have a list of labels.
    """

    def __init__(self, code: str) -> None:
        self.code: T.List[str] = code.splitlines()  # Split code into individual lines
        self.annotations: T.List[T.List[str]] = [[] for _ in range(len(self.code))]

    def annotate(self) -> T.List[T.List[str]]:
        tree = ast.parse("\n".join(self.code))
        self.visit(tree)  # Visit each node in the AST
        return self.annotations

    def annotate_lines(self, node: T.Any, labels: T.List[str]) -> None:
        start_line = node.lineno - 1
        end_line = getattr(node, "end_lineno", node.lineno) - 1
        for lineno in range(start_line, end_line + 1):
            self.annotations[lineno].extend(labels)

    def visit_Import(self, node: T.Any) -> None:
        first = node.names[0]
        labels = []
        for name in node.names:
            if name.asname is not None:
                labels.append(f"import:{name.name}")
                labels.append(f"alias:{name.asname}")
            else:
                labels.append(f"import:{name.name}")
        self.annotate_lines(node, labels)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: T.Any) -> None:
        labels = []
        for name in node.names:
            if name.asname is not None:
                labels.append(f"import:{name.name}")
                labels.append(f"alias:{name.asname}")
            else:
                labels.append(f"import:{name.name}")
        self.annotate_lines(node, labels)
        self.generic_visit(node)

    def get_decorator_name(self, n: T.Any) -> str:
        if hasattr(n, "attr"):
            # ast.Attribute
            return self.get_decorator_name(n.value) + "." + n.attr
        elif hasattr(n, "id"):
            # ast.Name
            return n.id
        elif hasattr(n, "func"):
            # ast.Call
            return self.get_decorator_name(n.func)
        else:
            print("Unsupported decorator node")
            print(
                ", ".join(
                    f"n.{k} = {getattr(n, k)}" for k in dir(n) if not k.startswith("_")
                )
            )
            # import pdb; pdb.set_trace()
            raise ValueError(n)

    def visit_FunctionDef(self, node: T.Any) -> None:
        self.annotate_lines(node, [f"function:{node.name}"])
        for decorator in node.decorator_list:
            name = self.get_decorator_name(decorator)
            self.annotate_lines(
                decorator, [f"function:{node.name}", f"decorator:{name}"]
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: T.Any) -> None:
        self.annotate_lines(node, [f"class:{node.name}"])
        for decorator in node.decorator_list:
            name = self.get_decorator_name(decorator)
            self.annotate_lines(decorator, [f"class:{node.name}", f"decorator:{name}"])
        self.generic_visit(node)


def pattern_match(
    patterns: T.Set[str], labels: T.List[str]
) -> T.Optional[T.Tuple[str, str]]:
    """Compare a set of regex patterns to a list of labels and return if any match"""
    for label in labels:
        for pattern in patterns:
            if re.match(pattern, label):
                return (pattern, label)
    return None


def get_labels(code: str) -> T.Set[str]:
    """Return all the annotations in the code"""
    annotator = LineAnnotator(code)
    annotations = annotator.annotate()
    all_labels = set()
    for line_annotations in annotations:
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
        print("err:", r.stderr)
        print(r)
        raise ValueError("failed to get repo code for {filename}")
    return index_code, git_code


def filter_code(
    code: str, patterns: T.Set[str], verbose: bool = False
) -> T.Generator[str, None, None]:
    """Remove lines from code that doesn't match the set of syntactic patterns"""
    annotator = LineAnnotator(code)
    annotations = annotator.annotate()
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


def repair(
    filename: str, commit: str, missing: T.Optional[str] = None, verbose: bool = False
) -> None:
    """Restore deleted lines to a file that match the `missing` pattern."""
    print(f"repairing {filename} from {commit} missing {missing}")
    index_code, git_code = get_codes(filename, commit)
    raw_labels = get_labels(index_code)
    allowed_patterns = {x for x in raw_labels if not x.startswith("decorator:")}
    if missing is not None:
        if ":" not in missing:
            # Assume this is just a name, and match types that introduce names.
            missing = "(class|function|import|alias):" + missing
        allowed_patterns.add(missing)
    lines = list(filter_code(git_code, allowed_patterns, verbose=verbose))
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
