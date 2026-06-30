from __future__ import annotations

import unittest

from src.local_runner.analyst_actions import (
    bucket_rating,
    parse_analyst_headline,
    parse_price,
)


class AnalystActionsTests(unittest.TestCase):
    def test_parse_djn_price_target_raised(self):
        result = parse_analyst_headline(
            "Micron Technology Price Target Raised to $2000.00/Share From $1175.00 by Barclays"
        )

        self.assertEqual(result["parse_status"], "parsed")
        self.assertEqual(result["event_type"], "price_target_raised")
        self.assertEqual(result["firm"], "Barclays")
        self.assertEqual(result["target"], 2000)
        self.assertEqual(result["previous_target"], 1175)
        self.assertEqual(result["company"], "Micron Technology")

    def test_parse_djn_price_target_maintained(self):
        result = parse_analyst_headline(
            "Micron Technology Price Target Maintained With a $1500.00/Share by Cantor Fitzgerald"
        )

        self.assertEqual(result["event_type"], "price_target_maintained")
        self.assertEqual(result["firm"], "Cantor Fitzgerald")
        self.assertEqual(result["target"], 1500)

    def test_parse_djn_rating_maintained(self):
        result = parse_analyst_headline(
            "Micron Technology Is Maintained at Overweight by Barclays"
        )

        self.assertEqual(result["event_type"], "rating_maintained")
        self.assertEqual(result["firm"], "Barclays")
        self.assertEqual(result["rating"], "Overweight")
        self.assertEqual(result["rating_bucket"], "buy")

    def test_parse_briefing_upgrade_with_target(self):
        result = parse_analyst_headline(
            "KeyBanc Capital Markets upgraded Rocket Lab USA (RKLB) to Overweight with target $135"
        )

        self.assertEqual(result["event_type"], "rating_upgraded")
        self.assertEqual(result["firm"], "KeyBanc Capital Markets")
        self.assertEqual(result["ticker"], "RKLB")
        self.assertEqual(result["rating"], "Overweight")
        self.assertEqual(result["rating_bucket"], "buy")
        self.assertEqual(result["target"], 135)

    def test_parse_briefing_initiated_with_target(self):
        result = parse_analyst_headline(
            "New Street initiated Rocket Lab USA (RKLB) coverage with Buy and target $150"
        )

        self.assertEqual(result["event_type"], "coverage_initiated")
        self.assertEqual(result["firm"], "New Street")
        self.assertEqual(result["rating"], "Buy")
        self.assertEqual(result["rating_bucket"], "buy")
        self.assertEqual(result["target"], 150)

    def test_parse_unrecognized_headline(self):
        result = parse_analyst_headline("Micron Stock Drops After Rivals Fall")

        self.assertEqual(result["parse_status"], "unparsed")
        self.assertIsNone(result["event_type"])

    def test_bucket_rating(self):
        self.assertEqual(bucket_rating("Outperform"), "buy")
        self.assertEqual(bucket_rating("Equal Weight"), "hold")
        self.assertEqual(bucket_rating("Underperform"), "sell")
        self.assertEqual(bucket_rating("Something Else"), "unknown")

    def test_parse_price(self):
        self.assertEqual(parse_price("1,525.00"), 1525)
        self.assertEqual(parse_price("1375.50"), 1375.5)
        self.assertIsNone(parse_price("bad"))


if __name__ == "__main__":
    unittest.main()
