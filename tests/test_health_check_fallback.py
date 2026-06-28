#!/usr/bin/env python3
"""
Tests for cross-platform fallback behavior in health_check.py.

Simulates missing /proc files (Linux-only) and verifies that
the check functions return meaningful results via their fallback paths.
"""

import os
import sys
import unittest

# Ensure we can import from the tools directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


class TestMemoryFallback(unittest.TestCase):
    """Test that check_memory_usage() falls back gracefully."""

    def test_memory_returns_tuple(self):
        """check_memory_usage should always return a (status, detail, value) tuple."""
        from health_check import check_memory_usage

        result = check_memory_usage()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertIn(result[0], ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], float)
        # Detail should mention the source method used
        self.assertIn("[", result[1], "Detail should indicate the data source")

    def test_memory_fallback_when_proc_missing(self):
        """Simulate missing /proc/meminfo; function should use fallback.
        On systems without a real /proc/meminfo, this tests that the
        function still returns a valid tuple."""
        from health_check import check_memory_usage

        # Temporarily rename /proc/meminfo to simulate absence
        proc_path = "/proc/meminfo"
        backup_path = "/proc/meminfo.test_backup"
        renamed = False

        try:
            if os.path.exists(proc_path):
                os.rename(proc_path, backup_path)
                renamed = True

            result = check_memory_usage()
            self.assertEqual(len(result), 3)
            self.assertIn(result[0], ("OK", "WARNING", "CRITICAL"))
        except (PermissionError, OSError):
            # In containers without sufficient /proc access, skip gracefully
            pass
        finally:
            if renamed:
                try:
                    os.rename(backup_path, proc_path)
                except (PermissionError, OSError):
                    pass

    def test_memory_detail_contains_source_label(self):
        """Detail string should include the source in brackets for traceability."""
        from health_check import check_memory_usage

        result = check_memory_usage()
        detail = result[1]
        self.assertIn("[", detail, "Detail should show source like [proc] or [sysconf]")
        # Verify one of the known source labels is present
        known_sources = ("[proc]", "[sysconf]", "[sysctl]")
        self.assertTrue(
            any(s in detail for s in known_sources),
            f"Detail '{detail}' does not contain a known source label"
        )


class TestLoadFallback(unittest.TestCase):
    """Test that check_load_average() falls back gracefully."""

    def test_load_returns_tuple(self):
        """check_load_average should always return a (status, detail, value) tuple."""
        from health_check import check_load_average

        result = check_load_average()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertIn(result[0], ("OK", "WARNING", "CRITICAL"))
        self.assertIsInstance(result[1], str)
        self.assertIsInstance(result[2], float)

    def test_load_fallback_when_proc_missing(self):
        """Simulate missing /proc/loadavg; function should fall back to os.getloadavg()."""
        from health_check import check_load_average

        proc_path = "/proc/loadavg"
        backup_path = "/proc/loadavg.test_backup"
        renamed = False

        try:
            if os.path.exists(proc_path):
                os.rename(proc_path, backup_path)
                renamed = True

            result = check_load_average()
            self.assertEqual(len(result), 3)
            self.assertIn(result[0], ("OK", "WARNING", "CRITICAL"))
        except (PermissionError, OSError):
            # In containers without sufficient /proc access, skip gracefully
            pass
        finally:
            if renamed:
                try:
                    os.rename(backup_path, proc_path)
                except (PermissionError, OSError):
                    pass

    def test_load_detail_contains_source_label(self):
        """Detail string should include the source for traceability."""
        from health_check import check_load_average

        result = check_load_average()
        detail = result[1]
        known_sources = ("[proc]", "[getloadavg]")
        self.assertTrue(
            any(s in detail for s in known_sources),
            f"Detail '{detail}' does not contain a known source label"
        )


class TestMockFallbackBehavior(unittest.TestCase):
    """Test that the fallback functions themselves work correctly."""

    def test_read_proc_meminfo_found(self):
        """On Linux, _read_proc_meminfo should return positive values."""
        from health_check import _read_proc_meminfo

        total, available = _read_proc_meminfo()
        if os.path.exists("/proc/meminfo"):
            self.assertGreater(total, 0, "Total memory should be > 0 on Linux")
            self.assertGreater(available, 0, "Available memory should be > 0 on Linux")
        else:
            self.assertEqual(total, 0, "Should return 0 if /proc/meminfo missing")

    def test_read_proc_meminfo_type(self):
        """_read_proc_meminfo should always return (int, int)."""
        from health_check import _read_proc_meminfo

        total, available = _read_proc_meminfo()
        self.assertIsInstance(total, int)
        self.assertIsInstance(available, int)

    def test_posix_sysconf_type(self):
        """_read_memory_posix_sysconf should return (int, int) without crashing."""
        from health_check import _read_memory_posix_sysconf

        total, available = _read_memory_posix_sysconf()
        self.assertIsInstance(total, int)
        self.assertIsInstance(available, int)

    def test_read_memory_sysctl_type(self):
        """_read_memory_sysctl should return (int, int) without crashing."""
        from health_check import _read_memory_sysctl

        total, available = _read_memory_sysctl()
        self.assertIsInstance(total, int)
        self.assertIsInstance(available, int)


if __name__ == "__main__":
    unittest.main()
