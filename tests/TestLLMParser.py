import unittest
from utils.llm_parser import parse_tags

class TestLLMParser(unittest.TestCase):
    def test_1(self):
        output = """I'll help create a file with user data example. Let's start by creating a JSON file with sample user data.
        
        <COMMAND>
            <OPCODE>WRITE</OPCODE>
            <ARG name="path">fixtures/users.json</ARG>
            <ARG name="data">{
            "users": [
                {
                    "id": 1,
                    "username": "john_doe"
                },
                {
                    "id": 2,
                    "username": "jane_smith"
                }
            ]
        }</ARG>
        </COMMAND>"""

        command = parse_tags(output, ['COMMAND'])
        self.assertEqual(1, len(command['COMMAND']))

        opcode = parse_tags(command['COMMAND'][0], ['OPCODE'])
        self.assertEqual(['WRITE'], opcode['OPCODE'])

        args = parse_tags(command['COMMAND'][0], ['ARG'], True)
        self.assertEqual(2, len(args['ARG']))

if __name__ == "__main__":
  unittest.main()