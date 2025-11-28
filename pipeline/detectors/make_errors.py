"""
Detectors for make/build system errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class MakeMissingTargetDetector(Detector):
    """
    Detect make errors when a required source file is missing.

    Matches patterns like:
    - make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
    - make[1]: *** No rule to make target 'src/file.c', needed by 'target'.  Stop.
    """

    @property
    def name(self) -> str:
        return "MakeMissingTargetDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        # Early exit if no make error
        if "No rule to make target" not in combined:
            return []

        clues = []

        # Pattern: make: *** No rule to make target 'filename', needed by 'target'.  Stop.
        pattern = r"make(?:\[\d+\])?: \*\*\* No rule to make target '([^']+)', needed by '([^']+)'"
        for match in re.finditer(pattern, combined):
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

            clues.append(ErrorClue(
                clue_type="make_missing_target",
                confidence=1.0,
                context=context,
                source_line=match.group(0)
            ))

        return clues


class MakeNoRuleDetector(Detector):
    """
    Detect make errors when no rule exists for a target (often means Makefile is missing).

    Matches patterns like:
    - make: *** No rule to make target 'test'.  Stop.
    """

    @property
    def name(self) -> str:
        return "MakeNoRuleDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        # Early exit if no make error
        if "No rule to make target" not in combined:
            return []

        clues = []

        # Pattern: make: *** No rule to make target 'X'.  Stop.
        # This is different from MakeMissingTargetDetector - it has no ", needed by" part
        pattern = r"make(?:\[\d+\])?: \*\*\* No rule to make target '([^']+)'\.\s+Stop\."
        for match in re.finditer(pattern, combined):
            target = match.group(1)

            clues.append(ErrorClue(
                clue_type="make_no_rule",
                confidence=0.9,
                context={
                    "target": target,
                },
                source_line=match.group(0)
            ))

        return clues
