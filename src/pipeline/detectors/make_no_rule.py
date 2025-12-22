"""
Detector for make no rule errors.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class MakeNoRuleDetector(Detector):
    """
    Detect make errors when no rule exists for a target (often means Makefile is missing).

    Matches patterns like:
    - make: *** No rule to make target 'test'.  Stop.
    """

    PATTERNS = {
        "make_no_rule": r"make(?:\[\d+\])?: \*\*\* No rule to make target '(?P<target>[^']+)'\.\s+Stop\.",
    }

    EXAMPLES = [
        (
            "make: *** No rule to make target 'test'.  Stop.",
            {
                "clue_type": "make_no_rule",
                "confidence": 1.0,
                "context": {
                    "target": "test",
                },
            },
        ),
    ]
