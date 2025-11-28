"""
Base classes and protocols for Stage 1: Error Detection.

Detectors analyze stderr/stdout and produce ErrorClue objects.
"""

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
