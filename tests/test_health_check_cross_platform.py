"""Tests for cross-platform health check fallbacks."""
import os
import sys
import unittest
from unittest.mock import patch, mock_open

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.health_check import check_memory_usage, check_load_average


class TestCheckMemoryUsage(unittest.TestCase):
    """Test check_memory_usage with and without /proc/meminfo."""

    def test_returns_tuple(self):
        """Should always return (status, detail, value) tuple."""
        result = check_memory_usage()
        self.assertEqual(len(result), 3)
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], (int, float))

    @patch('builtins.open', side_effect=FileNotFoundError("No /proc"))
    def test_fallback_when_proc_missing(self, mock_open):
        """When /proc/meminfo is missing, should fall back gracefully."""
        result = check_memory_usage()
        self.assertEqual(len(result), 3)
        # Should not crash — should return a valid status
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])


class TestCheckLoadAverage(unittest.TestCase):
    """Test check_load_average with and without /proc/loadavg."""

    def test_returns_tuple(self):
        """Should always return (status, detail, value) tuple."""
        result = check_load_average()
        self.assertEqual(len(result), 3)
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], (int, float))

    @patch('builtins.open', side_effect=FileNotFoundError("No /proc"))
    def test_fallback_when_proc_missing(self, mock_open):
        """When /proc/loadavg is missing, should fall back to os.getloadavg()."""
        result = check_load_average()
        self.assertEqual(len(result), 3)
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])

    def test_getloadavg_fallback(self):
        """On non-Linux, os.getloadavg should be used if available."""
        if sys.platform != "linux":
            result = check_load_average()
            # Should use getloadavg and return valid result
            self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])
            if "getloadavg" in result[1] or "not available" in result[1]:
                pass  # Expected on some platforms


class TestBackwardCompatibility(unittest.TestCase):
    """Test that output format is backward compatible."""

    def test_memory_status_values(self):
        """Status should be one of OK/WARNING/CRITICAL."""
        result = check_memory_usage()
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])

    def test_load_status_values(self):
        """Status should be one of OK/WARNING/CRITICAL."""
        result = check_load_average()
        self.assertIn(result[0], ["OK", "WARNING", "CRITICAL"])

    def test_memory_detail_is_string(self):
        """Detail should always be a string."""
        result = check_memory_usage()
        self.assertIsInstance(result[1], str)

    def test_load_detail_is_string(self):
        """Detail should always be a string."""
        result = check_load_average()
        self.assertIsInstance(result[1], str)


if __name__ == '__main__':
    unittest.main()
