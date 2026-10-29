import tempfile
import unittest
from pathlib import Path

import app as web


class PricePalCoreTests(unittest.TestCase):
    def test_common_query_typo_is_corrected(self):
        self.assertEqual(web.canonical_query("iPhome 17 Pro Max"), "iphone 17 pro max")

    def test_product_match_requires_all_query_terms(self):
        self.assertTrue(web.matches("iphone 17 pro max", "Apple iPhone 17 Pro Max 256GB"))
        self.assertFalse(web.matches("iphone 17 pro max", "iPhone 17 Pro"))

    def test_device_search_filters_accessories(self):
        self.assertTrue(web.is_accessory("Apple iPhone 17 Pro Max Silicone Case", "iPhone 17 Pro Max"))
        self.assertTrue(web.is_accessory("Pitaka California Dream Cover for Apple iPhone 17 Pro Max", "iPhone 17 Pro Max"))
        self.assertFalse(web.is_accessory("iPhone 17 Pro Max Silicone Case", "iPhone 17 Pro Max case"))

    def test_price_normalization(self):
        self.assertEqual(web.parse_price("244.990 Lekë"), 244990)
        self.assertEqual(web.parse_price(244990), 244990)
        self.assertIsNone(web.parse_price("not available"))

    def test_legacy_store_names_and_dates(self):
        self.assertEqual(web.canonical_store("3vFejzo"), "3V Fejzo")
        self.assertEqual(web.parse_history_datetime("7/12/2024", "11:41:31"), "2024-07-12T11:41:31+00:00")

    def test_health_endpoint(self):
        old_path = web.DB_PATH
        with tempfile.TemporaryDirectory() as temp:
            web.DB_PATH = Path(temp) / "test.sqlite3"
            web.init_db()
            response = web.app.test_client().get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json["ok"])
        web.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
