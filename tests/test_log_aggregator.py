import unittest
from tools.log_aggregator import parse_json_log, parse_text_log, parse_nginx_log

class TestIndependentLogParserFixtures(unittest.TestCase):
    def test_independent_json_parser_fixture(self):
        # Hand-written independent JSON log line avoiding parser-generated serialization biases
        raw_line = '{"timestamp": "2023-10-27T10:15:30Z", "level": "ERROR", "message": "Database connection timeout", "service": "auth-api"}'
        parsed = parse_json_log(raw_line)
        
        self.assertEqual(parsed.get("timestamp"), "2023-10-27T10:15:30Z")
        self.assertEqual(parsed.get("level"), "ERROR")
        self.assertEqual(parsed.get("message"), "Database connection timeout")
        self.assertEqual(parsed.get("service"), "auth-api")

    def test_independent_text_parser_fixture(self):
        # Hand-written legacy text log format
        raw_line = '[2023-10-27 12:00:01,452] [INFO] [worker-01] Task queue initialized successfully.'
        parsed = parse_text_log(raw_line)
        
        self.assertEqual(parsed.get("timestamp"), "2023-10-27 12:00:01,452")
        self.assertEqual(parsed.get("level"), "INFO")
        self.assertEqual(parsed.get("component"), "worker-01")
        self.assertIn("Task queue initialized", parsed.get("message"))

    def test_independent_nginx_parser_fixture(self):
        # Hand-written standard NGINX combined log format sample
        raw_line = '192.168.1.50 - - [27/Oct/2023:14:32:10 +0000] "POST /api/v1/checkout HTTP/1.1" 200 512 "https://example.com/cart" "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"'
        parsed = parse_nginx_log(raw_line)
        
        self.assertEqual(parsed.get("remote_addr"), "192.168.1.50")
        self.assertEqual(parsed.get("time_local"), "27/Oct/2023:14:32:10 +0000")
        self.assertEqual(parsed.get("request"), "POST /api/v1/checkout HTTP/1.1")
        self.assertEqual(parsed.get("status"), "200")
        self.assertEqual(parsed.get("body_bytes_sent"), "512")
        self.assertEqual(parsed.get("http_referer"), "https://example.com/cart")
        self.assertIn("Firefox/119.0", parsed.get("http_user_agent"))

if __name__ == "__main__":
    unittest.main()