#!/usr/bin/env python3
"""Tests for cross-platform health check fallbacks."""
import os
import sys
import platform
from unittest.mock import patch, mock_open

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "tools")
sys.path.insert(0, TOOLS_DIR)

from health_check import check_memory_usage, check_load_average

def test_memory_returns_tuple():
    """check_memory_usage returns (status, detail, value) tuple on any platform."""
    status, detail, value = check_memory_usage()
    assert isinstance(status, str)
    assert isinstance(detail, str)
    assert isinstance(value, (int, float))

def test_memory_status_valid():
    """Status must be OK, WARNING, or CRITICAL."""
    status, _, _ = check_memory_usage()
    assert status in ("OK", "WARNING", "CRITICAL"), f"unexpected status: {status}"

def test_load_returns_tuple():
    """check_load_average returns (status, detail, value) tuple on any platform."""
    status, detail, value = check_load_average()
    assert isinstance(status, str)
    assert isinstance(detail, str)
    assert isinstance(value, (int, float))

def test_load_status_valid():
    """Status must be OK, WARNING, or CRITICAL."""
    status, _, _ = check_load_average()
    assert status in ("OK", "WARNING", "CRITICAL"), f"unexpected status: {status}"

def test_memory_non_linux_does_not_crash():
    """On non-Linux, memory check should not crash even if /proc missing."""
    # We're likely on macOS right now, so this tests the fallback path
    if platform.system() == "Linux":
        return  # skip on Linux — Linux path is the primary one
    status, detail, value = check_memory_usage()
    assert "Cannot check" not in detail or "not supported" not in detail, f"fallback failed: {detail}"

def test_load_non_linux_uses_getloadavg():
    """On non-Linux, load check should use os.getloadavg() fallback."""
    if platform.system() == "Linux":
        return
    status, detail, value = check_load_average()
    # Should have a meaningful value, not "not supported"
    assert "not supported" not in detail, f"fallback failed: {detail}"

def test_memory_linux_path_simulated():
    """Simulate Linux path by patching platform.system to return Linux."""
    with patch("platform.system", return_value="Linux"):
        with patch("builtins.open", mock_open(read_data="MemTotal: 16384000 kB\nMemAvailable: 8192000 kB\n")):
            status, detail, value = check_memory_usage()
            assert status in ("OK", "WARNING", "CRITICAL")
            assert isinstance(value, float)

def test_load_linux_path_simulated():
    """Simulate Linux /proc/loadavg path."""
    with patch("platform.system", return_value="Linux"):
        with patch("builtins.open", mock_open(read_data="1.23 1.45 1.67 3/100 12345\n")):
            status, detail, value = check_load_average()
            assert status in ("OK", "WARNING", "CRITICAL")
            assert isinstance(value, float)

def test_memory_missing_proc_fallback():
    """On Linux with missing /proc/meminfo, should return WARNING with error."""
    with patch("platform.system", return_value="Linux"):
        with patch("builtins.open", side_effect=FileNotFoundError("no /proc/meminfo")):
            status, detail, value = check_memory_usage()
            assert status == "WARNING"
            assert "Cannot check" in detail

def test_load_missing_proc_fallback():
    """On Linux with missing /proc/loadavg, should return WARNING with error."""
    with patch("platform.system", return_value="Linux"):
        with patch("builtins.open", side_effect=FileNotFoundError("no /proc/loadavg")):
            status, detail, value = check_load_average()
            assert status == "WARNING"
            assert "Cannot check" in detail

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
