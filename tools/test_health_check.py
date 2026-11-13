import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import health_check


class TestCrossPlatformFallbacks(unittest.TestCase):
    def test_memory_fallback_non_linux(self):
        with patch("health_check.MEMINFO_PATH", "/nonexistent/meminfo"), \
             patch("health_check.sys.platform", "darwin"), \
             patch("health_check._read_macos_memory", return_value=None):
            status, detail, _ = health_check.check_memory_usage()
            self.assertEqual(status, "WARNING")
            self.assertIn("unavailable", detail)

    def test_memory_macos_fallback(self):
        with patch("health_check.MEMINFO_PATH", "/nonexistent/meminfo"), \
             patch("health_check.sys.platform", "darwin"), \
             patch("health_check._read_macos_memory", return_value=(16 * 1024**3, 8 * 1024**3)):
            status, detail, pct = health_check.check_memory_usage()
            self.assertEqual(status, "OK")
            self.assertIn("50.0%", detail)

    def test_load_fallback_os_getloadavg(self):
        with patch("health_check.LOADAVG_PATH", "/nonexistent/loadavg"), \
             patch("health_check.os.getloadavg", return_value=(1.0, 1.0, 1.0)):
            status, detail, load = health_check.check_load_average()
            self.assertIn(status, ("OK", "WARNING", "CRITICAL"))

    def test_load_fallback_unavailable(self):
        with patch("health_check.LOADAVG_PATH", "/nonexistent/loadavg"), \
             patch("health_check.os.getloadavg", side_effect=OSError):
            status, detail, _ = health_check.check_load_average()
            self.assertEqual(status, "WARNING")
            self.assertIn("unavailable", detail)


if __name__ == "__main__":
    unittest.main()
