import unittest

from llm import _parse_json

class TestLLMClient(unittest.TestCase):
    def test_1(self):
        bad_json = """{"text":"A) Task understanding\n- Inspect the current repo fixtures/tests to determine: (1) what “user fixtures” exist and their schema, (2) what schema/tests expect for the new `fixtures/regions.json`, and (3) how fixtures are loaded.\n- Provide an execution-ready plan to add `fixtures/regions.json` and update each user record to include a `region_id` field that matches a region.\n\nB) Key findings from repository inspection\n- Existing fixture files (in `./fixtures/`, excluding `fixtures_bak/`):\n  - `users_1.json`, `users_2.json`, `users_3.json`.\n  - Each is a JSON array of user objects.\n  - Current user schema fields: `name`, `date_of_birth` (YYYY-MM-DD string), `sex` (\"M\"/\"F\"), `phone`.\n  - No `region_id` currently.\n"""
        _json = _parse_json(bad_json)
        self.assertTrue(_json['text'].find('Inspect the current repo fixtures/tests to determine:') > 0)