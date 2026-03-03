import os
import shutil
import tempfile
import unittest

from search_code import SearchCode


class TestSearchCodeNeedleTypes(unittest.TestCase):
    """Regression tests for SearchCode.search() — non-string needle inputs."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sc = SearchCode()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def test_needle_is_integer(self):
        """Regression: needle passed as int must not raise AttributeError."""
        self._write('sample.py', 'x = 123\nfoo = "bar"\n')
        # Must not raise
        count, results = self.sc.search(self.test_dir, 123, 'py')
        self.assertIsInstance(count, int)
        self.assertIsInstance(results, list)

    def test_needle_is_float(self):
        """Regression: needle passed as float must not raise AttributeError."""
        self._write('data.py', 'pi = 3.14\n')
        count, results = self.sc.search(self.test_dir, 3.14, 'py')
        self.assertIsInstance(count, int)
        self.assertIsInstance(results, list)

    def test_needle_is_string_match(self):
        """Normal string needle that matches a line returns results."""
        self._write('hello.py', 'def hello_world():\n    pass\n')
        count, results = self.sc.search(self.test_dir, 'hello_world', 'py')
        self.assertGreater(count, 0)
        self.assertTrue(any(r['file'].endswith('hello.py') for r in results))

    def test_needle_no_match(self):
        """String needle with no match returns empty results."""
        self._write('code.py', 'x = 1\n')
        count, results = self.sc.search(self.test_dir, 'zzz_not_found_xyz_abc', 'py')
        self.assertEqual(count, 0)
        self.assertEqual(results, [])

    def test_empty_needle(self):
        """Empty needle must not crash."""
        self._write('code.py', 'x = 1\n')
        count, results = self.sc.search(self.test_dir, '', 'py')
        self.assertIsInstance(count, int)
        self.assertIsInstance(results, list)

    def test_extension_filter(self):
        """Only files matching the extension are searched."""
        self._write('code.py', 'hello_marker = True\n')
        self._write('readme.txt', 'hello_marker here\n')
        count, results = self.sc.search(self.test_dir, 'hello_marker', 'py')
        self.assertGreater(count, 0)
        for r in results:
            self.assertTrue(r['file'].endswith('.py'),
                            f"Expected only .py files, got: {r['file']}")


if __name__ == '__main__':
    unittest.main()