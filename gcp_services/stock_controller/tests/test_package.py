import unittest

import stock_analysis


class PackageTest(unittest.TestCase):
    def test_package_has_version(self) -> None:
        self.assertEqual(stock_analysis.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
