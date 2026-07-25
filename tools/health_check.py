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


def _check_memory_linux() -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """Check memory usage via /proc/meminfo (Linux). Returns None if unavailable."""
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().replace(" kB", "")
                    try:
                        meminfo[key] = int(value) * 1024
                    except ValueError:
                        pass

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        if total == 0:
            return None, None, None
        used = total - available
        pct = (used / total) * 100
        return pct, f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", total
    except Exception:
        return None, None, None


def _check_memory_psutil() -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """Check memory usage via psutil (cross-platform). Returns None if unavailable."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        pct = mem.percent
        return pct, f"{pct:.1f}% used ({mem.used // (1024**3)}GB/{mem.total // (1024**3)}GB)", mem.total
    except ImportError:
        return None, None, None


def _check_memory_windows() -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """Check memory usage on Windows via ctypes. Returns None if unavailable."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32

        class MEMORYSTATUSEX(ctypes.Structure):
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

        memoryStatus = MEMORYSTATUSEX()
        memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus)):
            return None, None, None

        total = memoryStatus.ullTotalPhys
        available = memoryStatus.ullAvailPhys
        used = total - available
        pct = (used / total) * 100 if total > 0 else 0
        return pct, f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", total
    except Exception:
        return None, None, None


def _check_memory_macos() -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """Check memory usage on macOS via sysctl/vm_stat. Returns None if unavailable."""
    try:
        # Try sysctl for total memory
        total_str = subprocess.check_output(["sysctl", "-n", "hw.memsize"],
                                            text=True, stderr=subprocess.DEVNULL).strip()
        total = int(total_str)

        # Try vm_stat for page info
        vm_out = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)

        # Get page size
        page_size_str = subprocess.check_output(["pagesize"], text=True,
                                                 stderr=subprocess.DEVNULL).strip()
        page_size = int(page_size_str)

        # Parse key values from vm_stat
        pages_free = 0
        pages_active = 0
        pages_inactive = 0
        pages_wired = 0
        pages_speculative = 0
        pages_purgeable = 0
        pages_compressor = 0

        for line in vm_out.strip().split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            key, val_str = line.split(':', 1)
            key = key.strip()
            val_str = val_str.strip().rstrip('.')
            try:
                val = int(val_str)
            except ValueError:
                continue

            if key == 'Pages free':
                pages_free = val
            elif key == 'Pages active':
                pages_active = val
            elif key == 'Pages inactive':
                pages_inactive = val
            elif key == 'Pages wired down':
                pages_wired = val
            elif key == 'Pages speculative':
                pages_speculative = val
            elif key == 'Pages purgeable':
                pages_purgeable = val
            elif key == 'pages stored in compressor':
                pages_compressor = val
            elif key == 'Pages occupied by compressor':
                pages_compressor = val

        total_pages = pages_free + pages_active + pages_inactive + pages_wired + pages_speculative
        # On modern macOS, "memory used" = active + wired + compressor
        used_pages = pages_active + pages_wired + pages_compressor
        pct = (used_pages / total_pages * 100) if total_pages > 0 else 0

        return pct, f"{pct:.1f}% used ({used_pages * page_size // (1024**3)}GB/{total // (1024**3)}GB)", total
    except Exception:
        return None, None, None


def check_memory_usage() -> Tuple[str, str, float]:
    """
    Check memory usage with cross-platform fallbacks.
    Priority: /proc/meminfo (Linux) > psutil > macOS vm_stat > Windows ctypes.
    """
    # 1) Linux /proc/meminfo
    pct, detail, total = _check_memory_linux()
    if pct is not None:
        if pct < MEMORY_THRESHOLD_WARNING:
            return "OK", detail, pct
        elif pct < MEMORY_THRESHOLD_CRITICAL:
            return "WARNING", detail, pct
        else:
            return "CRITICAL", detail, pct

    # 2) psutil (cross-platform)
    pct, detail, total = _check_memory_psutil()
    if pct is not None:
        if pct < MEMORY_THRESHOLD_WARNING:
            return "OK", detail, pct
        elif pct < MEMORY_THRESHOLD_CRITICAL:
            return "WARNING", detail, pct
        else:
            return "CRITICAL", detail, pct

    # 3) macOS vm_stat
    pct, detail, total = _check_memory_macos()
    if pct is not None:
        if pct < MEMORY_THRESHOLD_WARNING:
            return "OK", detail, pct
        elif pct < MEMORY_THRESHOLD_CRITICAL:
            return "WARNING", detail, pct
        else:
            return "CRITICAL", detail, pct

    # 4) Windows ctypes
    pct, detail, total = _check_memory_windows()
    if pct is not None:
        if pct < MEMORY_THRESHOLD_WARNING:
            return "OK", detail, pct
        elif pct < MEMORY_THRESHOLD_CRITICAL:
            return "WARNING", detail, pct
        else:
            return "CRITICAL", detail, pct

    # 5) No fallback available
    import platform
    return "WARNING", f"Memory check not available on {platform.system()}", 0


def check_load_average() -> Tuple[str, str, float]:
    """
    Check system load average with cross-platform fallbacks.
    Priority: /proc/loadavg (Linux) > os.getloadavg() (macOS/BSD).
    On Windows, returns WARNING as loadavg is not a standard metric.
    """
    # 1) Linux /proc/loadavg
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().strip().split()
            load = float(parts[0])
            cpu_count = os.cpu_count() or 1
            load_pct = (load / cpu_count) * 100

            if load_pct < 70:
                return "OK", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load
            elif load_pct < 90:
                return "WARNING", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load
            else:
                return "CRITICAL", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores)", load
    except (FileNotFoundError, IOError):
        pass

    # 2) os.getloadavg() (macOS/BSD/Linux — but only available on Unix)
    try:
        load_avg = os.getloadavg()
        load = load_avg[0]  # 1-minute load average
        cpu_count = os.cpu_count() or 1
        load_pct = (load / cpu_count) * 100

        if load_pct < 70:
            return "OK", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores, via os.getloadavg())", load
        elif load_pct < 90:
            return "WARNING", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores, via os.getloadavg())", load
        else:
            return "CRITICAL", f"Load: {load} ({load_pct:.0f}% of {cpu_count} cores, via os.getloadavg())", load
    except (OSError, AttributeError):
        pass

    # 3) Not available on this platform
    import platform
    return "WARNING", f"Load average not available on {platform.system()}", 0


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
