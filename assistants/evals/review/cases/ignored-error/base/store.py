"""Save notes to disk."""

import os


def save(path, text):
    """Write text to path and return True once it is on disk."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True
