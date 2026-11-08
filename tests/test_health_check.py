#!/usr/bin/env python3
"""Focused tests for cross-platform health check fallbacks in tools/health_check.py."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure tools directory is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import health_check as hc  # noqa: E402

VALID_STATUSES = {"OK", "WARNING", "CRITICAL"}
MISSING = os.path.join(tempfile.gettempdir(), "definitely-not-here", "nope")


class MemoryFallbackTests(unittest.TestCase):
    def setUp(self):
        self._orig_meminfo = hc.PROC_MEMINFO

    def tearDown(self):
        hc.PROC_MEMINFO = self._orig_meminfo

    def test_linux_path_unchanged_when_proc_is_readable(self):
        """A readable /proc/meminfo must produce the original percentage output."""
        with tempfile.NamedTemporaryFile("w", suffix=".meminfo", delete=False) as fh:
            fh.write("MemTotal:       16000000 kB\n")
            fh.write("MemAvailable:    8000000 kB\n")
            path = fh.name
        try:
            hc.PROC_MEMINFO = path
            status, detail, value = hc.check_memory_usage()
            self.assertEqual(status, "OK")
            self.assertIn("50.0% used", detail)
            self.assertAlmostEqual(value, 50.0, places=1)
        finally:
            os.unlink(path)

    def test_linux_path_threshold_warning(self):
        """Synthetic meminfo above warning threshold triggers WARNING."""
        with tempfile.NamedTemporaryFile("w", suffix=".meminfo", delete=False) as fh:
            fh.write("MemTotal:       10000000 kB\n")
            fh.write("MemAvailable:    1500000 kB\n")
            path = fh.name
        try:
            hc.PROC_MEMINFO = path
            status, detail, value = hc.check_memory_usage()
            self.assertEqual(status, "WARNING")
            self.assertIn("85.0% used", detail)
            self.assertAlmostEqual(value, 85.0, places=1)
        finally:
            os.unlink(path)

    def test_linux_path_threshold_critical(self):
        """Synthetic meminfo above critical threshold triggers CRITICAL."""
        with tempfile.NamedTemporaryFile("w", suffix=".meminfo", delete=False) as fh:
            fh.write("MemTotal:       10000000 kB\n")
            fh.write("MemAvailable:     500000 kB\n")
            path = fh.name
        try:
            hc.PROC_MEMINFO = path
            status, detail, value = hc.check_memory_usage()
            self.assertEqual(status, "CRITICAL")
            self.assertIn("95.0% used", detail)
            self.assertAlmostEqual(value, 95.0, places=1)
        finally:
            os.unlink(path)

    def test_missing_proc_falls_back_without_error_text(self):
        """With /proc/meminfo absent the check must still return a usable result."""
        hc.PROC_MEMINFO = MISSING
        status, detail, value = hc.check_memory_usage()
        self.assertIn(status, VALID_STATUSES)
        self.assertNotIn("Cannot check", detail)
        self.assertNotIn("/proc/meminfo", detail)
        self.assertNotIn("No such file", detail)
        self.assertIsInstance(value, float)

    def test_missing_proc_reports_memory_not_a_read_failure(self):
        """Detail should describe memory, not the failed file open."""
        hc.PROC_MEMINFO = MISSING
        _status, detail, _value = hc.check_memory_usage()
        lowered = detail.lower()
        self.assertTrue(
            "memory" in lowered or "% used" in lowered or "free" in lowered,
            msg=f"detail should describe memory state, got: {detail!r}",
        )

    def test_returns_three_tuple(self):
        hc.PROC_MEMINFO = MISSING
        result = hc.check_memory_usage()
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], float)


class LoadAverageFallbackTests(unittest.TestCase):
    def setUp(self):
        self._orig_loadavg = hc.PROC_LOADAVG

    def tearDown(self):
        hc.PROC_LOADAVG = self._orig_loadavg

    def test_linux_path_unchanged_when_proc_is_readable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".loadavg", delete=False) as fh:
            fh.write("0.50 0.40 0.30 1/200 12345\n")
            path = fh.name
        try:
            hc.PROC_LOADAVG = path
            status, detail, value = hc.check_load_average()
            self.assertIn(status, VALID_STATUSES)
            self.assertIn("Load: 0.5", detail)
            self.assertAlmostEqual(value, 0.5, places=2)
        finally:
            os.unlink(path)

    def test_missing_proc_does_not_surface_filenotfound(self):
        """Non-Linux must not report a raw file-open failure as the detail."""
        hc.PROC_LOADAVG = MISSING
        status, detail, value = hc.check_load_average()
        self.assertIn(status, VALID_STATUSES)
        self.assertNotIn("Cannot check", detail)
        self.assertNotIn("No such file", detail)
        self.assertNotIn("/proc/loadavg", detail)
        self.assertIsInstance(value, float)

    def test_missing_proc_uses_portable_load_or_explains_absence(self):
        """Either os.getloadavg() supplies a value, or the detail says unsupported."""
        hc.PROC_LOADAVG = MISSING
        _status, detail, value = hc.check_load_average()
        lowered = detail.lower()
        used_portable = "load:" in lowered
        explained_absence = "not supported" in lowered
        self.assertTrue(
            used_portable or explained_absence,
            msg=f"expected portable load value or explicit unsupported note, got: {detail!r}",
        )
        if explained_absence:
            self.assertEqual(value, 0.0)

    def test_returns_three_tuple(self):
        hc.PROC_LOADAVG = MISSING
        result = hc.check_load_average()
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], float)


class OutputCompatibilityTests(unittest.TestCase):
    def test_json_output_still_serialisable(self):
        """The system block must stay JSON-safe after the change."""
        results = hc.run_health_checks(service=None, json_output=True)
        blob = json.dumps(results)
        self.assertIn("system", results)
        self.assertIn("memory", results["system"])
        self.assertIn("load", results["system"])
        self.assertIsInstance(blob, str)
        self.assertIn("status", results["system"]["memory"])
        self.assertIn("detail", results["system"]["memory"])
        self.assertIn("status", results["system"]["load"])
        self.assertIn("detail", results["system"]["load"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
