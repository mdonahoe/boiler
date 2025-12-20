#!/usr/bin/env python3
"""
Unit tests to validate that all detectors have working examples.

Each detector should have an EXAMPLES list with (error_text, expected_clue_dict) tuples.
This test suite validates that:
1. Every detector has EXAMPLES defined
2. Each example error produces a clue with the expected properties
"""

from collections import defaultdict
import sys
import os
import re
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.detectors import registry as detector_registry
from pipeline import handlers


class DetectorExamplesTest(unittest.TestCase):
    """Test that all detectors have valid working examples"""

    def setUp(self):
        """Register detectors before each test"""
        handlers.register_all_handlers()
        self.detectors = detector_registry.get_detector_registry()._detectors

    def test_all_detectors_subclasses_are_registered(self):
        detectors_found = defaultdict(list)  # map from classname to list of files
        files_found = defaultdict(list)
        res = subprocess.run(['git', 'grep', 'class.*Detector', '--', 'pipeline/detectors'], capture_output=True)
        for line in res.stdout.decode('utf-8').splitlines():
            filename, classdef = line.split(":", 1)
            match = re.search(r'class (.*)\(Detector\)', classdef)
            if match:
                classname = match.group(1)
                detectors_found[classname].append(filename)
                files_found[filename].append(classname)

        # We should have found something
        if not detectors_found:
            raise AssertionError("no detectors found")

        # Ensure all found detectors are in the registry
        detectors_registered = {d.name for d in self.detectors}
        unregistered = set(detectors_found.keys()) - detectors_registered
        if unregistered:
            raise AssertionError(f"Found {len(unregistered)} unregistered Detector subclasses: {unregistered}")

        # Ensure all found detectors are only defined once
        for detector, files in detectors_found.items():
            with self.subTest(detector=detector):
                self.assertEqual(1, len(files), f"{detector} is defined in multiple files: {files}")

        # Ensure every file only defines a single detector
        for file, detectors in files_found.items():
            with self.subTest(file=file):
                self.assertEqual(1, len(detectors), f"{file} is defines in multiple detectors: {detectors}")
        
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
            with self.subTest(detector=detector.name):
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
            # TODO(claude): use a unittest context manager here so that if a detector fails, the error message makes it clear which
            for i, example in enumerate(detector.EXAMPLES):
                error_text, expected_clue = example
                with self.subTest(detector=detector.name, i=i, error_text=error_text):
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

    def test_detectors_do_not_override_base_methods(self):
        """Verify Detector subclasses don't override detect() or pattern_to_clue()"""
        from pipeline.detectors.base import Detector

        for detector in self.detectors:
            class_name = detector.__class__.__name__

            # Check if detect() is overridden
            detect_method = detector.__class__.detect
            base_detect_method = Detector.detect
            self.assertIs(
                detect_method,
                base_detect_method,
                f"{class_name} should not override detect() method",
            )

            # Check if pattern_to_clue() is overridden
            pattern_to_clue_method = detector.__class__.pattern_to_clue
            base_pattern_to_clue_method = Detector.pattern_to_clue
            self.assertIs(
                pattern_to_clue_method,
                base_pattern_to_clue_method,
                f"{class_name} should not override pattern_to_clue() method",
            )


if __name__ == "__main__":
    unittest.main()
