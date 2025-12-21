#!/usr/bin/env python3
"""
Restore the first deleted line from the smallest file with deletions.
Deterministic: always picks the same line given the same repo state.
"""
import argparse
import subprocess
import os
import sys
import re

def get_diff():
    """Get git diff output."""
    result = subprocess.run(
        ['git', 'diff', 'HEAD'],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout

def parse_deletions(diff_output):
    """
    Parse diff to extract deleted lines with file and position info.
    Returns list of (filepath, line_number, line_content, context_before)
    """
    deletions = []
    current_file = None
    new_line_num = 0
    context = []
    
    for line in diff_output.split('\n'):
        if line.startswith('--- a/'):
            current_file = line[6:]
            context = []
        elif line.startswith('+++ b/'):
            pass
        elif line.startswith('@@'):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if match:
                new_line_num = int(match.group(1)) - 1  # -1 because we increment before adding
            context = []
        elif line.startswith('-') and not line.startswith('---'):
            # This is a deleted line
            content = line[1:]  # Strip leading '-'
            deletions.append((
                current_file,
                new_line_num,
                content,
                context[-3:] if context else []  # Last 3 context lines
            ))
        elif line.startswith('+') and not line.startswith('+++'):
            # Added line - skip but increment line number
            new_line_num += 1
        elif line and not line.startswith('\\'):
            # Context line (unchanged)
            context.append(line[1:] if line.startswith(' ') else line)
            new_line_num += 1
    
    return deletions

def get_file_size(filepath):
    """Get size of file, or infinity if it doesn't exist."""
    try:
        return os.path.getsize(filepath)
    except:
        return float('inf')

def restore_line(filepath, line_num, content, context_before):
    """Insert a line at the specified position in a file."""
    if not os.path.exists(filepath):
        print(f"Error: {filepath} does not exist")
        return False
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Insert at position (line_num is 0-indexed for insertion point)
    lines.insert(line_num, content + '\n' if not content.endswith('\n') else content)
    
    with open(filepath, 'w') as f:
        f.writelines(lines)
    
    return True

def restore_random_line():
    diff = get_diff()
    
    if not diff:
        print("No changes found (working directory matches HEAD)")
        return 0
    
    deletions = parse_deletions(diff)
    
    if not deletions:
        print("No deletions found (only additions)")
        return 0
    
    # Group by file
    by_file = {}
    for filepath, line_num, content, context in deletions:
        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].append((line_num, content, context))
    
    # Sort files by size (smallest first)
    files_by_size = sorted(by_file.keys(), key=get_file_size)
    
    smallest_file = files_by_size[0]
    
    # Sort deletions in this file by line number (first deleted line)
    first_deletion = min(by_file[smallest_file], key=lambda x: x[0])
    line_num, content, context = first_deletion
    
    print(f"File: {smallest_file} ({get_file_size(smallest_file)} bytes)")
    print(f"Line number: {line_num}")
    print(f"Content: {repr(content)}")
    
    if restore_line(smallest_file, line_num, content, context):
        print(f"\n✓ Restored line in {smallest_file}")
        return 0
    else:
        print(f"\n✗ Failed to restore line")
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', type=int, default=1)
    args = parser.parse_args()
    for _ in range(args.n):
        x = restore_random_line()
        if x:
            return x
    return 0


if __name__ == '__main__':
    sys.exit(main())
