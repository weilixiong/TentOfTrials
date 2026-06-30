#!/usr/bin/env python3
"""
Health check tool for TentOfTrials.
Provides system health diagnostics with cross-platform support.
"""

import os
import sys
import json
import platform
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_memory_info() -> Dict[str, Any]:
    """
    Get memory information with cross-platform fallbacks.
    
    Returns:
        Dict containing memory info with keys: total, available, percent, used
    """
    memory_info = {
        'total': 0,
        'available': 0,
        'percent': 0,
        'used': 0,
        'source': 'unknown'
    }
    
    # Try Linux /proc/meminfo first
    if platform.system() == 'Linux' and os.path.exists('/proc/meminfo'):
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        memory_info['total'] = int(line.split()[1]) * 1024
                    elif 'MemAvailable' in line:
                        memory_info['available'] = int(line.split()[1]) * 1024
                    elif 'MemFree' in line and memory_info['available'] == 0:
                        memory_info['available'] = int(line.split()[1]) * 1024
            
            if memory_info['total'] > 0:
                memory_info['used'] = memory_info['total'] - memory_info['available']
                memory_info['percent'] = (memory_info['used'] / memory_info['total']) * 100
                memory_info['source'] = '/proc/meminfo'
                return memory_info
        except (IOError, ValueError, IndexError) as e:
            print(f"Warning: Failed to read /proc/meminfo: {e}", file=sys.stderr)
    
    # Fallback to psutil if available
    if PSUTIL_AVAILABLE:
        try:
            mem = psutil.virtual_memory()
            memory_info['total'] = mem.total
            memory_info['available'] = mem.available
            memory_info['used'] = mem.used
            memory_info['percent'] = mem.percent
            memory_info['source'] = 'psutil'
            return memory_info
        except Exception as e:
            print(f"Warning: psutil memory check failed: {e}", file=sys.stderr)
    
    # Final fallback using os module (limited info)
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        memory_info['used'] = usage.ru_maxrss * 1024  # Convert KB to bytes
        memory_info['source'] = 'resource'
    except (ImportError, AttributeError) as e:
        print(f"Warning: resource module not available: {e}", file=sys.stderr)
    
    return memory_info


def get_load_average() -> Dict[str, Any]:
    """
    Get system load average with cross-platform fallbacks.
    
    Returns:
        Dict containing load info with keys: load1, load5, load15, source
    """
    load_info = {
        'load1': 0.0,
        'load5': 0.0,
        'load15': 0.0,
        'source': 'unknown'
    }
    
    # Try Linux /proc/loadavg first
    if platform.system() == 'Linux' and os.path.exists('/proc/loadavg'):
        try:
            with open('/proc/loadavg', 'r') as f:
                data = f.read().strip().split()
                if len(data) >= 3:
                    load_info['load1'] = float(data[0])
                    load_info['load5'] = float(data[1])
                    load_info['load15'] = float(data[2])
                    load_info['source'] = '/proc/loadavg'
                    return load_info
        except (IOError, ValueError, IndexError) as e:
            print(f"Warning: Failed to read /proc/loadavg: {e}", file=sys.stderr)
    
    # Fallback to os.getloadavg() (available on Unix-like systems including macOS)
    try:
        load_avg = os.getloadavg()
        load_info['load1'] = load_avg[0]
        load_info['load5'] = load_avg[1]
        load_info['load15'] = load_avg[2]
        load_info['source'] = 'os.getloadavg'
        return load_info
    except (AttributeError, OSError) as e:
        print(f"Warning: os.getloadavg() not available: {e}", file=sys.stderr)
    
    # Fallback to psutil if available
    if PSUTIL_AVAILABLE:
        try:
            load_avg = psutil.getloadavg()
            load_info['load1'] = load_avg[0]
            load_info['load5'] = load_avg[1]
            load_info['load15'] = load_avg[2]
            load_info['source'] = 'psutil'
            return load_info
        except Exception as e:
            print(f"Warning: psutil load check failed: {e}", file=sys.stderr)
    
    return load_info


def get_cpu_info() -> Dict[str, Any]:
    """
    Get CPU information with cross-platform support.
    
    Returns:
        Dict containing CPU info with keys: count, percent, source
    """
    cpu_info = {
        'count': os.cpu_count() or 0,
        'percent': 0.0,
        'source': 'os'
    }
    
    if PSUTIL_AVAILABLE:
        try:
            cpu_info['percent'] = psutil.cpu_percent(interval=0.1)
            cpu_info['source'] = 'psutil'
        except Exception as e:
            print(f"Warning: psutil CPU check failed: {e}", file=sys.stderr)
    
    return cpu_info


def get_disk_info() -> Dict[str, Any]:
    """
    Get disk usage information with cross-platform support.
    
    Returns:
        Dict containing disk info with keys: total, used, free, percent, source
    """
    disk_info = {
        'total': 0,
        'used': 0,
        'free': 0,
        'percent': 0.0,
        'source': 'unknown'
    }
    
    if PSUTIL_AVAILABLE:
        try:
            usage = psutil.disk_usage('/')
            disk_info['total'] = usage.total
            disk_info['used'] = usage.used
            disk_info['free'] = usage.free
            disk_info['percent'] = usage.percent
            disk_info['source'] = 'psutil'
        except Exception as e:
            print(f"Warning: psutil disk check failed: {e}", file=sys.stderr)
    
    return disk_info


def get_network_info() -> Dict[str, Any]:
    """
    Get network information with cross-platform support.
    
    Returns:
        Dict containing network info with keys: bytes_sent, bytes_recv, source
    """
    network_info = {
        'bytes_sent': 0,
        'bytes_recv': 0,
        'source': 'unknown'
    }
    
    if PSUTIL_AVAILABLE:
        try:
            net = psutil.net_io_counters()
            network_info['bytes_sent'] = net.bytes_sent
            network_info['bytes_recv'] = net.bytes_recv
            network_info['source'] = 'psutil'
        except Exception as e:
            print(f"Warning: psutil network check failed: {e}", file=sys.stderr)
    
    return network_info


def get_system_info() -> Dict[str, Any]:
    """
    Get general system information.
    
    Returns:
        Dict containing system info
    """
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'hostname': platform.node(),
        'python_version': platform.python_version(),
        'uptime': get_uptime()
    }


def get_uptime() -> Optional[float]:
    """
    Get system uptime in seconds with cross-platform support.
    
    Returns:
        Uptime in seconds or None if unavailable
    """
    if PSUTIL_AVAILABLE:
        try:
            import time
            return time.time() - psutil.boot_time()
        except Exception:
            pass
    
    # Fallback for Unix-like systems
    if platform.system() in ('Linux', 'Darwin'):
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.read().split()[0])
        except (IOError, ValueError, IndexError):
            pass
    
    return None


def run_health_check() -> Dict[str, Any]:
    """
    Run comprehensive health check.
    
    Returns:
        Dict containing all health check results
    """
    health_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'healthy',
        'system': get_system_info(),
        'memory': get_memory_info(),
        'load': get_load_average(),
        'cpu': get_cpu_info(),
        'disk': get_disk_info(),
        'network': get_network_info()
    }
    
    # Determine overall status
    warnings = []
    
    # Check memory
    if health_data['memory']['percent'] > 90:
        warnings.append('High memory usage')
    elif health_data['memory']['percent'] > 80:
        warnings.append('Elevated memory usage')
    
    # Check load
    cpu_count = health_data['cpu']['count']
    if cpu_count > 0 and health_data['load']['load1'] > cpu_count * 2:
        warnings.append('High system load')
    
    # Check disk
    if health_data['disk']['percent'] > 90:
        warnings.append('Low disk space')
    
    if warnings:
        health_data['status'] = 'warning'
        health_data['warnings'] = warnings
    
    return health_data


def main():
    """Main entry point for health check tool."""
    try:
        health_data = run_health_check()
        
        # Output as JSON
        print(json.dumps(health_data, indent=2, default=str))
        
        # Exit with appropriate code
        if health_data['status'] == 'healthy':
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f"Error running health check: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()