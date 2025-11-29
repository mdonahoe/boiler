#!/usr/bin/env python3
import unittest
import subprocess
import sys
import os
import difflib

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from py_repair import filter_code, get_labels, LineAnnotator


EXAMPLE_C = """
// some comment
#include "something.h"
int x = 1;
int foo() {
    return 0;
};
int bar() { return 1; };
const char* name = "hello world";
// the end
"""


EXAMPLE_PY = """
import some_package
import typing as T
from another_package import a_module as diff_name
# define X
X = 1
@some_package.a_decorator
@another
def bar():
    y = 1
    def baz():
        pass
    return 1

@dataclass
class Dog:
    "man's best friend"
    name: str
    age: int

    @verb
    def bark(self) -> str:
        return "woof"

@dataclasses.dataclass(frozen=True)
class Cat:
    "meow"
    name: str
    age: int
    claws: bool
"""

class PyRepairTest(unittest.TestCase):
    def test_annotations(self) -> None:
        """
        Ensure a complicated example has expected line annotations
        """
        code = EXAMPLE_PY
        annotator = LineAnnotator(code)
        annotations = annotator.annotate()
        expected = [
            [],  # blank line
            ["import:some_package"],  # import
            ["import:typing", "alias:T"],  # import
            ["import:a_module", "alias:diff_name"],  # import
            [],  # comment
            [],  # variable def
            ["function:bar", "decorator:some_package.a_decorator"],  # attr decorator
            ["function:bar", "decorator:another"],  # simple decorator
            ["function:bar"],  # function signature
            ["function:bar"],  # function body, y = 1
            ["function:bar", "function:baz"],  # function body and another function def
            ["function:bar", "function:baz"],  # function body and another function body
            ["function:bar"],  # function body and another function body
            [],  # blank line
            ["class:Dog", "decorator:dataclass"],
            ["class:Dog"],
            ["class:Dog"],
            ["class:Dog"],
            ["class:Dog"],
            ["class:Dog"],
            ["class:Dog", "function:bark", "decorator:verb"],
            ["class:Dog", "function:bark"],
            ["class:Dog", "function:bark"],
            [],  # blank
            ["class:Cat", "decorator:dataclasses.dataclass"],
            ["class:Cat"],
            ["class:Cat"],
            ["class:Cat"],
            ["class:Cat"],
            ["class:Cat"],
        ]
        self.assertEqual(expected, annotations)

    def test_empty_patterns(self) -> None:
        """
        We should filter out all classes, functions and imports if no patterns are given
        """
        code = """# start
import foo
# define X
X = 1
@foo.whatever
def bar():
    return 1
# end"""
        output = "\n".join(filter_code(code, set(), verbose=True))
        expected = """# start
# define X
X = 1
# end"""
        self.assertMultiLineEqual(expected, output)

    def test_decorators(self) -> None:
        """
        classes, functions and methods should be correctly decorated
        """
        code = """# start
X = 1
@foo
def bar():
    return 1
# end"""
        lines = filter_code(code, {".*foo", ".*bar"}, verbose=True)
        output = "\n".join(lines)
        self.assertMultiLineEqual(code, output)

    def test_import_alias(self) -> None:
        """
        import lines should be included if their 'asname' matches a pattern
        """
        code = """# start
import typing as T
# end"""
        lines = filter_code(code, {"alias:T"}, verbose=True)
        output = "\n".join(lines)
        self.assertMultiLineEqual(code, output)

    def test_get_labels(self) -> None:
        code = """#start
import foo
import bar as baz
@memo
def func(): pass
class Snake:
    def bite(): pass
# end"""
        labels = get_labels(code)
        expected = set([
            "import:foo",
            "import:bar",
            "alias:baz",
            "decorator:memo",
            "function:func",
            "class:Snake",
            "function:bite",
        ])
        self.assertSetEqual(expected, labels)

    def test_filter_code_c(self) -> None:
        """
        Filter c code
        """
        output = "\n".join(filter_code(EXAMPLE_C, set(), language="c"))
        # confirm that all the functions and includes got filtered out
        expected = """// some comment
int x = 1;
const char* name = "hello world";
// the end"""
        self.assertMultiLineEqual(expected, output)


class PythonFeatureTest(unittest.TestCase):
    def test_python_feature_output(self) -> None:
        """
        Run python_feature_test.py and verify output matches expected results
        """
        # Run the python_feature_test.py and capture output
        result = subprocess.run(
            ["python3", "tests/python_feature_test.py"],
            capture_output=True,
            text=True
        )

        # Extract only the printed feature lines (filter out unittest output)
        output_lines = result.stdout.splitlines()

        # Read expected output from python_feature_test.txt
        try:
            with open("tests/python_feature_test.txt", "r") as f:
                expected_lines = [line.rstrip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            self.fail("python_feature_test.txt not found!")

        # Compare the outputs
        if output_lines != expected_lines:
            # Show detailed diff
            diff = difflib.unified_diff(
                expected_lines,
                output_lines,
                fromfile="tests/python_feature_test.txt",
                tofile="actual output",
                lineterm=""
            )
            diff_output = "\n".join(list(diff))

            error_msg = f"python_feature_test.py stdout does not match expected results!\n"
            error_msg += f"Expected {len(expected_lines)} lines, got {len(output_lines)} lines\n\n"
            error_msg += f"Differences:\n{'-' * 80}\n{diff_output}\n"
            error_msg += f"python_feature_test.py exited with code {result.returncode}\n"
            error_msg += f"python_feature_test.py stderr:\n{result.stderr}"

            self.fail(error_msg)


if __name__ == "__main__":
    unittest.main()
