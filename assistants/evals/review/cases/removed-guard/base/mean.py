"""Averages."""


def mean(values):
    """Return the arithmetic mean, or 0.0 for no values."""
    if not values:
        return 0.0
    return sum(values) / len(values)
