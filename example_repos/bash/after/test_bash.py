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

    def test_simple_arithmetic(self):
        """Test that bash can do arithmetic."""
        input_str = "echo $((2 + 2))[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # Check that 4 appears in the output
        self.assertIn("4", result.output,
                     "Expected '4' as result of 2+2")

        self.assertTrue(result.did_exit, "Bash should have exited")
        self.assertEqual(result.exit_code, 0, f"Bash should exit with code 0, got {result.exit_code}")

    def test_variable_assignment(self):
        """Test that bash can assign and use variables."""
        input_str = "X=hello[enter]echo $X[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # Check that hello appears in the output
        self.assertIn("hello", result.output,
                     "Expected variable value 'hello' in output")

        self.assertTrue(result.did_exit, "Bash should have exited")

    def test_command_substitution(self):
        """Test that bash can do command substitution."""
        input_str = "echo $(echo nested)[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # Check that nested appears in the output
        self.assertIn("nested", result.output,
                     "Expected 'nested' from command substitution")

        self.assertTrue(result.did_exit, "Bash should have exited")


class TestBashBuiltins(unittest.TestCase):
    """Tests for bash builtin commands."""

    def test_pwd(self):
        """Test that pwd builtin works."""
        input_str = "pwd[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # pwd should output a path starting with /
        self.assertIn("/", result.output,
                     "Expected pwd to output a path")

        self.assertTrue(result.did_exit, "Bash should have exited")

    def test_cd_and_pwd(self):
        """Test that cd changes directory."""
        input_str = "cd /tmp[enter]pwd[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # Should show /tmp in output
        self.assertIn("/tmp", result.output,
                     "Expected '/tmp' after cd")

        self.assertTrue(result.did_exit, "Bash should have exited")


class TestBashExitCodes(unittest.TestCase):
    """Tests for exit codes."""

    def test_exit_with_code(self):
        """Test that exit with code works."""
        input_str = "exit 42[enter]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        self.assertTrue(result.did_exit, "Bash should have exited")
        self.assertEqual(result.exit_code, 42,
                        f"Expected exit code 42, got {result.exit_code}")

    def test_false_command(self):
        """Test that false command sets exit code to 1."""
        input_str = "false[enter]echo $?[enter][sleep:50][ctrl-D]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["/bin/bash", "--norc", "--noprofile"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=2.0,
            rows=24,
            cols=80
        )

        # $? should be 1 after false
        self.assertIn("1", result.output,
                     "Expected exit code 1 after false command")

        self.assertTrue(result.did_exit, "Bash should have exited")


if __name__ == "__main__":
    unittest.main()
