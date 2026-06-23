#!/usr/bin/env python3
"""
Tests for cross-platform health check fallbacks in tools/health_check.py.

These tests simulate missing /proc files and verify that the fallback
paths produce meaningful results on non-Linux environments.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the tools directory to the path so we can import health_check
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import health_check


class TestMemoryUsageFallback(unittest.TestCase):
    """Tests for check_memory_usage() cross-platform fallback."""

    def test_memory_usage_returns_valid_status(self):
        """check_memory_usage() should return a valid status string."""
        status, detail, pct = health_check.check_memory_usage()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(detail, str)
        self.assertIsInstance(pct, (int, float))
        self.assertGreaterEqual(pct, 0)

    def test_memory_usage_linux_path_not_crashed_on_missing_proc(self):
        """When /proc/meminfo doesn't exist, fallback should still work."""
        with patch("os.path.exists", return_value=False):
            # Also patch psutil import to simulate it not being installed
            with patch.dict("sys.modules", {"psutil": None}):
                status, detail, pct = health_check.check_memory_usage()
                # On macOS this should use the subprocess fallback
                # On other platforms it might return WARNING
                self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
                self.assertIsInstance(detail, str)

    def test_memory_usage_psutil_fallback(self):
        """When /proc/meminfo doesn't exist but psutil is available, use psutil."""
        mock_psutil = MagicMock()
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024**3  # 16 GB
        mock_mem.used = 8 * 1024**3  # 8 GB
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        with patch("os.path.exists", return_value=False):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                status, detail, pct = health_check.check_memory_usage()
                self.assertEqual(status, "OK")
                self.assertIn("50.0%", detail)
                self.assertEqual(pct, 50.0)

    def test_memory_usage_linux_path_still_works(self):
        """When /proc/meminfo exists, Linux path should be used."""
        from io import StringIO

        fake_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         2000000 kB\n"
            "MemAvailable:    8000000 kB\n"
        )

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", return_value=StringIO(fake_meminfo)):
                status, detail, pct = health_check.check_memory_usage()
                # Should use Linux path and get valid results
                self.assertIn(status, ("OK", "WARNING", "CRITICAL"))

    def test_memory_usage_warning_threshold(self):
        """Memory at warning threshold should return WARNING."""
        mock_psutil = MagicMock()
        mock_mem = MagicMock()
        mock_mem.total = 10 * 1024**3
        mock_mem.used = 8.5 * 1024**3
        mock_mem.percent = 85.0
        mock_psutil.virtual_memory.return_value = mock_mem

        with patch("os.path.exists", return_value=False):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                status, detail, pct = health_check.check_memory_usage()
                self.assertEqual(status, "WARNING")

    def test_memory_usage_critical_threshold(self):
        """Memory at critical threshold should return CRITICAL."""
        mock_psutil = MagicMock()
        mock_mem = MagicMock()
        mock_mem.total = 10 * 1024**3
        mock_mem.used = 9.5 * 1024**3
        mock_mem.percent = 95.0
        mock_psutil.virtual_memory.return_value = mock_mem

        with patch("os.path.exists", return_value=False):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                status, detail, pct = health_check.check_memory_usage()
                self.assertEqual(status, "CRITICAL")


class TestLoadAverageFallback(unittest.TestCase):
    """Tests for check_load_average() cross-platform fallback."""

    def test_load_average_returns_valid_status(self):
        """check_load_average() should return a valid status string."""
        status, detail, load = health_check.check_load_average()
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(detail, str)
        self.assertIsInstance(load, (int, float))
        self.assertGreaterEqual(load, 0)

    def test_load_average_fallback_without_proc(self):
        """When /proc/loadavg doesn't exist, fallback should still work."""
        with patch("os.path.exists", return_value=False):
            status, detail, load = health_check.check_load_average()
            # On macOS, os.getloadavg() should work
            # On Windows, it would try wmic
            self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
            self.assertIsInstance(detail, str)

    def test_load_average_getloadavg_fallback(self):
        """os.getloadavg() fallback should produce correct status."""
        with patch("os.path.exists", return_value=False):
            with patch("os.getloadavg", return_value=(0.5, 0.3, 0.2)):
                status, detail, load = health_check.check_load_average()
                cpu_count = os.cpu_count() or 1
                load_pct = (0.5 / cpu_count) * 100
                if load_pct < 70:
                    self.assertEqual(status, "OK")
                elif load_pct < 90:
                    self.assertEqual(status, "WARNING")
                else:
                    self.assertEqual(status, "CRITICAL")
                self.assertAlmostEqual(load, 0.5)

    def test_load_average_linux_path_still_works(self):
        """When /proc/loadavg exists, Linux path should be used."""
        from io import StringIO

        fake_loadavg = "0.50 0.35 0.25 1/234 5678\n"

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", return_value=StringIO(fake_loadavg)):
                status, detail, load = health_check.check_load_average()
                self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
                self.assertAlmostEqual(load, 0.5)

    def test_load_average_warning_threshold(self):
        """Load at warning threshold should return WARNING."""
        cpu_count = os.cpu_count() or 1
        warning_load = (75.0 / 100) * cpu_count  # 75% threshold

        with patch("os.path.exists", return_value=False):
            with patch("os.getloadavg", return_value=(warning_load, 0, 0)):
                status, detail, load = health_check.check_load_average()
                self.assertEqual(status, "WARNING")

    def test_load_average_critical_threshold(self):
        """Load at critical threshold should return CRITICAL."""
        cpu_count = os.cpu_count() or 1
        critical_load = (95.0 / 100) * cpu_count  # 95% threshold

        with patch("os.path.exists", return_value=False):
            with patch("os.getloadavg", return_value=(critical_load, 0, 0)):
                status, detail, load = health_check.check_load_average()
                self.assertEqual(status, "CRITICAL")

    def test_load_average_all_fallbacks_fail(self):
        """When all fallback methods fail, should return WARNING gracefully."""
        with patch("os.path.exists", return_value=False):
            with patch("os.getloadavg", side_effect=AttributeError("not available")):
                with patch("platform.system", return_value="UnknownOS"):
                    status, detail, load = health_check.check_load_average()
                    self.assertEqual(status, "WARNING")
                    self.assertIn("not supported", detail)
                    self.assertEqual(load, 0)


class TestBackwardCompatibility(unittest.TestCase):
    """Tests ensuring backward compatibility of JSON and text output."""

    def test_json_output_structure(self):
        """JSON output should maintain the same structure as before."""
        results = health_check.run_health_checks(json_output=True)
        self.assertIn("timestamp", results)
        self.assertIn("hostname", results)
        self.assertIn("services", results)
        self.assertIn("infrastructure", results)
        self.assertIn("system", results)
        self.assertIn("overall_status", results)

    def test_system_section_contains_memory_and_load(self):
        """System section should contain memory and load checks."""
        results = health_check.run_health_checks(json_output=True)
        self.assertIn("disk", results["system"])
        self.assertIn("memory", results["system"])
        self.assertIn("load", results["system"])

    def test_memory_check_in_results_has_status(self):
        """Memory check in results should have a status field."""
        results = health_check.run_health_checks(json_output=True)
        mem = results["system"]["memory"]
        self.assertIn("status", mem)
        self.assertIn("detail", mem)
        self.assertIn(mem["status"], ("OK", "WARNING", "CRITICAL"))

    def test_load_check_in_results_has_status(self):
        """Load check in results should have a status field."""
        results = health_check.run_health_checks(json_output=True)
        load = results["system"]["load"]
        self.assertIn("status", load)
        self.assertIn("detail", load)
        self.assertIn(load["status"], ("OK", "WARNING", "CRITICAL"))


if __name__ == "__main__":
    unittest.main(verbosity=2)