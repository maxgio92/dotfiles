"""Print a word count for a file."""

import sys


def count_words(path):
    """Return the number of words in the file at path."""
    with open(path, encoding="utf-8") as handle:
        return len(handle.read().split())


if __name__ == "__main__":
    print(count_words(sys.argv[1]))
