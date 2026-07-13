#!/usr/bin/env python3
"""
Independent parser fixture tests for log_aggregator.py.

These fixtures are HAND-WRITTEN representative log lines — NOT generated
by the same parser code they test. This eliminates the false-pass problem
described in the issue where test data was derived from parser output,
masking regressions when real log formats drift.

Fixture sources:
  - JSON: modeled after real structured-logging output (Datadog/Elastic common formats)
  - Text: modeled after syslog, Python logging, and application log conventions
  - Nginx: modeled after real nginx combined log format access logs
  - Malformed: edge cases that should not crash the parser

Each test validates: timestamp extraction, level detection, service/format,
and key format-specific fields.
"""

import json
import sys
import unittest
from pathlib import Path

# Add tools/ to path so we can import log_aggregator
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser, LogAggregator


# =============================================================================
# INDEPENDENT HAND-WRITTEN FIXTURES
# =============================================================================

# --- JSON log fixtures ---
# These represent real structured JSON log output from services like Datadog
# Agent, Elastic Filebeat, and container runtimes.
JSON_FIXTURES = [
    # 1. Standard JSON log with all fields
    {
        "line": json.dumps({
            "timestamp": "2024-03-15T08:30:45.123Z",
            "level": "ERROR",
            "service": "api-gateway",
            "message": "Connection timeout after 30s to upstream: database-primary",
            "trace_id": "abc123def456",
            "duration_ms": 30125
        }),
        "expected_level": "error",
        "expected_service": "api-gateway",
        "expected_format": "json",
        "expected_message_contains": "Connection timeout",
    },
    # 2. JSON log with 'severity' instead of 'level'
    {
        "line": json.dumps({
            "time": "2024-03-15T09:00:00.000Z",
            "severity": "WARN",
            "logger": "auth-service",
            "msg": "Rate limit approaching: 85/100 requests per minute",
        }),
        "expected_level": "warn",
        "expected_service": "auth-service",
        "expected_format": "json",
        "expected_message_contains": "Rate limit",
    },
    # 3. JSON log with nested fields (@timestamp, lvl)
    {
        "line": json.dumps({
            "@timestamp": "2024-03-15T10:15:30.000Z",
            "lvl": "INFO",
            "app": "scheduler",
            "event": "Cron job 'cleanup-temp-files' completed successfully in 2.3s",
            "metadata": {"job_id": 42, "rows_cleaned": 1500}
        }),
        "expected_level": "info",
        "expected_service": "scheduler",
        "expected_format": "json",
        "expected_message_contains": "cleanup-temp-files",
    },
    # 4. JSON log with minimal fields (just message)
    {
        "line": json.dumps({
            "message": "Heartbeat OK"
        }),
        "expected_level": "info",  # default when no level field
        "expected_service": None,
        "expected_format": "json",
        "expected_message_contains": "Heartbeat",
    },
]

# --- Plain text log fixtures ---
# These represent common plain-text log formats from syslog, Python logging,
# and application-specific logging conventions.
TEXT_FIXTURES = [
    # 1. Syslog-style with timestamp, level, service in brackets
    {
        "line": "2024-03-15 08:30:45 [worker-3] ERROR: Task queue overflow — 5000 pending jobs",
        "expected_level": "error",
        "expected_service": "worker-3",
        "expected_format": "text",
        "expected_message_contains": "Task queue overflow",
    },
    # 2. Standard Python logging output
    {
        "line": "2024-03-15T09:01:00 WARNING [cache] Memory usage at 92% — triggering eviction",
        "expected_level": "warn",
        "expected_service": "cache",
        "expected_format": "text",
        "expected_message_contains": "Memory usage",
    },
    # 3. INFO-level log with ISO timestamp
    {
        "line": "2024-03-15T10:00:00 INFO [db-migrator] Migration v42 applied in 1.2s",
        "expected_level": "info",
        "expected_service": "db-migrator",
        "expected_format": "text",
        "expected_message_contains": "Migration v42",
    },
    # 4. DEBUG-level log with service marker
    {
        "line": "2024-03-15 11:45:30 [payments] DEBUG: Request body validated — proceeding to charge",
        "expected_level": "debug",
        "expected_service": "payments",
        "expected_format": "text",
        "expected_message_contains": "Request body validated",
    },
    # 5. Plain log with no timestamp (just message + level keyword)
    {
        "line": "FATAL: Out of memory — shutting down process [orchestrator]",
        "expected_level": "error",  # FATAL maps to error
        "expected_service": "orchestrator",
        "expected_format": "text",
        "expected_message_contains": "Out of memory",
    },
]

# --- Nginx access log fixtures ---
# Hand-written after real nginx combined log format:
#   $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
NGINX_FIXTURES = [
    # 1. Successful GET request (200)
    {
        "line": '192.168.1.100 - - [15/Mar/2024:08:30:45 +0000] "GET /api/v1/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"',
        "expected_level": "info",
        "expected_service": "nginx",
        "expected_format": "nginx",
        "expected_status": 200,
        "expected_remote_addr": "192.168.1.100",
        "expected_method": "GET",
        "expected_path": "/api/v1/users",
        "expected_body_bytes": "1234",
    },
    # 2. Server error (500)
    {
        "line": '10.0.0.5 - admin [15/Mar/2024:08:31:00 +0000] "POST /api/v1/orders HTTP/1.1" 500 89 "https://app.example.com/dashboard" "curl/7.88.1"',
        "expected_level": "error",
        "expected_service": "nginx",
        "expected_format": "nginx",
        "expected_status": 500,
        "expected_remote_addr": "10.0.0.5",
        "expected_method": "POST",
        "expected_path": "/api/v1/orders",
    },
    # 3. Not found (404)
    {
        "line": '172.16.0.1 - - [15/Mar/2024:08:32:15 +0000] "GET /favicon.ico HTTP/1.1" 404 45 "https://app.example.com/" "Mozilla/5.0"',
        "expected_level": "warn",
        "expected_service": "nginx",
        "expected_format": "nginx",
        "expected_status": 404,
        "expected_remote_addr": "172.16.0.1",
    },
]

# --- Malformed / edge case lines ---
# These represent inputs that should NOT cause crashes or exceptions.
MALFORMED_LINES = [
    "",                              # empty line
    "   ",                           # whitespace only
    "{invalid json",                 # broken JSON
    "\x00\x01\x02",                  # binary garbage
    "just some random text without any structure at all",
    "2024-03-15 [missing-level] just a date and service bracket",
    "-",                             # single dash (common in piped input)
    " " * 500,                       # very long whitespace
]


# =============================================================================
# TESTS
# =============================================================================

class TestJSONLogParser(unittest.TestCase):
    """Verify JSON parser extracts correct fields from independent fixtures."""

    def setUp(self):
        self.parser = JSONLogParser()

    def test_parses_standard_json(self):
        """Fixture 1: Standard JSON with timestamp, level, service, message."""
        entry = self.parser.parse(JSON_FIXTURES[0]["line"])
        self.assertIsNotNone(entry, "Should parse valid JSON")
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["service"], "api-gateway")
        self.assertEqual(entry["timestamp"], "2024-03-15T08:30:45.123Z")
        self.assertIn("Connection timeout", entry["message"])
        # Verify nested fields are preserved
        self.assertIn("trace_id", entry["fields"])
        self.assertEqual(entry["fields"]["trace_id"], "abc123def456")

    def test_parses_json_with_severity_field(self):
        """Fixture 2: JSON with 'severity' and 'logger' alternate field names."""
        entry = self.parser.parse(JSON_FIXTURES[1]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "WARN")
        self.assertEqual(entry["service"], "auth-service")
        self.assertEqual(entry["timestamp"], "2024-03-15T09:00:00.000Z")
        self.assertIn("Rate limit", entry["message"])

    def test_parses_json_with_at_timestamp_and_lvl(self):
        """Fixture 3: JSON with @timestamp and lvl field names."""
        entry = self.parser.parse(JSON_FIXTURES[2]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "INFO")
        self.assertEqual(entry["service"], "scheduler")
        self.assertEqual(entry["timestamp"], "2024-03-15T10:15:30.000Z")
        self.assertIn("cleanup-temp-files", entry["message"])

    def test_parses_minimal_json(self):
        """Fixture 4: Minimal JSON with only a message field."""
        entry = self.parser.parse(JSON_FIXTURES[3]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["level"], "info")  # default
        self.assertIn("Heartbeat", entry["message"])

    def test_rejects_invalid_json(self):
        """Broken JSON should return None, not crash."""
        self.assertIsNone(self.parser.parse("{invalid json"))

    def test_rejects_non_dict_json(self):
        """JSON arrays or scalars should return None."""
        self.assertIsNone(self.parser.parse("[1, 2, 3]"))
        self.assertIsNone(self.parser.parse("42"))
        self.assertIsNone(self.parser.parse('"just a string"'))


class TestTextLogParser(unittest.TestCase):
    """Verify text parser extracts correct fields from independent fixtures."""

    def setUp(self):
        self.parser = TextLogParser()

    def test_parses_syslog_style(self):
        """Fixture 1: Syslog-style with timestamp, service bracket, ERROR level."""
        entry = self.parser.parse(TEXT_FIXTURES[0]["line"])
        self.assertIsNotNone(entry, "Should parse non-empty text line")
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["service"], "worker-3")
        self.assertIsNotNone(entry["timestamp"], "Should extract timestamp")
        self.assertIn("Task queue overflow", entry["message"])

    def test_parses_python_logging_style(self):
        """Fixture 2: Python logging with ISO timestamp, WARNING level."""
        entry = self.parser.parse(TEXT_FIXTURES[1]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "cache")
        self.assertIn("Memory usage", entry["message"])

    def test_parses_info_log(self):
        """Fixture 3: INFO-level log with ISO timestamp."""
        entry = self.parser.parse(TEXT_FIXTURES[2]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["service"], "db-migrator")
        self.assertIn("Migration v42", entry["message"])

    def test_parses_debug_log(self):
        """Fixture 4: DEBUG-level log."""
        entry = self.parser.parse(TEXT_FIXTURES[3]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "debug")
        self.assertEqual(entry["service"], "payments")
        self.assertIn("Request body validated", entry["message"])

    def test_parses_fatal_without_timestamp(self):
        """Fixture 5: FATAL log with no timestamp."""
        entry = self.parser.parse(TEXT_FIXTURES[4]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "error")  # FATAL → error
        self.assertEqual(entry["service"], "orchestrator")
        self.assertIn("Out of memory", entry["message"])

    def test_empty_line_returns_none(self):
        """Empty lines should be skipped."""
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse("   "))


class TestNginxLogParser(unittest.TestCase):
    """Verify nginx parser extracts correct fields from independent fixtures."""

    def setUp(self):
        self.parser = NginxLogParser()

    def test_parses_200_response(self):
        """Fixture 1: Successful GET request."""
        entry = self.parser.parse(NGINX_FIXTURES[0]["line"])
        self.assertIsNotNone(entry, "Should parse valid nginx access log")
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["service"], "nginx")
        self.assertIsNotNone(entry["timestamp"])
        self.assertEqual(entry["fields"]["status"], 200)
        self.assertEqual(entry["fields"]["remote_addr"], "192.168.1.100")
        self.assertEqual(entry["fields"]["request"], "GET /api/v1/users HTTP/1.1")
        self.assertEqual(entry["fields"]["body_bytes"], "1234")

    def test_parses_500_response(self):
        """Fixture 2: Server error response."""
        entry = self.parser.parse(NGINX_FIXTURES[1]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["fields"]["status"], 500)
        self.assertEqual(entry["fields"]["remote_addr"], "10.0.0.5")
        self.assertIn("POST /api/v1/orders", entry["fields"]["request"])

    def test_parses_404_response(self):
        """Fixture 3: Not found response."""
        entry = self.parser.parse(NGINX_FIXTURES[2]["line"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["fields"]["status"], 404)
        self.assertEqual(entry["fields"]["remote_addr"], "172.16.0.1")

    def test_rejects_non_nginx_lines(self):
        """Parser should return None for lines that don't match nginx format."""
        self.assertIsNone(self.parser.parse("plain text log line"))
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse('{"json": "log"}'))


class TestMalformedInput(unittest.TestCase):
    """Verify that malformed or edge-case lines do not crash parsing."""

    def setUp(self):
        self.json_parser = JSONLogParser()
        self.text_parser = TextLogParser()
        self.nginx_parser = NginxLogParser()

    def test_malformed_lines_dont_crash(self):
        """All malformed lines should be handled without exception."""
        for line in MALFORMED_LINES:
            try:
                self.json_parser.parse(line)
            except Exception as e:
                self.fail(f"JSONLogParser crashed on {line!r}: {e}")
            try:
                self.text_parser.parse(line)
            except Exception as e:
                self.fail(f"TextLogParser crashed on {line!r}: {e}")
            try:
                self.nginx_parser.parse(line)
            except Exception as e:
                self.fail(f"NginxLogParser crashed on {line!r}: {e}")


class TestAggregatorIntegration(unittest.TestCase):
    """Integration tests verifying the aggregator processes fixtures correctly."""

    def setUp(self):
        self.aggregator = LogAggregator()

    def test_processes_json_fixtures(self):
        """JSON fixtures should be parsed as JSON format."""
        for fixture in JSON_FIXTURES:
            result = self.aggregator._parse_line(fixture["line"])
            self.assertTrue(result)
        # Check that entries have the right format
        json_entries = [e for e in self.aggregator.entries if e.get("format") == "json"]
        self.assertGreaterEqual(len(json_entries), len(JSON_FIXTURES))

    def test_processes_text_fixtures(self):
        """Text fixtures should be parsed as text format."""
        for fixture in TEXT_FIXTURES:
            result = self.aggregator._parse_line(fixture["line"])
            self.assertTrue(result)
        text_entries = [e for e in self.aggregator.entries if e.get("format") == "text"]
        self.assertGreaterEqual(len(text_entries), len(TEXT_FIXTURES))

    def test_processes_nginx_fixtures(self):
        """Nginx fixtures should be parsed as nginx format (NOT text)."""
        for fixture in NGINX_FIXTURES:
            result = self.aggregator._parse_line(fixture["line"])
            self.assertTrue(result)
        nginx_entries = [e for e in self.aggregator.entries if e.get("format") == "nginx"]
        self.assertEqual(
            len(nginx_entries), len(NGINX_FIXTURES),
            "Nginx lines should be parsed as 'nginx' format, not swallowed by text parser"
        )

    def test_summary_has_correct_level_counts(self):
        """Summary should aggregate level counts correctly."""
        fixtures = JSON_FIXTURES + TEXT_FIXTURES + NGINX_FIXTURES
        for fixture in fixtures:
            self.aggregator._parse_line(fixture["line"])

        summary = self.aggregator.get_summary()
        self.assertGreater(summary["total_entries"], 0)
        self.assertIn("by_level", summary)
        self.assertIn("by_service", summary)
        # At least some error/warn/info entries
        levels = summary["by_level"]
        self.assertTrue(
            any(l in levels for l in ["error", "warn", "info"]),
            f"Should have recognized log levels, got: {levels}"
        )

    def test_error_timeline_includes_errors(self):
        """Error timeline should track error-level entries."""
        # Process a known error fixture
        self.aggregator._parse_line(JSON_FIXTURES[0]["line"])  # ERROR
        self.aggregator._parse_line(NGINX_FIXTURES[1]["line"])  # 500 → error

        timeline = self.aggregator.get_error_timeline()
        total_errors = sum(item["count"] for item in timeline)
        self.assertGreaterEqual(total_errors, 2)

    def test_build_report_json_exports(self):
        """JSON export should not crash with fixture data."""
        for fixture in JSON_FIXTURES + TEXT_FIXTURES + NGINX_FIXTURES:
            self.aggregator._parse_line(fixture["line"])

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            self.aggregator.export_json(tmp)
            self.assertTrue(Path(tmp).exists())
            with open(tmp) as f:
                data = json.load(f)
            self.assertIn("summary", data)
            self.assertIn("entries", data)
        finally:
            Path(tmp).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
