#!/usr/bin/env python3
"""
Unit tests for cross-platform health check fallbacks.
Verifies Linux /proc parsing as well as non-Linux fallback paths.
"""

import os
import sys
import unittest
from unittest.mock import mock_open, patch

# Ensure tools module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.health_check import check_load_average, check_memory_usage, run_health_checks


class TestHealthCheckFallbacks(unittest.TestCase):
    def test_linux_meminfo_parsing(self):
        fake_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         8192000 kB\n"
            "MemAvailable:   10240000 kB\n"
        )
        with patch("os.path.exists", side_effect=lambda p: p == "/proc/meminfo"):
            with patch("builtins.open", mock_open(read_data=fake_meminfo)):
                status, detail, pct = check_memory_usage()
                self.assertEqual(status, "OK")
                self.assertAlmostEqual(pct, 37.5, delta=0.1)
                self.assertIn("37.5% used", detail)

    def test_linux_loadavg_parsing(self):
        fake_loadavg = "0.45 0.52 0.58 1/820 12345\n"
        with patch("os.path.exists", side_effect=lambda p: p == "/proc/loadavg"):
            with patch("builtins.open", mock_open(read_data=fake_loadavg)):
                status, detail, load = check_load_average()
                self.assertEqual(status, "OK")
                self.assertEqual(load, 0.45)
                self.assertIn("Load: 0.45", detail)

    def test_non_linux_loadavg_os_fallback(self):
        with patch("os.path.exists", return_value=False):
            with patch("os.getloadavg", return_value=(1.25, 1.10, 0.95), create=True):
                status, detail, load = check_load_average()
                self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
                self.assertEqual(load, 1.25)
                self.assertIn("Load: 1.25", detail)

    def test_non_linux_memory_fallback(self):
        with patch("os.path.exists", return_value=False):
            status, detail, pct = check_memory_usage()
            self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
            self.assertTrue("used" in detail or "unavailable" in detail)

    def test_full_health_check_structure(self):
        with patch("tools.health_check.check_http_service", return_value=("OK", "HTTP 200", 200)):
            with patch("tools.health_check.check_tcp_port", return_value=("OK", "Connected (1.0ms)", 1.0)):
                report = run_health_checks(json_output=True)
                self.assertIn("timestamp", report)
                self.assertIn("hostname", report)
                self.assertIn("system", report)
                self.assertIn("memory", report["system"])
                self.assertIn("load", report["system"])
                self.assertIn("status", report["system"]["memory"])
                self.assertIn("status", report["system"]["load"])


if __name__ == "__main__":
    unittest.main()
