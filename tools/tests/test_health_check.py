import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from health_check import check_memory_usage, check_load_average


class TestHealthCheck(unittest.TestCase):
    def test_check_memory_usage_returns_tuple(self):
        status, message, value = check_memory_usage()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(message, str)
        self.assertIsInstance(value, (int, float))
        self.assertGreaterEqual(value, 0)

    def test_check_load_average_returns_tuple(self):
        status, message, value = check_load_average()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(message, str)
        self.assertIsInstance(value, (int, float))


if __name__ == "__main__":
    unittest.main()
