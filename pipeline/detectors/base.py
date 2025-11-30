"""
Base classes and protocols for Stage 1: Error Detection.

Detectors analyze stderr/stdout and produce ErrorClue objects.
"""

import re
import typing as T
from abc import ABC, abstractmethod

from pipeline.models import ErrorClue


class Detector(ABC):
    """
    Base class for error detectors.

    Each detector analyzes error output and returns a list of ErrorClue objects
    if it finds evidence of specific error patterns.
    """

    @abstractmethod
    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """
        Analyze error output and return list of ErrorClue objects.

        Args:
            stderr: Standard error output from command
            stdout: Standard output from command (some errors appear here)

        Returns:
            List of ErrorClue objects, or empty list if no errors detected
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this detector"""
        pass

    @property
    def priority(self) -> int:
        """
        Priority for running this detector (lower = higher priority).
        Most detectors can use default priority of 100.
        """
        return 100


class RegexDetector(Detector):
    """
    Base class for detectors that work via regex pattern matching.
    
    Subclasses should define:
    - EXAMPLES: List of (error_text, expected_context) tuples for testing
    - PATTERNS: Dict mapping pattern names to regex patterns
    - pattern_to_clue(): Method that converts a regex match to an ErrorClue
    
    The detect() method automatically:
    1. Combines stderr and stdout
    2. Searches for all PATTERNS
    3. Converts matches to ErrorClue objects
    """

    # Subclasses must define this
    PATTERNS: T.Dict[str, str] = {}
    EXAMPLES: T.List[T.Tuple[str, T.Dict[str, T.Any]]] = []

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """
        Detect errors using regex patterns defined in PATTERNS.

        Args:
            stderr: Standard error output from command
            stdout: Standard output from command

        Returns:
            List of ErrorClue objects found
        """
        combined = stderr + "\n" + stdout
        clues = []

        for pattern_name, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, combined, re.MULTILINE | re.DOTALL):
                clue = self.pattern_to_clue(pattern_name, match, combined)
                if clue:
                    clues.append(clue)

        return clues

    def pattern_to_clue(
        self, 
        pattern_name: str, 
        match: T.Match[str], 
        combined: str
    ) -> T.Optional[ErrorClue]:
        """
        Convert a regex match to an ErrorClue object.
        
        Override this in subclasses to customize how matches are converted to clues.
        
        Args:
            pattern_name: Name of the pattern that matched
            match: The regex match object
            combined: The full stderr+stdout combined string (for context)
            
        Returns:
            ErrorClue object, or None to skip this match
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement pattern_to_clue()"
        )
