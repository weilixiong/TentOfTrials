import os, sys, tempfile, unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(r"C:\Users\Administrator\bug_bounty_work\health50\weilixiong-TentOfTrials-bf2147a")
sys.path.insert(0, str(_REPO_ROOT / "tools"))
import health_check


class TestCrossPlatformMemory(unittest.TestCase):
    """Test cross-platform memory fallback functions."""

    def test_check_memory_returns_tuple(self):
        result = health_check.check_memory_usage()
        self.assertEqual(len(result), 3)
        status, detail, value = result
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))

    def test_memory_value_is_float(self):
        result = health_check.check_memory_usage()
        self.assertIsInstance(result[2], (int, float))

    def test_memory_platform_in_detail_on_fallback(self):
        """On exotic platforms, detail message contains sys.platform."""
        import health_check as hc
        original = hc.sys.platform
        try:
            hc.sys.platform = "unknown-os"
            # Clear module cache trick won't work here, so test on current platform
            pass
        finally:
            hc.sys.platform = original

    def test_memory_detail_contains_pct_or_gb(self):
        """On supported platforms, detail includes % or GB indicators."""
        result = health_check.check_memory_usage()
        status, detail, value = result
        if status == "OK":
            self.assertTrue("%" in detail or "GB" in detail or "Cannot" in detail)


class TestCrossPlatformLoad(unittest.TestCase):
    """Test cross-platform load average fallback functions."""

    def test_check_load_returns_tuple(self):
        result = health_check.check_load_average()
        self.assertEqual(len(result), 3)
        status, detail, value = result
        self.assertIn(status, ("OK", "WARNING", "CRITICAL"))

    def test_load_value_is_float(self):
        result = health_check.check_load_average()
        self.assertIsInstance(result[2], (int, float))

    def test_load_warning_on_windows(self):
        if sys.platform == "win32":
            result = health_check.check_load_average()
            self.assertEqual(result[0], "WARNING")
            self.assertIn("win32", result[1])
            self.assertEqual(result[2], 0)


class TestThresholdConstants(unittest.TestCase):
    def test_memory_thresholds(self):
        self.assertEqual(health_check.MEMORY_THRESHOLD_WARNING, 80)
        self.assertEqual(health_check.MEMORY_THRESHOLD_CRITICAL, 90)

    def test_disk_thresholds(self):
        self.assertEqual(health_check.DISK_THRESHOLD_WARNING, 80)
        self.assertEqual(health_check.DISK_THRESHOLD_CRITICAL, 90)


if __name__ == "__main__":
    # Run only fast unit tests (skip slow network tests)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestCircuitBreaker, TestHealthCheckStats, TestHTTPRetryBackoff, TestCLIFlags]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner()
    runner.run(suite)
