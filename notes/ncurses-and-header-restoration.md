# Ncurses Support and Header File Restoration Improvements

**Date:** 2025-12-08
**Status:** Significant progress on viw repo - 11/12 iterations successful

## Changes Made

### 1. Added Ncurses Stdlib Symbols
**File:** `pipeline/planners/c_code_restore.py`

Added 73 ncurses symbols to `STDLIB_SYMBOL_TO_HEADER` dictionary:
- **Functions:** `initscr`, `endwin`, `refresh`, `wrefresh`, `getch`, `wgetch`, `printw`, `wprintw`, `mvprintw`, `addch`, `waddch`, `addstr`, `move`, `wmove`, `clear`, `wclear`, `erase`, `raw`, `noraw`, `cbreak`, `echo`, `noecho`, `keypad`, `nodelay`, `timeout`, `curs_set`, `start_color`, `init_pair`, `attron`, `attroff`, `attrset`, `getmaxx`, `getmaxy`, `newwin`, `delwin`, `subwin`, `mvwin`, `box`, `border`, `scrollok`, `scroll`, etc.
- **Constants/Variables:** `stdscr`, `curscr`, `newscr`, `LINES`, `COLS`, `TRUE`, `FALSE`, `ERR`, `OK`
- **Attributes:** `A_NORMAL`, `A_STANDOUT`, `A_UNDERLINE`, `A_REVERSE`, `A_BLINK`, `A_DIM`, `A_BOLD`, etc.
- **Colors:** `COLOR_BLACK`, `COLOR_RED`, `COLOR_GREEN`, `COLOR_YELLOW`, `COLOR_BLUE`, `COLOR_MAGENTA`, `COLOR_CYAN`, `COLOR_WHITE`
- **Key Constants:** `KEY_DOWN`, `KEY_UP`, `KEY_LEFT`, `KEY_RIGHT`, `KEY_HOME`, `KEY_BACKSPACE`, `KEY_F0`, `KEY_DC`, `KEY_IC`, `KEY_ENTER`, `KEY_END`, `KEY_PPAGE`, `KEY_NPAGE`, `KEY_RESIZE`, `KEY_MOUSE`, etc.

All map to `"ncurses.h"`

### 2. Added Git History Search for Deleted Headers

Added three new helper methods to search git history when header files have been deleted:

#### `MissingCFunctionPlanner._find_header_for_function()`
Searches git history for function declarations in .h files:
```python
git grep "function_name(" HEAD -- "*.h"
```
Parses output format: `HEAD:path/to/file.h:code`
Returns header filename if declaration found (ends with `;`)

#### `MissingCFunctionPlanner._find_header_for_macro()`  
Searches git history for macro definitions:
```python
git grep "#define macro_name" HEAD -- "*.h"
```

#### `MissingCTypePlanner._find_header_for_type()`
Searches git history for type definitions:
```python
git grep "} type_name;" HEAD -- "*.h"
git grep "typedef.*type_name" HEAD -- "*.h"
```

All use correct parsing: `parts = line.split(':', 2)` where `parts[1]` is the file path.

### 3. Smart Header Content Restoration

Modified planners to restore missing declarations/definitions to stub header files:

#### `MissingCTypePlanner`
- **Before:** If include already present in source file, skip
- **After:** If include present, restore the type definition to the header file
  - Creates plan with `target_file=header_path`, `element_type="type"`
  - Example: Restore `state_t` typedef to `src/state.h`

#### `MissingCFunctionPlanner`
- **Before:** If include already present in source file, skip  
- **After:** If include present, restore function declarations to the header file
  - Creates plan with `target_file=header_path`, `element_type="function"`
  - Example: Restore `init_state()`, `destroy_state()` declarations to `src/state.h`

This allows boiler to incrementally fill in stub header files with the declarations/definitions they need.

## Testing Results

**Repo:** github.com/lpan/viw (ncurses-based vim clone)
**Initial state:** All .c and .h files deleted from git
**Test command:** `boil make test`

### Progress
- **Iteration 1:** Restore Makefile ✓
- **Iteration 2:** Restore src/*.c stubs ✓
- **Iteration 3-7:** Restore main.c and test file content ✓
- **Iteration 8:** Add #includes for stdio.h, stdlib.h, and restore #include "state.h", #include "listeners.h" to main.c ✓
- **Iteration 9:** Create stub for listeners.h ✓
- **Iteration 10:** Create stub for state.h ✓
- **Iteration 11:** Restore `state_t` typedef, `init_state()`, `start_listener()`, `destroy_state()` declarations to header files ✓
- **Iteration 12:** **FAILS** - detector doesn't detect errors in header files ✗

### Success Rate
**11/12 iterations successful (91.7%)**

Previously failed at iteration 9 with "Could not fix all clues"

## Remaining Issue: Header File Error Detection

### The Problem
C compiler errors that occur in `.h` files are not being detected by the pipeline detectors.

**Example from iteration 12:**
```
src/listeners.h:15:21: error: unknown type name 'state_t'
src/state.h:8:3: error: unknown type name 'buffer_t'
src/state.h:9:3: error: unknown type name 'screen_t'
```

These errors are **not detected** - no clues created with `file_path: "src/listeners.h"` or `file_path: "src/state.h"`

Only errors in `.c` files are detected, leading to clues like:
```python
{'file_path': 'src/main.c', 'line_number': '26', 'function_name': 'start_listener'}
```

### Root Cause
The detector regex patterns in `pipeline/detectors/file_errors.py` likely only match file paths ending in `.c`:
- `CImplicitDeclarationDetector`
- `CUndeclaredIdentifierDetector`  
- `CUnknownTypeNameDetector`

### Fix Needed
Update the regex patterns in these detectors to also match `.h` files:
- Current pattern probably: `src/\w+\.c:\d+`
- Should be: `src/[\w/]+\.(c|h):\d+`

This would allow the planners to:
1. Detect `state_t` is missing in `listeners.h`
2. Find it's defined in `state.h` via git grep
3. Create plan to add `#include "state.h"` to `listeners.h`
4. Continue iterating until all transitive dependencies are resolved

### Why This Matters
Header files often have includes that provide their dependencies:
```c
// Original listeners.h
#include "controller.h"
#include "buffer.h"

void start_listener(state_t *st);  // state_t comes from controller.h
```

When we restore just the function declaration without its includes, compilation fails.

## Architecture Notes

### Stub Files Are Intentional
The `restore_stub` action creates minimal placeholder files. This is by design:
- Allows compiler to proceed past "file not found" errors
- Reveals what content is actually needed
- Enables incremental restoration via subsequent iterations

### Surgical vs Wholesale Restoration  
The planner approach is to restore specific elements (functions, types, includes) rather than entire files. This is intentional:
- More precise and understandable
- Avoids restoring unnecessary code
- Better for the iterative repair model

### Git Grep Parsing
The correct way to parse `git grep` output:
```python
# git grep output: HEAD:path/to/file.h:line content
parts = line.split(':', 2)
ref = parts[0]      # "HEAD"
path = parts[1]     # "path/to/file.h"
code = parts[2]     # "line content"
```

**NOT:**
```python
file_ref = parts[0]  # Wrong - this is "HEAD", not "HEAD:path"
if ':' in file_ref:
    header_path = file_ref.split(':', 1)[1]  # Wrong - file_ref doesn't have ':'
```

## Future Improvements

1. **Header file error detection** - Update detector regexes to match .h files
2. **Include dependency analysis** - When restoring a declaration/definition, also restore the includes it depends on
3. **Multi-line type definitions** - Better handling of complex typedef structs that span multiple lines
4. **Header include guards** - Detect and restore `#ifndef HEADER_H` / `#define HEADER_H` / `#endif` patterns
5. **Forward declarations** - Sometimes a forward declaration (`struct foo;`) is sufficient instead of full include

## Files Modified

- `~/boiler/pipeline/planners/c_code_restore.py` - Main changes
  - `MissingCFunctionPlanner.STDLIB_SYMBOL_TO_HEADER` - Added ncurses symbols
  - `MissingCFunctionPlanner._find_header_for_function()` - New method
  - `MissingCFunctionPlanner._find_header_for_macro()` - Enhanced with git grep
  - `MissingCFunctionPlanner.plan()` - Now restores to header files when include present
  - `MissingCTypePlanner._find_header_for_type()` - Enhanced with git grep  
  - `MissingCTypePlanner._plan_for_clue()` - Now restores to header files when include present

## Testing Commands

```bash
cd ~/viw
python3 ~/boiler/boil.py --abort  # Reset to clean state
python3 ~/boiler/boil.py make test  # Run with default 25 iterations
python3 ~/boiler/boil.py --check  # View iteration-by-iteration progress
```

For verbose output:
```bash
BOIL_VERBOSE=1 python3 ~/boiler/boil.py make test
```

To test a specific error file:
```bash
python3 ~/boiler/boil.py --handle-error ~/viw/.boil/iter11.exit2.txt
```
