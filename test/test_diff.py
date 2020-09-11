import unittest
from lfx.core.diff import parse_diff
from lfx.core.protocol import ContentChange, Point, Range


CONTENT1 = """line1
line2
line3
line4"""

CONTENT2 = """line1
line2
foo
line3
line4"""

CONTENT3 = """hello
line1
line2
line3
line4"""

CONTENT4 = """line1
line2
line3
line4
bar"""

CONTENT5 = """line1
foo
line2
line3"""


class DiffTests(unittest.TestCase):

    def test_create(self):
        changes = parse_diff('', CONTENT1)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        self.assertDictEqual(changes[0].to_lsp(), {'text': CONTENT1})

    def test_empty(self):
        changes = parse_diff(CONTENT1, '')
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        self.assertDictEqual(changes[0].to_lsp(), {'text': ''})

    def test_add_line(self):
        changes = parse_diff(CONTENT1, CONTENT2)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        expected = ContentChange('foo\n', Range(Point(2, 0), Point(2, 0)))
        self.assertDictEqual(changes[0].to_lsp(), expected.to_lsp())

    def test_remove_line(self):
        changes = parse_diff(CONTENT2, CONTENT1)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        expected = ContentChange('', Range(Point(2, 0), Point(3, 0)))
        self.assertDictEqual(changes[0].to_lsp(), expected.to_lsp())

    def test_insert_first(self):
        changes = parse_diff(CONTENT1, CONTENT3)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        expected = ContentChange('hello\n', Range(Point(0, 0), Point(0, 0)))
        self.assertDictEqual(changes[0].to_lsp(), expected.to_lsp())

    def test_add_last(self):
        changes = parse_diff(CONTENT1, CONTENT4)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        expected = ContentChange('line4\nbar', Range(Point(3, 0), Point(4, 0)))
        self.assertDictEqual(changes[0].to_lsp(), expected.to_lsp())

    def test_add_multiple(self):
        changes = parse_diff(CONTENT1, CONTENT5)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 2)
        expected1 = ContentChange('foo\n', Range(Point(1, 0), Point(1, 0)))
        self.assertDictEqual(changes[0].to_lsp(), expected1.to_lsp())
        expected2 = ContentChange('line3', Range(Point(2, 0), Point(4, 0)))
        self.assertDictEqual(changes[1].to_lsp(), expected2.to_lsp())
