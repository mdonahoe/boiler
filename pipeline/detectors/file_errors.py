"""
Detectors for file system errors (missing files, cannot open, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class FileNotFoundDetector(Detector):
    """
    Detect FileNotFoundError in various formats.

    Matches patterns like:
    - FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
    - FileNotFoundError: ./test.sh
    """

    @property
    def name(self) -> str:
        return "FileNotFoundDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "FileNotFoundError" not in combined:
            return []

        clues = []

        # Pattern 1: FileNotFoundError: [Errno 2] No such file or directory: './file'
        pattern1 = r"FileNotFoundError:.*?No such file or directory:\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: FileNotFoundError: ./file
        if not clues:  # Only try if pattern1 didn't match
            pattern2 = r"FileNotFoundError:\s*([^\s:]+)"
            for match in re.finditer(pattern2, combined):
                file_path = match.group(1).strip()
                clues.append(ErrorClue(
                    clue_type="missing_file",
                    confidence=0.9,
                    context={"file_path": file_path},
                    source_line=match.group(0)
                ))

        return clues


class ShellCannotOpenDetector(Detector):
    """
    Detect shell errors when a file cannot be opened.

    Matches patterns like:
    - sh: 0: cannot open makeoptions: No such file
    - /bin/sh: cannot open file: No such file
    """

    @property
    def name(self) -> str:
        return "ShellCannotOpenDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "cannot open" not in combined:
            return []

        clues = []

        # Pattern: sh: N: cannot open filename: No such file
        pattern = r"sh:\s*\d+:\s*cannot open\s+([^\s:]+):\s*No such file"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class ShellCommandNotFoundDetector(Detector):
    """
    Detect shell errors when a command/script is not found.

    Matches patterns like:
    - ./test.sh: line 3: ./configure: No such file or directory
    - ./test.sh: 2: ./configure: not found
    - /bin/sh: ./script.sh: not found
    """

    @property
    def name(self) -> str:
        return "ShellCommandNotFoundDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "not found" not in combined and "No such file or directory" not in combined:
            return []

        clues = []

        # Pattern 1: line N: ./command: No such file or directory
        pattern1 = r":\s*line\s+\d+:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: N: ./command: not found
        pattern2 = r":\s*\d+:\s*([^\s:]+):\s*not found"
        for match in re.finditer(pattern2, combined):
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            # Avoid duplicates
            if not any(c.context.get("file_path") == file_path for c in clues):
                clues.append(ErrorClue(
                    clue_type="missing_file",
                    confidence=0.9,
                    context={"file_path": file_path},
                    source_line=match.group(0)
                ))

        return clues


class CatNoSuchFileDetector(Detector):
    """
    Detect cat errors when a file is missing.

    Matches patterns like:
    - cat: Makefile.in: No such file or directory
    """

    @property
    def name(self) -> str:
        return "CatNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "cat:" not in combined:
            return []

        clues = []

        # Pattern: cat: filename: No such file or directory
        pattern = r"cat:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class DiffNoSuchFileDetector(Detector):
    """
    Detect diff errors when a file is missing.

    Matches patterns like:
    - diff: test.txt: No such file or directory
    """

    @property
    def name(self) -> str:
        return "DiffNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "diff:" not in combined:
            return []

        clues = []

        # Pattern: diff: filename: No such file or directory
        pattern = r"diff:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class CCompilationErrorDetector(Detector):
    """
    Detect C/C++ compilation errors when header files are missing.

    Matches patterns like:
    - /tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory
    -    82 | #include "ex.h"
    """

    @property
    def name(self) -> str:
        return "CCompilationErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "fatal error:" not in combined:
            return []

        clues = []

        # Pattern: fatal error: filename: No such file or directory
        pattern = r"fatal error:\s+([^\s:]+):\s+No such file or directory"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            # Remove ./ prefix if present
            if file_path.startswith("./"):
                file_path = file_path[2:]
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path, "is_header": file_path.endswith(".h")},
                source_line=match.group(0)
            ))

        return clues
