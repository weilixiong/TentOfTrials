import builtins
import pathlib
import sys
import types
import unittest
from unittest.mock import mock_open, patch


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import health_check


class HealthCheckFallbackTests(unittest.TestCase):
    def test_memory_usage_prefers_proc_meminfo_when_available(self):
        proc_meminfo = "MemTotal:       1048576 kB\nMemAvailable:    524288 kB\n"

        with patch.object(builtins, "open", mock_open(read_data=proc_meminfo)):
            status, detail, percent = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(percent, 50.0)
        self.assertIn("50.0% used", detail)

    def test_memory_usage_falls_back_to_sysconf_without_proc_meminfo(self):
        values = {
            "SC_PAGE_SIZE": 4096,
            "SC_PHYS_PAGES": 1024,
            "SC_AVPHYS_PAGES": 256,
        }

        def fake_sysconf(name):
            return values[name]

        with patch.object(builtins, "open", side_effect=FileNotFoundError):
            with patch.object(health_check.os, "name", "posix"):
                with patch.object(health_check.os, "sysconf", side_effect=fake_sysconf, create=True):
                    status, detail, percent = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(percent, 75.0)
        self.assertIn("75.0% used", detail)

    def test_memory_usage_falls_back_to_macos_vm_stat(self):
        sysctl_result = types.SimpleNamespace(stdout="8192\n")
        vm_stat_result = types.SimpleNamespace(
            stdout=(
                "Mach Virtual Memory Statistics: (page size of 1024 bytes)\n"
                "Pages free:                               2.\n"
                "Pages inactive:                           1.\n"
                "Pages speculative:                        1.\n"
            )
        )

        with patch.object(builtins, "open", side_effect=FileNotFoundError):
            with patch.object(health_check.os, "sysconf", side_effect=ValueError, create=True):
                with patch.object(health_check.sys, "platform", "darwin"):
                    with patch.object(
                        health_check.subprocess,
                        "run",
                        side_effect=[sysctl_result, vm_stat_result],
                    ):
                        status, detail, percent = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertEqual(percent, 50.0)
        self.assertIn("50.0% used", detail)

    def test_load_average_prefers_proc_loadavg_when_available(self):
        with patch.object(builtins, "open", mock_open(read_data="1.00 0.50 0.25 1/100 123\n")):
            with patch.object(health_check.os, "cpu_count", return_value=4):
                status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 1.0)
        self.assertIn("25% of 4 cores", detail)

    def test_load_average_falls_back_to_os_getloadavg_without_proc_loadavg(self):
        with patch.object(builtins, "open", side_effect=FileNotFoundError):
            with patch.object(health_check.os, "getloadavg", return_value=(2.0, 1.0, 0.5), create=True):
                with patch.object(health_check.os, "cpu_count", return_value=4):
                    status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 2.0)
        self.assertIn("50% of 4 cores", detail)


if __name__ == "__main__":
    unittest.main()
