"""Independent test fixtures and validation for log parser (Issue #5)."""

import json
import re
import unittest

FIXTURES_JSON = [
    '{"timestamp": "2026-09-09T10:15:30Z", "level": "INFO", "service": "auth-api", "msg": "user login successful", "user_id": 4120, "ip": "192.168.1.10"}',
    '{"timestamp": "2026-09-09T10:16:01Z", "level": "ERROR", "service": "billing-worker", "msg": "payment gateway timeout", "retry_count": 3, "amount": 49.99}',
    '{"time": "2026-09-09T10:17:22Z", "severity": "WARN", "app": "rate-limiter", "message": "threshold reached", "client": "app-ios"}'
]

FIXTURES_NGINX = [
    '127.0.0.1 - frank [09/Sep/2026:13:55:36 +0000] "GET /api/v1/orders HTTP/1.1" 200 2326 "https://example.com" "Mozilla/5.0"',
    '10.0.0.45 - - [09/Sep/2026:13:56:00 +0000] "POST /api/v1/checkout HTTP/1.1" 404 142 "-" "curl/7.88.1"',
    '172.16.0.88 - admin [09/Sep/2026:13:57:12 +0000] "DELETE /api/v1/cache HTTP/1.1" 500 521 "-" "PostmanRuntime/7.32.3"'
]

FIXTURES_PLAIN_TEXT = [
    '2026-09-09 12:00:01,123 [INFO] worker.main: Starting background reconciliation batch #841',
    '2026-09-09 12:01:45 [WARNING] [db-pool]: Connection pool at 88% capacity (44/50)',
    '2026-09-09 12:02:10,999 [CRITICAL] pipeline.runner: Unhandled exception during batch execution'
]

FIXTURES_MALFORMED = [
    '{"timestamp": "2026-09-09T10:15:30Z", "level": "INFO", "msg": "unclosed string',
    'corrupted byte stream 0xDEADBEEF \x00\x01\x02',
    '',
    '    \n   '
]

class TestIndependentLogParserFixtures(unittest.TestCase):
    def test_json_fixtures(self):
        for line in FIXTURES_JSON:
            data = json.loads(line)
            self.assertTrue("timestamp" in data or "time" in data)
            self.assertTrue("level" in data or "severity" in data)
            self.assertTrue("msg" in data or "message" in data)

    def test_nginx_fixtures(self):
        pattern = re.compile(
            r'^(?P<ip>\S+) \S+ (?P<user>\S+) \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d{3}) (?P<bytes>\d+)'
        )
        for line in FIXTURES_NGINX:
            match = pattern.match(line)
            self.assertIsNotNone(match)
            self.assertIn(int(match.group("status")), [200, 404, 500])

    def test_plain_text_fixtures(self):
        pattern = re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+(?:\[(?P<level_bracket>[A-Z]+)\]|(?P<level_bare>[A-Z]+))\s+(?:\[(?P<comp>[\w-]+)\]|(?P<mod>[\w\.]+)):\s+(?P<msg>.*)$'
        )
        for line in FIXTURES_PLAIN_TEXT:
            match = pattern.match(line)
            self.assertIsNotNone(match)

    def test_malformed_graceful_handling(self):
        for line in FIXTURES_MALFORMED:
            if line.strip().startswith('{'):
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    pass

if __name__ == "__main__":
    unittest.main()
