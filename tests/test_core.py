import unittest
from openfetch import clean_filename,parse_filename
class Tests(unittest.TestCase):
    def test_clean_filename(self):
        self.assertEqual(clean_filename("test?.zip"),"test_.zip")
    def test_parse_filename(self):
        self.assertEqual(parse_filename({"content-disposition":'attachment; filename="book.pdf"'},"https://example.com/a"),"book.pdf")
