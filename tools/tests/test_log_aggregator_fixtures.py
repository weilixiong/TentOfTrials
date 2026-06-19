#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_line(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip()


class IndependentLogParserFixtureTests(unittest.TestCase):
    def test_json_fixture_extracts_expected_fields(self):
        entry = JSONLogParser().parse(fixture_line("log_aggregator_independent.jsonl"))

        self.assertEqual(1781869531, entry["timestamp"])
        self.assertEqual("warn", entry["level"])
        self.assertEqual("billing", entry["service"])
        self.assertEqual("json", entry["format"])
        self.assertEqual("inv_123", entry["fields"]["invoice_id"])

    def test_plain_text_fixture_extracts_timestamp_level_and_service(self):
        entry = TextLogParser().parse(fixture_line("log_aggregator_plain.log"))

        self.assertEqual(1781873131, entry["timestamp"])
        self.assertEqual("error", entry["level"])
        self.assertEqual("worker", entry["service"])
        self.assertEqual("text", entry["format"])
        self.assertIn("job_id=abc123", entry["message"])

    def test_nginx_fixture_extracts_access_log_fields(self):
        entry = NginxLogParser().parse(fixture_line("log_aggregator_nginx.log"))

        self.assertEqual(1781873160, entry["timestamp"])
        self.assertEqual("error", entry["level"])
        self.assertEqual("nginx", entry["service"])
        self.assertEqual("nginx", entry["format"])
        self.assertEqual("203.0.113.10", entry["fields"]["remote_addr"])
        self.assertEqual(503, entry["fields"]["status"])
        self.assertEqual("GET /api/orders?id=42 HTTP/1.1", entry["fields"]["request"])

    def test_aggregator_uses_nginx_parser_before_generic_text_parser(self):
        aggregator = LogAggregator()

        self.assertTrue(aggregator._parse_line(fixture_line("log_aggregator_nginx.log")))

        self.assertEqual("nginx", aggregator.entries[0]["format"])
        self.assertEqual({"nginx": 1}, dict(aggregator.service_counts))
        self.assertEqual({"error": 1}, dict(aggregator.level_counts))

    def test_malformed_specific_format_lines_do_not_crash(self):
        self.assertIsNone(JSONLogParser().parse("{not-json"))
        self.assertIsNone(NginxLogParser().parse("not an nginx access log line"))


if __name__ == "__main__":
    unittest.main()
