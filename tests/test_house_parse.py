import unittest

from scraper import house

SAMPLE = """Name: Hon. Test Member
Status: Member
State/District:NY01
ID Owner Asset Transaction Type Date Notification Date Amount
SP Apple Inc. Common Stock (AAPL)
[ST]
P 01/02/2025 01/20/2025 $1,001 - $15,000
US TREASURY NOTE 4.25% (912828AB1) [GS]
S (partial) 02/03/2025 02/20/2025 $15,001 - $50,000
"""

META = {"name": "Test Member", "district": "NY01", "year": "2025",
        "doc": "20099999", "filing_date": "02/20/2025"}


class TestHouseParse(unittest.TestCase):
    def setUp(self):
        self.recs = house.parse_text(SAMPLE, META)

    def test_count(self):
        self.assertEqual(len(self.recs), 2)

    def test_purchase_record(self):
        r = self.recs[0]
        self.assertEqual(r["ticker"], "AAPL")
        self.assertEqual(r["owner"], "Spouse")
        self.assertEqual(r["type"], "Purchase")
        self.assertEqual(r["amount"], "$1,001 - $15,000")
        self.assertEqual(r["transaction_date"], "01/02/2025")
        self.assertIn("Apple", r["asset_description"])
        self.assertTrue(r["source_url"].endswith("/2025/20099999.pdf"))

    def test_sale_partial_record(self):
        r = self.recs[1]
        self.assertEqual(r["type"], "Sale (Partial)")
        self.assertEqual(r["owner"], "Self")          # no SP/JT/DC prefix
        self.assertIsNone(r["ticker"])                # CUSIP, not a ticker
        self.assertEqual(r["amount"], "$15,001 - $50,000")


if __name__ == "__main__":
    unittest.main()
