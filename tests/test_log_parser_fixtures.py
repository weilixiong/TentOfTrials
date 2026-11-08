#!/usr/bin/env python3
"""
Unit tests and independent log parser fixtures for tools/log_aggregator.py.

Validates JSONLogParser, TextLogParser, and NginxLogParser against independent,
hand-written fixture log lines without relying on parser-generated samples.
Verifies timestamp, level, service/format, key fields, malformed lines,
parser precedence, and CLI compatibility.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from log_aggregator import (
    JSONLogParser,
    TextLogParser,
    NginxLogParser,
    LogAggregator,
    parse_args,
)


class TestJSONLogParserFixtures(unittest.TestCase):
    """Independent fixture tests for JSONLogParser."""

    def setUp(self):
        self.parser = JSONLogParser()

    def test_independent_json_fixture_standard(self):
        """Test parsing standard JSON log line with epoch timestamp."""
        line = '{"timestamp": 1705329121, "level": "ERROR", "service": "auth-service", "message": "Failed login attempt for user admin", "user_id": 42}'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["timestamp"], 1705329121)
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["service"], "auth-service")
        self.assertEqual(entry["message"], "Failed login attempt for user admin")
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["fields"]["user_id"], 42)

    def test_independent_json_fixture_iso_timestamp(self):
        """Test parsing JSON log line with ISO-8601 string timestamp normalized to epoch."""
        line = '{"time": "2024-01-15T14:32:01Z", "severity": "WARN", "logger": "payment-service", "msg": "Payment gateway response delayed", "latency_ms": 3500}'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        # 2024-01-15T14:32:01Z -> 1705329121
        self.assertEqual(entry["timestamp"], 1705329121)
        self.assertEqual(entry["level"], "WARN")
        self.assertEqual(entry["service"], "payment-service")
        self.assertEqual(entry["message"], "Payment gateway response delayed")
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["fields"]["latency_ms"], 3500)

    def test_independent_json_fixture_alternate_field_keys(self):
        """Test alternate JSON keys: @timestamp, lvl, app, event."""
        line = '{"@timestamp": 1705329121, "lvl": "INFO", "app": "api-gateway", "event": "Route dispatched successfully", "path": "/api/v1/orders"}'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["timestamp"], 1705329121)
        self.assertEqual(entry["level"], "INFO")
        self.assertEqual(entry["service"], "api-gateway")
        self.assertEqual(entry["message"], "Route dispatched successfully")
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["fields"]["path"], "/api/v1/orders")

    def test_independent_json_fixture_debug_level(self):
        """Test debug severity level in JSON log line."""
        line = '{"timestamp": 1705329121, "level": "DEBUG", "service": "cache-service", "message": "Cache key invalidated", "key": "session:xyz"}'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "DEBUG")
        self.assertEqual(entry["service"], "cache-service")
        self.assertEqual(entry["format"], "json")

    def test_independent_json_fixture_malformed_syntax(self):
        """Test truncated/invalid JSON string does not crash and returns None."""
        malformed_lines = [
            '{"timestamp": 1705329121, "level": "ERROR", "message": ',
            '{invalid json}',
            '{"unclosed string',
            '{"timestamp": }',
        ]
        for line in malformed_lines:
            with self.subTest(line=line):
                result = self.parser.parse(line)
                self.assertIsNone(result)

    def test_independent_json_fixture_non_dict_json(self):
        """Test valid JSON that is not an object/dict returns None without crashing."""
        non_dict_lines = [
            '["item1", "item2"]',
            '"just a string"',
            '12345',
            'true',
            'null',
        ]
        for line in non_dict_lines:
            with self.subTest(line=line):
                result = self.parser.parse(line)
                self.assertIsNone(result)

    def test_independent_json_fixture_empty_and_whitespace(self):
        """Test empty string and whitespace lines return None."""
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse("   \n\t  "))


class TestTextLogParserFixtures(unittest.TestCase):
    """Independent fixture tests for TextLogParser."""

    def setUp(self):
        self.parser = TextLogParser()

    def test_independent_text_fixture_standard_format(self):
        """Test plain text log line with standard date-time and bracketed service."""
        line = "2024-01-15 14:32:01 [auth] ERROR: Authentication failed for user root"
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        dt = datetime(2024, 1, 15, 14, 32, 1, tzinfo=timezone.utc)
        self.assertEqual(entry["timestamp"], int(dt.timestamp()))
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["service"], "auth")
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["message"], line)
        self.assertEqual(entry["fields"]["raw"], line)

    def test_independent_text_fixture_iso8601_format(self):
        """Test plain text log line with ISO-8601 timestamp."""
        line = "2024-01-15T14:32:01 [database] WARN: Connection pool utilization above 85%"
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        dt = datetime(2024, 1, 15, 14, 32, 1, tzinfo=timezone.utc)
        self.assertEqual(entry["timestamp"], int(dt.timestamp()))
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "database")
        self.assertEqual(entry["format"], "text")

    def test_independent_text_fixture_syslog_format(self):
        """Test plain text log line with syslog timestamp format."""
        line = "Jan 15 14:32:01 [billing] INFO: Invoice generation completed"
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry["timestamp"])
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["service"], "billing")
        self.assertEqual(entry["format"], "text")

    def test_independent_text_fixture_colon_service_prefix(self):
        """Test uppercase service prefix followed by colon (e.g. AUTH: message)."""
        line = "AUTH: 2024-01-15 14:32:01 CRITICAL: System shutdown initiated"
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["service"], "AUTH")
        self.assertEqual(entry["level"], "error")

    def test_independent_text_fixture_levels(self):
        """Test recognition of various log levels (FATAL, WARNING, NOTICE, DEBUG, TRACE)."""
        level_map = [
            ("2024-01-15 14:32:01 [srv] FATAL: crash", "error"),
            ("2024-01-15 14:32:01 [srv] WARNING: disk low", "warn"),
            ("2024-01-15 14:32:01 [srv] NOTICE: reboot", "info"),
            ("2024-01-15 14:32:01 [srv] DEBUG: memory allocation dump", "debug"),
            ("2024-01-15 14:32:01 [srv] TRACE: packet payload", "debug"),
        ]
        for line, expected_level in level_map:
            with self.subTest(line=line):
                entry = self.parser.parse(line)
                self.assertIsNotNone(entry)
                self.assertEqual(entry["level"], expected_level)

    def test_independent_text_fixture_unstructured_line(self):
        """Test unstructured/malformed plain text does not crash and returns graceful entry."""
        unstructured = "random gibberish without timestamp or level anywhere in this string"
        entry = self.parser.parse(unstructured)
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["timestamp"])
        self.assertEqual(entry["level"], "unknown")
        self.assertIsNone(entry["service"])
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["message"], unstructured)

    def test_independent_text_fixture_empty_line(self):
        """Test empty line returns None."""
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse("   \n  "))


class TestNginxLogParserFixtures(unittest.TestCase):
    """Independent fixture tests for NginxLogParser."""

    def setUp(self):
        self.parser = NginxLogParser()

    def test_independent_nginx_fixture_200_ok(self):
        """Test parsing standard Nginx 200 OK access log line."""
        line = '192.168.1.100 - - [15/Jan/2024:14:32:01 +0000] "GET /index.html HTTP/1.1" 200 1024 "https://example.com" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        dt = datetime(2024, 1, 15, 14, 32, 1, tzinfo=timezone.utc)
        self.assertEqual(entry["timestamp"], int(dt.timestamp()))
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["service"], "nginx")
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["message"], "GET /index.html HTTP/1.1")
        self.assertEqual(entry["fields"]["remote_addr"], "192.168.1.100")
        self.assertEqual(entry["fields"]["status"], 200)
        self.assertEqual(entry["fields"]["body_bytes"], "1024")
        self.assertEqual(entry["fields"]["referer"], "https://example.com")
        self.assertIn("Mozilla/5.0", entry["fields"]["user_agent"])

    def test_independent_nginx_fixture_404_warn(self):
        """Test 4xx status code maps to warn level."""
        line = '192.168.1.101 - - [15/Jan/2024:14:32:01 +0000] "GET /missing.png HTTP/1.1" 404 256 "-" "curl/7.88.1"'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["fields"]["status"], 404)
        self.assertEqual(entry["fields"]["remote_addr"], "192.168.1.101")

    def test_independent_nginx_fixture_500_error(self):
        """Test 500 status code maps to error level."""
        line = '192.168.1.102 - - [15/Jan/2024:14:32:01 +0000] "POST /api/v1/checkout HTTP/1.1" 500 512 "https://example.com/cart" "Mozilla/5.0"'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["fields"]["status"], 500)
        self.assertEqual(entry["fields"]["request"], "POST /api/v1/checkout HTTP/1.1")

    def test_independent_nginx_fixture_503_error(self):
        """Test 503 status code maps to error level."""
        line = '192.168.1.103 - - [15/Jan/2024:14:32:01 +0000] "GET /healthz HTTP/1.1" 503 128 "-" "Kube-Probe/1.28"'
        entry = self.parser.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["fields"]["status"], 503)

    def test_independent_nginx_fixture_malformed_syntax(self):
        """Test incomplete or malformed Nginx access line returns None without crashing."""
        malformed_lines = [
            '192.168.1.100 - - [15/Jan/2024:14:32:01 +0000] "GET /incomplete',
            '192.168.1.100 missing fields',
            'not an nginx log line at all',
            '192.168.1.1 - - [bad] "GET /" abc def',
            '',
        ]
        for line in malformed_lines:
            with self.subTest(line=line):
                result = self.parser.parse(line)
                self.assertIsNone(result)


class TestLogAggregatorIntegration(unittest.TestCase):
    """Integration and precedence tests for LogAggregator."""

    def setUp(self):
        self.aggregator = LogAggregator()

    def test_parser_precedence_nginx_not_swallowed_by_text(self):
        """Verify Nginx log line is routed to NginxLogParser, not TextLogParser."""
        line = '192.168.1.100 - - [15/Jan/2024:14:32:01 +0000] "GET /index.html HTTP/1.1" 200 1024 "-" "curl/7.68.0"'
        matched = self.aggregator._parse_line(line)
        self.assertTrue(matched)
        self.assertEqual(len(self.aggregator.entries), 1)
        entry = self.aggregator.entries[0]
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["service"], "nginx")
        self.assertEqual(entry["fields"]["status"], 200)

    def test_parser_precedence_json(self):
        """Verify JSON log line is routed to JSONLogParser."""
        line = '{"timestamp": 1705329121, "level": "INFO", "service": "auth", "message": "hello"}'
        matched = self.aggregator._parse_line(line)
        self.assertTrue(matched)
        entry = self.aggregator.entries[0]
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["service"], "auth")

    def test_parser_precedence_text(self):
        """Verify plain text log line is routed to TextLogParser."""
        line = "2024-01-15 14:32:01 [auth] ERROR: connection refused"
        matched = self.aggregator._parse_line(line)
        self.assertTrue(matched)
        entry = self.aggregator.entries[0]
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["service"], "auth")

    def test_aggregator_summary_and_error_rate(self):
        """Verify aggregation counts, error rate, hourly counts, and time range."""
        lines = [
            '{"timestamp": 1705329121, "level": "ERROR", "service": "auth", "message": "bad pwd"}',
            '{"timestamp": 1705329125, "level": "INFO", "service": "auth", "message": "logged in"}',
            '2024-01-15 14:32:10 [worker] WARN: slow response',
            '192.168.1.1 - - [15/Jan/2024:14:32:15 +0000] "GET /api HTTP/1.1" 500 100 "-" "test"',
        ]
        for line in lines:
            self.aggregator._parse_line(line)

        summary = self.aggregator.get_summary()
        self.assertEqual(summary["total_entries"], 4)
        self.assertEqual(summary["by_level"].get("error"), 2)
        self.assertEqual(summary["by_level"].get("info"), 1)
        self.assertEqual(summary["by_level"].get("warn"), 1)
        self.assertEqual(summary["error_rate"], 50.0)
        self.assertIsNotNone(summary["time_range"])

    def test_process_fixture_files(self):
        """Process disk fixture files and verify aggregated counts."""
        fixture_files = [
            FIXTURES_DIR / "json_logs.log",
            FIXTURES_DIR / "text_logs.log",
            FIXTURES_DIR / "nginx_logs.log",
            FIXTURES_DIR / "malformed_logs.log",
        ]
        for path in fixture_files:
            if path.exists():
                count = self.aggregator.process_file(str(path))
                self.assertGreaterEqual(count, 0)

        self.assertGreater(len(self.aggregator.entries), 0)
        summary = self.aggregator.get_summary()
        self.assertIn("by_level", summary)
        self.assertIn("by_service", summary)

    def test_search_and_export(self):
        """Test search, export_json, export_csv, and html report generation."""
        line = '{"timestamp": 1705329121, "level": "ERROR", "service": "auth", "message": "unique_needle_token"}'
        self.aggregator._parse_line(line)

        results = self.aggregator.search("unique_needle_token")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["message"], "unique_needle_token")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "out.json")
            csv_path = os.path.join(tmpdir, "out.csv")
            html_path = os.path.join(tmpdir, "out.html")

            self.aggregator.export_json(json_path)
            self.assertTrue(os.path.exists(json_path))
            with open(json_path, "r") as f:
                data = json.load(f)
                self.assertEqual(data["summary"]["total_entries"], 1)

            self.aggregator.export_csv(csv_path)
            self.assertTrue(os.path.exists(csv_path))

            self.aggregator.generate_html_report(html_path)
            self.assertTrue(os.path.exists(html_path))


class TestLogAggregatorCLICompatibility(unittest.TestCase):
    """Verify existing log aggregation CLI behavior remains compatible."""

    def test_cli_help_flag(self):
        """Verify python3 log_aggregator.py --help executes successfully."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "log_aggregator.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--input", result.stdout)
        self.assertIn("--format", result.stdout)
        self.assertIn("--search", result.stdout)

    def test_cli_execution_with_fixture_input(self):
        """Verify executing log_aggregator.py CLI against fixture file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "report.json")
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS_DIR / "log_aggregator.py"),
                    "--input",
                    str(FIXTURES_DIR / "json_logs.log"),
                    "--output",
                    out_file,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "r") as f:
                report = json.load(f)
                self.assertIn("summary", report)
                self.assertEqual(report["summary"]["total_entries"], 4)


if __name__ == "__main__":
    unittest.main()
