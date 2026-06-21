import os
import platform


def check_memory_usage():
    if platform.system() == 'Linux':
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.readlines()
            # Parse memory info
            total_memory = int(meminfo[0].split(':')[1].strip().split()[0])
            free_memory = int(meminfo[1].split(':')[1].strip().split()[0])
            used_memory = total_memory - free_memory
            return ('OK', {'total': total_memory, 'used': used_memory, 'free': free_memory})
        except Exception as e:
            return ('WARNING', str(e))
    else:
        # Fallback for non-Linux systems
        try:
            import psutil
            mem = psutil.virtual_memory()
            return ('OK', {'total': mem.total, 'used': mem.used, 'free': mem.free})
        except Exception as e:
            return ('WARNING', str(e))


def check_load_average():
    if platform.system() == 'Linux':
        try:
            with open('/proc/loadavg', 'r') as f:
                loadavg = f.read().strip().split()
            return ('OK', {'load1': loadavg[0], 'load5': loadavg[1], 'load15': loadavg[2]})
        except Exception as e:
            return ('WARNING', str(e))
    else:
        # Fallback for non-Linux systems
        try:
            loadavg = os.getloadavg()
            return ('OK', {'load1': loadavg[0], 'load5': loadavg[1], 'load15': loadavg[2]})
        except Exception as e:
            return ('WARNING', str(e))


if __name__ == '__main__':
    memory_status = check_memory_usage()
    load_status = check_load_average()
    print('Memory Status:', memory_status)
    print('Load Status:', load_status)