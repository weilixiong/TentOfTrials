#!/usr/bin/env python3
"""Focused tests for the cross-platform fallbacks in tools/health_check.py.

Run with:
    python3 tools/test_health_check.py
    python3 -m unittest discover -s tools -p "test_*.py"

The tests simulate a host without /proc (macOS, Windows, BSD) by making the
/proc readers raise FileNotFoundError, then assert that the memory and load
checks still return meaningful values through the portable fallbacks, and
that the JSON/text report shape stays backward compatible.
"""

import importlib.util
import json
import os
import pathlib
import unittest
from unittest import mock

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("health_check", _HERE / "health_check.py")
health_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(health_check)

GB = 1024 ** 3


def _proc_missing(*args, **kwargs):
    raise FileNotFoundError(2, "No such file or directory", "/proc/meminfo")


class ProcReaderTests(unittest.TestCase):
    """The /proc readers must signal a missing /proc with FileNotFoundError."""

    def setUp(self):
        self.real_open = open

        def fake_open(path, *args, **kwargs):
            if str(path).startswith("/proc/"):
                raise FileNotFoundError(2, "No such file or directory", str(path))
            return self.real_open(path, *args, **kwargs)

        self.patcher = mock.patch("builtins.open", side_effect=fake_open)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_meminfo_reader_raises_when_proc_missing(self):
        with self.assertRaises(FileNotFoundError):
            health_check._read_proc_meminfo()

    def test_loadavg_reader_raises_when_proc_missing(self):
        with self.assertRaises(FileNotFoundError):
            health_check._read_proc_loadavg()

    def test_meminfo_reader_parses_proc_content(self):
        content = "MemTotal:       16777216 kB\nMemAvailable:    4194304 kB\nBogus\n"

        class _FakeFile:
            def __init__(self):
                self._lines = iter(content.splitlines())

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._lines)

        with mock.patch("builtins.open", return_value=_FakeFile()):
            meminfo = health_check._read_proc_meminfo()
        self.assertEqual(meminfo["MemTotal"], 16 * GB)
        self.assertEqual(meminfo["MemAvailable"], 4 * GB)


class MemoryCheckTests(unittest.TestCase):
    def test_proc_path_still_used_when_available(self):
        meminfo = {"MemTotal": 16 * GB, "MemAvailable": 4 * GB}
        with mock.patch.object(health_check, "_read_proc_meminfo", return_value=meminfo) as reader:
            with mock.patch.object(health_check, "_fallback_memory_values") as fallback:
                status, detail, pct = health_check.check_memory_usage()
        reader.assert_called_once()
        fallback.assert_not_called()
        self.assertEqual(status, "OK")
        self.assertEqual(round(pct, 1), 75.0)
        self.assertIn("75.0% used", detail)

    def test_missing_proc_uses_portable_fallback(self):
        with mock.patch.object(health_check, "_read_proc_meminfo", side_effect=FileNotFoundError):
            with mock.patch.object(
                health_check, "_fallback_memory_values", return_value=(16 * GB, 2 * GB)
            ):
                status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "WARNING")
        self.assertEqual(round(pct, 1), 87.5)
        self.assertIn("87.5% used", detail)
        self.assertNotIn("Cannot check", detail)

    def test_sysconf_is_used_as_a_fallback_source(self):
        values = {
            "SC_PAGE_SIZE": 4096,
            "SC_PAGESIZE": 4096,
            "SC_PHYS_PAGES": 4 * 1024 * 1024,
            "SC_AVPHYS_PAGES": 1024 * 1024,
        }
        with mock.patch.object(health_check, "_read_proc_meminfo", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_sysconf_int", side_effect=lambda name: values.get(name)):
                with mock.patch.object(health_check, "_windows_memory", return_value=None):
                    with mock.patch.object(health_check, "_macos_total_memory", return_value=None):
                        with mock.patch.object(health_check, "_macos_available_memory", return_value=None):
                            status, detail, pct = health_check.check_memory_usage()
        # 4Mi pages * 4096 = 16GiB total, 1Mi pages * 4096 = 4GiB available
        self.assertEqual(status, "OK")
        self.assertEqual(round(pct, 1), 75.0)
        self.assertIn("75.0% used", detail)

    def test_windows_memory_source_is_used(self):
        with mock.patch.object(health_check, "_read_proc_meminfo", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_windows_memory", return_value=(8 * GB, 6 * GB)):
                status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertEqual(round(pct, 1), 25.0)
        self.assertIn("25.0% used", detail)

    def test_no_memory_source_is_a_warning(self):
        with mock.patch.object(health_check, "_read_proc_meminfo", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_fallback_memory_values", return_value=(None, None)):
                status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "WARNING")
        self.assertIn("Cannot check", detail)

    def test_unknown_available_memory_is_a_warning(self):
        with mock.patch.object(health_check, "_read_proc_meminfo", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_fallback_memory_values", return_value=(8 * GB, None)):
                status, detail, pct = health_check.check_memory_usage()
        self.assertEqual(status, "WARNING")
        self.assertIn("available memory unknown", detail)


class LoadCheckTests(unittest.TestCase):
    def test_proc_path_still_used_when_available(self):
        with mock.patch.object(health_check, "_read_proc_loadavg", return_value=0.5) as reader:
            with mock.patch.object(health_check, "_load_from_getloadavg") as fallback:
                status, detail, load = health_check.check_load_average()
        reader.assert_called_once()
        fallback.assert_not_called()
        self.assertEqual(status, "OK")
        self.assertIn("Load: 0.5", detail)

    def test_getloadavg_fallback(self):
        with mock.patch.object(health_check, "_read_proc_loadavg", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_load_from_getloadavg", return_value=2.0):
                status, detail, load = health_check.check_load_average()
        self.assertEqual(status, "OK")
        self.assertIn("Load: 2.00", detail)
        self.assertIn("cores", detail)

    def test_cpu_utilisation_fallback_maps_to_a_load_average(self):
        cores = os.cpu_count() or 1
        with mock.patch.object(health_check, "_read_proc_loadavg", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_load_from_getloadavg", return_value=None):
                with mock.patch.object(health_check, "_windows_cpu_utilization", return_value=50.0):
                    status, detail, load = health_check.check_load_average()
        self.assertEqual(status, "OK")
        self.assertAlmostEqual(load, (50.0 / 100) * cores, places=6)
        self.assertIn(f"{cores} cores", detail)

    def test_no_load_source_is_a_warning(self):
        with mock.patch.object(health_check, "_read_proc_loadavg", side_effect=FileNotFoundError):
            with mock.patch.object(health_check, "_load_from_getloadavg", return_value=None):
                with mock.patch.object(health_check, "_windows_cpu_utilization", return_value=None):
                    status, detail, load = health_check.check_load_average()
        self.assertEqual(status, "WARNING")
        self.assertIn("Cannot check", detail)


class EndToEndTests(unittest.TestCase):
    def test_checks_work_without_proc_files(self):
        real_open = open

        def fake_open(path, *args, **kwargs):
            if str(path).startswith("/proc/"):
                raise FileNotFoundError(2, "No such file or directory", str(path))
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fake_open):
            with mock.patch.object(health_check, "_fallback_memory_values", return_value=(16 * GB, 8 * GB)):
                with mock.patch.object(health_check, "_load_from_getloadavg", return_value=1.0):
                    mem = health_check.check_memory_usage()
                    load = health_check.check_load_average()

        self.assertEqual(mem[0], "OK")
        self.assertNotIn("Cannot check", mem[1])
        self.assertEqual(load[0], "OK")
        self.assertNotIn("Cannot check", load[1])


class OutputCompatibilityTests(unittest.TestCase):
    def test_report_shape_is_unchanged(self):
        results = health_check.run_health_checks(json_output=True)
        for key in ("timestamp", "hostname", "services", "infrastructure", "system", "overall_status"):
            self.assertIn(key, results)
        for key in ("disk", "memory", "load"):
            self.assertIn(key, results["system"])
            self.assertIn("status", results["system"][key])
            self.assertIn("detail", results["system"][key])
        self.assertIn(results["overall_status"], ("OK", "DEGRADED"))
        json.dumps(results)

    def test_checks_do_not_raise_on_the_current_host(self):
        for check in (health_check.check_memory_usage, health_check.check_load_average):
            status, detail, value = check()
            self.assertIn(status, ("OK", "WARNING", "CRITICAL"))
            self.assertIsInstance(detail, str)
            self.assertIsInstance(value, float)


if __name__ == "__main__":
    unittest.main(verbosity=2)
