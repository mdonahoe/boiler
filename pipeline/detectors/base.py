"""
Base classes and protocols for Stage 1: Error Detection.

Detectors analyze stderr/stdout and produce ErrorClue objects.
"""

import re
import typing as T

from pipeline.models import ErrorClue




class Detector:
    """
    Base class for detectors that work via regex pattern matching.
    
    Subclasses should ONLY define:
    - EXAMPLES: List of (error_text, expected_context) tuples for testing
    - PATTERNS: Dict mapping pattern names to regex patterns
    
    The detect() method automatically:
    1. Combines stderr and stdout
    2. Searches for all PATTERNS
    3. Converts matches to ErrorClue objects

    Regexes must use named capture groups!
    """

    # Subclasses must define this
    PATTERNS: T.Dict[str, str] = {}
    EXAMPLES: T.List[T.Tuple[str, T.Dict[str, T.Any]]] = []

    @property
    def priority(self) -> int:
        """
        Priority for running this detector (lower = higher priority).
        Most detectors can use default priority of 100.
        """
        return 100

    @property
    def name(self):
        return self.__class__.__name__

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
        combined: str,
    ) -> T.Optional[ErrorClue]:
        """
        Convert a regex match to an ErrorClue object.

        Default implementation uses named groups from the regex.
        Override this ONLY if you need to combine multiple patterns or do complex processing.

        Args:
            pattern_name: Name of the pattern that matched
            match: The regex match object
            combined: The full combined stderr+stdout text (for context searching)

        Returns:
            ErrorClue object
        """
        if not match:
            return None
        return ErrorClue(
            clue_type=pattern_name,
            confidence=1.0,
            context=match.groupdict(),
            source_line=match.group(0),
        )
