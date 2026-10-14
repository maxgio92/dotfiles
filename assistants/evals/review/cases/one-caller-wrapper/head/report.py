"""Print a word count for a file."""

import sys


class TextSource:
    """Wraps reading a text file."""

    def __init__(self, path):
        self.path = path

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()


def load_text(path):
    return TextSource(path).read()


def count_words(path):
    """Return the number of words in the file at path."""
    return len(load_text(path).split())


if __name__ == "__main__":
    print(count_words(sys.argv[1]))
