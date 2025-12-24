#!/usr/bin/env python3
"""
Test suite for bash shell using unittest framework
"""

import sys
import os
import unittest

# Import testty functions
sys.path.insert(0, os.path.dirname(__file__))
from testty import run_with_pty, parse_input_string


class TestBashBasic(unittest.TestCase):
    """Tests for basic bash functionality."""

    def test_echo_hello_world(self):
        """Test that bash can echo hello world."""
        input_str = "echo 'hello world'[enter][sleep:100][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # Check that hello world appears in the output
        self.assertIn("hello world", result.output,
                     "Expected 'hello world' in bash output")

        # Should have exited cleanly
        self.assertTrue(result.did_exit, "Bash should have exited")
        self.assertEqual(result.exit_code, 0, f"Bash should exit with code 0, got {result.exit_code}")


if __name__ == "__main__":
    unittest.main()
