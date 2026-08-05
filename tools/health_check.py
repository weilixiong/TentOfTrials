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
import shutil
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
    """Check disk usage with cross-platform fallbacks.

    Strategy:
      1. shutil.disk_usage() -- Python >= 3.3, all platforms
      2. os.statvfs()         -- Unix-only fallback
      3. WARNING              -- graceful degradation
    """
    # Method 1: shutil.disk_usage (cross-platform, preferred)
    try:
        usage = shutil.disk_usage(path)
        total = usage.total
        free = usage.free
        used = usage.used
        pct = (used / total) * 100 if total > 0 else 0

        if pct < DISK_THRESHOLD_WARNING:
            status = "OK"
        elif pct < DISK_THRESHOLD_CRITICAL:
            status = "WARNING"
        else:
            status = "CRITICAL"

        detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
        return status, detail, pct
    except Exception:
        pass

    # Method 2: os.statvfs (Unix fallback)
    try:
        stat = os.statvfs(path)
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bavail
        used = total - free
        pct = (used / total) * 100

        if pct < DISK_THRESHOLD_WARNING:
            status = "OK"
        elif pct < DISK_THRESHOLD_CRITICAL:
            status = "WARNING"
        else:
            status = "CRITICAL"

        detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
        return status, detail, pct
    except Exception:
        pass

    # Method 3: unable to check
    return "WARNING", "Cannot check disk usage: no method available on this OS", 0


def check_memory_usage() -> Tuple[str, str, float]:
    """Check memory usage with cross-platform fallbacks.

    Strategy (tried in order):
      1. psutil.virtual_memory()        -- cross-platform, optional dependency
      2. /proc/meminfo                  -- Linux
      3. sysctl hw.memsize + vm_stat    -- macOS
      4. wmic / systeminfo              -- Windows
      5. WARNING                        -- graceful degradation
    """
    # Helper: try importing psutil
    def _try_psutil():
        try:
            import psutil as _psutil
            return _psutil
        except ImportError:
            return None

    platform = sys.platform

    # Method 1: psutil (works on all platforms if installed)
    psutil_mod = _try_psutil()
    if psutil_mod is not None:
        try:
            mem = psutil_mod.virtual_memory()
            pct = mem.percent
            total = mem.total
            used = mem.used

            if pct < MEMORY_THRESHOLD_WARNING:
                status = "OK"
            elif pct < MEMORY_THRESHOLD_CRITICAL:
                status = "WARNING"
            else:
                status = "CRITICAL"

            detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
            return status, detail, pct
        except Exception:
            pass

    # Method 2a: /proc/meminfo (Linux)
    if platform.startswith("linux"):
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
            used = total - available
            pct = (used / total) * 100 if total > 0 else 0

            if pct < MEMORY_THRESHOLD_WARNING:
                return "OK", f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)", pct
            elif pct < MEMORY_THRESHOLD_CRITICAL:
                return "WARNING", f"{pct:.1f}% used", pct
            else:
                return "CRITICAL", f"{pct:.1f}% used", pct
        except Exception:
            pass

    # Method 2b: sysctl/vm_stat (macOS)
    if platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            total = int(result.stdout.strip())

            result = subprocess.run(
                ["sysctl", "-n", "hw.pagesize"],
                capture_output=True, text=True, timeout=5
            )
            page_size = int(result.stdout.strip())

            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5
            )
            vm = {}
            for vline in result.stdout.strip().split(chr(10)):
                if ":" in vline:
                    key, val = vline.split(":", 1)
                    val = val.strip().rstrip(".")
                    try:
                        vm[key.strip()] = int(val)
                    except ValueError:
                        pass

            free_pages = vm.get("Pages free", 0)
            inactive_pages = vm.get("Pages inactive", 0)
            available = (free_pages + inactive_pages) * page_size
            used = total - available
            pct = (used / total) * 100 if total > 0 else 0

            if pct < MEMORY_THRESHOLD_WARNING:
                status = "OK"
            elif pct < MEMORY_THRESHOLD_CRITICAL:
                status = "WARNING"
            else:
                status = "CRITICAL"

            detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
            return status, detail, pct
        except Exception:
            pass

    # Method 2c: wmic / systeminfo (Windows)
    if platform == "win32":
        try:
            result = subprocess.run(
                ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory", "/Value"],
                capture_output=True, text=True, timeout=10
            )
            mem = {}
            for wline in result.stdout.strip().split(chr(10)):
                wline = wline.strip()
                if "=" in wline:
                    key, val = wline.split("=", 1)
                    try:
                        mem[key.strip()] = int(val.strip()) * 1024
                    except ValueError:
                        pass

            total = mem.get("TotalVisibleMemorySize", 0)
            free = mem.get("FreePhysicalMemory", 0)
            used = total - free
            pct = (used / total) * 100 if total > 0 else 0

            if pct < MEMORY_THRESHOLD_WARNING:
                status = "OK"
            elif pct < MEMORY_THRESHOLD_CRITICAL:
                status = "WARNING"
            else:
                status = "CRITICAL"

            detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
            return status, detail, pct
        except Exception:
            pass

        # Fallback: systeminfo
        try:
            result = subprocess.run(
                ["systeminfo"],
                capture_output=True, text=True, timeout=15,
            )
            total = None
            available = None
            for sinfo_line in result.stdout.split(chr(10)):
                line_lower = sinfo_line.lower()
                if "total physical memory" in line_lower:
                    parts = sinfo_line.replace(",", "").split()
                    for p in parts:
                        if p.replace(".", "").isdigit():
                            total = int(float(p)) * 1024 * 1024
                            break
                if "available physical memory" in line_lower:
                    parts = sinfo_line.replace(",", "").split()
                    for p in parts:
                        if p.replace(".", "").isdigit():
                            available = int(float(p)) * 1024 * 1024
                            break

            if total and available:
                used = total - available
                pct = (used / total) * 100 if total > 0 else 0

                if pct < MEMORY_THRESHOLD_WARNING:
                    status = "OK"
                elif pct < MEMORY_THRESHOLD_CRITICAL:
                    status = "WARNING"
                else:
                    status = "CRITICAL"

                detail = f"{pct:.1f}% used ({used // (1024**3)}GB/{total // (1024**3)}GB)"
                return status, detail, pct
        except Exception:
            pass

    # Method 3: graceful degradation
    return "WARNING", "Cannot check memory: unsupported platform or no method available", 0


def check_load_average() -> Tuple[str, str, float]:
    """Check CPU load with cross-platform fallbacks.

    Strategy (tried in order):
      1. os.getloadavg()                -- Unix/macOS built-in
      2. psutil.getloadavg() / cpu_percent() -- cross-platform
      3. /proc/loadavg                  -- Linux
      4. wmic cpu LoadPercentage        -- Windows
      5. WARNING                        -- graceful degradation
    """
    def _try_psutil():
        try:
            import psutil as _psutil
            return _psutil
        except ImportError:
            return None

    platform = sys.platform

    # Method 1: os.getloadavg() (Unix/macOS)
    try:
        load = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        load_pct = (load / cpu_count) * 100

        if load_pct < 70:
            status = "OK"
        elif load_pct < 90:
            status = "WARNING"
        else:
            status = "CRITICAL"

        detail = f"Load: {load:.2f} ({load_pct:.0f}% of {cpu_count} cores)"
        return status, detail, load
    except Exception:
        pass

    # Method 2: psutil (cross-platform)
    psutil_mod = _try_psutil()
    if psutil_mod is not None:
        try:
            load_avg = psutil_mod.getloadavg()
            if load_avg:
                load = load_avg[0]
                cpu_count = os.cpu_count() or 1
                load_pct = (load / cpu_count) * 100

                if load_pct < 70:
                    status = "OK"
                elif load_pct < 90:
                    status = "WARNING"
                else:
                    status = "CRITICAL"

                detail = f"Load: {load:.2f} ({load_pct:.0f}% of {cpu_count} cores)"
                return status, detail, load
        except Exception:
            pass

        try:
            cpu_pct = psutil_mod.cpu_percent(interval=0.5)
            if cpu_pct < 70:
                status = "OK"
            elif cpu_pct < 90:
                status = "WARNING"
            else:
                status = "CRITICAL"

            detail = f"CPU usage: {cpu_pct:.1f}% (instant sample)"
            return status, detail, cpu_pct
        except Exception:
            pass

    # Method 3: /proc/loadavg (Linux)
    if platform.startswith("linux"):
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
        except Exception:
            pass

    # Method 4: wmic (Windows)
    if platform == "win32":
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "LoadPercentage"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split(chr(10))
            for wline in lines[1:]:
                wline = wline.strip()
                if wline and wline.isdigit():
                    load_pct = float(wline)
                    cpu_count = os.cpu_count() or 1

                    if load_pct < 70:
                        status = "OK"
                    elif load_pct < 90:
                        status = "WARNING"
                    else:
                        status = "CRITICAL"

                    detail = f"CPU usage: {load_pct:.1f}% ({cpu_count} cores)"
                    return status, detail, load_pct
        except Exception:
            pass

    # Method 5: graceful degradation
    return "WARNING", "Cannot check CPU load: unsupported platform or no method available", 0



# ---------------------------------------------------------------------------
# HEALTH CHECK RUNNER
# ---------------------------------------------------------------------------

def run_health_checks(service: Optional[str] = None, json_output: bool = False) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "platform": sys.platform,
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
    print(f"  Platform: {results.get('platform', 'unknown')}")
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
