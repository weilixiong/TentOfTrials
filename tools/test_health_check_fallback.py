import unittest
from unittest.mock import patch, MagicMock
import os
import platform
import sys

# Add parent directory to path so we can import health_check
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools.health_check as hc

class TestHealthCheckFallback(unittest.TestCase):

    @patch('os.path.exists')
    @patch('platform.system')
    @patch('subprocess.check_output')
    def test_darwin_memory_fallback(self, mock_check_output, mock_system, mock_exists):
        # Setup mocks
        mock_exists.return_value = False
        mock_system.return_value = "Darwin"
        
        # Mock sysctl hw.memsize returning 16GB
        # Mock vm_stat returning statistics
        def check_output_side_effect(cmd, *args, **kwargs):
            if "sysctl" in cmd:
                return b"17179869184\n"
            elif "vm_stat" in cmd:
                return (
                    b"Mach Virtual Memory Statistics: (page size of 4096 bytes)\n"
                    b"Pages free:                  1000000.\n"
                    b"Pages active:                2000000.\n"
                    b"Pages inactive:              1000000.\n"
                    b"Pages speculative:            200000.\n"
                )
            raise ValueError(f"Unexpected subprocess call: {cmd}")
            
        mock_check_output.side_effect = check_output_side_effect
        
        status, detail, val = hc.check_memory_usage()
        
        self.assertEqual(status, "OK")
        # 47.5% used (used memory = 16GB - 2.2M pages * 4096 = 17179869184 - 9011200000 = 8168669184 = 7.6GB used out of 16GB)
        self.assertIn("47.5% used", detail)
        self.assertAlmostEqual(val, 47.548, places=2)

    @patch('os.path.exists')
    @patch('platform.system')
    @patch('os.cpu_count')
    def test_darwin_load_fallback(self, mock_cpu_count, mock_system, mock_exists):
        mock_exists.return_value = False
        mock_system.return_value = "Darwin"
        mock_cpu_count.return_value = 4
        
        # Mock os.getloadavg to return load values
        with patch('os.getloadavg', return_value=(1.5, 1.2, 1.0), create=True):
            status, detail, val = hc.check_load_average()
            
            self.assertEqual(status, "OK")
            self.assertIn("Load: 1.5 (38% of 4 cores)", detail)
            self.assertEqual(val, 1.5)

    @patch('os.path.exists')
    @patch('platform.system')
    def test_windows_memory_fallback(self, mock_system, mock_exists):
        mock_exists.return_value = False
        mock_system.return_value = "Windows"
        
        # Let's mock ctypes completely
        mock_ctypes = MagicMock()
        
        # Dummy structure fields
        class MockStructure:
            dwLength = 0
            dwMemoryLoad = 40
            ullTotalPhys = 17179869184
            ullAvailPhys = 10307921510
            
        mock_ctypes.Structure = object
        
        with patch.dict('sys.modules', {'ctypes': mock_ctypes}):
            # Set structure return value
            mock_ctypes.sizeof.return_value = 64
            
            # Since MEMORYSTATUSEX is defined inside check_memory_usage, we will mock ctypes
            # in sys.modules. We need to make sure MEMORYSTATUSEX instantiation returns our mocked struct
            # and windll.kernel32.GlobalMemoryStatusEx is called.
            # To do this cleanly, we'll configure mock_ctypes:
            # MEMORYSTATUSEX is defined as a subclass of ctypes.Structure
            # When MEMORYSTATUSEX() is called, it returns a new instance.
            # We can capture the instance or mock the __new__ or __init__ of Structure
            # Or even simpler, mock_ctypes.Structure can be a class that has the fields we want!
            class DummyStructure(object):
                def __init__(self, *args, **kwargs):
                    self.dwLength = 0
                    self.dwMemoryLoad = 40
                    self.ullTotalPhys = 17179869184
                    self.ullAvailPhys = 10307921510
                    
            mock_ctypes.Structure = DummyStructure
            mock_ctypes.sizeof.return_value = 64
            
            status, detail, val = hc.check_memory_usage()
            
            # Verify status code is OK and uses 40% memory load from dwMemoryLoad
            self.assertEqual(status, "OK")
            self.assertEqual(val, 40.0)

if __name__ == '__main__':
    unittest.main()
