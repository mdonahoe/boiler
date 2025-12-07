#!/usr/bin/env python3
"""
Test boiling example repositories end-to-end.

This test creates a temporary git repository, copies files from the
example_repos/*/before/ directory, commits them, deletes all files,
and verifies that boiling successfully restores enough files to pass "make test"

After boiling, it also analyzes the .boil/ debug output to verify:
1. Which detectors, planners, and executors were used
2. That all registered components are used in at least one repo
"""

import sys
import os
import unittest
import tempfile
import shutil
import subprocess
import json
import re
import glob
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.handlers import register_all_handlers
from pipeline.detectors.registry import get_detector_registry
from pipeline.planners.registry import get_planner_registry
from pipeline.executors.registry import get_executor_registry


class ExampleReposTest(unittest.TestCase):
    """Test boiling of example repositories"""
    

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_simple_repo_boiling(self):
        """Test that the simple example repo can be boiled successfully"""
        self._test_repo_boiling("simple")

    @unittest.skipIf(os.environ.get('SKIP_SLOW_TESTS') == '1', "Slow test skipped")
    def test_dim_repo_boiling(self):
        """Test that the dim example repo can be boiled successfully"""
        self._test_repo_boiling("dim")

    @unittest.skipIf(os.environ.get('SKIP_SLOW_TESTS') == '1', "Slow test skipped")
    def test_treesitter_repo_boiling(self):
        "test tree-sitter"
        self._test_repo_boiling("tree-sitter")

    def _test_repo_boiling(self, repo_name):
        """Helper function to test boiling of a repo"""
        # Get the path to the boil script and example repo
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        # Use before/ folder - it contains the files that should be committed to git
        # After deletion, boiling should restore them
        example_before_dir = os.path.join(boiler_dir, "example_repos", repo_name, "before")

        # Verify the example directory exists
        self.assertTrue(os.path.exists(example_before_dir),
                       f"Example directory not found: {example_before_dir}")

        # Import the utility function
        from tests.test_utils import copy_and_boil

        # Special handling for dim.c - clear instead of delete
        special_handling = {"dim.c": "clear"} if repo_name == "dim" else None

        # Run the boil test with temporary directory cleanup via context manager
        with copy_and_boil(
            src_dir=example_before_dir,
            test_command=["make", "test"],
            preserve_tmpdir=False,
            verify_before=True,
            delete_files=True,
            timeout=120,
            special_file_handling=special_handling
        ) as result:
            tmpdir = result['tmpdir']
            boil_result = result['boil_result']

            # Check that boil succeeded
            self.assertEqual(boil_result.returncode, 0,
                           f"Boil should succeed for {repo_name}. Output:\n{boil_result.stdout}\n{boil_result.stderr}")

            # Verify Makefile was restored
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "Makefile")),
                          f"Makefile should be restored for {repo_name}")

            # Verify the test passes after restoration
            final_result = subprocess.run(["make", "test"], cwd=tmpdir, capture_output=True, text=True)
            self.assertEqual(final_result.returncode, 0,
                           f"Test should pass after restoration for {repo_name}. Output:\n{final_result.stdout}\n{final_result.stderr}")

            # Verify that boiled content matches the after/ folder
            example_after_dir = os.path.join(boiler_dir, "example_repos", repo_name, "after")
            if os.path.exists(example_after_dir):
                self._verify_after_is_subset_of_boiled(repo_name, example_after_dir, tmpdir)
            else:
                raise ValueError(f"directory {example_after_dir} is missing!")

            # Analyze .boil/ debug output
            boil_dir = os.path.join(tmpdir, ".boil")
            if os.path.exists(boil_dir):
                used_components = self._analyze_boil_debug(boil_dir)

                # Compare against expected lists if they exist
                self._compare_against_expected(repo_name, used_components)
            else:
                raise ValueError(f"directory {boil_dir} is missing!")

    def _verify_after_is_subset_of_boiled(self, repo_name, after_dir, boiled_dir):
        """Verify that after/ is a subset of the boiled directory"""
        after_files = self._get_all_non_hidden_files(after_dir)
        boiled_files_rel = set(
            os.path.relpath(f, boiled_dir) 
            for f in self._get_all_non_hidden_files(boiled_dir)
        )

        # Check all files in after/ exist in boiled
        for after_file in after_files:
            relative_path = os.path.relpath(after_file, after_dir)
            if relative_path not in boiled_files_rel:
                msg = f"\n{'='*70}\n"
                msg += f"[{repo_name}] FILE IN after/ NOT FOUND IN BOILED RESULT\n"
                msg += f"{'='*70}\n"
                msg += f"File: {relative_path}\n\n"
                msg += f"Files in after/:\n"
                after_files_rel = sorted(os.path.relpath(f, after_dir) for f in after_files)
                for f in after_files_rel:
                    msg += f"  - {f}\n"
                msg += f"\nFiles in boiled result:\n"
                for f in sorted(boiled_files_rel):
                    msg += f"  - {f}\n"
                msg += f"{'='*70}\n"
                self.fail(msg)

            # Check file content line-by-line
            boiled_file = os.path.join(boiled_dir, relative_path)
            with open(after_file, 'r', errors='ignore') as f:
                after_lines = f.readlines()
            with open(boiled_file, 'r', errors='ignore') as f:
                boiled_lines = f.readlines()

            # All lines in after/ should exist in boiled/ in the same order
            boiled_idx = 0
            for after_idx, after_line in enumerate(after_lines):
                found = False
                for idx in range(boiled_idx, len(boiled_lines)):
                    if boiled_lines[idx] == after_line:
                        boiled_idx = idx + 1
                        found = True
                        break

                if not found:
                    msg = f"\n{'='*70}\n"
                    msg += f"[{repo_name}] LINE IN after/ NOT FOUND IN BOILED RESULT\n"
                    msg += f"{'='*70}\n"
                    msg += f"File: {relative_path}\n"
                    msg += f"Problem at line {after_idx + 1} in after/:\n"
                    msg += f"  {after_line.rstrip()}\n\n"
                    msg += f"after/{relative_path}:\n"
                    for i, line in enumerate(after_lines, 1):
                        mark = " <-- MISSING FROM BOILED" if i == after_idx + 1 else ""
                        msg += f"  {i:3d}: {line.rstrip()}{mark}\n"
                    msg += f"\nBoiled {relative_path} (relevant section):\n"
                    for i, line in enumerate(boiled_lines, 1):
                        msg += f"  {i:3d}: {line.rstrip()}\n"
                    msg += f"{'='*70}\n"
                    self.fail(msg)

    def _get_all_non_hidden_files(self, directory):
        """Recursively get all non-hidden files in directory"""
        files = []
        for root, dirs, filenames in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    files.append(os.path.join(root, filename))
        return files

    def _analyze_boil_debug(self, boil_dir):
        """
        Analyze .boil/ debug output to extract used detectors, planners, and executors.
        
        Returns dict with keys: 'detectors', 'planners', 'executors'
        """
        used_detectors = set()
        used_planners = set()
        used_executors = set()
        
        # Get all pipeline JSON files
        json_files = glob.glob(os.path.join(boil_dir, "iter*.pipeline.json"))
        
        # Build mappings from clue_types/plan_types/actions to component names
        detector_registry = get_detector_registry()
        planner_registry = get_planner_registry()
        executor_registry = get_executor_registry()
        
        # Map clue_types to detectors
        clue_to_detector = self._build_clue_to_detector_map(detector_registry)
        # Map clue_types to planners
        clue_to_planner = self._build_clue_to_planner_map(planner_registry)
        # Map actions to executors
        action_to_executor = self._build_action_to_executor_map(executor_registry)
        
        # Process each JSON file
        for json_file in json_files:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract detectors from clues_detected
            for clue in data.get("clues_detected", []):
                clue_type = clue.get("clue_type", "")
                if clue_type in clue_to_detector:
                    used_detectors.add(clue_to_detector[clue_type])
            
            # Extract planners from plans_generated/attempted
            for plan in data.get("plans_generated", []) + data.get("plans_attempted", []):
                clue_source = plan.get("clue_source", {})
                clue_type = clue_source.get("clue_type", "")
                if clue_type in clue_to_planner:
                    used_planners.add(clue_to_planner[clue_type])
                
                # Also extract executors from actions
                action = plan.get("action", "")
                if action in action_to_executor:
                    used_executors.add(action_to_executor[action])
        
        return {
            'detectors': sorted(used_detectors),
            'planners': sorted(used_planners),
            'executors': sorted(used_executors)
        }
    
    def _build_clue_to_detector_map(self, detector_registry):
        """Build mapping from clue_type to detector name"""
        mapping = {}
        
        # Use PATTERNS attribute from detectors to map clue_types
        for detector in detector_registry._detectors:
            detector_name = detector.name
            # Check if detector has PATTERNS attribute (Detector subclasses)
            if hasattr(detector, 'PATTERNS'):
                for clue_type in detector.PATTERNS.keys():
                    # If multiple detectors produce the same clue_type, keep the first one
                    # (in practice, each clue_type should map to one detector)
                    if clue_type not in mapping:
                        mapping[clue_type] = detector_name
                    else:
                        # Multiple detectors for same clue_type - keep both
                        # Store as list if needed, but for now just overwrite
                        # (we can improve this later if needed)
                        pass
        
        # Also test detectors with their EXAMPLES to catch any clue_types not in PATTERNS
        for detector in detector_registry._detectors:
            if hasattr(detector, 'EXAMPLES'):
                for example_text, expected in detector.EXAMPLES:
                    clue_type = expected.get('clue_type')
                    if clue_type and clue_type not in mapping:
                        mapping[clue_type] = detector.name
        
        return mapping
    
    def _build_clue_to_planner_map(self, planner_registry):
        """Build mapping from clue_type to planner name"""
        mapping = {}
        for planner in planner_registry._planners:
            # Test which clue types this planner handles
            test_clue_types = [
                "missing_file", "missing_file_simple", "permission_denied",
                "make_no_rule", "make_missing_target", "linker_undefined_symbols",
                "missing_c_include", "missing_c_function", "missing_python_code",
                "python_name_error", "test_failure"
            ]
            for clue_type in test_clue_types:
                if planner.can_handle(clue_type):
                    mapping[clue_type] = planner.name
        return mapping
    
    def _build_action_to_executor_map(self, executor_registry):
        """Build mapping from action to executor name"""
        mapping = {}
        test_actions = ["restore_full", "restore_c_element", "restore_python_element"]
        for executor in executor_registry._executors:
            for action in test_actions:
                if executor.can_handle(action):
                    mapping[action] = executor.name
        return mapping
    
    def _compare_against_expected(self, repo_name, used_components):
        """
        Compare used components against expected lists for this repo.
        
        Expected lists can be defined in a file: example_repos/{repo_name}/expected_components.json
        Format:
        {
            "detectors": ["Detector1", "Detector2"],
            "planners": ["Planner1", "Planner2"],
            "executors": ["Executor1", "Executor2"]
        }
        """
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        expected_file = os.path.join(boiler_dir, "example_repos", repo_name, "expected_components.json")
        
        if not os.path.exists(expected_file):
            # No expected file - skip comparison
            return
        
        with open(expected_file, 'r') as f:
            expected = json.load(f)
        
        issues = []
        
        # Check detectors
        expected_detectors = set(expected.get("detectors", []))
        used_detectors = set(used_components['detectors'])
        missing_detectors = expected_detectors - used_detectors
        unexpected_detectors = used_detectors - expected_detectors
        
        if missing_detectors:
            issues.append(f"Missing expected detectors: {sorted(missing_detectors)}")
        if unexpected_detectors:
            issues.append(f"Unexpected detectors: {sorted(unexpected_detectors)}")
        
        # Check planners
        expected_planners = set(expected.get("planners", []))
        used_planners = set(used_components['planners'])
        missing_planners = expected_planners - used_planners
        unexpected_planners = used_planners - expected_planners
        
        if missing_planners:
            issues.append(f"Missing expected planners: {sorted(missing_planners)}")
        if unexpected_planners:
            issues.append(f"Unexpected planners: {sorted(unexpected_planners)}")
        
        # Check executors
        expected_executors = set(expected.get("executors", []))
        used_executors = set(used_components['executors'])
        missing_executors = expected_executors - used_executors
        unexpected_executors = used_executors - expected_executors
        
        if missing_executors:
            issues.append(f"Missing expected executors: {sorted(missing_executors)}")
        if unexpected_executors:
            issues.append(f"Unexpected executors: {sorted(unexpected_executors)}")
        
        if issues:
            msg = "\n".join([
                f"Component usage mismatch for {repo_name}:",
                ""
            ] + issues + [
                "",
                f"Expected:",
                f"  Detectors: {sorted(expected_detectors)}",
                f"  Planners: {sorted(expected_planners)}",
                f"  Executors: {sorted(expected_executors)}",
                f"",
                f"Actual:",
                f"  Detectors: {sorted(used_detectors)}",
                f"  Planners: {sorted(used_planners)}",
                f"  Executors: {sorted(used_executors)}",
            ])
            raise AssertionError(msg)

    def test_component_coverage(self):
        """
        Verify that all registered detectors, planners, and executors are covered
        in at least one expected_components.json file.
        
        This test reads all expected_components.json files and ensures every
        registered component appears in at least one file. It does not require
        running the actual boil tests.
        """
        register_all_handlers()
        detector_registry = get_detector_registry()
        planner_registry = get_planner_registry()
        executor_registry = get_executor_registry()
        
        all_detectors = set(detector_registry.list_detectors())
        all_planners = set(planner_registry.list_planners())
        all_executors = set(executor_registry.list_executors())
        
        # Collect expected components from ALL JSON files
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        example_repos_dir = os.path.join(boiler_dir, "example_repos")
        
        expected_detectors = set()
        expected_planners = set()
        expected_executors = set()
        json_files_found = []
        
        # Find all expected_components.json files
        if os.path.exists(example_repos_dir):
            for repo_name in os.listdir(example_repos_dir):
                repo_path = os.path.join(example_repos_dir, repo_name)
                if not os.path.isdir(repo_path):
                    continue
                
                expected_file = os.path.join(repo_path, "expected_components.json")
                if os.path.exists(expected_file):
                    json_files_found.append(repo_name)
                    try:
                        with open(expected_file, 'r') as f:
                            expected = json.load(f)
                        expected_detectors.update(expected.get("detectors", []))
                        expected_planners.update(expected.get("planners", []))
                        expected_executors.update(expected.get("executors", []))
                    except Exception as e:
                        raise AssertionError(f"Could not read {expected_file}: {e}")
        
        if not json_files_found:
            self.skipTest("No expected_components.json files found")
        
        # Check for components not covered in any expected JSON file
        missing_detectors = all_detectors - expected_detectors
        missing_planners = all_planners - expected_planners
        missing_executors = all_executors - expected_executors
        
        # Check for components in JSON files that don't exist (typos/invalid names)
        invalid_detectors = expected_detectors - all_detectors
        invalid_planners = expected_planners - all_planners
        invalid_executors = expected_executors - all_executors
        
        # Build report
        issues = []
        if missing_detectors:
            issues.append(f"Missing detectors ({len(missing_detectors)}): {sorted(missing_detectors)}")
        if missing_planners:
            issues.append(f"Missing planners ({len(missing_planners)}): {sorted(missing_planners)}")
        if missing_executors:
            issues.append(f"Missing executors ({len(missing_executors)}): {sorted(missing_executors)}")
        
        if invalid_detectors:
            issues.append(f"Invalid detector names in JSON files ({len(invalid_detectors)}): {sorted(invalid_detectors)}")
        if invalid_planners:
            issues.append(f"Invalid planner names in JSON files ({len(invalid_planners)}): {sorted(invalid_planners)}")
        if invalid_executors:
            issues.append(f"Invalid executor names in JSON files ({len(invalid_executors)}): {sorted(invalid_executors)}")
        
        if issues:
            msg = "\n".join([
                "=" * 80,
                "COMPONENT COVERAGE VERIFICATION FAILED",
                "=" * 80,
                "",
                "The following registered components are not covered in any expected_components.json file:",
                ""
            ] + issues + [
                "",
                f"Checked JSON files: {', '.join(json_files_found)}",
                "",
                "Covered components (from all expected_components.json files):"
            ])
            
            if expected_detectors or expected_planners or expected_executors:
                msg += f"\n  Detectors ({len(expected_detectors)}): {sorted(expected_detectors)}\n"
                msg += f"  Planners ({len(expected_planners)}): {sorted(expected_planners)}\n"
                msg += f"  Executors ({len(expected_executors)}): {sorted(expected_executors)}\n"
            
            msg += f"\nTotal registered: {len(all_detectors)} detectors, {len(all_planners)} planners, {len(all_executors)} executors"
            msg += f"\nTotal covered: {len(expected_detectors)} detectors, {len(expected_planners)} planners, {len(expected_executors)} executors"
            msg += "\n" + "=" * 80
            raise AssertionError(msg)
        
        # Don't print anything on success - keep it quiet




if __name__ == "__main__":
    unittest.main()
