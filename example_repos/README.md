# Example Repositories

This directory contains example repositories used to test boil's file restoration capabilities.

## Structure

Each example repo has two directories:

```
example_repos/
├── simple/
│   ├── before/    # Full working codebase
│   └── after/     # Minimal codebase (subset of before/)
├── bash/
│   └── before/    # (after/ not yet created)
└── ...
```

### `before/` - The Complete Codebase

Contains the **full source code** that can be compiled and tested:
- All source files needed to build the project
- Test files that verify the built binary works
- Extra/unused code (functions, files) that could theoretically be removed
- Must pass `make test` (which compiles and runs tests)

### `after/` - The Boiled-Down Codebase

Contains the **minimal source code** - what remains after removing unnecessary parts:
- Strict subset of `before/` (only deletions, no additions)
- Every file in `after/` must exist in `before/`
- Every line in `after/` must appear in `before/` in the same order
- Files can be completely removed or have content deleted
- Must still pass `make test`

## The Relationship

The `after/` directory represents what you get when you "boil down" the codebase - removing unnecessary code while keeping tests passing.

**Example** (simple repo):
```
before/simple.c (920 bytes):     after/simple.c (83 bytes):
  #include <stdio.h>               #include <stdio.h>
  #include <stdlib.h>              int main() {
  int unused() { ... }                 printf("Hello\n");
  int main() {                         return 0;
      printf("Hello\n");           }
      return 0;
  }
```

The `unused()` function and extra includes are removed in `after/`.

## How Tests Use This

1. **test_example_repos.py**: Copies `before/`, deletes all files, runs `boil --hard make test`, verifies boil can restore the codebase and tests pass

2. **test_after_is_subset.py**: Validates that `after/` is truly a subset of `before/`:
   - No new files in `after/` that don't exist in `before/`
   - Each file in `after/` has same or fewer lines than `before/`
   - Lines in `after/` appear in same order as in `before/`
   - Repos without `after/` are skipped

## Adding a New Example Repo

1. Create `example_repos/myrepo/before/` with complete working code
2. Ensure `make test` compiles the project and runs tests on the built binary
3. Create `example_repos/myrepo/after/` by copying `before/` and removing unnecessary code
4. Verify `make test` still passes in `after/`
5. Add test case in `tests/test_example_repos.py`
