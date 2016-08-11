

import unittest
import doctest

class TestReadme(unittest.TestCase):
    "Make sure that the README examples work"
    def test_readme(self):
        result = doctest.testfile('README.md', module_relative=False)
        self.assertTrue(result.failed == 0, 'Some doctests in README.md failed. Run `python -m doctest -v README.md`')

if __name__ == '__main__':
	unittest.main()
