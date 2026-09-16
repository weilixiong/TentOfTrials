#!/usr/bin/env python3
"""
Unit tests verifying log parsers against independent, hand-written fixtures.
Covers JSON, plain text, Nginx access logs, and malformed lines.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.log_aggregator import JSONLogParser, TextLogParser, NginxLogParser, LogAggregator
from tools.fixtures.log_fixtures import (
    JSON_FIXTURES,
    TEXT_FIXTURES,
    NGINX_FIXTURES,
    MALFORMED_FIXTURES,
)


class TestIndependentLogParserFixtures(unittest.TestCase):
    def setUp(self):
        self.json_parser = JSONLogParser()
        self.text_parser = TextLogParser()
        self.nginx_parser = NginxLogParser()
        self.aggregator = LogAggregator()

    def test_json_fixtures(self):
        for fixture in JSON_FIXTURES:
            entry = self.json_parser.parse(fixture["raw"])
            self.assertIsNotNone(entry, f"Failed to parse JSON line: {fixture['raw']}")
            self.assertEqual(entry["format"], fixture["expected_format"])
            self.assertEqual(entry["service"], fixture["expected_service"])
            self.assertEqual(entry["level"], fixture["expected_level"])
            self.assertEqual(entry["message"], fixture["expected_message"])

    def test_text_fixtures(self):
        for fixture in TEXT_FIXTURES:
            entry = self.text_parser.parse(fixture["raw"])
            self.assertIsNotNone(entry, f"Failed to parse Text line: {fixture['raw']}")
            self.assertEqual(entry["format"], fixture["expected_format"])
            self.assertEqual(entry["service"], fixture["expected_service"])
            self.assertEqual(entry["level"], fixture["expected_level"])

    def test_nginx_fixtures(self):
        for fixture in NGINX_FIXTURES:
            entry = self.nginx_parser.parse(fixture["raw"])
            self.assertIsNotNone(entry, f"Failed to parse Nginx line: {fixture['raw']}")
            self.assertEqual(entry["format"], fixture["expected_format"])
            self.assertEqual(entry["service"], fixture["expected_service"])
            self.assertEqual(entry["level"], fixture["expected_level"])
            self.assertEqual(entry["fields"]["status"], fixture["expected_status"])
            self.assertEqual(entry["fields"]["request"], fixture["expected_request"])

    def test_malformed_lines_do_not_crash(self):
        for line in MALFORMED_FIXTURES:
            # None of the parsers should raise an exception on malformed inputs
            try:
                res_json = self.json_parser.parse(line)
                res_nginx = self.nginx_parser.parse(line)
                res_text = self.text_parser.parse(line)
                # aggregator parse line
                self.aggregator._parse_line(line)
            except Exception as e:
                self.fail(f"Parser raised unexpected exception on malformed line '{line}': {e}")

    def test_aggregator_end_to_end_with_fixtures(self):
        agg = LogAggregator()
        all_lines = (
            [f["raw"] for f in JSON_FIXTURES]
            + [f["raw"] for f in TEXT_FIXTURES]
            + [f["raw"] for f in NGINX_FIXTURES]
        )
        for line in all_lines:
            success = agg._parse_line(line)
            self.assertTrue(success, f"Expected aggregator to parse line: {line}")

        self.assertGreater(len(agg.entries), 0)
        self.assertGreater(len(agg.level_counts), 0)
        self.assertGreater(len(agg.service_counts), 0)


if __name__ == "__main__":
    unittest.main()
