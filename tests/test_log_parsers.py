import unittest
from datetime import datetime, timezone

# We assume tools/log_aggregator.py is importable. If not, we use importlib.
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'tools'))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

class TestLogParsers(unittest.TestCase):
    def test_json_parser(self):
        parser = JSONLogParser()
        
        # Valid JSON
        valid_line = '{"timestamp": 1700000000, "level": "ERROR", "service": "backend", "message": "DB connection failed"}'
        result = parser.parse(valid_line)
        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1700000000)
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "backend")
        self.assertEqual(result["message"], "DB connection failed")
        self.assertEqual(result["format"], "json")
        
        # Malformed JSON
        malformed_line = '{"timestamp": 1700000000, "level": "ERROR", "service": '
        self.assertIsNone(parser.parse(malformed_line))

    def test_text_parser(self):
        parser = TextLogParser()
        
        # Valid plain text with known timestamp format
        valid_line = '2026-11-07 10:15:30 [frontend] ERROR: Component crashed unexpectedly'
        result = parser.parse(valid_line)
        self.assertIsNotNone(result)
        
        # Verify timestamp (2026-11-07 10:15:30 UTC -> some int)
        dt = datetime(2026, 11, 7, 10, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(result["timestamp"], int(dt.timestamp()))
        
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["service"], "frontend")
        self.assertEqual(result["format"], "text")
        
        # Malformed / Unsupported text line (should not crash, might return None or partial data)
        # In this parser, it returns partial data for random strings
        unsupported = 'Just a random line without any timestamp or structure'
        result_unsup = parser.parse(unsupported)
        self.assertIsNotNone(result_unsup)
        self.assertIsNone(result_unsup["timestamp"])
        self.assertEqual(result_unsup["level"], "unknown")
        self.assertIsNone(result_unsup["service"])

    def test_nginx_parser(self):
        parser = NginxLogParser()
        
        # Valid nginx line
        valid_line = '192.168.1.1 - - [07/Nov/2026:10:15:30 +0000] "GET /api/v1/users HTTP/1.1" 404 123 "-" "Mozilla/5.0"'
        result = parser.parse(valid_line)
        self.assertIsNotNone(result)
        
        dt = datetime(2026, 11, 7, 10, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(result["timestamp"], int(dt.timestamp()))
        
        self.assertEqual(result["level"], "warn") # 404 is warn
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["message"], "GET /api/v1/users HTTP/1.1")
        self.assertEqual(result["fields"]["status"], 404)
        
        # Malformed nginx line (should not crash)
        malformed = '192.168.1.1 - - [bad-date] "GET /" abc def'
        self.assertIsNone(parser.parse(malformed))

if __name__ == '__main__':
    unittest.main()
