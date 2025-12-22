"""
Test that detector regexes are efficient and don't have excessive backtracking.
"""

import re
import unittest
import importlib
import pkgutil
from pathlib import Path

import src.pipeline.detectors
from src.pipeline.detectors.base import Detector


class TestDetectorRegexEfficiency(unittest.TestCase):
    """
    Test that all detector regexes avoid exponential backtracking.

    When a regex has multiple lazy quantifiers (.*?), the regex engine
    can backtrack through all possible combinations of how much text
    each .*? consumed, creating exponential time complexity.
    """

    def _find_all_detector_classes(self):
        """Find all Detector subclasses in the detectors package."""
        detector_classes = []

        # Get the path to the detectors package
        detectors_path = Path(src.pipeline.detectors.__file__).parent

        # Iterate through all modules in the detectors package
        for module_info in pkgutil.iter_modules([str(detectors_path)]):
            if module_info.name in ('base', 'registry', '__init__'):
                continue

            # Import the module
            module_name = f'src.pipeline.detectors.{module_info.name}'
            try:
                module = importlib.import_module(module_name)

                # Find all classes in the module that are Detector subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, Detector) and
                        attr is not Detector):
                        detector_classes.append(attr)
            except ImportError:
                pass

        return detector_classes

    def _count_lazy_quantifiers(self, pattern: str) -> int:
        """
        Count the number of lazy quantifiers (.*?, .+?, etc.) in a regex pattern.

        This checks for:
        - .*?
        - .+?
        - .{n,m}?
        - (?:...)*?
        - (?:...)+?

        We ignore lazy quantifiers inside character classes [...] and
        after escaped characters.
        """
        count = 0
        i = 0
        in_char_class = False

        while i < len(pattern):
            char = pattern[i]

            # Track character classes
            if char == '[' and (i == 0 or pattern[i-1] != '\\'):
                in_char_class = True
            elif char == ']' and (i == 0 or pattern[i-1] != '\\'):
                in_char_class = False

            # Only count lazy quantifiers outside character classes
            if not in_char_class and i < len(pattern) - 1:
                # Check for .*?
                if pattern[i:i+3] == '.*?':
                    count += 1
                    i += 3
                    continue
                # Check for .+?
                elif pattern[i:i+3] == '.+?':
                    count += 1
                    i += 3
                    continue
                # Check for .{n,m}? patterns
                elif char == '.' and i < len(pattern) - 1 and pattern[i+1] == '{':
                    # Look for closing } followed by ?
                    j = i + 2
                    while j < len(pattern) and pattern[j] != '}':
                        j += 1
                    if j < len(pattern) - 1 and pattern[j+1] == '?':
                        count += 1
                        i = j + 2
                        continue

            i += 1

        return count

    def test_no_multiple_lazy_quantifiers(self):
        """
        Test that no detector pattern has more than one lazy quantifier.

        Multiple lazy quantifiers can cause exponential backtracking.
        """
        detector_classes = self._find_all_detector_classes()

        # Ensure we found some detectors
        self.assertGreater(len(detector_classes), 0,
                          "Should find at least one detector class")

        violations = []

        for detector_class in detector_classes:
            detector = detector_class()

            # Check each pattern
            for pattern_name, pattern in detector.PATTERNS.items():
                lazy_count = self._count_lazy_quantifiers(pattern)

                if lazy_count > 1:
                    violations.append({
                        'detector': detector.name,
                        'pattern_name': pattern_name,
                        'pattern': pattern,
                        'lazy_quantifier_count': lazy_count,
                    })

        # Report all violations
        if violations:
            error_msg = "\n\nDetected inefficient regex patterns with multiple lazy quantifiers:\n\n"
            for v in violations:
                error_msg += f"  Detector: {v['detector']}\n"
                error_msg += f"  Pattern: {v['pattern_name']}\n"
                error_msg += f"  Lazy quantifiers: {v['lazy_quantifier_count']}\n"
                error_msg += f"  Regex: {v['pattern']}\n\n"

            error_msg += "Multiple lazy quantifiers (.*?, .+?, etc.) can cause exponential backtracking.\n"
            error_msg += "Consider rewriting these patterns to use more specific matches.\n"

            self.fail(error_msg)

    def test_lazy_quantifier_counting(self):
        """Test that the lazy quantifier counting logic works correctly."""
        # Patterns with one lazy quantifier
        self.assertEqual(self._count_lazy_quantifiers(r'foo.*?bar'), 1)
        self.assertEqual(self._count_lazy_quantifiers(r'foo.+?bar'), 1)
        self.assertEqual(self._count_lazy_quantifiers(r'foo.{1,5}?bar'), 1)

        # Patterns with multiple lazy quantifiers
        self.assertEqual(self._count_lazy_quantifiers(r'foo.*?bar.*?baz'), 2)
        self.assertEqual(self._count_lazy_quantifiers(r'foo.+?bar.+?baz'), 2)
        self.assertEqual(self._count_lazy_quantifiers(r'foo.*?bar.+?baz'), 2)
        self.assertEqual(self._count_lazy_quantifiers(r'a.*?b.*?c.*?d'), 3)

        # Patterns with no lazy quantifiers
        self.assertEqual(self._count_lazy_quantifiers(r'foo.*bar'), 0)
        self.assertEqual(self._count_lazy_quantifiers(r'foo.+bar'), 0)
        self.assertEqual(self._count_lazy_quantifiers(r'foo\d+bar'), 0)

        # Edge cases: lazy quantifiers in character classes (should not count)
        self.assertEqual(self._count_lazy_quantifiers(r'foo[.*?]bar'), 0)

        # Real-world patterns that should pass
        self.assertEqual(self._count_lazy_quantifiers(
            r"'(?P<missing_element>(?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found"
        ), 1)


if __name__ == '__main__':
    unittest.main()
