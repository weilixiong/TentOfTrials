#!/usr/bin/env python3
"""Test cross-platform fallbacks for health_check.py."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from health_check import check_memory_usage, check_load_average

def test_memory_fallback_without_proc():
    orig_exists = os.path.exists
    def mock_exists(path):
        return False if path == "/proc/meminfo" else orig_exists(path)
    os.path.exists = mock_exists
    try:
        status, detail, pct = check_memory_usage()
        assert status in ("OK", "WARNING"), f"Expected OK/WARNING, got {status}"
        assert detail, "Detail should not be empty"
        print(f"  memory_fallback (no /proc): {status} - {detail}")
    finally:
        os.path.exists = orig_exists

def test_memory_fallback_psutil():
    try:
        import psutil
        status, detail, pct = check_memory_usage()
        assert status in ("OK", "WARNING"), f"Expected OK/WARNING, got {status}"
        assert "fallback" in detail or "psutil" in detail or "sysconf" in detail, f"Expected fallback: {detail}"
        print(f"  memory_fallback (psutil): {status} - {detail}")
    except ImportError:
        print("  psutil not available, skipping")

def test_memory_with_proc():
    if os.path.exists("/proc/meminfo"):
        status, detail, pct = check_memory_usage()
        assert status in ("OK", "WARNING", "CRITICAL"), f"Unexpected: {status}"
        print(f"  memory_with_proc: {status} - {detail}")
    else:
        print("  /proc/meminfo not available (non-Linux), skipping")

def test_load_fallback_without_proc():
    orig_exists = os.path.exists
    def mock_exists(path):
        return False if path == "/proc/loadavg" else orig_exists(path)
    os.path.exists = mock_exists
    try:
        status, detail, load = check_load_average()
        assert status in ("OK", "WARNING"), f"Expected OK/WARNING, got {status}"
        assert detail, "Detail should not be empty"
        print(f"  load_fallback (no /proc): {status} - {detail}")
    finally:
        os.path.exists = orig_exists

def test_load_with_proc():
    if os.path.exists("/proc/loadavg"):
        status, detail, load = check_load_average()
        assert status in ("OK", "WARNING", "CRITICAL"), f"Unexpected: {status}"
        print(f"  load_with_proc: {status} - {detail}")
    else:
        print("  /proc/loadavg not available (non-Linux), skipping")

def main():
    print("=" * 60)
    print("Health Check Cross-Platform Fallback Tests")
    print("=" * 60)
    tests = [test_memory_fallback_without_proc, test_memory_fallback_psutil,
             test_memory_with_proc, test_load_fallback_without_proc, test_load_with_proc]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  {test.__name__}: FAILED - {e}")
            failures += 1
    print(f"\nResults: {len(tests)} tests, {failures} failures")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
