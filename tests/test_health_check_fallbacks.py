import builtins
import unittest
from unittest import mock

from tools import health_check


class HealthCheckFallbackTests(unittest.TestCase):
    def test_memory_usage_falls_back_to_sysconf_when_proc_is_missing(self) -> None:
        def fake_sysconf(name: str) -> int:
            values = {
                "SC_PAGE_SIZE": 4096,
                "SC_PHYS_PAGES": 1024,
                "SC_AVPHYS_PAGES": 768,
            }
            return values[name]

        with mock.patch.object(builtins, "open", side_effect=FileNotFoundError("/proc/meminfo")):
            with mock.patch.object(health_check.sys, "platform", "freebsd"):
                with mock.patch.object(health_check.os, "sysconf", side_effect=fake_sysconf):
                    status, detail, percent = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertIn("25.0% used", detail)
        self.assertEqual(percent, 25.0)

    def test_memory_usage_sysconf_total_only_still_returns_useful_detail(self) -> None:
        def fake_sysconf(name: str) -> int:
            if name == "SC_PAGE_SIZE":
                return 4096
            if name == "SC_PHYS_PAGES":
                return 1024
            raise ValueError(name)

        with mock.patch.object(builtins, "open", side_effect=FileNotFoundError("/proc/meminfo")):
            with mock.patch.object(health_check.sys, "platform", "freebsd"):
                with mock.patch.object(health_check.os, "sysconf", side_effect=fake_sysconf):
                    status, detail, percent = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertIn("Physical memory:", detail)
        self.assertIn("available memory unavailable", detail)
        self.assertEqual(percent, 0)

    def test_load_average_falls_back_to_os_getloadavg_when_proc_is_missing(self) -> None:
        with mock.patch.object(builtins, "open", side_effect=FileNotFoundError("/proc/loadavg")):
            with mock.patch.object(health_check.os, "getloadavg", return_value=(2.0, 1.0, 0.5)):
                with mock.patch.object(health_check.os, "cpu_count", return_value=4):
                    status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 2.0)
        self.assertIn("Load: 2.0", detail)
        self.assertIn("50% of 4 cores", detail)

    def test_run_health_checks_keeps_system_output_shape(self) -> None:
        with mock.patch.object(health_check, "check_http_service", return_value=("OK", "HTTP 200", 200)):
            with mock.patch.object(health_check, "check_tcp_port", return_value=("OK", "Connected", 1.0)):
                with mock.patch.object(health_check, "check_disk_usage", return_value=("OK", "10% used", 10.0)):
                    with mock.patch.object(health_check, "check_memory_usage", return_value=("OK", "20% used", 20.0)):
                        with mock.patch.object(health_check, "check_load_average", return_value=("OK", "Load: 1", 1.0)):
                            results = health_check.run_health_checks()

        self.assertEqual(results["overall_status"], "OK")
        self.assertEqual(results["system"]["memory"]["detail"], "20% used")
        self.assertEqual(results["system"]["load"]["status"], "OK")
        self.assertIn("backend", results["services"])


if __name__ == "__main__":
    unittest.main()
