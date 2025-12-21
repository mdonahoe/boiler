#!/usr/bin/env python3
"""
Automatically invoke Claude to fix boiler when it encounters unfixable errors.

Usage:
    python3 auto_fix_boiler.py [TARGET_REPO]

Example:
    cd /root/dim
    python3 ~/boiler/auto_fix_boiler.py

Or from anywhere:
    python3 ~/boiler/auto_fix_boiler.py /root/dim
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def get_repo_path():
    """Get target repo path from args or current directory"""
    if len(sys.argv) > 1:
        return os.path.abspath(sys.argv[1])
    return os.getcwd()


def check_boil_status(repo_path):
    """Check if boiler failed and return failure info"""
    boil_dir = os.path.join(repo_path, ".boil")

    if not os.path.exists(boil_dir):
        return None, "No .boil directory found - boiler hasn't been run yet"

    # Find the latest iteration
    pipeline_files = sorted(
        [f for f in os.listdir(boil_dir) if f.startswith("iter") and f.endswith(".pipeline.json")],
        key=lambda x: int(x.split("iter")[1].split(".")[0])
    )

    if not pipeline_files:
        return None, "No pipeline iteration files found"

    latest_file = os.path.join(boil_dir, pipeline_files[-1])

    with open(latest_file, 'r') as f:
        data = json.load(f)

    if data.get("success", False):
        return None, "Boiler succeeded - no fix needed"

    return data, None


def get_error_summary(repo_path):
    """Get a summary of errors from boil --check"""
    result = subprocess.run(
        ["boil", "--check"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout


def create_claude_prompt(repo_path, error_data, error_summary):
    """Create the prompt to send to Claude"""

    prompt = f"""I need your help fixing boiler to handle errors in this repository.

IMPORTANT SETUP:
- You are working in TWO directories:
  1. /root/boiler - The boiler codebase (where you'll make changes)
  2. {repo_path} - The target repo with the .boil folder (where errors happened)
- Start by reading /root/boiler/AGENTS.md for detailed instructions
- Then analyze {repo_path}/.boil/ for error details

CURRENT SITUATION:
Boiler has failed to fix errors in {repo_path}

Status from 'boil --check':
{error_summary}

YOUR TASK:
Follow the instructions in /root/boiler/AGENTS.md and:
1. Analyze the debugging information in {repo_path}/.boil/
2. Understand what error pattern boiler couldn't handle
3. Create new detectors/planners in /root/boiler/pipeline/ to handle this error
4. Test your changes with 'make check' and 'make test' in /root/boiler
5. Validate the fix works by running 'boil make test' in {repo_path}

Make boiler handle this error pattern generically for ANY repository, not just this specific case.
"""

    return prompt


def invoke_claude_cli(prompt):
    """Invoke Claude via CLI"""
    # Check if 'claude' command is available
    claude_check = subprocess.run(
        ["which", "claude"],
        capture_output=True,
        text=True
    )

    if claude_check.returncode != 0:
        print("ERROR: 'claude' CLI not found in PATH")
        print("\nTo use this script automatically, install Claude CLI.")
        print("\nAlternatively, copy this prompt to Claude manually:")
        print(f"\n{'='*80}")
        print("PROMPT FOR CLAUDE")
        print(f"{'='*80}\n")
        print(prompt)
        print(f"\n{'='*80}\n")
        return False

    print("Invoking Claude CLI...")
    print(f"This may take a few minutes as Claude analyzes and fixes boiler...\n")

    try:
        # Invoke claude by piping the prompt to stdin
        # Use --print mode for non-interactive execution
        result = subprocess.run(
            ["claude", "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=os.path.expanduser("~/boiler")  # Run from boiler directory
        )

        print("="*80)
        print("CLAUDE'S RESPONSE")
        print("="*80)
        print(result.stdout)
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        print("="*80)

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("ERROR: Claude timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"ERROR: Failed to invoke Claude: {e}")
        return False


def main():
    repo_path = get_repo_path()

    print(f"Checking boiler status in: {repo_path}")
    print()

    # Check if boiler failed
    error_data, error_msg = check_boil_status(repo_path)

    if error_msg:
        print(f"Status: {error_msg}")
        print("\nNothing to fix!")
        return 0

    print("Status: Boiler FAILED - automatic fix needed")
    print()

    # Get error summary
    error_summary = get_error_summary(repo_path)

    # Create prompt
    prompt = create_claude_prompt(repo_path, error_data, error_summary)
    print(prompt)
    return 0

    # Try to invoke Claude CLI, fall back to manual prompt
    success = invoke_claude_cli(prompt)

    if success:
        print("\nClaude has analyzed and attempted to fix boiler.")
        print("Please review the changes and test with:")
        print(f"  cd {repo_path}")
        print(f"  boil --abort")
        print(f"  boil make test")
    else:
        print("it didnt work")

    return 0


if __name__ == "__main__":
    sys.exit(main())
