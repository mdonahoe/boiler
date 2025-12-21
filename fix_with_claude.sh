#!/bin/bash
# Invoke Claude to fix boiler for unfixable errors
# Usage: ~/boiler/fix_with_claude.sh [TARGET_REPO]

set -e

REPO_PATH="${1:-$(pwd)}"
REPO_PATH="$(cd "$REPO_PATH" && pwd)"
BOILER_DIR="$(cd ~/boiler && pwd)"

echo "Target repo: $REPO_PATH"
echo "Boiler dir:  $BOILER_DIR"
echo ""

# Generate the prompt
PROMPT=$(python3 "$BOILER_DIR/auto_fix_boiler.py" "$REPO_PATH")

# Save to temp file for easy debugging
TEMP_PROMPT="/tmp/claude_boiler_fix_prompt.txt"
echo "$PROMPT" > "$TEMP_PROMPT"
echo "Prompt saved to: $TEMP_PROMPT"
echo ""

# Invoke Claude with proper working directory and permissions
echo "Invoking Claude CLI from $BOILER_DIR..."
echo "This may take a few minutes..."
echo ""

cd "$BOILER_DIR"

# Add both directories as additional working directories
echo "$PROMPT" | claude --print \
    --dangerously-skip-permissions \
    2>&1 || true

echo ""
echo "================================================================================"
echo "Next steps:"
echo "  1. Review the changes Claude made in $BOILER_DIR"
echo "  2. Test: cd $BOILER_DIR && make test"
echo "  3. Try again: cd $REPO_PATH && boil --abort && boil make test"
echo "================================================================================"
