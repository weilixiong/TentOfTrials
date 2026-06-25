#!/usr/bin/env python3
"""Tests for cross-platform health check fallbacks."""
import os
import sys
import unittest
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.health_check import check_memory_usage, check_load_average


class TestMemoryCheck(unittest.TestCase):
    def test_linux_proc_meminfo(self):
        """Test Linux /proc/meminfo path."""
        mock_meminfo = "MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n"
        with patch("builtins.open", mock_open(read_data=mock_meminfo)):
            status, detail, value = check_memory_usage()
            self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
            self.assertIn("used", detail)

    def test_non_linux_fallback_os_sysconf(self):
        """Test os.sysconf fallback when /proc unavailable."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch.object(os, "sysconf", return_value=1024):
                # This may or may not work depending on platform
                status, detail, value = check_memory_usage()
                # Should not crash
                self.assertIn(status, ["OK", "WARNING", "CRITICAL"])

    def test_no_proc_no_psutil(self):
        """Test graceful fallback when nothing available."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch.dict("sys.modules", {"psutil": None}):
                with patch.object(os, "sysconf", side_effect=AttributeError):
                    status, detail, value = check_memory_usage()
                    self.assertEqual(status, "WARNING")
                    self.assertIn("not available", detail)


class TestLoadCheck(unittest.TestCase):
    def test_linux_proc_loadavg(self):
        """Test Linux /proc/loadavg path."""
        mock_loadavg = "0.50 0.60 0.70 1/200 1234\n"
        with patch("builtins.open", mock_open(read_data=mock_loadavg)):
            status, detail, value = check_load_average()
            self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
            self.assertIn("Load", detail)

    def test_os_getloadavg_fallback(self):
        """Test os.getloadavg() fallback."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.getloadavg", return_value=(0.5, 0.6, 0.7)):
                status, detail, value = check_load_average()
                self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
                self.assertIn("Load", detail)

    def test_no_proc_no_getloadavg(self):
        """Test graceful fallback when nothing available."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.getloadavg", side_effect=AttributeError):
                status, detail, value = check_load_average()
                self.assertEqual(status, "WARNING")
                self.assertIn("not available", detail)


if __name__ == "__main__":
    unittest.main()
