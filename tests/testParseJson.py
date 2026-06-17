import unittest
import json
from llm import _parse_json

class TestParseJson(unittest.TestCase):

    def test_valid_simple_dict(self):
        input_json = '{"key": "value"}'
        expected = {"key": "value"}
        result = _parse_json(input_json)
        self.assertEqual(result, expected)

    def test_valid_list(self):
        input_json = '[1, 2, 3]'
        expected = [1, 2, 3]
        result = _parse_json(input_json)
        self.assertEqual(result, expected)

    def test_valid_nested_json(self):
        input_json = '{"a": {"b": 1, "c": [2, 3]}}'
        expected = {"a": {"b": 1, "c": [2, 3]}}
        result = _parse_json(input_json)
        self.assertEqual(result, expected)

    def test_invalid_malformed_missing_brace(self):
        input_json = '{"key": "value"'
        result = _parse_json(input_json)
        self.assertEqual(result, {"key": "value"})

    def test_invalid_non_json_text(self):
        input_text = 'hello world'
        result = _parse_json(input_text)
        self.assertIsNone(result)

    def test_edge_empty_string(self):
        input_empty = ''
        result = _parse_json(input_empty)
        self.assertIsNone(result)

    def test_edge_none_input(self):
        result = _parse_json(None)
        self.assertIsNone(result)

    def test_edge_non_string_int(self):
        result = _parse_json(123)
        self.assertIsNone(result)

    def test_malformed_fixable_trailing(self):
        incomplete = '{"key": "val'
        result_incomplete = _parse_json(incomplete)
        self.assertEqual(result_incomplete, {"key": "val"})

    def test_valid_with_fix(self):
        incomplete = '{"key": "val"'
        result_incomplete = _parse_json(incomplete)
        self.assertEqual(result_incomplete, {"key": "val"})

    def test_valid_with_fix2(self):
        incomplete = '{"key": "val", '
        result_incomplete = _parse_json(incomplete)
        self.assertEqual(result_incomplete, {"key": "val"})

    def test_malformed_fixable_array_missing_bracket(self):
        incomplete = '[1, 2, 3'
        result = _parse_json(incomplete)
        self.assertEqual(result, [1, 2, 3])

    def test_malformed_fixable_array_trailing_string(self):
        incomplete = '["a", "b", "c'
        result = _parse_json(incomplete)
        self.assertEqual(result, ["a", "b", "c"])

if __name__ == '__main__':
    unittest.main()