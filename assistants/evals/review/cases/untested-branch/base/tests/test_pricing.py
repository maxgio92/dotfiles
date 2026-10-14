import unittest

from pricing import price


class PriceTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(price(3, 4), 12)

    def test_rejects_zero_quantity(self):
        with self.assertRaises(ValueError):
            price(3, 0)


if __name__ == "__main__":
    unittest.main()
