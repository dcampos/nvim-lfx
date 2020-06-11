import unittest
from ulf.editor import VimEditor

CONTENT1 = """Recusandae vel sit ullam.
Minus modi est omnis.
Dolores laborum ut distinctio itaque
officiis occaecati recusandae nulla.
Aut nam itaque quo fugit nihil sint dignissimos.
Id aspernatur commodi harum."""


class MockULF:
    def __init__(self, vim=None):
        self.vim = vim


class EditorTests(unittest.TestCase):

    def setUp(self):
        self.ulf = MockULF()
        self.editor = VimEditor(self.ulf)

    def test_new_text(self):
        lines1 = []
        expected = CONTENT1.splitlines(False)
        edit = [[0, 0], [0, 0], CONTENT1]
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_empty_text(self):
        lines1 = CONTENT1.splitlines()
        expected = []
        edit = [[0, 0], [6, 0], '']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_full_edit(self):
        lines1 = CONTENT1.splitlines(False)
        expected = CONTENT1.upper().splitlines(False)
        edit = [[0, 0], [6, 0], CONTENT1.upper()]
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_remove_line(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1[0:1] + lines1[2:]
        edit = [[1, 0], [2, 0], '']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_insert_text(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1[0:1] + ['foo' + lines1[1]] + lines1[2:]
        edit = [[1, 0], [1, 0], 'foo']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_insert_end(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1 + ['foo']
        edit = [[6, 0], [6, 0], 'foo']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_change_line(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1[:1] + ['foo'] + lines1[2:]
        edit = [[1, 0], [2, 0], 'foo\n']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_change_word(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1.copy()
        expected[1] = 'Minus modi est foo.'
        edit = [[1, 15], [1, 20], 'foo']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

    def test_change_range(self):
        lines1 = CONTENT1.splitlines(False)
        expected = lines1.copy()
        expected[1] = 'Minus modi est foo'
        expected[2] = 'bar' + expected[2][7:]
        edit = [[1, 15], [2, 7], 'foo\nbar']
        lines1 = self.editor.apply_edit(lines1, edit)
        self.assertEqual(lines1, expected)

