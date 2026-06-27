#!/usr/bin/env python3
"""Tests for cross-platform health check fallbacks."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
HEALTH_CHECK_PATH = TOOLS_DIR / "health_check.py"


def load_health_check():
    spec = importlib.util.spec_from_file_location("health_check", HEALTH_CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["health_check"] = module
    spec.loader.exec_module(module)
    return module


class HealthCheckFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hc = load_health_check()

    def test_memory_linux_path_when_proc_exists(self) -> None:
        fake_meminfo = (
            "MemTotal:       8000000 kB\n"
            "MemAvailable:   4000000 kB\n"
        )
        with mock.patch.object(self.hc.os.path, "isfile", return_value=True), mock.patch(
            "builtins.open", mock.mock_open(read_data=fake_meminfo)
        ):
            status, detail, pct = self.hc.check_memory_usage()
        self.assertEqual(status, "OK")
        self.assertIn("50.0%", detail)
        self.assertGreater(pct, 0)

    def test_memory_fallback_when_proc_missing(self) -> None:
        with mock.patch.object(self.hc.os.path, "isfile", return_value=False), mock.patch.object(
            self.hc.os, "sysconf", side_effect=[4096, 2_000_000, 1_000_000], create=True
        ):
            status, detail, pct = self.hc.check_memory_usage()
        self.assertIn(status, {"OK", "WARNING", "CRITICAL"})
        self.assertIn("fallback", detail)
        self.assertGreaterEqual(pct, 0)

    def test_load_linux_path_when_proc_exists(self) -> None:
        with mock.patch.object(self.hc.os.path, "isfile", return_value=True), mock.patch(
            "builtins.open", mock.mock_open(read_data="1.25 0.50 0.25 2/100 12345\n")
        ), mock.patch.object(self.hc.os, "cpu_count", return_value=4):
            status, detail, load = self.hc.check_load_average()
        self.assertEqual(status, "OK")
        self.assertIn("1.25", detail)
        self.assertEqual(load, 1.25)

    def test_load_fallback_uses_getloadavg(self) -> None:
        with mock.patch.object(self.hc.os.path, "isfile", return_value=False), mock.patch.object(
            self.hc.os, "getloadavg", return_value=(2.0, 1.5, 1.0), create=True
        ), mock.patch.object(self.hc.os, "cpu_count", return_value=4):
            status, detail, load = self.hc.check_load_average()
        self.assertIn(status, {"OK", "WARNING", "CRITICAL"})
        self.assertIn("fallback", detail)
        self.assertEqual(load, 2.0)


if __name__ == "__main__":
    unittest.main()
