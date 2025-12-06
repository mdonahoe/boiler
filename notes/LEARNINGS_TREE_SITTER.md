# Learnings from Tree-Sitter Repository Repair

This document captures key insights and patterns learned while extending boiler to handle errors in the tree-sitter repository.

## Summary

The tree-sitter repository presented a complex repair challenge involving:
- C compilation and linking errors
- Rust/Cargo build system errors
- Permission and executable issues
- Generic runtime errors from compiled binaries

Successfully repairing this repository required adding ~10 new error handlers and fixing a bug in boil.py.

## Key Patterns Discovered

### 1. Rust/Cargo Build System Errors

**Pattern**: Rust errors cascade - fixing one reveals another deeper in the build process.

**Handlers needed**:
- `handle_cargo_toml_not_found` - Missing Cargo.toml files across workspace
- `handle_cargo_missing_library` - Missing src/lib.rs, src/main.rs, benches/*
- `handle_cargo_couldnt_read` - Generic "couldn't read file" errors
- `handle_rust_module_not_found` - Missing .rs module files (E0583)
- `handle_rust_panic_no_such_file` - Build script panics trying to access files
- `handle_rust_env_not_defined` - Missing build.rs causing undefined env vars

**Key insight**: Cargo error messages often include the crate directory. Extract and prepend it to suggested file paths.

Example from `handle_cargo_missing_library`:
```python
# Extract crate directory from error
# "couldn't find `src/lib.rs` in package `tree-sitter-cli` at `crates/cli`"
crate_match = re.search(r"at [`']([^'`]+)[`']", err)
if crate_match:
    crate_dir = crate_match.group(1)
    # Prepend to suggested path
    full_path = os.path.join(crate_dir, suggested_path)
```

### 2. Build Script Analysis

**Pattern**: When build scripts panic, the panic message often shows the source code that failed.

**Solution**: Use `git show` to read the build script, then parse it to find file operations:
```python
# Read build script from git
result = subprocess.run(
    ["git", "show", f"{ref}:{build_script_path}"],
    stdout=subprocess.PIPE, text=True
)
build_script_content = result.stdout

# Search for file operations in the code
for match in re.finditer(r'["\']([\w/.-]+)["\']', build_script_content):
    file_path = match.group(1)
    if restore_missing_file(file_path):
        return True
```

### 3. C Linker Errors

**Initial approach (failed)**: Match undefined symbols to filenames using patterns like `ts_<filename>_<function>`.

**Problem**: Symbol names don't always match file names (e.g., `get_changed_ranges` could be in `get_changed_ranges.c` or `api.c` or `alloc.c`).

**Correct approach**: Search deleted file contents for symbols:
```python
# Get deleted C files
deleted_c_files = [f for f in deleted_files if f.endswith('.c')]

# For each file, use git show to read contents
for c_file in deleted_c_files:
    result = subprocess.run(
        ["git", "show", f"{ref}:{c_file}"],
        stdout=subprocess.PIPE, text=True
    )
    file_contents = result.stdout

    # Count how many undefined symbols appear in this file
    score = sum(1 for symbol in undefined_symbols if symbol in file_contents)

    # Restore files with highest scores first
```

**Key insight**: Content-based matching is more reliable than name-based heuristics.

### 4. Generic Runtime Errors

**Pattern**: Some runtime errors from compiled binaries don't specify which file is missing:
```
No such file or directory (os error 2)
```

**Challenge**: No file path in the error message.

**Solution**:
1. Check commonly missing config files first (fixtures.json, config.json)
2. Search error context for any file path patterns
3. This is a catch-all handler - place near end of HANDLERS list

Example:
```python
def handle_generic_no_such_file(err: str) -> bool:
    if "No such file or directory (os error 2)" not in err:
        return False

    # Check common config files
    common_config_files = [
        "test/fixtures/fixtures.json",
        "fixtures.json",
        "config.json",
    ]

    deleted_files = get_deleted_files(ref=ctx().git_ref)
    for config_file in common_config_files:
        if config_file in deleted_files:
            if restore_missing_file(config_file):
                return True

    # Fall back to searching error context for file paths...
```

### 5. Permission Errors vs Missing Files

**Pattern**: Both permission errors and missing files can cause similar symptoms.

**Solution**: Distinguish and handle both:
```python
def handle_permission_denied(err: str) -> bool:
    # Check for permission error patterns
    if "PermissionError:" not in err and "Permission denied" not in err:
        return False

    # Extract file path
    file_path = extract_from_error(err)

    # If file doesn't exist, restore it
    if not os.path.exists(file_path):
        return restore_missing_file(file_path)

    # File exists but has wrong permissions - restore from git
    # (This restores the file with correct permissions)
    subprocess.check_call(["git", "checkout", "HEAD", "--", file_path])
    return True
```

**Key insight**: `git checkout` not only restores content but also permissions.

### 6. Handler Ordering Matters

**Pattern**: Handlers are tried in order. Specific handlers should come before generic ones.

**Order used**:
1. Specific build system errors (cargo, make)
2. Compilation errors (C, Rust)
3. Linking errors
4. File access errors (permission, not found)
5. Runtime errors (empty files, test failures)
6. Python import errors
7. **Generic catch-alls last** (handle_generic_no_such_file, handle_missing_file)

### 7. Debugging Handler Issues

**Tool discovered**: The `--handle-error` flag allows testing handlers on saved error output:

```bash
# Run boil, it fails and saves .boil/iter1.exit2.txt
/root/boiler/boil ./run_tests_with_env.sh

# Test handlers on the saved error
/root/boiler/boil --handle-error .boil/iter1.exit2.txt
```

This prints each handler as it's tried and shows which one matches (or that none matched).

**Bug fixed**: Had to add `from handlers import HANDLERS` to boil.py for this to work.

### 8. Error Message Patterns to Watch For

Common patterns that indicate missing files:

| Pattern | Likely cause | Handler type |
|---------|-------------|-------------|
| `fatal error: <file>: No such file or directory` | Missing C header | C compilation |
| `undefined reference to '<symbol>'` | Missing C source | C linker |
| `file not found for module` (E0583) | Missing Rust module | Rust module |
| `could not find '<file>' in package` | Missing Rust source | Cargo library |
| `couldn't read '<file>'` | Missing file | Generic read |
| `thread 'main' panicked at <file>:<line>` | Build script panic | Parse build script |
| `environment variable '<VAR>' not defined at compile time` | Missing build.rs | Env not defined |
| `No such file or directory (os error 2)` | Missing file (unspecified) | Generic runtime |

### 9. Git Operations Best Practices

**Use `git show` to read deleted file contents**:
```python
# Better than git checkout + read + git reset
result = subprocess.run(
    ["git", "show", f"{ref}:{file_path}"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)
content = result.stdout
```

**Check deleted files once, cache the result**:
```python
deleted_files = get_deleted_files(ref=ctx().git_ref)  # Called by handler
# get_deleted_files runs: git diff --name-only --diff-filter=D HEAD
```

**Use `restore_missing_file` consistently**:
```python
# Don't do:
subprocess.check_call(["git", "checkout", "HEAD", "--", file_path])

# Do:
restore_missing_file(file_path)  # Handles errors, logging, etc.
```

## Metrics

**Handlers added**: 10
- handle_cargo_toml_not_found
- handle_cargo_missing_library
- handle_cargo_couldnt_read
- handle_rust_env_not_defined
- handle_rust_module_not_found
- handle_rust_panic_no_such_file
- handle_cannot_open_file (MIGRATED to CannotOpenFileDetector)
- handle_permission_denied (modified signature)
- handle_executable_not_found (modified signature)
- handle_generic_no_such_file

**Bugs fixed**: 1
- Missing import in boil.py prevented --handle-error flag from working

**Test command**: `./run_tests_with_env.sh` (runs `make test` with environment diagnostics)

**Repair success**: Boiler successfully restored 100+ deleted files and got the test suite running.

## Recommendations for Future Work

### 1. Pattern Library
Create a library of common error patterns for different ecosystems:
- Rust/Cargo
- C/C++ (Make, CMake)
- Python (pip, pytest)
- JavaScript/TypeScript (npm, yarn)
- Go (go build)

### 2. Smart File Matching
When multiple files could satisfy an error, use heuristics:
- File name similarity (Levenshtein distance)
- Directory structure hints
- File modification time (restore most recently changed first)
- File size (larger files more likely to contain symbols)

### 3. Error Context Extraction
Build a more sophisticated context extractor that:
- Understands multi-line error messages
- Tracks related errors (build cascades)
- Extracts structured data (line numbers, symbol names, paths)

### 4. Handler Composition
Some errors need multiple files restored. Consider:
- Detecting related errors
- Batch restoring related files
- Creating handler chains for known patterns

### 5. Testing Framework
Add tests for handlers:
- Synthetic error messages
- Known error corpus from real projects
- Regression tests for fixed issues

## Conclusion

The tree-sitter repository repair demonstrated that boiler's handler-based architecture is flexible enough to handle complex, multi-language build systems. The key to success was:

1. **Iterative refinement**: Each error revealed the next layer
2. **Content over heuristics**: Searching file contents more reliable than name matching
3. **Proper layering**: Specific handlers before generic ones
4. **Good debugging tools**: --handle-error flag was invaluable

The handlers added for tree-sitter should work for many Rust projects using Cargo workspaces and C libraries using Make.
