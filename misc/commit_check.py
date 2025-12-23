"""
See if a given commit is deletion-only, and thus a good candidate for a boiler test
"""
import subprocess
import sys


def git(cmd):
    return subprocess.check_output(["git"] + cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")


def is_subsequence(before, after):
    i = 0
    for ch in after:
        while i < len(before) and before[i] != ch:
            i += 1
        if i == len(before):
            return False
        i += 1
    return True


def check_commit(commit):
    # Get list of changed files with status
    diff = git(["diff-tree", "--no-commit-id", "--name-status", "-r", commit])

    for line in diff.splitlines():
        status, path = line.split("\t", 1)

        # New files are additions → fail
        if status == "A":
            print(f"FAIL: new file added: {path}")
            return False

        # Deleted files are fine
        if status == "D":
            continue

        # Modified files
        before = git(["show", f"{commit}^:{path}"])
        after = git(["show", f"{commit}:{path}"])

        if not is_subsequence(before, after):
            print(f"FAIL: non-deletion change in {path}")
            return False

    return True


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

    if check_commit(commit):
        print("PASS: commit is deletions-only")
        return 0
    else:
        print("FAIL: commit contains additions or reordering")
        return 1


if __name__ == "__main__":
    sys.exit(main())
