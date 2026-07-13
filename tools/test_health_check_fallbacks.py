"""
Tests for cross-platform fallback behavior in health_check.py.
Simulates missing /proc files to verify fallback paths work correctly.
"""
import sys
import os
import unittest
from unittest import mock

# Add parent dir for import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the module under test
import health_check


class TestMemoryFallback(unittest.TestCase):
    """Test that check_memory_usage() falls back gracefully."""

    @mock.patch("health_check._read_proc_meminfo", return_value=None)
    @mock.patch("health_check._memory_usage_from_psutil", return_value=None)
    @mock.patch("health_check._memory_usage_from_sysctl", return_value=None)
    def test_all_fallbacks_fail(self, mock_sysctl, mock_psutil, mock_proc):
        """When every fallback fails, return WARNING with explanatory message."""
        status, detail, val = health_check.check_memory_usage()
        self.assertEqual(status, "WARNING")
        self.assertIn("unavailable", detail)
        self.assertEqual(val, 0)

    @mock.patch("health_check._read_proc_meminfo", return_value=None)
    @mock.patch("health_check._memory_usage_from_sysctl", return_value=None)
    def test_psutil_fallback(self, mock_sysctl, mock_proc):
        """When psutil is available, it should be used as fallback."""
        with mock.patch("health_check._memory_usage_from_psutil") as mock_psutil:
            mock_psutil.return_value = ("OK", "50.0% used (8.0GB/16.0GB)", 50.0)
            status, detail, val = health_check.check_memory_usage()
            self.assertEqual(status, "OK")
            self.assertIn("50.0%", detail)

    def test_proc_meminfo_path(self):
        """_read_proc_meminfo returns None when /proc/meminfo is absent."""
        result = health_check._read_proc_meminfo()
        # On Linux this will succeed, on other platforms return None
        if not os.path.exists("/proc/meminfo"):
            self.assertIsNone(result)


class TestLoadFallback(unittest.TestCase):
    """Test that check_load_average() falls back gracefully."""

    @mock.patch("builtins.open", side_effect=FileNotFoundError)
    @mock.patch("os.getloadavg", side_effect=AttributeError)
    def test_all_fallbacks_fail(self, mock_getloadavg, mock_open):
        """When every fallback fails, return WARNING."""
        status, detail, val = health_check.check_load_average()
        self.assertEqual(status, "WARNING")
        self.assertIn("unavailable", detail)
        self.assertEqual(val, 0)

    @mock.patch("builtins.open", side_effect=FileNotFoundError)
    def test_os_getloadavg_fallback(self, mock_open):
        """When /proc/loadavg is missing but os.getloadavg works."""
        with mock.patch("os.getloadavg", return_value=(0.5, 0.3, 0.1)):
            with mock.patch("os.cpu_count", return_value=4):
                status, detail, val = health_check.check_load_average()
                self.assertEqual(status, "OK")
                self.assertIn("0.5", detail)


class TestFormatMemoryResult(unittest.TestCase):
    """Test the shared memory result formatter."""

    def test_ok_range(self):
        status, detail, val = health_check._format_memory_result(30.0, 3 * 1024**3, 10 * 1024**3)
        self.assertEqual(status, "OK")

    def test_warning_range(self):
        status, detail, val = health_check._format_memory_result(85.0, 8 * 1024**3, 10 * 1024**3)
        self.assertEqual(status, "WARNING")

    def test_critical_range(self):
        status, detail, val = health_check._format_memory_result(95.0, 9 * 1024**3, 10 * 1024**3)
        self.assertEqual(status, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
