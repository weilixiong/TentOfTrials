import builtins
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from health_check import check_load_average, check_memory_usage


class HealthCheckFallbackTests(unittest.TestCase):
    def test_memory_usage_falls_back_to_sysconf_when_proc_is_missing(self):
        sysconf_values = {
            "SC_PAGE_SIZE": 4096,
            "SC_PHYS_PAGES": 1000,
            "SC_AVPHYS_PAGES": 250,
        }

        with patch.object(builtins, "open", side_effect=FileNotFoundError("no proc")):
            with patch(
                "health_check.get_windows_memory_status",
                return_value=None,
            ):
                with patch(
                    "health_check.os.sysconf",
                    side_effect=lambda key: sysconf_values[key],
                    create=True,
                ):
                    status, detail, pct = check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(round(pct, 1), 75.0)
        self.assertIn("75.0% used", detail)

    def test_memory_usage_uses_windows_fallback_when_available(self):
        with patch.object(builtins, "open", side_effect=FileNotFoundError("no proc")):
            with patch(
                "health_check.get_windows_memory_status",
                return_value=(8 * 1024**3, 2 * 1024**3),
            ):
                status, detail, pct = check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(round(pct, 1), 75.0)
        self.assertIn("75.0% used", detail)

    def test_memory_usage_returns_warning_when_no_fallback_is_available(self):
        with patch.object(builtins, "open", side_effect=FileNotFoundError("no proc")):
            with patch("health_check.get_windows_memory_status", return_value=None):
                with patch(
                    "health_check.os.sysconf",
                    side_effect=OSError("unsupported"),
                    create=True,
                ):
                    status, detail, pct = check_memory_usage()

        self.assertEqual(status, "WARNING")
        self.assertEqual(pct, 0)
        self.assertIn("Cannot check", detail)

    def test_load_average_falls_back_to_os_getloadavg_when_proc_is_missing(self):
        with patch.object(builtins, "open", side_effect=FileNotFoundError("no proc")):
            with patch(
                "health_check.os.getloadavg",
                return_value=(1.0, 0.5, 0.25),
                create=True,
            ):
                with patch("health_check.os.cpu_count", return_value=4):
                    status, detail, load = check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 1.0)
        self.assertIn("25% of 4 cores", detail)

    def test_load_average_returns_warning_when_no_fallback_is_available(self):
        with patch.object(builtins, "open", side_effect=FileNotFoundError("no proc")):
            with patch(
                "health_check.os.getloadavg",
                side_effect=OSError("unsupported"),
                create=True,
            ):
                status, detail, load = check_load_average()

        self.assertEqual(status, "WARNING")
        self.assertEqual(load, 0)
        self.assertIn("Cannot check", detail)


if __name__ == "__main__":
    unittest.main()
