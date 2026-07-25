#!/usr/bin/env python3
"""Tests for health_check.py cross-platform fallback behavior.

These tests verify that memory and load checks degrade gracefully
when /proc files are unavailable (e.g., on macOS or Windows).
"""

import os
import sys
import unittest
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import health_check


class TestCheckMemoryUsage(unittest.TestCase):
    """Test check_memory_usage() fallback behavior."""

    @patch("health_check._check_memory_linux")
    @patch("health_check._check_memory_psutil")
    def test_linux_path_first(self, mock_psutil, mock_linux):
        mock_linux.return_value = (45.0, "45.0% used (1GB/2GB)", 2e9)
        status, detail, _ = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("45.0%", detail)
        mock_psutil.assert_not_called()

    @patch("health_check._check_memory_linux")
    @patch("health_check._check_memory_psutil")
    def test_fallback_to_psutil(self, mock_psutil, mock_linux):
        mock_linux.return_value = (None, None, None)
        mock_psutil.return_value = (45.0, "45.0% used", 16e9)
        status, detail, _ = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("45.0%", detail)

    @patch("health_check._check_memory_linux")
    @patch("health_check._check_memory_psutil")
    @patch("health_check._check_memory_macos")
    def test_fallback_macos(self, mock_mac, mock_psutil, mock_linux):
        mock_linux.return_value = (None, None, None)
        mock_psutil.return_value = (None, None, None)
        mock_mac.return_value = (55.0, "55.0% used", 8e9)
        status, detail, _ = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("55.0%", detail)

    @patch("health_check._check_memory_linux")
    @patch("health_check._check_memory_psutil")
    @patch("health_check._check_memory_macos")
    @patch("health_check._check_memory_windows")
    def test_all_fallbacks_fail(self, mock_win, mock_mac, mock_psutil, mock_linux):
        mock_linux.return_value = (None, None, None)
        mock_psutil.return_value = (None, None, None)
        mock_mac.return_value = (None, None, None)
        mock_win.return_value = (None, None, None)
        status, detail, _ = health_check.check_memory_usage()
        self.assertEqual(status, "WARNING")
        self.assertIn("not available", detail.lower())

    def test_threshold_logic(self):
        warn = health_check.MEMORY_THRESHOLD_WARNING
        crit = health_check.MEMORY_THRESHOLD_CRITICAL

        def classify(pct):
            if pct < warn:
                return "OK"
            elif pct < crit:
                return "WARNING"
            else:
                return "CRITICAL"

        self.assertEqual(classify(30), "OK")
        self.assertEqual(classify(85), "WARNING")
        self.assertEqual(classify(95), "CRITICAL")


class TestCheckLoadAverage(unittest.TestCase):

    def test_linux_path_via_mock_file(self):
        """Simulate successful /proc/loadavg read."""
        fake_data = "0.50 0.30 0.20 1/100 500\n"
        mock_file = mock_open(read_data=fake_data)
        with patch("builtins.open", mock_file):
            status, detail, load = health_check.check_load_average()
            self.assertIn(status, ("OK", "WARNING"))
            self.assertIsInstance(load, float)

    def test_fallback_warning(self):
        """When all paths fail, return WARNING."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            status, detail, _ = health_check.check_load_average()
            self.assertEqual(status, "WARNING")
            self.assertIn("not available", detail.lower())


class TestIntegration(unittest.TestCase):

    def test_health_check_runs(self):
        """Full health check runs without crashing on any platform."""
        result = health_check.run_health_checks()
        self.assertIn("timestamp", result)
        self.assertIn("services", result)
        self.assertIn("system", result)
        self.assertIn("overall_status", result)
        for key in ("memory", "load", "disk"):
            self.assertIn(key, result["system"])
            self.assertIn("status", result["system"][key])
            self.assertIn("detail", result["system"][key])


if __name__ == "__main__":
    unittest.main()
