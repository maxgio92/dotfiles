"""Order pricing."""


def price(amount, quantity):
    """Return the total price for quantity items at amount each."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    return amount * quantity
