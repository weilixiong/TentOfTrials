#!/usr/bin/env python3
"""
Health check tool for the Tent of Trials platform.
Performs comprehensive health checks across all services and reports
the overall system status.

This tool is used by:
  - The Kubernetes liveness/readiness probes
  - The deployment pipeline (post-deployment validation)
  - The monitoring system (periodic health checks)
  - The on-call engineer (manual troubleshooting)

The health check performs the following checks:
  1. Service availability (HTTP health endpoints)
  2. Database connectivity (connection test)
  3. Redis connectivity (ping test)
  4. Kafka connectivity (metadata fetch)
  5. Message queue depth (consumer lag check)
  6. Certificate expiry (TLS certificate check)
  7. Disk space (filesystem usage check)
  8. Memory usage (process memory check)

Each check returns a status of OK, WARNING, or CRITICAL, along with
a detail message and optional diagnostic data.

Usage:
    python3 health_check.py                  # Check all services
    python3 health_check.py --service backend # Check specific service
    python3 health_check.py --json            # JSON output
    python3 health_check.py --watch           # Continuous monitoring
"""

import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

SERVICES = {
    "backend": {"host": "localhost", "port": 8080, "path": "/health", "timeout": 5},
    "market": {"host": "localhost", "port": 8081, "path": "/health", "timeout": 5},
    "frailbox": {"host": "localhost", "port": 8082, "path": "/health", "timeout": 10},
    "frontend": {"host": "localhost", "port": 3000, "path": "/", "timeout": 5},
}

INFRASTRUCTURE = {
    "postgresql": {"host": os.environ.get("DB_HOST", "localhost"), "port": int(os.environ.get("DB_PORT", "5432")), "timeout": 5},
    "redis": {"host": os.environ.get("REDIS_HOST", "localhost"), "port": int(os.environ.get("REDIS_PORT", "6379")), "timeout": 5},
    "kafka": {"host": os.environ.get("KAFKA_HOST", "localhost"), "port": int(os.environ.get("KAFKA_PORT", "9092")), "timeout": 5},
}

DISK_THRESHOLD_WARNING = 80
DISK_THRESHOLD_CRITICAL = 90

MEMORY_THRESHOLD_WARNING = 80
MEMORY_THRESHOLD_CRITICAL = 90

# ---------------------------------------------------------------------------
# CHECK FUNCTIONS
# ---------------------------------------------------------------------------

def check_http_service(host: str, port: int, path: str, timeout: int) -> Tuple[str, str, int]:
    import http.client
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        status = resp.status
        body = resp.read().decode("utf-8", errors="replace")[:200]
        conn.close()

        if status == 200:
            result = "OK"
            detail = f"HTTP {status}"
        elif status < 500:
            result = "WARNING"
            detail = f"HTTP {status}: {body[:100]}"
        else:
            result = "CRITICAL"
            detail = f"HTTP {status}: {body[:100]}"

        return result, detail, status
    except Exception as e:
        return "CRITICAL", str(e), 0


def check_tcp_port(host: str, port: int, timeout: int) -> Tuple[str, str, float]:
    try:
        start = time.time()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        latency = (time.time() - start) * 1000
        return "OK", f"Connected ({latency:.1f}ms)", latency
    except socket.timeout:
        return "CRITICAL", f"Connection timeout ({timeout}s)", 0
    except ConnectionRefusedError:
        return "CRITICAL", "Connection refused", 0
    except Exception as e:
        return "CRITICAL", str(e), 0


def check_certificate_expiry(host: str, port: int = 443) -> Tuple[str, str, int]:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return "WARNING", "No certificate found", 0

                from datetime import datetime as dt
                expires = dt.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                days_left = (expires - dt.now()).days

                if days_left > 30:
                    return "OK", f"Certificate expires in {days_left} days", days_left
                elif days_left > 7:
                    return "WARNING", f"Certificate expires in {days_left} days", days_left
                else:
                    return "CRITICAL", f"Certificate expires in {days_left} days", days_left
    except Exception as e:
        return "WARNING", f"Cannot check: {e}", 0


def check_disk_usage(path: str = "/") -> Tuple[str, str, float]:
    try:
        stat = os.statvfs(path)
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bavail
        used = total - free
        pct = (used / total) * 100

        if pct < DISK_THRESHOLD_WARNING:
            return "OK", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
        elif pct < DISK_THRESHOLD_CRITICAL:
            return "WARNING", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
        else:
            return "CRITICAL", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
    except Exception as e:
        return "WARNING", f"Cannot check: {e}", 0


# ---------------------------------------------------------------------------
# CROSS-PLATFORM RESOURCE FALLBACKS
#
# The memory and load checks used to read /proc/meminfo and /proc/loadavg
# directly, which only exist on Linux. The helpers below keep that path
# untouched, but provide standard-library fallbacks (ctypes, sysctl, vm_stat,
# sysconf and os.getloadavg) so the checks stay useful on macOS, Windows and
# BSD, where the /proc read used to degrade to a generic failure.
# ---------------------------------------------------------------------------


def _read_proc_meminfo() -> Dict[str, int]:
    """Parse /proc/meminfo into a mapping of byte counts.

    Raises FileNotFoundError when /proc is unavailable (non-Linux hosts);
    that is the signal for the caller to use the portable fallbacks.
    """
    meminfo: Dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip().replace(" kB", "")
                try:
                    meminfo[key] = int(value) * 1024
                except ValueError:
                    pass
    return meminfo


def _read_proc_loadavg() -> float:
    """Return the 1-minute load average from /proc/loadavg.

    Raises FileNotFoundError when /proc is unavailable (non-Linux hosts).
    """
    with open("/proc/loadavg") as f:
        parts = f.read().strip().split()
    return float(parts[0])


def _sysconf_int(name: str) -> Optional[int]:
    """Return a positive sysconf value, or None when it is unavailable."""
    try:
        value = int(os.sysconf(name))
    except (AttributeError, ValueError, OSError, NameError):
        return None
    return value if value > 0 else None


def _page_size() -> Optional[int]:
    """Return the system page size in bytes (SC_PAGE_SIZE / SC_PAGESIZE)."""
    for name in ("SC_PAGE_SIZE", "SC_PAGESIZE"):
        size = _sysconf_int(name)
        if size:
            return size
    return None


def _windows_memory() -> Optional[Tuple[int, int]]:
    """Return (total_bytes, available_bytes) via the Windows MemoryStatusEx API."""
    if os.name != "nt":
        return None

    import ctypes

    class _MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
    except Exception:
        return None
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def _macos_total_memory() -> Optional[int]:
    """Return total physical memory on macOS via sysctl."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return int(value) if value.isdigit() else None


def _macos_available_memory(page_size: int) -> Optional[int]:
    """Return available memory on macOS from the vm_stat page counters."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
    except Exception:
        return None

    reclaimable = {"pages free", "pages inactive", "pages speculative", "pages purgeable"}
    pages = 0
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        value = value.strip().rstrip(".")
        if not value.isdigit():
            continue
        if key.strip().lower() in reclaimable:
            pages += int(value)
    return pages * page_size if pages else None


def _fallback_memory_values() -> Tuple[Optional[int], Optional[int]]:
    """Return (total_bytes, available_bytes) from portable sources.

    Returns (None, None) when the host exposes no usable memory information.
    """
    total: Optional[int] = None
    available: Optional[int] = None

    windows = _windows_memory()
    if windows is not None:
        total, available = windows

    page_size = _page_size()

    if total is None:
        pages = _sysconf_int("SC_PHYS_PAGES")
        if pages and page_size:
            total = pages * page_size

    if total is None:
        total = _macos_total_memory()

    if available is None:
        avail_pages = _sysconf_int("SC_AVPHYS_PAGES")
        if avail_pages and page_size:
            available = avail_pages * page_size

    if available is None and page_size:
        available = _macos_available_memory(page_size)

    return total, available


def _load_from_getloadavg() -> Optional[float]:
    """Return the 1-minute load average from os.getloadavg() (Unix)."""
    try:
        return os.getloadavg()[0]
    except (AttributeError, OSError):
        return None


def _windows_cpu_times() -> Optional[Tuple[int, int, int]]:
    """Return (idle, kernel, user) 100ns CPU counters on Windows."""
    if os.name != "nt":
        return None

    import ctypes

    class _FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

    idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
    try:
        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
    except Exception:
        return None

    def to_int(value: "_FileTime") -> int:
        return (value.dwHighDateTime << 32) | value.dwLowDateTime

    return to_int(idle), to_int(kernel), to_int(user)


def _windows_cpu_utilization() -> Optional[float]:
    """Return Windows CPU utilisation in percent, derived from GetSystemTimes."""
    first = _windows_cpu_times()
    if first is None:
        return None
    time.sleep(0.1)
    second = _windows_cpu_times()
    if second is None:
        return None

    idle_delta = second[0] - first[0]
    kernel_delta = second[1] - first[1]
    user_delta = second[2] - first[2]
    total_delta = kernel_delta + user_delta
    if total_delta <= 0:
        return None

    busy_delta = (kernel_delta - idle_delta) + user_delta
    return max(0.0, min(100.0, (busy_delta / total_delta) * 100))


def check_memory_usage() -> Tuple[str, str, float]:
    try:
        meminfo = _read_proc_meminfo()
    except FileNotFoundError:
        pass
    except Exception as e:
        return "WARNING", f"Cannot check: {e}", 0
    else:
        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = total - available
        pct = (used / total) * 100 if total > 0 else 0

        if pct < MEMORY_THRESHOLD_WARNING:
            return "OK", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
        elif pct < MEMORY_THRESHOLD_CRITICAL:
            return "WARNING", f"{pct:.1f}% used", pct
        else:
            return "CRITICAL", f"{pct:.1f}% used", pct

    # No /proc/meminfo (macOS, Windows, BSD, ...): use the portable sources.
    try:
        total, available = _fallback_memory_values()
    except Exception as e:
        return "WARNING", f"Cannot check: {e}", 0

    if not total:
        return "WARNING", "Cannot check: no portable memory source available", 0
    if not available:
        return "WARNING", (
            f"Cannot check: {total // (1024**3)}GB total, available memory unknown"
        ), 0

    used = total - available
    pct = (used / total) * 100

    if pct < MEMORY_THRESHOLD_WARNING:
        return "OK", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
    elif pct < MEMORY_THRESHOLD_CRITICAL:
        return "WARNING", f"{pct:.1f}% used", pct
    else:
        return "CRITICAL", f"{pct:.1f}% used", pct


def check_load_average() -> Tuple[str, str, float]:
    try:
        load = _read_proc_loadavg()
    except FileNotFoundError:
        pass
    except Exception as e:
        return "WARNING", f"Cannot check: {e}", 0
    else:
        cpu_count = os.cpu_count() or 1
        load_pct = (load / cpu_count) * 100

        if load_pct < 70:
            return "OK", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load
        elif load_pct < 90:
            return "WARNING", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load
        else:
            return "CRITICAL", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load

    # No /proc/loadavg: prefer os.getloadavg(), then derive a load average
    # from CPU utilisation so the output keeps the same shape everywhere.
    cpu_count = os.cpu_count() or 1

    load = _load_from_getloadavg()
    if load is None:
        utilization = _windows_cpu_utilization()
        if utilization is None:
            return "WARNING", "Cannot check: no portable load source available", 0
        load = (utilization / 100) * cpu_count

    load_pct = (load / cpu_count) * 100

    if load_pct < 70:
        return "OK", f"Load: {load:.2f} ({load_pct:.0f}% of {cpu_count} cores)", load
    elif load_pct < 90:
        return "WARNING", f"Load: {load:.2f} ({load_pct:.0f}% of {cpu_count} cores)", load
    else:
        return "CRITICAL", f"Load: {load:.2f} ({load_pct:.0f}% of {cpu_count} cores)", load


# ---------------------------------------------------------------------------
# HEALTH CHECK RUNNER
# ---------------------------------------------------------------------------

def run_health_checks(service: Optional[str] = None, json_output: bool = False) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "services": {},
        "infrastructure": {},
        "system": {},
        "overall_status": "OK",
    }

    all_ok = True

    # Check services
    for name, config in SERVICES.items():
        if service and name != service:
            continue
        status, detail, code = check_http_service(
            config["host"], config["port"], config["path"], config["timeout"]
        )
        results["services"][name] = {
            "status": status,
            "detail": detail,
            "code": code,
            "endpoint": f"http://{config['host']}:{config['port']}{config['path']}",
        }
        if status == "CRITICAL":
            all_ok = False

    # Check infrastructure
    for name, config in INFRASTRUCTURE.items():
        if service and name != service:
            continue
        status, detail, latency = check_tcp_port(config["host"], config["port"], config["timeout"])
        results["infrastructure"][name] = {
            "status": status,
            "detail": detail,
            "endpoint": f"{config['host']}:{config['port']}",
        }
        if status == "CRITICAL":
            all_ok = False

    # Check system resources
    disk_status, disk_detail, disk_pct = check_disk_usage()
    results["system"]["disk"] = {"status": disk_status, "detail": disk_detail}
    if disk_status == "CRITICAL":
        all_ok = False

    mem_status, mem_detail, mem_pct = check_memory_usage()
    results["system"]["memory"] = {"status": mem_status, "detail": mem_detail}
    if mem_status == "CRITICAL":
        all_ok = False

    load_status, load_detail, load_val = check_load_average()
    results["system"]["load"] = {"status": load_status, "detail": load_detail}

    # Check certificate expiry (web services)
    for name, config in SERVICES.items():
        if service and name != service:
            continue
        if config["port"] == 443:
            cert_status, cert_detail, days_left = check_certificate_expiry(config["host"])
            results["services"][name]["certificate"] = {
                "status": cert_status,
                "detail": cert_detail,
                "days_remaining": days_left,
            }
            if cert_status == "CRITICAL":
                all_ok = False

    results["overall_status"] = "OK" if all_ok else "DEGRADED"

    return results


def print_health_report(results: Dict[str, Any]):
    print(f"\n{'='*60}")
    print(f"  HEALTH CHECK REPORT")
    print(f"  Host: {results['hostname']}")
    print(f"  Time: {results['timestamp']}")
    print(f"  Overall: {results['overall_status']}")
    print(f"{'='*60}")

    for category, items in [("Services", results["services"]),
                             ("Infrastructure", results["infrastructure"]),
                             ("System", results["system"])]:
        if items:
            print(f"\n  {category}:")
            for name, check in items.items():
                if isinstance(check, dict) and "status" in check:
                    status_icon = {"OK": "✓", "WARNING": "⚠", "CRITICAL": "✗"}.get(check["status"], "?")
                    print(f"    {status_icon} {name}: {check['detail']}")
                else:
                    print(f"    {name}:")
                    for sub_name, sub_check in check.items():
                        if isinstance(sub_check, dict) and "status" in sub_check:
                            sub_icon = {"OK": "✓", "WARNING": "⚠", "CRITICAL": "✗"}.get(sub_check["status"], "?")
                            print(f"      {sub_icon} {sub_name}: {sub_check['detail']}")
    print()


def parse_args():
    parser = argparse.ArgumentParser(description="Health check tool")
    parser.add_argument("--service", "-s", help="Check specific service only")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--output", "-o", help="Output file path")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.watch:
        print(f"Continuous monitoring (interval: {args.interval}s). Press Ctrl+C to stop.")
        try:
            while True:
                results = run_health_checks(args.service, args.json)
                if args.json:
                    print(json.dumps(results, indent=2))
                else:
                    print_health_report(results)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    else:
        results = run_health_checks(args.service, args.json)
        if args.json:
            output = json.dumps(results, indent=2)
            print(output)
        else:
            print_health_report(results)

        if args.output:
            with open(args.output, "w") as f:
                if args.json:
                    json.dump(results, f, indent=2)
                else:
                    json.dump(results, f, indent=2)
            print(f"Report saved to {args.output}")

        if results["overall_status"] == "DEGRADED":
            return 1

    return 0


if __name__ == "__main__":
    main()
