#!/usr/bin/env python3
"""
Generate expected_components.json files for each example repo
by running boil and analyzing the .boil/ debug output.
"""

import sys
import os
import tempfile
import subprocess
import shutil
import json
import glob

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.handlers import register_all_handlers
from pipeline.detectors.registry import get_detector_registry
from pipeline.planners.registry import get_planner_registry
from pipeline.executors.registry import get_executor_registry
from tests.test_example_repos import ExampleReposTest


def analyze_boil_debug(boil_dir):
    """Analyze .boil/ debug output to extract used components"""
    test_instance = ExampleReposTest()
    test_instance.setUp()
    return test_instance._analyze_boil_debug(boil_dir)


def run_boil_and_analyze(repo_name, boiler_dir):
    """Run boil on a repo and return component usage"""
    print(f"\n{'='*80}")
    print(f"Analyzing {repo_name}...")
    print(f"{'='*80}")
    
    boil_script = os.path.join(boiler_dir, "boil")
    example_before_dir = os.path.join(boiler_dir, "example_repos", repo_name, "before")
    
    if not os.path.exists(example_before_dir):
        print(f"Warning: {example_before_dir} does not exist, skipping")
        return None
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=tmpdir, check=True, capture_output=True)
        
        # Copy files from before/ directory
        for item in os.listdir(example_before_dir):
            if item.startswith('.'):
                continue
            src = os.path.join(example_before_dir, item)
            dst = os.path.join(tmpdir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst)
        
        # Make scripts executable
        for item in os.listdir(example_before_dir):
            if not item.startswith('.'):
                item_path = os.path.join(tmpdir, item)
                if os.path.isfile(item_path) and os.access(os.path.join(example_before_dir, item), os.X_OK):
                    os.chmod(item_path, 0o755)
        
        # Commit all files
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                      cwd=tmpdir, check=True, capture_output=True)
        
        # Delete all files (but keep .git)
        for item in os.listdir(tmpdir):
            if item == ".git":
                continue
            item_path = os.path.join(tmpdir, item)
            if os.path.isfile(item_path):
                if item_path.endswith("dim.c"):
                    # Clear content for dim.c
                    with open(item_path, "w"):
                        pass
                else:
                    os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        
        # Run boil
        print(f"Running boil on {repo_name}...")
        boil_result = subprocess.run(
            [boil_script, "make", "test"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if boil_result.returncode != 0:
            print(f"Warning: boil failed for {repo_name}")
            print(f"stdout: {boil_result.stdout[-500:]}")
            print(f"stderr: {boil_result.stderr[-500:]}")
            # Still try to analyze if .boil exists
        
        # Analyze .boil/ debug output
        boil_dir = os.path.join(tmpdir, ".boil")
        if os.path.exists(boil_dir):
            components = analyze_boil_debug(boil_dir)
            return components
        else:
            print(f"Warning: No .boil directory found for {repo_name}")
            return None


def main():
    boiler_dir = os.path.dirname(__file__)
    example_repos_dir = os.path.join(boiler_dir, "example_repos")
    
    # Get all example repos
    repos = [d for d in os.listdir(example_repos_dir)
             if os.path.isdir(os.path.join(example_repos_dir, d))
             and d not in ['.git', '__pycache__']]
    
    print(f"Found example repos: {repos}")
    
    register_all_handlers()
    
    # Analyze each repo
    results = {}
    for repo_name in repos:
        components = run_boil_and_analyze(repo_name, boiler_dir)
        if components:
            results[repo_name] = components
    
    # Generate expected_components.json files
    print(f"\n{'='*80}")
    print("Generating expected_components.json files...")
    print(f"{'='*80}")
    
    for repo_name, components in results.items():
        expected_file = os.path.join(example_repos_dir, repo_name, "expected_components.json")
        
        output = {
            "detectors": components['detectors'],
            "planners": components['planners'],
            "executors": components['executors']
        }
        
        with open(expected_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n{repo_name}:")
        print(f"  Detectors ({len(components['detectors'])}): {components['detectors']}")
        print(f"  Planners ({len(components['planners'])}): {components['planners']}")
        print(f"  Executors ({len(components['executors'])}): {components['executors']}")
        print(f"  Saved to: {expected_file}")
    
    print(f"\n{'='*80}")
    print("Done!")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
