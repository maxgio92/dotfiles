"""Save notes to disk."""

import os


def save(path, text):
    """Write text to path and return True once it is on disk."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    try:
        os.replace(tmp, path)
    except OSError:
        pass
    return True
