"""Name formatting."""


def initials(name):
    """Return the upper-case initials of a full name."""
    return "".join(part[0].upper() for part in name.split())
