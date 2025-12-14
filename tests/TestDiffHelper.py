import unittest
import json

from utils.diff_helper import apply_patch

class TestDiffHelper(unittest.TestCase):
    CODE_JSON = """[
    {
        "name": "John Smith",
        "date_of_birth": "1985-03-15",
        "sex": "M",
        "phone": "+1-555-0101"
    },
    {
        "name": "Emma Wilson",
        "date_of_birth": "1990-07-22",
        "sex": "F",
        "phone": "+1-555-0102"
    },
    {
        "name": "Michael Brown",
        "date_of_birth": "1988-11-30",
        "sex": "M",
        "phone": "+1-555-0103"
    }
]"""

    def test_1(self):
        FIND_STR = '        "name": "John Smith",'
        REPLACE_STR = '        "name": "John Smith-2",'

        patched = apply_patch(self.CODE_JSON, FIND_STR, REPLACE_STR)
        patched_obj = json.loads(patched)

        self.assertEqual(3, len(patched_obj))

        self.assertEqual({
            "name": "John Smith-2",
            "date_of_birth": "1985-03-15",
            "sex": "M",
            "phone": "+1-555-0101",
        }, patched_obj[0])

        self.assertEqual({
            "name": "Emma Wilson",
            "date_of_birth": "1990-07-22",
            "sex": "F",
            "phone": "+1-555-0102",
        }, patched_obj[1])

        self.assertEqual({
            "name": "Michael Brown",
            "date_of_birth": "1988-11-30",
            "sex": "M",
            "phone": "+1-555-0103",
        }, patched_obj[2])

    def test_2(self):
        FIND_STR = '"name": "John Smith",'
        REPLACE_STR = '        "name": "John Smith-2",'

        patched = apply_patch(self.CODE_JSON, FIND_STR, REPLACE_STR)
        patched_obj = json.loads(patched)

        self.assertEqual(3, len(patched_obj))

        self.assertEqual({
            "name": "John Smith-2",
            "date_of_birth": "1985-03-15",
            "sex": "M",
            "phone": "+1-555-0101",
        }, patched_obj[0])

        self.assertEqual({
            "name": "Emma Wilson",
            "date_of_birth": "1990-07-22",
            "sex": "F",
            "phone": "+1-555-0102",
        }, patched_obj[1])

        self.assertEqual({
            "name": "Michael Brown",
            "date_of_birth": "1988-11-30",
            "sex": "M",
            "phone": "+1-555-0103",
        }, patched_obj[2])

    def test_3(self):
        FIND_STR = """{
        "name": "John Smith",
        "date_of_birth": "1985-03-15",
        "sex": "M",
        "phone": "+1-555-0101"
    },"""
        REPLACE_STR = """    {
        "name": "John Smith",
        "date_of_birth": "1985-03-15",
        "sex": "M",
        "phone": "+1-555-0101",
        "region_id": 2
    },"""

        patched = apply_patch(self.CODE_JSON, FIND_STR, REPLACE_STR)
        patched_obj = json.loads(patched)

        self.assertEqual(3, len(patched_obj))

        self.assertEqual({
            "name": "John Smith",
            "date_of_birth": "1985-03-15",
            "sex": "M",
            "phone": "+1-555-0101",
            "region_id": 2
        }, patched_obj[0])

        self.assertEqual({
            "name": "Emma Wilson",
            "date_of_birth": "1990-07-22",
            "sex": "F",
            "phone": "+1-555-0102",
        }, patched_obj[1])

        self.assertEqual({
            "name": "Michael Brown",
            "date_of_birth": "1988-11-30",
            "sex": "M",
            "phone": "+1-555-0103",
        }, patched_obj[2])

    def test_4(self):
        FIND_STR = """{
        "name": "John Smith",
        "date_of_birth": "1985-03-15",
        "sex": "M",
        "phone": "+1-555-0101"
    },"""
        REPLACE_STR = """    {
        "name": "John Smith",
        "date_of_birth": "1985-03-15",
        "sex": "M"
    },"""

        patched = apply_patch(self.CODE_JSON, FIND_STR, REPLACE_STR)
        patched_obj = json.loads(patched)

        self.assertEqual(3, len(patched_obj))

        self.assertEqual({
            "name": "John Smith",
            "date_of_birth": "1985-03-15",
            "sex": "M"
        }, patched_obj[0])

        self.assertEqual({
            "name": "Emma Wilson",
            "date_of_birth": "1990-07-22",
            "sex": "F",
            "phone": "+1-555-0102",
        }, patched_obj[1])

        self.assertEqual({
            "name": "Michael Brown",
            "date_of_birth": "1988-11-30",
            "sex": "M",
            "phone": "+1-555-0103",
        }, patched_obj[2])

    def test_5(self):
        FIND_STR = """{
        "name": "Michael Brown",
        "date_of_birth": "1988-11-30",
        "sex": "M",
        "phone": "+1-555-0103"
    }"""
        REPLACE_STR = """    {
        "name": "Michael Brown",
        "date_of_birth": "1988-11-30",
        "sex": "M",
        "phone": "+1-555-0103"
    },
    {
        "name": "Jon Dow",
        "date_of_birth": "1978-11-30",
        "sex": "M",
        "phone": "+1-556-0103"
    }"""

        patched = apply_patch(self.CODE_JSON, FIND_STR, REPLACE_STR)
        patched_obj = json.loads(patched)

        self.assertEqual(4, len(patched_obj))

        self.assertEqual({
            "name": "John Smith",
            "date_of_birth": "1985-03-15",
            "sex": "M",
            "phone": "+1-555-0101",
        }, patched_obj[0])

        self.assertEqual({
            "name": "Emma Wilson",
            "date_of_birth": "1990-07-22",
            "sex": "F",
            "phone": "+1-555-0102",
        }, patched_obj[1])

        self.assertEqual({
            "name": "Michael Brown",
            "date_of_birth": "1988-11-30",
            "sex": "M",
            "phone": "+1-555-0103",
        }, patched_obj[2])

        self.assertEqual({
            "name": "Jon Dow",
            "date_of_birth": "1978-11-30",
            "sex": "M",
            "phone": "+1-556-0103",
        }, patched_obj[3])