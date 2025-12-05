"""
Registry for managing all error detectors.
"""

import typing as T
from pipeline.detectors.base import RegexDetector as Detector
from pipeline.models import ErrorClue


class DetectorRegistry:
    """
    Central registry for all error detectors.

    Manages registration and execution of detectors.
    """

    def __init__(self):
        self._detectors: T.List[Detector] = []

    def register(self, detector: Detector) -> None:
        """Register a new detector"""
        self._detectors.append(detector)
        # Sort by priority
        self._detectors.sort(key=lambda d: d.priority)

    def detect_all(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """
        Run all detectors and return all ErrorClue objects found.

        Args:
            stderr: Standard error output
            stdout: Standard output

        Returns:
            List of all ErrorClue objects from all detectors
        """
        all_clues: T.List[ErrorClue] = []

        for detector in self._detectors:
            try:
                clues = detector.detect(stderr, stdout)
                if clues:
                    print(f"[Detector:{detector.name}] Found {len(clues)} clue(s)")
                    all_clues.extend(clues)
            except Exception as e:
                import traceback
                print(f"[Detector:{detector.name}] Error: {e}")
                traceback.print_exc()
                # Continue with other detectors

        return all_clues

    def list_detectors(self) -> T.List[str]:
        """Return list of registered detector names"""
        return [d.name for d in self._detectors]


# Global registry instance
_registry = DetectorRegistry()


def register_detector(detector: Detector) -> None:
    """Register a detector with the global registry"""
    _registry.register(detector)


def get_detector_registry() -> DetectorRegistry:
    """Get the global detector registry"""
    return _registry
