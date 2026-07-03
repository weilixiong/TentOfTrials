import unittest
from pathlib import Path

from tools.log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "log_parser_samples"


class IndependentLogParserFixtureTests(unittest.TestCase):
    def test_json_fixture_extracts_core_fields(self):
        parser = JSONLogParser()
        lines = (FIXTURE_DIR / "app.jsonl").read_text(encoding="utf-8").splitlines()

        first = parser.parse(lines[0])
        second = parser.parse(lines[1])

        self.assertEqual(first["timestamp"], "2026-06-18T09:15:02Z")
        self.assertEqual(first["level"], "ERROR")
        self.assertEqual(first["service"], "payments")
        self.assertEqual(first["format"], "json")
        self.assertEqual(first["fields"]["request_id"], "req_123")
        self.assertEqual(second["level"], "INFO")
        self.assertEqual(second["service"], "worker")
        self.assertEqual(second["message"], "job completed")

    def test_plain_text_fixture_extracts_timestamp_level_service(self):
        parser = TextLogParser()
        lines = (FIXTURE_DIR / "app.log").read_text(encoding="utf-8").splitlines()

        first = parser.parse(lines[0])
        second = parser.parse(lines[1])
        malformed = parser.parse(lines[2])

        self.assertEqual(first["timestamp"], 1781778030)
        self.assertEqual(first["level"], "info")
        self.assertEqual(first["service"], "api")
        self.assertEqual(first["format"], "text")
        self.assertEqual(second["level"], "warn")
        self.assertEqual(second["service"], "scheduler")
        self.assertIsNone(malformed["timestamp"])
        self.assertEqual(malformed["level"], "unknown")
        self.assertEqual(malformed["format"], "text")

    def test_nginx_fixture_extracts_access_log_fields_and_rejects_malformed_line(self):
        parser = NginxLogParser()
        lines = (FIXTURE_DIR / "access.log").read_text(encoding="utf-8").splitlines()

        ok = parser.parse(lines[0])
        error = parser.parse(lines[1])

        self.assertEqual(ok["timestamp"], 1781781753)
        self.assertEqual(ok["level"], "info")
        self.assertEqual(ok["service"], "nginx")
        self.assertEqual(ok["format"], "nginx")
        self.assertEqual(ok["fields"]["remote_addr"], "203.0.113.10")
        self.assertEqual(ok["fields"]["remote_user"], "alice")
        self.assertEqual(ok["fields"]["status"], 200)
        self.assertEqual(error["level"], "error")
        self.assertEqual(error["fields"]["status"], 502)
        self.assertIsNone(parser.parse(lines[2]))

    def test_aggregator_uses_specific_nginx_parser_before_text_fallback(self):
        aggregator = LogAggregator()
        count = aggregator.process_file(str(FIXTURE_DIR / "access.log"))

        self.assertEqual(count, 3)
        self.assertEqual(aggregator.entries[0]["format"], "nginx")
        self.assertEqual(aggregator.entries[1]["format"], "nginx")
        self.assertEqual(aggregator.entries[2]["format"], "text")
        self.assertEqual(aggregator.service_counts["nginx"], 2)
        self.assertEqual(aggregator.level_counts["error"], 1)


if __name__ == "__main__":
    unittest.main()
