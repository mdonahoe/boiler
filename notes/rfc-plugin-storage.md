# RFC: Plugin Storage Location

## Problem

Currently, `boil --abort` and `boil --finish` delete the entire `.boil/` directory:

```go
os.RemoveAll(".boil")
```

This destroys user-created plugins in `.boil/plugins/`, which should be preserved and committable to the repository.

## Requirements

1. Plugins should survive `--abort` and `--finish`
2. Plugins should be committable by users
3. Session files (iter*.txt, iter*.json, boil.index) should still be cleaned up
4. Minimal change to existing behavior

## Proposal: Selective Cleanup

Instead of deleting the entire `.boil/` directory, selectively delete only session files:

### Files to DELETE on cleanup:
- `iter*.exit*.txt` - command output per iteration
- `iter*.pipeline.json` - pipeline state per iteration
- `boil.index` - git index file for boiling

### Files to PRESERVE:
- `plugins/` - user-created detectors and planners

### Implementation

Replace:
```go
os.RemoveAll(".boil")
```

With a helper function:
```go
func CleanBoilSession() {
    // Remove iteration files
    entries, _ := os.ReadDir(".boil")
    for _, entry := range entries {
        name := entry.Name()
        if strings.HasPrefix(name, "iter") || name == "boil.index" {
            os.RemoveAll(filepath.Join(".boil", name))
        }
    }

    // Remove .boil only if empty (no plugins)
    remaining, _ := os.ReadDir(".boil")
    if len(remaining) == 0 {
        os.Remove(".boil")
    }
}
```

## Alternatives Considered

### Move plugins outside .boil/
- Use `.boil-plugins/` or `boil-plugins/` instead
- Pro: Clear separation
- Con: Breaking change, requires migration, two directories to manage

### Symlink plugins to external location
- Pro: Could work
- Con: Complex, platform issues

## Recommendation

**Selective cleanup** is the simplest solution with minimal code changes and no breaking changes for users.

## Affected Code

1. `src/boil/core/fix.go:61` - stale session cleanup
2. `src/boil/core/fix.go:277` - AbortBoiling()
3. `src/boil/core/fix.go:294` - FinishBoiling()
