import unittest

from py_repair import filter_code, LineAnnotator


# TODO(matt): make this file run on save of py_repair.py


class PyRepairTest(unittest.TestCase):
    def test_annotations(self):
        code = """
import foo
# define X
X = 1
@foo.whatever
def bar():
    y = 1
    def baz():
        pass
    return 1
"""
        annotator = LineAnnotator(code)
        annotations = annotator.annotate()
        expected = [
            [], # blank line
            [['import:foo']],  # import
            [], # comment
            [], # variable def
            [['function:bar']],  # decorator
            [['function:bar']], # function signature
            [['function:bar']], # function body, y = 1
            [['function:bar'], ['function:baz']], # function body and another function def
            [['function:bar'], ['function:baz']], # function body and another function body
            [['function:bar']], # function body and another function body
        ]
        self.assertEqual(expected, annotations)

    def test_empty_patterns(self):
        code = """
import foo
# define X
X = 1
@foo.whatever
def bar():
    return 1
"""
        output = "\n".join(filter_code(code, set(), verbose=True))
        expected = """
# define X
X = 1
"""
        self.assertMultiLineEqual(expected, output)

    def test_decorators(self):
        code = """
import foo
X = 1
@foo.whatever
def bar():
    return 1
"""
        lines = filter_code(code, {"foo", "bar"}, verbose=True)
        output = "\n".join(lines)
        self.assertMultiLineEqual(code, output)

    def test_import_alias(self):
        code = \
"""# imports
import typing as T
"""
        lines = filter_code(code, {"T"}, verbose=True)
        output = "\n".join(lines)
        self.assertMultiLineEqual(code, output)

if __name__ == "__main__":
    unittest.main()
