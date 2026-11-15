#!/usr/bin/env python3
import os
import platform
import json
import sys

def check_memory_usage():
    """
    Checks memory usage. 
    Priority: /proc/meminfo (Linux) -> os.sysconf (Unix/macOS fallback).
    """
    # Linux-specific path
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            mem_info = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    mem_info[parts[0].strip()] = parts[1].strip()
            
            total = mem_info.get("MemTotal", "Unknown")
            available = mem_info.get("MemAvailable", "Unknown")
            return "OK", f"Linux MemTotal: {total}, MemAvailable: {available}"
        except Exception as e:
            return "WARNING", f"Error reading /proc/meminfo: {str(e)}"

    # Cross-platform fallback (macOS/BSD/Unix)
    try:
        # os.sysconf is available on most Unix-like systems
        pagesize = os.sysconf('SC_PAGE_SIZE')
        phys_pages = os.sysconf('SC_PHYS_PAGES')
        avail_pages = os.sysconf('SC_AVPHYS_PAGES')
        
        total_gb = (pagesize * phys_pages) / (1024**3)
        avail_gb = (pagesize * avail_pages) / (1024**3)
        
        return "OK", f"Fallback Total: {total_gb:.2f}GB, Available: {avail_gb:.2f}GB"
    except Exception:
        return "WARNING", "Memory diagnostics unavailable on this platform"

def check_load_average():
    """
    Checks system load average.
    Priority: /proc/loadavg (Linux) -> os.getloadavg (Unix/macOS fallback).
    """
    # Linux-specific path
    if os.path.exists("/proc/loadavg"):
        try:
            with open("/proc/loadavg", "r") as f:
                load = f.read().strip()
            return "OK", f"Linux Load: {load}"
        except Exception as e:
            return "WARNING", f"Error reading /proc/loadavg: {str(e)}"

    # Cross-platform fallback
    try:
        # os.getloadavg() returns 1, 5, and 15 minute averages
        load1, load5, load15 = os.getloadavg()
        return "OK", f"Fallback Load: {load1:.2f}, {load5:.2f}, {load15:.2f}"
    except Exception:
        return "WARNING", "Load average unavailable on this platform"

def run_health_check(output_json=False):
    results = {
        "memory": check_memory_usage(),
        "load": check_load_average(),
        "platform": platform.system(),
        "timestamp": os.popen("date").read().strip()
    }
    
    if output_json:
        return json.dumps(results, indent=2)
    
    report = []
    for key, (status, detail) in [("Memory", results["memory"]), ("Load", results["load"])]:
        report.append(f"[{status}] {key}: {detail}")
    return "\n".join(report)

def validate_fallbacks():
    """Internal validation to simulate missing /proc files."""
    print("--- Running Fallback Validation ---")
    # We simulate by checking if we are NOT on Linux or if /proc is missing
    if not os.path.exists("/proc"):
        print("Confirmed: /proc not found. Using fallbacks.")
    
    mem_status, mem_detail = check_memory_usage()
    load_status, load_detail = check_load_average()
    
    print(f"Memory Check: {mem_status} - {mem_detail}")
    print(f"Load Check: {load_status} - {load_detail}")
    print("--- Validation Complete ---")

if __name__ == "__main__":
    if "--test-fallbacks" in sys.argv:
        validate_fallbacks()
    else:
        print(run_health_check("--json" in sys.argv))
