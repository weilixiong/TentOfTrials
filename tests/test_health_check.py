import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HEALTH_CHECK_PATH = ROOT / "tools" / "health_check.py"

spec = importlib.util.spec_from_file_location("health_check", HEALTH_CHECK_PATH)
health_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(health_check)


class HealthCheckSystemFallbackTests(unittest.TestCase):
    def test_proc_memory_provider_parses_meminfo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meminfo_path = Path(tmpdir) / "meminfo"
            meminfo_path.write_text(
                "MemTotal:       2048000 kB\n"
                "MemAvailable:   512000 kB\n",
                encoding="utf-8",
            )

            total, available = health_check._memory_from_proc(str(meminfo_path))

        self.assertEqual(total, 2048000 * 1024)
        self.assertEqual(available, 512000 * 1024)

    def test_memory_check_uses_non_proc_fallback(self):
        with mock.patch.object(health_check, "_memory_from_proc", side_effect=FileNotFoundError), \
             mock.patch.object(health_check, "_memory_from_sysconf", return_value=(100, 25)), \
             mock.patch.object(health_check, "_memory_from_macos_vm_stat", return_value=None), \
             mock.patch.object(health_check, "_memory_from_windows", return_value=None):
            status, detail, pct = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(pct, 75)
        self.assertIn("75.0% used", detail)

    def test_load_check_uses_non_proc_fallback(self):
        with mock.patch.object(health_check, "_load_from_proc", side_effect=FileNotFoundError), \
             mock.patch.object(health_check, "_load_from_getloadavg", return_value=1.0), \
             mock.patch.object(health_check.os, "cpu_count", return_value=2):
            status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 1.0)
        self.assertEqual(detail, "Load: 1.0 (50% of 2 cores)")

    def test_load_check_reports_platform_unavailable_without_proc_path(self):
        with mock.patch.object(health_check, "_load_from_proc", return_value=None), \
             mock.patch.object(health_check, "_load_from_getloadavg", return_value=None):
            status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "WARNING")
        self.assertEqual(load, 0)
        self.assertNotIn("/proc/loadavg", detail)

    def test_disk_check_uses_cross_platform_disk_usage(self):
        with mock.patch.object(health_check.shutil, "disk_usage", return_value=(100, 85, 15)):
            status, detail, pct = health_check.check_disk_usage("/tmp")

        self.assertEqual(status, "WARNING")
        self.assertEqual(pct, 85)
        self.assertIn("85.0% used", detail)


if __name__ == "__main__":
    unittest.main()
