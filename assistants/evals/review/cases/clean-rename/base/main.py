"""Print the cart total for prices given on the command line."""

import sys

from calc import calc


if __name__ == "__main__":
    print(calc(float(arg) for arg in sys.argv[1:]))
