#!/usr/bin/env python3
"""
Tests for cross-platform health check fallbacks.

These tests verify that the memory and load average checks handle missing
/proc files gracefully and fall back to alternative methods.
"""

import os
import platform
import sys
import unittest
from unittest.mock import patch, mock_open, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from health_check import (
    check_memory_usage,
    check_load_average,
    _get_memory_info_linux,
    _get_memory_info_macos,
    _get_memory_info_windows,
    _get_load_average_procfs,
    _get_load_average_os,
    MEMORY_THRESHOLD_WARNING,
    MEMORY_THRESHOLD_CRITICAL,
)


class TestMemoryFallbacks(unittest.TestCase):
    """Tests for memory usage fallback behavior."""

    def test_linux_proc_meminfo_success(self):
        """Test that /proc/meminfo parsing works correctly."""
        meminfo_content = """MemTotal:       16000000 kB
MemFree:         4000000 kB
MemAvailable:    8000000 kB
Buffers:          500000 kB
Cached:          3000000 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            result = _get_memory_info_linux()
            self.assertIsNotNone(result)
            total, available = result
            self.assertEqual(total, 16000000 * 1024)
            self.assertEqual(available, 8000000 * 1024)

    def test_linux_proc_meminfo_missing(self):
        """Test graceful handling when /proc/meminfo is missing."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = _get_memory_info_linux()
            self.assertIsNone(result)

    def test_linux_proc_meminfo_permission_denied(self):
        """Test graceful handling when /proc/meminfo is not readable."""
        with patch("builtins.open", side_effect=PermissionError):
            result = _get_memory_info_linux()
            self.assertIsNone(result)

    @patch("subprocess.run")
    def test_macos_fallback_success(self, mock_run):
        """Test macOS memory info via sysctl and vm_stat."""
        # Mock sysctl response
        sysctl_result = MagicMock()
        sysctl_result.returncode = 0
        sysctl_result.stdout = "17179869184\n"  # 16GB

        # Mock vm_stat response
        vm_stat_result = MagicMock()
        vm_stat_result.returncode = 0
        vm_stat_result.stdout = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                              100000.
Pages inactive:                          200000.
Pages speculative:                        50000.
Pages active:                            300000.
"""

        mock_run.side_effect = [sysctl_result, vm_stat_result]

        result = _get_memory_info_macos()
        self.assertIsNotNone(result)
        total, available = result
        self.assertEqual(total, 17179869184)
        # Available = (100000 + 200000 + 50000) * 4096
        self.assertEqual(available, 350000 * 4096)

    @patch("subprocess.run")
    def test_macos_fallback_command_not_found(self, mock_run):
        """Test graceful handling when sysctl/vm_stat not available."""
        mock_run.side_effect = FileNotFoundError
        result = _get_memory_info_macos()
        self.assertIsNone(result)

    def test_check_memory_usage_returns_valid_tuple(self):
        """Test that check_memory_usage returns valid status tuple."""
        status, detail, pct = check_memory_usage()
        self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
        self.assertIsInstance(detail, str)
        self.assertIsInstance(pct, (int, float))

    @patch("health_check._get_memory_info_linux")
    @patch("health_check._get_memory_info_macos")
    @patch("health_check._get_memory_info_windows")
    def test_check_memory_fallback_chain(self, mock_win, mock_mac, mock_linux):
        """Test that fallback chain works when primary method fails."""
        mock_linux.return_value = None
        mock_mac.return_value = None
        mock_win.return_value = (16 * 1024**3, 8 * 1024**3)  # 16GB total, 8GB available

        with patch("platform.system", return_value="Linux"):
            status, detail, pct = check_memory_usage()
            # Should eventually succeed via Windows fallback
            self.assertEqual(status, "OK")
            self.assertIn("50", detail)  # ~50% used


class TestLoadAverageFallbacks(unittest.TestCase):
    """Tests for load average fallback behavior."""

    def test_procfs_load_average_success(self):
        """Test that /proc/loadavg parsing works correctly."""
        loadavg_content = "0.52 0.58 0.59 1/237 12345\n"
        with patch("builtins.open", mock_open(read_data=loadavg_content)):
            result = _get_load_average_procfs()
            self.assertIsNotNone(result)
            self.assertAlmostEqual(result, 0.52)

    def test_procfs_load_average_missing(self):
        """Test graceful handling when /proc/loadavg is missing."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = _get_load_average_procfs()
            self.assertIsNone(result)

    def test_procfs_load_average_permission_denied(self):
        """Test graceful handling when /proc/loadavg is not readable."""
        with patch("builtins.open", side_effect=PermissionError):
            result = _get_load_average_procfs()
            self.assertIsNone(result)

    def test_os_getloadavg_success(self):
        """Test os.getloadavg() fallback on Unix-like systems."""
        # Use create=True since os.getloadavg doesn't exist on Windows
        with patch("os.getloadavg", return_value=(1.5, 1.2, 0.9), create=True):
            result = _get_load_average_os()
            self.assertIsNotNone(result)
            self.assertAlmostEqual(result, 1.5, places=2)

    def test_os_getloadavg_not_available(self):
        """Test graceful handling when os.getloadavg() is not available."""
        # On Windows, os.getloadavg doesn't exist, so test that directly
        if platform.system() == "Windows":
            result = _get_load_average_os()
            self.assertIsNone(result)
        else:
            with patch("os.getloadavg", side_effect=AttributeError, create=True):
                result = _get_load_average_os()
                self.assertIsNone(result)

    def test_check_load_average_returns_valid_tuple(self):
        """Test that check_load_average returns valid status tuple."""
        status, detail, load_val = check_load_average()
        self.assertIn(status, ["OK", "WARNING", "CRITICAL"])
        self.assertIsInstance(detail, str)
        self.assertIsInstance(load_val, (int, float))

    @patch("health_check._get_load_average_procfs")
    @patch("health_check._get_load_average_os")
    def test_load_fallback_chain(self, mock_os_load, mock_procfs):
        """Test that fallback chain works when /proc is unavailable."""
        mock_procfs.return_value = None
        mock_os_load.return_value = 0.5

        with patch("platform.system", return_value="Darwin"):
            status, detail, load_val = check_load_average()
            self.assertEqual(status, "OK")
            self.assertAlmostEqual(load_val, 0.5)

    @patch("health_check._get_load_average_procfs")
    @patch("health_check._get_load_average_os")
    @patch("platform.system")
    def test_windows_load_average_unavailable(self, mock_system, mock_os_load, mock_procfs):
        """Test Windows graceful degradation for load average."""
        mock_procfs.return_value = None
        mock_os_load.return_value = None
        mock_system.return_value = "Windows"

        status, detail, load_val = check_load_average()
        self.assertEqual(status, "OK")
        self.assertIn("not available", detail.lower())


class TestOutputCompatibility(unittest.TestCase):
    """Tests to verify backward-compatible output format."""

    def test_memory_ok_format(self):
        """Test that OK memory status has expected format."""
        with patch("health_check._get_memory_info_linux") as mock:
            mock.return_value = (16 * 1024**3, 12 * 1024**3)  # 25% used
            with patch("platform.system", return_value="Linux"):
                status, detail, pct = check_memory_usage()
                self.assertEqual(status, "OK")
                self.assertIn("%", detail)
                self.assertIn("used", detail)
                self.assertIn("GB", detail)

    def test_memory_warning_format(self):
        """Test that WARNING memory status has expected format."""
        total = 16 * 1024**3
        available = int(total * 0.15)  # 85% used -> WARNING
        with patch("health_check._get_memory_info_linux") as mock:
            mock.return_value = (total, available)
            with patch("platform.system", return_value="Linux"):
                status, detail, pct = check_memory_usage()
                self.assertEqual(status, "WARNING")
                self.assertIn("%", detail)

    def test_memory_critical_format(self):
        """Test that CRITICAL memory status has expected format."""
        total = 16 * 1024**3
        available = int(total * 0.05)  # 95% used -> CRITICAL
        with patch("health_check._get_memory_info_linux") as mock:
            mock.return_value = (total, available)
            with patch("platform.system", return_value="Linux"):
                status, detail, pct = check_memory_usage()
                self.assertEqual(status, "CRITICAL")
                self.assertIn("%", detail)

    def test_load_ok_format(self):
        """Test that OK load status has expected format."""
        with patch("health_check._get_load_average_procfs") as mock:
            mock.return_value = 0.5
            with patch("os.cpu_count", return_value=4):
                status, detail, load_val = check_load_average()
                self.assertEqual(status, "OK")
                self.assertIn("Load:", detail)
                self.assertIn("cores", detail)


if __name__ == "__main__":
    unittest.main()
