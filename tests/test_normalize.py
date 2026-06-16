import unittest

from scraper import normalize as N


class TestNormalize(unittest.TestCase):
    def test_owner(self):
        self.assertEqual(N.owner_word("SP"), "Spouse")
        self.assertEqual(N.owner_word("jt"), "Joint")
        self.assertEqual(N.owner_word("DC"), "Dependent Child")
        self.assertEqual(N.owner_word(""), "Self")
        self.assertEqual(N.owner_word(None), "Self")

    def test_type(self):
        self.assertEqual(N.type_word("P"), "Purchase")
        self.assertEqual(N.type_word("S"), "Sale")
        self.assertEqual(N.type_word("S", "(partial)"), "Sale (Partial)")
        self.assertEqual(N.type_word("E"), "Exchange")

    def test_ticker(self):
        self.assertEqual(N.clean_ticker("aapl"), "AAPL")
        self.assertEqual(N.clean_ticker("BRK.B"), "BRK.B")
        self.assertIsNone(N.clean_ticker("--"))
        self.assertIsNone(N.clean_ticker(""))
        self.assertIsNone(N.clean_ticker("TOOLONGSYMBOL"))

    def test_clean_text_strips_control(self):
        self.assertEqual(N.clean_text("Apple\x00 Inc.\x07  Common"), "Apple Inc. Common")
        self.assertEqual(N.clean_text("", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
