#!/usr/bin/env python3
"""
Test that enforces after/ folder is a strict subset of before/ folder.

For each subrepo in example_repos/:
- The after/ folder must not have any files that don't exist in before/
- Each file in after/ must have the same or fewer lines as in before/
- Lines in after/ must appear in the same order as in before/ (deletions only)
"""

import os
import unittest


class AfterIsSubsetTest(unittest.TestCase):
    """Test that after/ is a subset of before/ for each example repo"""

    def test_after_is_subset_of_before(self):
        """Verify after/ folder only contains deletions from before/"""
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        example_repos_dir = os.path.join(boiler_dir, "example_repos")

        # Iterate over each subrepo
        for subrepo_name in os.listdir(example_repos_dir):
            subrepo_path = os.path.join(example_repos_dir, subrepo_name)
            if not os.path.isdir(subrepo_path):
                continue

            before_dir = os.path.join(subrepo_path, "before")
            after_dir = os.path.join(subrepo_path, "after")

            if not os.path.exists(before_dir) or not os.path.exists(after_dir):
                continue

            # Check no new files in after/
            self._check_no_new_files(subrepo_name, before_dir, after_dir)

            # Check each file in after/ is a line-wise subset of before/
            self._check_files_are_line_subsets(subrepo_name, before_dir, after_dir)

    def _check_no_new_files(self, subrepo_name, before_dir, after_dir):
        """Ensure after/ doesn't have files that aren't in before/"""
        after_files = self._get_all_files(after_dir)
        before_files_set = set(os.path.relpath(f, before_dir) for f in self._get_all_files(before_dir))

        for after_file in after_files:
            relative_path = os.path.relpath(after_file, after_dir)
            if relative_path not in before_files_set:
                msg = f"\n{'='*70}\n"
                msg += f"[{subrepo_name}] EXTRA FILE IN after/ THAT DOESN'T EXIST IN before/\n"
                msg += f"{'='*70}\n"
                msg += f"File: {relative_path}\n\n"
                msg += f"Files in before/:\n"
                for f in sorted(before_files_set):
                    msg += f"  - {f}\n"
                msg += f"\nFiles in after/:\n"
                after_files_rel = sorted(os.path.relpath(f, after_dir) for f in after_files)
                for f in after_files_rel:
                    mark = " <-- EXTRA" if f == relative_path else ""
                    msg += f"  - {f}{mark}\n"
                msg += f"{'='*70}\n"
                self.fail(msg)

    def _check_files_are_line_subsets(self, subrepo_name, before_dir, after_dir):
        """Ensure each file in after/ is a line-wise subset of before/"""
        after_files = self._get_all_files(after_dir)

        for after_file in after_files:
            relative_path = os.path.relpath(after_file, after_dir)
            before_file = os.path.join(before_dir, relative_path)

            if not os.path.exists(before_file):
                continue

            with open(after_file, 'r', errors='ignore') as f:
                after_lines = f.readlines()

            with open(before_file, 'r', errors='ignore') as f:
                before_lines = f.readlines()

            # Check that after has same or fewer lines
            if len(after_lines) > len(before_lines):
                msg = f"\n{'='*70}\n"
                msg += f"[{subrepo_name}] FILE HAS MORE LINES IN after/ THAN before/\n"
                msg += f"{'='*70}\n"
                msg += f"File: {relative_path}\n"
                msg += f"  before/ has {len(before_lines)} lines\n"
                msg += f"  after/  has {len(after_lines)} lines\n\n"
                msg += f"before/{relative_path}:\n"
                for i, line in enumerate(before_lines, 1):
                    msg += f"  {i:3d}: {line.rstrip()}\n"
                msg += f"\nafter/{relative_path}:\n"
                for i, line in enumerate(after_lines, 1):
                    msg += f"  {i:3d}: {line.rstrip()}\n"
                msg += f"{'='*70}\n"
                self.fail(msg)

            # Check that lines in after appear in the same order in before
            self._check_lines_in_order(subrepo_name, relative_path, before_lines, after_lines)

    def _check_lines_in_order(self, subrepo_name, file_path, before_lines, after_lines):
        """Verify after_lines appear in order within before_lines"""
        before_idx = 0

        for after_idx, after_line in enumerate(after_lines):
            # Find this line in before starting from current position
            found = False
            for idx in range(before_idx, len(before_lines)):
                if before_lines[idx] == after_line:
                    before_idx = idx + 1
                    found = True
                    break

            if not found:
                msg = f"\n{'='*70}\n"
                msg += f"[{subrepo_name}] LINE IN after/ NOT FOUND OR OUT OF ORDER IN before/\n"
                msg += f"{'='*70}\n"
                msg += f"File: {file_path}\n"
                msg += f"Problem at line {after_idx + 1} in after/:\n"
                msg += f"  {after_line.rstrip()}\n\n"
                msg += f"before/{file_path}:\n"
                for i, line in enumerate(before_lines, 1):
                    prefix = ">>>" if i > before_idx - 5 and i <= before_idx else "   "
                    msg += f"  {prefix} {i:3d}: {line.rstrip()}\n"
                msg += f"\nafter/{file_path}:\n"
                for i, line in enumerate(after_lines, 1):
                    mark = " <-- PROBLEM HERE" if i == after_idx + 1 else ""
                    msg += f"   {i:3d}: {line.rstrip()}{mark}\n"
                msg += f"\nExpected to find line {after_idx + 1} somewhere after line {before_idx} in before/\n"
                msg += f"{'='*70}\n"
                self.fail(msg)

    def _get_all_files(self, directory):
        """Recursively get all files in directory (excluding hidden files)"""
        files = []
        for root, dirs, filenames in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in filenames:
                if not filename.startswith('.'):
                    files.append(os.path.join(root, filename))

        return files


if __name__ == "__main__":
    unittest.main()
