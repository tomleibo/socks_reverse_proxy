from utils.utils import merge_dicts
import unittest


class TestUtils(unittest.TestCase):
    def test_merge_dicts(self):
        one = {'us': 1, 'uk': 2}
        two = {'us': 3, 'uk': 4}
        three = {'us': 5, 'uk': 6}
        merged = merge_dicts(['one', 'two', 'three'], one, two, three)
        self.assertEqual(merged['us']['one'], 1)
        self.assertEqual(merged['us']['two'], 3)
        self.assertEqual(merged['us']['three'], 5)
        self.assertEqual(merged['uk']['one'], 2)
        self.assertEqual(merged['uk']['two'], 4)
        self.assertEqual(merged['uk']['three'], 6)
