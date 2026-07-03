import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "log_aggregator"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8").strip()


class LogAggregatorFixtureTests(unittest.TestCase):
    def test_json_fixture_parses_core_fields(self):
        entry = JSONLogParser().parse(read_fixture("json.log"))

        self.assertIsNotNone(entry)
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["timestamp"], "2024-05-17T12:34:56Z")
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["service"], "payments")
        self.assertEqual(entry["message"], "charge settlement failed")
        self.assertEqual(entry["fields"]["request_id"], "req-7f2")

    def test_text_fixture_parses_timestamp_level_and_service(self):
        entry = TextLogParser().parse(read_fixture("text.log"))

        self.assertIsNotNone(entry)
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["timestamp"], 1715949301)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "scheduler")
        self.assertIn("retrying delayed payout job", entry["message"])

    def test_nginx_fixture_parses_key_fields(self):
        entry = NginxLogParser().parse(read_fixture("nginx.log"))

        self.assertIsNotNone(entry)
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["timestamp"], 1715949362)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["service"], "nginx")
        self.assertEqual(entry["message"], "GET /api/trials/42 HTTP/1.1")
        self.assertEqual(entry["fields"]["remote_addr"], "203.0.113.24")
        self.assertEqual(entry["fields"]["remote_user"], "frank")
        self.assertEqual(entry["fields"]["status"], 502)
        self.assertEqual(entry["fields"]["body_bytes"], "512")

    def test_malformed_fixture_does_not_crash_aggregator(self):
        aggregator = LogAggregator()

        self.assertTrue(aggregator._parse_line(read_fixture("malformed.log")))
        self.assertEqual(aggregator.entries[0]["format"], "text")
        self.assertEqual(aggregator.entries[0]["level"], "unknown")

    def test_aggregator_routes_nginx_before_plain_text_fallback(self):
        aggregator = LogAggregator()

        self.assertTrue(aggregator._parse_line(read_fixture("nginx.log")))
        self.assertEqual(aggregator.entries[0]["format"], "nginx")
        self.assertEqual(aggregator.level_counts["error"], 1)
        self.assertEqual(aggregator.service_counts["nginx"], 1)


if __name__ == "__main__":
    unittest.main()
