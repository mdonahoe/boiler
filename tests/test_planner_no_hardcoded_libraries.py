"""
Test that planners don't contain hard-coded library-specific keywords.

Planners should be generic and work for any C library, not just tree-sitter.
"""

import os
import unittest
from pathlib import Path


class TestPlannerNoHardcodedLibraries(unittest.TestCase):
    """
    Ensure planners are generic and don't hard-code library-specific logic.
    """

    BANNED_KEYWORDS = [
        "tree_sitter",
        "TSLanguage",
        "TSParser",
        "TSNode",
        "TSTree",
        "TSPoint",
        "TSRange",
        "TSQuery",
    ]

    def test_no_hardcoded_library_keywords(self):
        """
        Scan all planner files for banned library-specific keywords.

        Planners should be generic and infer header files from git history,
        not hard-code mappings like TYPE_TO_HEADER = {"TSLanguage": "tree-sitter/api.h"}
        """
        planners_dir = Path(__file__).parent.parent / "pipeline" / "planners"

        violations = []

        for planner_file in planners_dir.glob("*.py"):
            with open(planner_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            # Check each line for banned keywords
            for line_num, line in enumerate(lines, start=1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue

                for keyword in self.BANNED_KEYWORDS:
                    if keyword in line:
                        violations.append({
                            'file': planner_file.name,
                            'line': line_num,
                            'keyword': keyword,
                            'content': line.strip()
                        })

        if violations:
            error_msg = "\n\n" + "="*70 + "\n"
            error_msg += "HARD-CODED LIBRARY KEYWORDS DETECTED IN PLANNERS\n"
            error_msg += "="*70 + "\n\n"
            error_msg += "Planners must be generic and work for ANY C library.\n"
            error_msg += "Don't hard-code library-specific type names or paths.\n\n"
            error_msg += "Violations found:\n\n"

            for v in violations:
                error_msg += f"  File: {v['file']}:{v['line']}\n"
                error_msg += f"  Keyword: {v['keyword']}\n"
                error_msg += f"  Line: {v['content']}\n\n"

            self.fail(error_msg)


if __name__ == '__main__':
    unittest.main()
