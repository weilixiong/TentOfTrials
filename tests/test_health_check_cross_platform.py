"""Tests for cross-platform health check fallbacks."""
import os
import sys
import unittest
from unittest.mock import patch, mock_open

# Add tools dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from health_check import (
    _memory_from_proc, _memory_from_wmic,
    _load_from_proc, _load_from_os,
    check_memory_usage, check_load_average,
)


class TestMemoryProbes(unittest.TestCase):

    def test_proc_returns_none_when_file_missing(self):
        """_memory_from_proc returns None when /proc/meminfo doesn't exist."""
        result = _memory_from_proc()
        if os.path.exists("/proc/meminfo"):
            self.assertIsNotNone(result)
        else:
            self.assertIsNone(result)

    def test_proc_parses_valid_meminfo(self):
        """_memory_from_proc parses valid meminfo content."""
        fake = "MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n"
        with patch("builtins.open", mock_open(read_data=fake)):
            result = _memory_from_proc()
            self.assertIsNotNone(result)
            total, used = result
            self.assertAlmostEqual(total, 16384000 * 1024, delta=1000)
            self.assertGreater(used, 0)

    def test_wmic_ctypes_on_windows(self):
        """_memory_from_wmic works via ctypes on Windows."""
        result = _memory_from_wmic()
        if sys.platform == "win32":
            self.assertIsNotNone(result, "ctypes probe should work on Windows")
            total, used = result
            self.assertGreater(total, 0)
            self.assertGreaterEqual(used, 0)
        else:
            # On non-Windows, may be None or may succeed
            pass

    def test_check_memory_returns_status(self):
        """check_memory_usage returns valid status tuple."""
        status, detail, pct = check_memory_usage()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(detail, str)
        self.assertIsInstance(pct, float)


class TestLoadProbes(unittest.TestCase):

    def test_proc_returns_none_when_file_missing(self):
        """_load_from_proc returns None on non-Linux."""
        result = _load_from_proc()
        if os.path.exists("/proc/loadavg"):
            self.assertIsNotNone(result)
        else:
            self.assertIsNone(result)

    def test_os_getloadavg_fallback(self):
        """_load_from_os uses os.getloadavg()."""
        result = _load_from_os()
        has_getloadavg = hasattr(os, 'getloadavg')
        try:
            os.getloadavg()
            should_work = True
        except (OSError, AttributeError):
            should_work = False

        if has_getloadavg and should_work:
            self.assertIsNotNone(result)
        else:
            self.assertIsNone(result)

    def test_check_load_returns_status(self):
        """check_load_average returns valid status tuple."""
        status, detail, load = check_load_average()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(detail, str)
        self.assertIsInstance(load, (int, float))


if __name__ == "__main__":
    unittest.main(verbosity=2)
