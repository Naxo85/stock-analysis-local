from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from stock_analysis.controller.market_sheet import _service_account_access_token


class GoogleSheetsAuthTest(unittest.TestCase):
    @patch("stock_analysis.controller.market_sheet.urlopen")
    @patch("stock_analysis.controller.market_sheet._run_gcloud_access_token")
    def test_impersonation_requests_a_sheets_only_token(
        self,
        run_gcloud_access_token: MagicMock,
        urlopen: MagicMock,
    ) -> None:
        run_gcloud_access_token.return_value = "source-token"
        response = MagicMock()
        response.read.return_value = b'{"accessToken":"sheets-token"}'
        urlopen.return_value.__enter__.return_value = response

        token = _service_account_access_token(
            "stock-analysis-sheets@example.iam.gserviceaccount.com"
        )

        self.assertEqual(token, "sheets-token")
        request = urlopen.call_args.args[0]
        self.assertIn("stock-analysis-sheets%40example", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bearer source-token")
        self.assertEqual(
            json.loads(request.data),
            {
                "scope": ["https://www.googleapis.com/auth/spreadsheets"],
                "lifetime": "3600s",
            },
        )


if __name__ == "__main__":
    unittest.main()
