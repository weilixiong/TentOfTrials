#!/usr/bin/env python3
"""Independent parser fixture tests for TentOfTrials log aggregator.

Run: python3 -m pytest tools/tests/test_parser_fixtures.py -v
 or: python3 tools/tests/test_parser_fixtures.py
"""
import os
import sys
import unittest

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser
from .fixtures_data import JSON_FIXTURES, TEXT_FIXTURES
from .nginx_fixtures import NGINX_FIXTURES, MALFORMED_FIXTURES


class TestJSONParserFixtures(unittest.TestCase):
    """Validate JSON log parser against hand-written fixtures."""

    def setUp(self):
        self.parser = JSONLogParser()

    def test_json_fixtures(self):
        for i, fixture in enumerate(JSON_FIXTURES):
            with self.subTest(i=i, line=fixture["line"][:60]):
                result = self.parser.parse(fixture["line"])
                self.assertIsNotNone(result, f"Parser returned None for: {fixture['line'][:80]}")
                expect = fixture["expect"]
                self.assertEqual(result["format"], expect["format"])
                self.assertEqual(result["level"], expect["level"])
                self.assertEqual(result["service"], expect["service"])
                if expect.get("ts_present"):
                    self.assertIsNotNone(result["timestamp"], "Timestamp should be present")
                if "field_check" in expect:
                    fields = result.get("fields", {})
                    for key, val in expect["field_check"].items():
                        self.assertEqual(fields.get(key), val, f"Field {key} mismatch")

    def test_json_timestamp_types(self):
        """Timestamp fields should be preserved from the JSON entry."""
        result = self.parser.parse(JSON_FIXTURES[0]["line"])
        self.assertIsNotNone(result)
        self.assertIsNotNone(result["timestamp"])


class TestTextParserFixtures(unittest.TestCase):
    """Validate text log parser against hand-written fixtures."""

    def setUp(self):
        self.parser = TextLogParser()

    def test_text_fixtures(self):
        for i, fixture in enumerate(TEXT_FIXTURES):
            with self.subTest(i=i, line=fixture["line"][:60]):
                result = self.parser.parse(fixture["line"])
                self.assertIsNotNone(result, f"Parser returned None for: {fixture['line'][:80]}")
                expect = fixture["expect"]
                self.assertEqual(result["format"], expect["format"])
                self.assertEqual(result["level"], expect["level"])
                if expect.get("service"):
                    self.assertEqual(result["service"], expect["service"])
                if expect.get("ts_present"):
                    self.assertIsNotNone(result["timestamp"], "Timestamp should be present")

    def test_text_empty_line(self):
        result = self.parser.parse("")
        self.assertIsNone(result, "Empty line should return None")

    def test_text_whitespace_only(self):
        result = self.parser.parse("   ")
        self.assertIsNone(result, "Whitespace-only line should return None")


class TestNginxParserFixtures(unittest.TestCase):
    """Validate nginx log parser against hand-written fixtures."""

    def setUp(self):
        self.parser = NginxLogParser()

    def test_nginx_fixtures(self):
        for i, fixture in enumerate(NGINX_FIXTURES):
            with self.subTest(i=i, line=fixture["line"][:60]):
                result = self.parser.parse(fixture["line"])
                self.assertIsNotNone(result, f"Parser returned None for: {fixture['line'][:80]}")
                expect = fixture["expect"]
                self.assertEqual(result["format"], expect["format"])
                self.assertEqual(result["level"], expect["level"])
                self.assertEqual(result["service"], expect["service"])
                if expect.get("ts_present"):
                    self.assertIsNotNone(result["timestamp"], "Timestamp should be present")
                if "field_check" in expect:
                    fields = result.get("fields", {})
                    for key, val in expect["field_check"].items():
                        self.assertEqual(fields.get(key), val, f"Field {key} mismatch")

    def test_nginx_status_level_mapping(self):
        """2xx=info, 3xx=info, 4xx=warn, 5xx=error."""
        cases = [
            ('10.0.0.1 - - [15/Mar/2024:10:00:00 +0000] "GET / HTTP/1.1" 200 100 "-" "-"', "info"),
            ('10.0.0.1 - - [15/Mar/2024:10:00:00 +0000] "GET / HTTP/1.1" 301 0 "-" "-"', "info"),
            ('10.0.0.1 - - [15/Mar/2024:10:00:00 +0000] "GET / HTTP/1.1" 404 0 "-" "-"', "warn"),
            ('10.0.0.1 - - [15/Mar/2024:10:00:00 +0000] "GET / HTTP/1.1" 503 0 "-" "-"', "error"),
        ]
        for line, expected_level in cases:
            result = self.parser.parse(line)
            self.assertIsNotNone(result)
            self.assertEqual(result["level"], expected_level)


class TestMalformedLines(unittest.TestCase):
    """Malformed/unsupported lines should not crash any parser."""

    def test_malformed_json(self):
        parser = JSONLogParser()
        for line in MALFORMED_FIXTURES:
            try:
                result = parser.parse(line)
                # It's fine if it returns None or a partial result
            except Exception as e:
                self.fail(f"JSON parser crashed on malformed line: {e}")

    def test_malformed_text(self):
        parser = TextLogParser()
        for line in MALFORMED_FIXTURES:
            try:
                result = parser.parse(line)
            except Exception as e:
                self.fail(f"Text parser crashed on malformed line: {e}")

    def test_malformed_nginx(self):
        parser = NginxLogParser()
        for line in MALFORMED_FIXTURES:
            try:
                result = parser.parse(line)
            except Exception as e:
                self.fail(f"Nginx parser crashed on malformed line: {e}")


class TestFileFixtures(unittest.TestCase):
    """Validate parsers against fixture files on disk."""

    def setUp(self):
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")

    def _load_fixture(self, name):
        path = os.path.join(self.fixtures_dir, name)
        with open(path) as f:
            return [line.rstrip("\n") for line in f if line.strip()]

    def test_json_fixture_file(self):
        parser = JSONLogParser()
        lines = self._load_fixture("json_logs.jsonl")
        parsed = 0
        for line in lines:
            result = parser.parse(line)
            if result is not None:
                parsed += 1
        self.assertGreater(parsed, 0, "No lines parsed from json fixture")
        self.assertEqual(parsed, len(lines), "Not all JSON lines parsed")

    def test_text_fixture_file(self):
        parser = TextLogParser()
        lines = self._load_fixture("text_logs.txt")
        parsed = 0
        for line in lines:
            result = parser.parse(line)
            if result is not None:
                parsed += 1
        self.assertGreater(parsed, 0, "No lines parsed from text fixture")

    def test_nginx_fixture_file(self):
        parser = NginxLogParser()
        lines = self._load_fixture("nginx_logs.txt")
        parsed = 0
        for line in lines:
            result = parser.parse(line)
            if result is not None:
                parsed += 1
        self.assertGreater(parsed, 0, "No lines parsed from nginx fixture")
        self.assertEqual(parsed, len(lines), "Not all nginx lines parsed")

    def test_malformed_fixture_file(self):
        """Malformed fixtures should not crash any parser."""
        lines = self._load_fixture("malformed_logs.txt")
        for ParserClass in [JSONLogParser, TextLogParser, NginxLogParser]:
            parser = ParserClass()
            for line in lines:
                try:
                    parser.parse(line)
                except Exception as e:
                    self.fail(f"{ParserClass.__name__} crashed on malformed fixture: {e}")


class TestAggregatorIntegration(unittest.TestCase):
    """Quick integration test: run aggregator on fixture files."""

    def test_aggregator_processes_fixtures(self):
        from log_aggregator import LogAggregator
        agg = LogAggregator()
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        total = 0
        for name in ["json_logs.jsonl", "text_logs.txt", "nginx_logs.txt"]:
            path = os.path.join(fixtures_dir, name)
            count = agg.process_file(path)
            total += count
        self.assertGreater(total, 0, "Aggregator parsed no entries from fixtures")
        self.assertGreater(len(agg.entries), 0, "Aggregator has no entries")


if __name__ == "__main__":
    unittest.main()
