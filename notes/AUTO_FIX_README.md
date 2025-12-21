# Auto-Fix Boiler with Claude

When boiler can't fix errors, use these scripts to automatically invoke Claude to improve boiler.

## Quick Start (Easiest Method)

```bash
cd /root/your-broken-repo
~/boiler/fix_with_claude.sh
```

**That's it!** Claude will:
- Analyze the `.boil/` debug output
- Figure out what detector/planner is missing
- Implement and test the fix
- Validate it works on your repo

## What Each Script Does

### 1. `fix_with_claude.sh` ⭐ **USE THIS ONE**
The all-in-one wrapper that just works.

```bash
~/boiler/fix_with_claude.sh /root/dim
```

- Auto-detects failures
- Generates the prompt
- Invokes Claude with correct permissions
- Claude fixes boiler automatically

### 2. `auto_fix_boiler.py`
Python script that generates the fix prompt.

```bash
python3 ~/boiler/auto_fix_boiler.py /root/dim
```

Outputs the prompt to stdout (used by the shell wrapper).

### 3. `auto_fix_boiler.sh`
Manual copy-paste version if you prefer.

```bash
~/boiler/auto_fix_boiler.sh /root/dim
```

Shows you the prompt and saves it to `.boil/claude_fix_prompt.txt` for manual copy-paste.

## Full Example Workflow

```bash
# 1. Try to boil your repo
cd /root/dim
boil make test
# ... fails with "No error clues detected"

# 2. Auto-fix with Claude
~/boiler/fix_with_claude.sh

# ... wait for Claude to analyze and fix ...

# 3. Test the fix
cd ~/boiler
make test  # Should pass

# 4. Try boiling again
cd /root/dim
boil --abort  # Reset to broken state
boil make test  # Should work now!
```

## Permissions Note

The `fix_with_claude.sh` script runs Claude as the `bot` user (not root) because:
- `--dangerously-skip-permissions` cannot be used with root/sudo
- The `bot` user owns `/root/boiler` and can make changes
- This allows Claude to edit detector/planner files automatically
- Running as non-root is safer for automated operations

Setup (already done):
```bash
# These commands were already run to set up the bot user
sudo useradd -m -s /bin/bash bot
sudo usermod -aG sudo bot
sudo chown -R bot:bot /root/boiler
sudo chmod -R 755 /root/boiler /root/dim
```

You can review Claude's changes in git before committing them.

## What Claude Will Do

When invoked, Claude will:

1. **Read** `/root/boiler/AGENTS.md` for instructions
2. **Analyze** `your-repo/.boil/` debug files
3. **Identify** what error pattern boiler missed
4. **Create** new detectors in `~/boiler/pipeline/detectors/`
5. **Create** new planners in `~/boiler/pipeline/planners/`
6. **Register** them in `~/boiler/pipeline/handlers.py`
7. **Test** with `make check` and `make test`
8. **Validate** on your actual repo

## Troubleshooting

**Q: "claude: command not found"**
A: Install Claude CLI. Use the manual script instead:
```bash
~/boiler/auto_fix_boiler.sh
# Then copy-paste the prompt to Claude Desktop
```

**Q: Claude says it doesn't have permission to read files**
A: Use the wrapper script: `~/boiler/fix_with_claude.sh`

**Q: I want to see the prompt first**
A: Run `python3 ~/boiler/auto_fix_boiler.py` to print it

**Q: Can I customize the prompt?**
A: Yes! Edit the prompt in `auto_fix_boiler.py` line 71-95

## Pro Tips

- The prompt is saved to `/tmp/claude_boiler_fix_prompt.txt` each run
- You can pipe the output: `python3 ~/boiler/auto_fix_boiler.py | claude --print`
- Run `boil --check` anytime to see detailed error info
- Use `boil --abort` to reset your repo to the broken state for testing

## Files Created

- `fix_with_claude.sh` - The main wrapper ⭐ **USE THIS**
- `auto_fix_boiler.py` - Prompt generator
- `auto_fix_boiler.sh` - Manual copy-paste version
- `AUTO_FIX_USAGE.md` - Detailed usage guide
- `AUTO_FIX_README.md` - This file
