import unittest
from unittest.mock import mock_open, patch

from tools import health_check


class HealthCheckFallbackTests(unittest.TestCase):
    def test_memory_uses_linux_proc_when_available(self):
        meminfo = "MemTotal:       1048576 kB\nMemAvailable:    524288 kB\n"

        with patch("builtins.open", mock_open(read_data=meminfo)):
            status, detail, pct = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertIn("50.0% used", detail)
        self.assertEqual(pct, 50.0)

    def test_memory_falls_back_to_sysconf_when_proc_missing(self):
        values = {
            "SC_PAGE_SIZE": 4096,
            "SC_PHYS_PAGES": 1024,
            "SC_AVPHYS_PAGES": 256,
        }

        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.sysconf", side_effect=lambda name: values[name], create=True
        ):
            status, detail, pct = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertIn("75.0% used", detail)
        self.assertEqual(pct, 75.0)

    def test_load_uses_linux_proc_when_available(self):
        with patch("builtins.open", mock_open(read_data="0.50 0.40 0.30 1/100 123\n")), patch(
            "os.cpu_count", return_value=2
        ):
            status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 0.5)
        self.assertIn("25% of 2 cores", detail)

    def test_load_falls_back_to_getloadavg_when_proc_missing(self):
        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.getloadavg", return_value=(1.5, 1.0, 0.5), create=True
        ), patch("os.cpu_count", return_value=3):
            status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 1.5)
        self.assertIn("50% of 3 cores", detail)


if __name__ == "__main__":
    unittest.main()
