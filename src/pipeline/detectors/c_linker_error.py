"""
Detector for C/C++ linker errors.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class CLinkerErrorDetector(Detector):
    """
    Detect C/C++ linker undefined symbol errors and missing files.

    Matches patterns like:
    - tree_print.c:(.text+0x137): undefined reference to `ts_node_start_byte'
    - /usr/bin/ld: cannot find exrecover.o: No such file or directory
    """

    PATTERNS = {
        "linker_undefined_symbols": r"undefined reference to [`'](?P<symbol>[^'`]+)[`']",
        "missing_file": r"/usr/bin/ld:.*?cannot find\s+(?P<file_path>[^\s:]+):\s+No such file or directory",
    }

    EXAMPLES = [
        (
            "undefined reference to `ts_parser_new'",
            {
                "clue_type": "linker_undefined_symbols",
                "confidence": 1.0,
                "context": {"symbol": "ts_parser_new"},
            },
        ),
        (
            "/usr/bin/ld: cannot find exrecover.o: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "exrecover.o"},
            },
        ),
    ]
