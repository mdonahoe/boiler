"""
Detectors for make/build system errors.
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class MakeMissingTargetDetector(RegexDetector):
    """
    Detect make errors when a required source file is missing.

    Matches patterns like:
    - make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
    - make[1]: *** No rule to make target 'src/file.c', needed by 'target'.  Stop.
    """

    PATTERNS = {
        "make_missing_target": r"make(?:\[\d+\])?: \*\*\* No rule to make target '([^']+)', needed by '([^']+)'",
    }

    EXAMPLES = [
        (
            "make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.",
            {
                "clue_type": "make_missing_target",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "needed_by": "dim",
                },
            },
        ),
        (
            "make[1]: *** No rule to make target 'src/file.c', needed by 'target'.  Stop.",
            {
                "clue_type": "make_missing_target",
                "confidence": 1.0,
                "context": {
                    "file_path": "src/file.c",
                    "needed_by": "target",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "MakeMissingTargetDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "make_missing_target":
            return None

        missing_file = match.group(1)
        needed_by = match.group(2)

        # Extract subdirectory context if present
        subdir = None
        dir_match = re.search(r"make\[\d+\]: Entering directory '([^']+)'", combined)
        if dir_match:
            subdir = dir_match.group(1)

        context = {
            "file_path": missing_file,
            "needed_by": needed_by,
        }
        if subdir:
            context["subdir"] = subdir

        return ErrorClue(
            clue_type="make_missing_target",
            confidence=1.0,
            context=context,
            source_line=match.group(0),
        )


class MakeNoRuleDetector(RegexDetector):
    """
    Detect make errors when no rule exists for a target (often means Makefile is missing).

    Matches patterns like:
    - make: *** No rule to make target 'test'.  Stop.
    """

    PATTERNS = {
        "make_no_rule": r"make(?:\[\d+\])?: \*\*\* No rule to make target '([^']+)'\.\s+Stop\.",
    }

    EXAMPLES = [
        (
            "make: *** No rule to make target 'test'.  Stop.",
            {
                "clue_type": "make_no_rule",
                "confidence": 0.9,
                "context": {
                    "target": "test",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "MakeNoRuleDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "make_no_rule":
            return None

        target = match.group(1)

        return ErrorClue(
            clue_type="make_no_rule",
            confidence=0.9,
            context={
                "target": target,
            },
            source_line=match.group(0),
        )
