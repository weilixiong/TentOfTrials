import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

class TestLogParsers(unittest.TestCase):
    def setUp(self):
        self.json_parser = JSONLogParser()
        self.text_parser = TextLogParser()
        self.nginx_parser = NginxLogParser()

    def test_json_parser(self):
        # Valid JSON
        line = '{"timestamp": 1705320000, "level": "error", "service": "auth-service", "message": "Login failed"}'
        result = self.json_parser.parse(line)
        self.assertIsNotNone(result)
        self.assertEqual(result['timestamp'], 1705320000)
        self.assertEqual(result['level'], "error")
        self.assertEqual(result['service'], "auth-service")
        self.assertEqual(result['message'], "Login failed")
        self.assertEqual(result['format'], "json")

        # Invalid JSON (malformed)
        bad_line = '{"timestamp": 1705320000, "level": "error", '
        self.assertIsNone(self.json_parser.parse(bad_line))

    def test_text_parser(self):
        # Valid Text
        line = "2024-01-15T12:00:00 [payment-worker] ERROR: Payment processing failed"
        result = self.text_parser.parse(line)
        self.assertIsNotNone(result)
        # 2024-01-15T12:00:00 UTC timestamp is 1705320000
        self.assertEqual(result['timestamp'], 1705320000)
        self.assertEqual(result['level'], "error")
        self.assertEqual(result['service'], "payment-worker")
        self.assertEqual(result['message'], line)
        self.assertEqual(result['format'], "text")

        # Fallback fields (if timestamp/level missing)
        line_no_meta = "Just a random log string without meta"
        res = self.text_parser.parse(line_no_meta)
        self.assertIsNotNone(res)
        self.assertIsNone(res['timestamp'])
        self.assertEqual(res['level'], "unknown")

    def test_nginx_parser(self):
        # Valid Nginx Combined
        line = '127.0.0.1 - frank [15/Jan/2024:12:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "http://example.com" "Mozilla/5.0"'
        result = self.nginx_parser.parse(line)
        self.assertIsNotNone(result)
        self.assertEqual(result['timestamp'], 1705320000)
        self.assertEqual(result['level'], "info")
        self.assertEqual(result['service'], "nginx")
        self.assertEqual(result['message'], "GET /api/users HTTP/1.1")
        self.assertEqual(result['fields']['status'], 200)

        # 500 error status
        line_500 = '192.168.1.1 - - [15/Jan/2024:12:00:00 +0000] "POST /api/data HTTP/1.1" 500 0 "-" "curl/7.68.0"'
        res_500 = self.nginx_parser.parse(line_500)
        self.assertEqual(res_500['level'], "error")

        # Invalid nginx log (malformed)
        bad_line = 'This is not an nginx log'
        self.assertIsNone(self.nginx_parser.parse(bad_line))

if __name__ == "__main__":
    unittest.main()
