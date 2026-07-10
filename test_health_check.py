#!/usr/bin/env python3

import builtins
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import health_check


class HealthCheckFallbackTests(unittest.TestCase):
    def test_memory_falls_back_when_proc_meminfo_is_missing(self):
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if path == "/proc/meminfo":
                raise FileNotFoundError(path)
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fake_open), \
             mock.patch("health_check._memory_from_sysconf", return_value=(8 * 1024**3, 6 * 1024**3)), \
             mock.patch("health_check._memory_from_windows", return_value=None):
            status, detail, pct = health_check.check_memory_usage()

        self.assertEqual(status, "OK")
        self.assertIn("25.0% used", detail)
        self.assertEqual(pct, 25.0)

    def test_load_falls_back_to_os_getloadavg_when_proc_loadavg_is_missing(self):
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if path == "/proc/loadavg":
                raise FileNotFoundError(path)
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fake_open), \
             mock.patch("os.getloadavg", return_value=(0.5, 0.4, 0.3), create=True), \
             mock.patch("os.cpu_count", return_value=4):
            status, detail, load = health_check.check_load_average()

        self.assertEqual(status, "OK")
        self.assertEqual(load, 0.5)
        self.assertIn("12% of 4 cores", detail)


if __name__ == "__main__":
    unittest.main()
