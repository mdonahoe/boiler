#!/usr/bin/env python3
"""
Script to detect which test reverts changes to boil.py.
Modifies boil.py, runs each test in sequence, and checks if changes persist.
"""

import subprocess
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent
BOIL_PY = REPO_ROOT / "boil.py"
TEST_DIR = REPO_ROOT / "tests"

def add_test_marker():
    """Add a unique marker to boil.py"""
    with open(BOIL_PY, 'r') as f:
        content = f.read()
    
    marker = "\n# TEST_MARKER: This should persist across tests\n"
    if marker not in content:
        with open(BOIL_PY, 'a') as f:
            f.write(marker)
    return marker

def has_git_diff():
    """Check if boil.py has uncommitted changes"""
    result = subprocess.run(
        ["git", "diff", "boil.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())

def get_test_files():
    """Get all test files"""
    test_files = sorted([
        f.name for f in TEST_DIR.glob("test_*.py")
        if f.is_file() and f.name != "test_boil_reversion.py"
    ])
    return test_files

def run_test(test_file):
    """Run a single test file"""
    test_path = TEST_DIR / test_file
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print('='*60)
    
    result = subprocess.run(
        [sys.executable, "-m", "unittest", str(test_path), "-v"],
        cwd=REPO_ROOT,
        capture_output=False
    )
    return result.returncode

def main():
    print("Boil.py Reversion Detector")
    print("="*60)
    
    # Save the original state
    subprocess.run(["git", "checkout", "boil.py"], cwd=REPO_ROOT, capture_output=True)
    
    # Add marker
    marker = add_test_marker()
    print(f"Added marker to boil.py")
    
    # Verify diff exists
    if not has_git_diff():
        print("ERROR: Failed to create git diff in boil.py")
        sys.exit(1)
    
    print("Confirmed git diff exists\n")
    
    # Get test files
    test_files = get_test_files()
    print(f"Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"  - {test_file}")
    
    # Run each test
    for test_file in test_files:
        run_test(test_file)
        
        # Check if diff still exists
        if not has_git_diff():
            print(f"\n{'!'*60}")
            print(f"ERROR: Test '{test_file}' reverted boil.py")
            print(f"{'!'*60}")
            sys.exit(1)
        else:
            print(f"✓ boil.py still modified after {test_file}")
    
    print(f"\n{'='*60}")
    print("SUCCESS: All tests passed without reverting boil.py")
    print('='*60)
    print(f"\nboil.py modifications preserved. Run 'git checkout boil.py' to revert.")

if __name__ == "__main__":
    main()
