"""Helpers for numeric series."""


def total(values):
    """Return the sum of values."""
    result = 0
    for value in values:
        result += value
    return result
