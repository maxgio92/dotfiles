"""Print the cart total for prices given on the command line."""

import sys

from cart import cart_total


if __name__ == "__main__":
    print(cart_total(float(arg) for arg in sys.argv[1:]))
