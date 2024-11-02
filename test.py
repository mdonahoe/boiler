import unittest

from py_repair import filter_code, get_labels, LineAnnotator


EXAMPLE = """
import some_package
import typing as T
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
        code = EXAMPLE
        annotator = LineAnnotator(code)
        annotations = annotator.annotate()
        expected = [
            [],  # blank line
            ["import:some_package"],  # import
            ["import:typing", "alias:T"],  # import
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


if __name__ == "__main__":
    unittest.main()
