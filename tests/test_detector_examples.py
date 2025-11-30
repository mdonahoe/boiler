#!/usr/bin/env python3
"""
Unit tests to validate that all detectors have working examples.

Each detector should have an EXAMPLES list with (error_text, expected_clue_dict) tuples.
This test suite validates that:
1. Every detector has EXAMPLES defined
2. Each example error produces a clue with the expected properties
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.detectors.make_errors import (
    MakeMissingTargetDetector,
    MakeNoRuleDetector,
)
from pipeline.detectors.permissions import PermissionDeniedDetector
from pipeline.detectors.python_code import (
    MissingPythonCodeDetector,
    PythonNameErrorDetector,
)
from pipeline.detectors.file_errors import (
    FopenNoSuchFileDetector,
    FileNotFoundDetector,
    ShellCannotOpenDetector,
    ShellCommandNotFoundDetector,
    CatNoSuchFileDetector,
    DiffNoSuchFileDetector,
    CLinkerErrorDetector,
    CCompilationErrorDetector,
    CIncompleteTypeDetector,
    CImplicitDeclarationDetector,
    CUndeclaredIdentifierDetector,
)


class DetectorExamplesTest(unittest.TestCase):
    """Test that all detectors have valid working examples"""

    def setUp(self):
        """Register detectors before each test"""
        self.detectors = [
            MakeMissingTargetDetector(),
            MakeNoRuleDetector(),
            PermissionDeniedDetector(),
            MissingPythonCodeDetector(),
            PythonNameErrorDetector(),
            FopenNoSuchFileDetector(),
            FileNotFoundDetector(),
            ShellCannotOpenDetector(),
            ShellCommandNotFoundDetector(),
            CatNoSuchFileDetector(),
            DiffNoSuchFileDetector(),
            CLinkerErrorDetector(),
            CCompilationErrorDetector(),
            CIncompleteTypeDetector(),
            CImplicitDeclarationDetector(),
            CUndeclaredIdentifierDetector(),
        ]

    def test_all_detectors_have_examples(self):
        """Verify every detector defines EXAMPLES"""
        for detector in self.detectors:
            self.assertTrue(
                hasattr(detector, "EXAMPLES"),
                f"{detector.name} does not have EXAMPLES attribute",
            )
            self.assertIsInstance(
                detector.EXAMPLES,
                list,
                f"{detector.name}.EXAMPLES is not a list",
            )
            self.assertGreater(
                len(detector.EXAMPLES),
                0,
                f"{detector.name}.EXAMPLES is empty",
            )

    def test_examples_have_correct_format(self):
        """Verify each example is a (error_text, expected_clue_dict) tuple"""
        for detector in self.detectors:
            for i, example in enumerate(detector.EXAMPLES):
                self.assertIsInstance(
                    example,
                    tuple,
                    f"{detector.name} example {i} is not a tuple",
                )
                self.assertEqual(
                    len(example),
                    2,
                    f"{detector.name} example {i} does not have 2 elements",
                )
                error_text, expected_clue = example
                self.assertIsInstance(
                    error_text,
                    str,
                    f"{detector.name} example {i} error_text is not a string",
                )
                self.assertIsInstance(
                    expected_clue,
                    dict,
                    f"{detector.name} example {i} expected_clue is not a dict",
                )

    def test_examples_produce_clues(self):
        """Verify each example error text produces at least one clue"""
        for detector in self.detectors:
            for i, example in enumerate(detector.EXAMPLES):
                error_text, expected_clue = example
                clues = detector.detect(error_text)

                self.assertGreater(
                    len(clues),
                    0,
                    f"{detector.name} example {i} produced no clues\n"
                    f"Error text: {error_text}\n"
                    f"Expected: {expected_clue}",
                )

    def test_examples_have_correct_clue_type(self):
        """Verify example errors produce clues with expected clue_type"""
        for detector in self.detectors:
            for i, example in enumerate(detector.EXAMPLES):
                error_text, expected_clue = example
                clues = detector.detect(error_text)

                self.assertGreater(
                    len(clues),
                    0,
                    f"{detector.name} example {i} produced no clues",
                )

                clue = clues[0]
                expected_type = expected_clue.get("clue_type")

                self.assertEqual(
                    clue.clue_type,
                    expected_type,
                    f"{detector.name} example {i}: "
                    f"expected clue_type={expected_type}, got {clue.clue_type}\n"
                    f"Error text: {error_text}",
                )

    def test_examples_have_correct_confidence(self):
        """Verify example errors produce clues with expected confidence"""
        for detector in self.detectors:
            for i, example in enumerate(detector.EXAMPLES):
                error_text, expected_clue = example
                clues = detector.detect(error_text)

                self.assertGreater(len(clues), 0)

                clue = clues[0]
                expected_confidence = expected_clue.get("confidence")

                self.assertAlmostEqual(
                    clue.confidence,
                    expected_confidence,
                    places=2,
                    msg=f"{detector.name} example {i}: "
                    f"expected confidence={expected_confidence}, got {clue.confidence}",
                )

    def test_examples_have_correct_context(self):
        """Verify example errors produce clues with expected context"""
        for detector in self.detectors:
            for i, example in enumerate(detector.EXAMPLES):
                error_text, expected_clue = example
                clues = detector.detect(error_text)

                self.assertGreater(len(clues), 0)

                clue = clues[0]
                expected_context = expected_clue.get("context", {})

                # Verify all expected context keys are present
                for key, expected_value in expected_context.items():
                    self.assertIn(
                        key,
                        clue.context,
                        f"{detector.name} example {i}: "
                        f"context missing key '{key}'\n"
                        f"Expected context: {expected_context}\n"
                        f"Got context: {clue.context}",
                    )

                    # Verify value matches (handle both exact and substring matches)
                    actual_value = clue.context[key]
                    if isinstance(expected_value, list):
                        # For lists, check if all expected items are in actual
                        if isinstance(actual_value, list):
                            for exp_item in expected_value:
                                self.assertIn(
                                    exp_item,
                                    actual_value,
                                    f"{detector.name} example {i}: "
                                    f"context['{key}'] missing item {exp_item}\n"
                                    f"Expected: {expected_value}\n"
                                    f"Got: {actual_value}",
                                )
                        else:
                            # If actual is not a list, this is an error
                            self.fail(
                                f"{detector.name} example {i}: "
                                f"context['{key}'] expected list, got {type(actual_value)}\n"
                                f"Expected: {expected_value}\n"
                                f"Got: {actual_value}"
                            )
                    else:
                        # For non-list values, check equality
                        self.assertEqual(
                            actual_value,
                            expected_value,
                            f"{detector.name} example {i}: "
                            f"context['{key}'] mismatch\n"
                            f"Expected: {expected_value}\n"
                            f"Got: {actual_value}",
                        )

    def test_detector_names_match_classes(self):
        """Verify detector name property matches the class name"""
        for detector in self.detectors:
            class_name = detector.__class__.__name__
            self.assertEqual(
                detector.name,
                class_name,
                f"{class_name}.name should return '{class_name}', got '{detector.name}'",
            )


if __name__ == "__main__":
    unittest.main()
