#!/usr/bin/env python3
import unittest
from unittest.mock import patch, mock_open
import health_check

class TestHealthCheckFallbacks(unittest.TestCase):

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n")
    def hardware_linux_memory_test(self, mock_file, mock_exists):
        mock_exists.return_value = True
        status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("used", detail)

    @patch("os.path.exists")
    @patch("os.sysconf")
    def test_non_linux_memory_fallback(self, mock_sysconf, mock_exists):
        mock_exists.return_value = False
        # SC_PAGE_SIZE -> 4096, SC_PHYS_PAGES -> 4194304 (16GB), SC_AVPHYS_PAGES -> 2097152 (8GB)
        mock_sysconf.side_effect = lambda name: {
            "SC_PAGE_SIZE": 4096,
            "SC_PHYS_PAGES": 4194304,
            "SC_AVPHYS_PAGES": 2097152
        }[name]

        status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("50.0% used", detail)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="0.45 0.50 0.55 1/500 12345\n")
    def test_linux_load_average(self, mock_file, mock_exists):
        mock_exists.return_value = True
        status, detail, load = health_check.check_load_average()
        self.assertEqual(status, "OK")
        self.assertEqual(load, 0.45)

    @patch("os.path.exists")
    @patch("os.getloadavg")
    def test_non_linux_load_average_fallback(self, mock_getloadavg, mock_exists):
        mock_exists.return_value = False
        mock_getloadavg.return_value = (1.2, 1.0, 0.9)
        status, detail, load = health_check.check_load_average()
        self.assertEqual(load, 1.2)
        self.assertIn("Load: 1.2", detail)

if __name__ == "__main__":
    unittest.main()
