#!/usr/bin/env python3
"""
Tests for cross-platform health check fallbacks.
Simulates missing /proc files and verifies fallback behavior.
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.health_check import check_memory_usage, check_load_average


def test_memory_check_returns_tuple():
    """Test 1: check_memory_usage returns a valid (status, detail, value) tuple."""
    status, detail, value = check_memory_usage()
    assert status in ("OK", "WARNING", "CRITICAL"), f"Invalid status: {status}"
    assert isinstance(detail, str), f"Detail should be string: {type(detail)}"
    assert isinstance(value, (int, float)), f"Value should be numeric: {type(value)}"
    print(f"  Test 1 PASSED: status={status}, detail={detail[:50]}, value={value}")


def test_load_check_returns_tuple():
    """Test 2: check_load_average returns a valid (status, detail, value) tuple."""
    status, detail, value = check_load_average()
    assert status in ("OK", "WARNING", "CRITICAL"), f"Invalid status: {status}"
    assert isinstance(detail, str), f"Detail should be string: {type(detail)}"
    assert isinstance(value, (int, float)), f"Value should be numeric: {type(value)}"
    print(f"  Test 2 PASSED: status={status}, detail={detail[:50]}, value={value}")


def test_memory_fallback_no_proc():
    """Test 3: Simulate missing /proc/meminfo and verify fallback works."""
    # Patch os.path.exists to simulate no /proc/meminfo
    with patch("os.path.exists", return_value=False),          patch("sys.platform", "win32"):
        # Also patch open to raise FileNotFoundError for /proc/meminfo
        original_open = open
        def mock_open(path, *args, **kwargs):
            if "/proc/meminfo" in str(path):
                raise FileNotFoundError("Simulated: /proc/meminfo not available")
            return original_open(path, *args, **kwargs)
        
        with patch("builtins.open", side_effect=mock_open):
            status, detail, value = check_memory_usage()
            # Should not crash, should return a valid result
            assert status in ("OK", "WARNING", "CRITICAL"), f"Invalid status: {status}"
            # On non-Linux without psutil, might get WARNING
            print(f"  Test 3 PASSED: fallback returned status={status}, detail={detail[:50]}")


def test_load_fallback_no_proc():
    """Test 4: Simulate missing /proc/loadavg and verify fallback works."""
    with patch("os.path.exists", return_value=False),          patch("sys.platform", "darwin"):
        original_open = open
        def mock_open(path, *args, **kwargs):
            if "/proc/loadavg" in str(path):
                raise FileNotFoundError("Simulated: /proc/loadavg not available")
            return original_open(path, *args, **kwargs)
        
        with patch("builtins.open", side_effect=mock_open):
            # Also make os.getloadavg work (it should on macOS)
            status, detail, value = check_load_average()
            assert status in ("OK", "WARNING", "CRITICAL"), f"Invalid status: {status}"
            print(f"  Test 4 PASSED: fallback returned status={status}, detail={detail[:50]}")


def test_backward_compatibility():
    """Test 5: Verify output format is backward compatible."""
    # Memory check should return percentage as third element
    _, _, mem_pct = check_memory_usage()
    assert 0 <= mem_pct <= 100 or mem_pct == 0, f"Memory percentage out of range: {mem_pct}"
    
    # Load check should return load value as third element
    _, _, load_val = check_load_average()
    assert isinstance(load_val, (int, float)), f"Load value should be numeric: {load_val}"
    
    print(f"  Test 5 PASSED: backward compatible (mem={mem_pct}, load={load_val})")


if __name__ == "__main__":
    print("\n  Running 5 cross-platform health check tests...\n")
    tests_passed = 0
    tests_total = 5
    
    try:
        test_memory_check_returns_tuple()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 1 FAILED: {e}")
    
    try:
        test_load_check_returns_tuple()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 2 FAILED: {e}")
    
    try:
        test_memory_fallback_no_proc()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 3 FAILED: {e}")
    
    try:
        test_load_fallback_no_proc()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 4 FAILED: {e}")
    
    try:
        test_backward_compatibility()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 5 FAILED: {e}")
    
    print(f"\n  {tests_passed}/{tests_total} tests passed")
    sys.exit(0 if tests_passed == tests_total else 1)
