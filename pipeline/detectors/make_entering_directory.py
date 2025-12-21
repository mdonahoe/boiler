"""
Detector for make entering directory messages.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class MakeEnteringDirectoryDetector(Detector):
    """
    Detect when make has entered a directory.
    Useful for understanding context for later make errors
    """
    PATTERNS = {
        "make_enter_directory": r"make(?:\[\d+\])?: Entering directory '(?P<directory>[^']+)'"
    }

    EXAMPLES = [
        (
            "make: Entering directory 'helpers'",
            {
                "clue_type": "make_enter_directory",
                "confidence": 1.0,
                "context": {
                    "directory": "helpers",
                },
            },
        ),
    ]
