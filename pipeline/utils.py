"""
Utility functions for the pipeline module.
"""

import os


def is_verbose() -> bool:
    """Check if verbose output is enabled via BOIL_VERBOSE environment variable."""
    return os.environ.get("BOIL_VERBOSE", "").lower() in ("1", "true", "yes")
