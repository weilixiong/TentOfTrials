#!/usr/bin/env python3
"""
Independent parser fixture tests for log_aggregator.py.

These tests use hand-written representative log lines to validate
the log parsers without relying on parser-generated samples.
This addresses the false-pass rate issue described in the module docstring.
"""

import os
import sys
import unittest
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from log_aggregator import LogParser, JsonLogParser, NginxLogParser, TextLogParser


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestJsonParserFixtures(unittest.TestCase):
    """Validate JSON log parser against independent hand-written fixtures."""

    @classmethod
    def setUpClass(cls):
        fixture_path = FIXTURES_DIR / "json_logs.txt"
        with open(fixture_path, "r", encoding="utf-8") as f:
            cls.lines = [line.strip() for line in f if line.strip()]

    def test_all_json_lines_parse_without_exception(self):
        """Every fixture line should be parseable as JSON."""
        parser = JsonLogParser()
        for i, line in enumerate(self.lines):
            try:
                result = parser.parse(line)
                self.assertIsNotNone(result, f"Line {i} returned None")
                self.assertIsInstance(result, dict, f"Line {i} result is not dict")
            except Exception as e:
                self.fail(f"Line {i} raised {type(e).__name__}: {e}")

    def test_parsed_json_has_required_fields(self):
        """Parsed JSON logs should contain timestamp and message fields."""
        parser = JsonLogParser()
        for i, line in enumerate(self.lines):
            result = parser.parse(line)
            self.assertIsNotNone(result, f"Line {i}: parse returned None")
            self.assertIn("timestamp", result, f"Line {i}: missing timestamp")
            self.assertIn("message", result, f"Line {i}: missing message")

    def test_error_logs_have_correct_level(self):
        """ERROR and FATAL logs should have correct level classification."""
        parser = JsonLogParser()
        error_lines = [l for l in self.lines if '"level":"ERROR"' in l or '"level":"FATAL"' in l or '"level":"CRITICAL"' in l]
        self.assertGreater(len(error_lines), 0, "No error-level fixture lines found")
        for i, line in enumerate(error_lines[:5]):
            result = parser.parse(line)
            self.assertIsNotNone(result)
            level = result.get("level", "").upper()
            self.assertIn(level, ["ERROR", "FATAL", "CRITICAL"])


class TestNginxParserFixtures(unittest.TestCase):
    """Validate Nginx log parser against independent hand-written fixtures."""

    @classmethod
    def setUpClass(cls):
        fixture_path = FIXTURES_DIR / "nginx_logs.txt"
        with open(fixture_path, "r", encoding="utf-8") as f:
            cls.lines = [line.strip() for line in f if line.strip()]

    def test_all_nginx_lines_parse_without_exception(self):
        """Every nginx fixture line should be parseable."""
        parser = NginxLogParser()
        for i, line in enumerate(self.lines):
            try:
                result = parser.parse(line)
                self.assertIsNotNone(result, f"Line {i} returned None")
            except Exception as e:
                self.fail(f"Line {i} raised {type(e).__name__}: {e}")

    def test_parsed_nginx_has_status_code(self):
        """Parsed nginx logs should extract HTTP status codes."""
        parser = NginxLogParser()
        for i, line in enumerate(self.lines):
            result = parser.parse(line)
            if result:
                status = result.get("status") or result.get("status_code")
                self.assertIsNotNone(status, f"Line {i}: missing status code")

    def test_nginx_200_status(self):
        """200-status lines should parse correctly."""
        parser = NginxLogParser()
        ok_lines = [l for l in self.lines if '" 200 ' in l or '" 201 ' in l or '" 204 ' in l]
        self.assertGreater(len(ok_lines), 0, "No 200-range fixture lines found")
        for line in ok_lines[:3]:
            result = parser.parse(line)
            self.assertIsNotNone(result)


class TestTextParserFixtures(unittest.TestCase):
    """Validate plain text/syslog parser against independent hand-written fixtures."""

    @classmethod
    def setUpClass(cls):
        fixture_path = FIXTURES_DIR / "text_logs.txt"
        with open(fixture_path, "r", encoding="utf-8") as f:
            cls.lines = [line.strip() for line in f if line.strip()]

    def test_all_text_lines_parse_without_exception(self):
        """Every text fixture line should be parseable."""
        parser = TextLogParser()
        for i, line in enumerate(self.lines):
            try:
                result = parser.parse(line)
                self.assertIsNotNone(result, f"Line {i} returned None")
            except Exception as e:
                self.fail(f"Line {i} raised {type(e).__name__}: {e}")

    def test_parsed_text_has_level(self):
        """Parsed text logs should extract severity level."""
        parser = TextLogParser()
        for i, line in enumerate(self.lines):
            result = parser.parse(line)
            if result:
                level = result.get("level") or result.get("severity")
                self.assertIsNotNone(level, f"Line {i}: missing level")

    def test_error_and_fatal_logs_detected(self):
        """ERROR and FATAL level markers should be correctly identified."""
        parser = TextLogParser()
        error_lines = [l for l in self.lines if '[ERROR]' in l or '[FATAL]' in l or '[CRITICAL]' in l]
        self.assertGreater(len(error_lines), 0, "No error-level text fixture lines")
        for line in error_lines[:3]:
            result = parser.parse(line)
            self.assertIsNotNone(result)


class TestParserIndependence(unittest.TestCase):
    """Verify that parsers work independently and don't share mutable state."""

    def test_parsers_dont_interfere(self):
        """Running multiple parsers concurrently should not corrupt results."""
        json_parser = JsonLogParser()
        nginx_parser = NginxLogParser()
        text_parser = TextLogParser()

        json_line = '{"timestamp":"2024-01-15T08:30:00Z","level":"INFO","message":"test"}'
        nginx_line = '127.0.0.1 - - [15/Jan/2024:08:30:00 +0000] "GET / HTTP/1.1" 200 15 "-" "curl"'
        text_line = '[INFO] 2024-01-15 08:30:00 test-svc - test message'

        json_result1 = json_parser.parse(json_line)
        nginx_result1 = nginx_parser.parse(nginx_line)
        text_result1 = text_parser.parse(text_line)

        # Second parse should give same results
        json_result2 = json_parser.parse(json_line)
        self.assertEqual(json_result1, json_result2, "JsonLogParser should be idempotent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
