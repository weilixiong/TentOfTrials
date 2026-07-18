#!/usr/bin/env python3
"""Independent parser fixtures for the legacy log aggregator.

The fixture lines in tests/fixtures/log_aggregator/independent_parser_lines.log
are hand-written representative examples. They are intentionally not generated
from tools.log_aggregator so parser regressions cannot false-pass by sharing the
same fixture-generation logic as the production parser.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "log_aggregator" / "independent_parser_lines.log"


class IndependentLogParserFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = FIXTURE_PATH.read_text(encoding="utf-8").splitlines()

    def test_json_fixture_validates_core_fields(self) -> None:
        parsed = JSONLogParser().parse(self.lines[0])

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["timestamp"], 1717228800)
        self.assertEqual(parsed["level"], "ERROR")
        self.assertEqual(parsed["service"], "billing-api")
        self.assertEqual(parsed["format"], "json")
        self.assertEqual(parsed["fields"]["request_id"], "req-json-001")
        self.assertEqual(parsed["fields"]["amount_cents"], 1299)

    def test_plain_text_fixture_validates_timestamp_level_service_and_raw_fields(self) -> None:
        parsed = TextLogParser().parse(self.lines[1])

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["timestamp"], 1717243262)
        self.assertEqual(parsed["level"], "warn")
        self.assertEqual(parsed["service"], "worker")
        self.assertEqual(parsed["format"], "text")
        self.assertIn("job_id=job-42", parsed["fields"]["raw"])
        self.assertIn("queue=emails", parsed["message"])

    def test_nginx_fixture_validates_access_log_fields(self) -> None:
        parsed = NginxLogParser().parse(self.lines[2])

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["timestamp"], 1717243323)
        self.assertEqual(parsed["level"], "info")
        self.assertEqual(parsed["service"], "nginx")
        self.assertEqual(parsed["format"], "nginx")
        self.assertEqual(parsed["fields"]["remote_addr"], "203.0.113.10")
        self.assertEqual(parsed["fields"]["request"], "GET /health HTTP/1.1")
        self.assertEqual(parsed["fields"]["status"], 200)
        self.assertEqual(parsed["fields"]["body_bytes"], "123")

    def test_malformed_fixture_does_not_crash_or_create_structured_fields(self) -> None:
        self.assertIsNone(JSONLogParser().parse(self.lines[3]))
        self.assertIsNone(NginxLogParser().parse(self.lines[3]))

        parsed = TextLogParser().parse(self.lines[3])
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertIsNone(parsed["timestamp"])
        self.assertEqual(parsed["level"], "unknown")
        self.assertIsNone(parsed["service"])
        self.assertEqual(parsed["format"], "text")

    def test_aggregator_uses_specific_parsers_before_text_fallback(self) -> None:
        aggregator = LogAggregator()
        parsed_count = aggregator.process_file(str(FIXTURE_PATH))

        self.assertEqual(parsed_count, 4)
        self.assertEqual([entry["format"] for entry in aggregator.entries], ["json", "text", "nginx", "text"])
        self.assertEqual(aggregator.entries[2]["service"], "nginx")
        self.assertEqual(aggregator.entries[2]["fields"]["status"], 200)
        self.assertEqual(aggregator.level_counts["error"], 1)
        self.assertEqual(aggregator.level_counts["warn"], 1)
        self.assertEqual(aggregator.level_counts["info"], 1)
        self.assertEqual(aggregator.level_counts["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
