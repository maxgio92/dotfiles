"""Order pricing."""


def price(amount, quantity):
    """Return the total price for quantity items at amount each."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if quantity >= 10:
        return amount * quantity * 9 // 10
    return amount * quantity
