# Auto-Fix Scripts Usage Guide

When boiler encounters errors it can't handle, use these scripts to automatically get Claude to fix it.

## Quick Start

### Option 1: Shell Script (Easiest - Copy & Paste)

```bash
cd /root/your-broken-repo
~/boiler/auto_fix_boiler.sh
```

This will:
- Check if boiler failed
- Generate a prompt for Claude
- Save it to `.boil/claude_fix_prompt.txt`
- Copy it to your clipboard (if available)
- Show you the prompt to paste into Claude Desktop/CLI

**Then**: Copy the prompt and paste it into Claude Desktop or Claude CLI.

### Option 2: Python Script (Automated with Claude CLI)

```bash
cd /root/your-broken-repo
python3 ~/boiler/auto_fix_boiler.py
```

This will:
- Check if boiler failed
- Automatically invoke Claude CLI with the fix prompt
- Show Claude's response
- Claude will analyze and fix boiler for you!

**Requirements**: `claude` CLI must be in your PATH

## Typical Workflow

1. **Run boiler and let it fail**:
   ```bash
   cd /root/dim
   boil make test
   # ... fails with unfixable errors
   ```

2. **Generate auto-fix prompt**:
   ```bash
   ~/boiler/auto_fix_boiler.sh
   ```

3. **Copy the generated prompt** (it's saved to `.boil/claude_fix_prompt.txt`)

4. **Paste into Claude** and let it analyze and fix boiler

5. **Test the fix**:
   ```bash
   boil --abort    # Reset to broken state
   boil make test  # Try again with fixed boiler
   ```

## Example Output

### When boiler succeeds:
```
$ ~/boiler/auto_fix_boiler.sh
Checking boiler status in: /root/dim

Status: Boiler SUCCEEDED - no fix needed!
```

### When boiler fails:
```
$ ~/boiler/auto_fix_boiler.sh
Checking boiler status in: /root/dim

Status: Boiler FAILED - generating fix prompt...

================================================================================
AUTOMATED FIX OPTIONS
================================================================================

Option 1: Use Claude Desktop (Recommended)
  1. Open Claude Desktop
  2. Copy-paste this prompt:

---[ START PROMPT ]---
Follow ~/boiler/AGENTS.md and apply it to /root/dim/.boil/

Current boil status from 'boil --check':
----------------------------------------
Found 1 pipeline iterations

Pipeline successes: 0
Pipeline failures:  1
Success rate:       0.0%

Error: No error clues detected by any detector
----------------------------------------

Please analyze the errors and improve boiler to handle them.
---[ END PROMPT ]---

Prompt saved to: /root/dim/.boil/claude_fix_prompt.txt
```

## Advanced: Using Python Script with Claude CLI

If you have `claude` CLI installed:

```bash
# Auto-invoke Claude
python3 ~/boiler/auto_fix_boiler.py /root/dim

# Or from within the repo:
cd /root/dim
python3 ~/boiler/auto_fix_boiler.py
```

## What Happens Next?

After you give Claude the prompt:

1. Claude reads `~/boiler/AGENTS.md` for instructions
2. Analyzes your `.boil/` debug output
3. Creates new detectors/planners/executors as needed
4. Tests with `make check` and `make test`
5. Validates the fix on your repo

Then you can test:
```bash
boil --abort       # Reset repo to broken state
boil make test     # Try boiling again with the fix
```

## Pro Tips

- The shell script (`auto_fix_boiler.sh`) always works and just generates a prompt
- The Python script (`auto_fix_boiler.py`) is fully automated but requires `claude` CLI
- Prompts are saved to `.boil/claude_fix_prompt.txt` for easy re-use
- You can edit the prompt before sending if you want to give Claude more context
- Run `boil --check` to see detailed failure info anytime

## Integration with Git Hooks (Optional)

You can add this to `.git/hooks/post-commit` to auto-generate fix prompts:

```bash
#!/bin/bash
if [ -d .boil ] && boil --check 2>&1 | grep -q "FAILED"; then
    echo "Boiler needs help! Run: ~/boiler/auto_fix_boiler.sh"
fi
```
