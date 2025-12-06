#!/usr/bin/env python3
"""
Profile the dim test to find bottlenecks
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.handlers import register_all_handlers
from tests.test_utils import run_boil_with_profiling

def run_dim_test():
    """Run the dim test and time it"""
    register_all_handlers()

    boiler_dir = os.path.dirname(__file__)
    example_before_dir = os.path.join(boiler_dir, "example_repos", "dim", "before")

    print(f"Working in temp directory...")

    tmpdir = run_boil_with_profiling(
        src_dir=example_before_dir,
        test_command=["make", "test"],
        boil_args=["-n", "20"],
        verbose=True,
        timeout=120
    )

    return tmpdir

if __name__ == "__main__":
    tmpdir = run_dim_test()
    print(f"\nTo clean up: rm -rf {tmpdir}")
