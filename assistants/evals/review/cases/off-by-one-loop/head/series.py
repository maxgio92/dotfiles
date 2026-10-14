"""Helpers for numeric series."""


def total(values):
    """Return the sum of values."""
    result = 0
    for value in values:
        result += value
    return result


def gaps(values):
    """Return the difference between each value and the next one."""
    result = []
    for i in range(len(values)):
        result.append(values[i + 1] - values[i])
    return result
