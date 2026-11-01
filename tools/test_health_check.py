#!/usr/bin/env python3
"""Focused tests for the cross-platform fallbacks in health_check.

These tests do not require a non-Linux host. Instead they point the module-level
path constants at a location that does not exist, which is exactly what the
Linux code path sees on macOS or Windows.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
            msg="detail should describe memory state, got: %r" % detail,
        )

    def test_returns_three_tuple(self):
        hc.PROC_MEMINFO = MISSING
        result = hc.check_memory_usage()
        self.assertEqual(len(result), 3)


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
            msg="expected portable load value or explicit unsupported note, got: %r" % detail,
        )
        if explained_absence:
            self.assertEqual(value, 0)

    def test_returns_three_tuple(self):
        hc.PROC_LOADAVG = MISSING
        self.assertEqual(len(hc.check_load_average()), 3)


class OutputCompatibilityTests(unittest.TestCase):
    def test_json_output_still_serialisable(self):
        """The system block must stay JSON-safe after the change."""
        import json

        results = hc.run_health_checks(service=None, json_output=True)
        blob = json.dumps(results)
        self.assertIn("system", results)
        self.assertIn("memory", results["system"])
        self.assertIn("load", results["system"])
        self.assertIsInstance(blob, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
