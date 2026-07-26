import os
import sys
import tempfile
import json
import pytest
from pathlib import Path

# Add tools directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from log_aggregator import (
    JSONLogParser,
    TextLogParser,
    NginxLogParser,
    LogAggregator,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestJSONLogParser:
    """Unit tests for JSONLogParser using hand-written fixture cases."""

    def test_parse_valid_json_standard_keys(self):
        parser = JSONLogParser()
        line = '{"timestamp": "2024-01-15T10:30:45", "level": "ERROR", "service": "auth-service", "message": "Failed login attempt for user admin", "user_id": 42}'
        result = parser.parse(line)
        assert result is not None
        assert result["timestamp"] == 1705314645
        assert result["level"] == "ERROR"
        assert result["service"] == "auth-service"
        assert result["message"] == "Failed login attempt for user admin"
        assert result["format"] == "json"
        assert result["fields"]["user_id"] == 42

    def test_parse_json_alternate_keys(self):
        parser = JSONLogParser()
        line = '{"@timestamp": "2024-01-15T11:00:00", "severity": "WARN", "app": "checkout-api", "msg": "Payment gateway response timeout", "retry_count": 3}'
        result = parser.parse(line)
        assert result is not None
        assert result["timestamp"] == 1705316400
        assert result["level"] == "WARN"
        assert result["service"] == "checkout-api"
        assert result["message"] == "Payment gateway response timeout"
        assert result["format"] == "json"
        assert result["fields"]["retry_count"] == 3

    def test_parse_json_numeric_timestamp(self):
        parser = JSONLogParser()
        line = '{"time": 1705320930, "lvl": "INFO", "logger": "user-service", "event": "User registered", "user_email": "test@example.com"}'
        result = parser.parse(line)
        assert result is not None
        assert result["timestamp"] == 1705320930
        assert result["level"] == "INFO"
        assert result["service"] == "user-service"
        assert result["message"] == "User registered"
        assert result["format"] == "json"

    def test_parse_invalid_json(self):
        parser = JSONLogParser()
        assert parser.parse("not a json string") is None
        assert parser.parse('{"incomplete": ') is None
        assert parser.parse("12345") is None


class TestTextLogParser:
    """Unit tests for TextLogParser using hand-written fixture cases."""

    def test_parse_iso8601_text(self):
        parser = TextLogParser()
        line = "2024-01-15T10:30:45 [auth-service] ERROR Failed login attempt for user admin"
        result = parser.parse(line)
        assert result is not None
        assert result["timestamp"] == 1705314645
        assert result["level"] == "error"
        assert result["service"] == "auth-service"
        assert result["format"] == "text"
        assert result["message"] == line

    def test_parse_syslog_text(self):
        parser = TextLogParser()
        line = "Jan 15 12:15:30 host1 USER_SVC: INFO User registered successfully"
        result = parser.parse(line)
        assert result is not None
        assert result["level"] == "info"
        assert result["service"] == "USER_SVC"
        assert result["format"] == "text"

    def test_parse_standard_text(self):
        parser = TextLogParser()
        line = "2024-01-15 11:00:00 WARN PAYMENT: Retry attempt 3 failed"
        result = parser.parse(line)
        assert result is not None
        assert result["timestamp"] == 1705316400
        assert result["level"] == "warn"
        assert result["service"] == "PAYMENT"
        assert result["format"] == "text"

    def test_empty_line(self):
        parser = TextLogParser()
        assert parser.parse("") is None
        assert parser.parse("   \n") is None


class TestNginxLogParser:
    """Unit tests for NginxLogParser using hand-written fixture cases."""

    def test_parse_nginx_200_info(self):
        parser = NginxLogParser()
        line = '192.168.1.10 - frank [15/Jan/2024:14:32:10 +0000] "GET /api/v1/health HTTP/1.1" 200 123 "https://example.com" "Mozilla/5.0"'
        result = parser.parse(line)
        assert result is not None
        assert result["service"] == "nginx"
        assert result["format"] == "nginx"
        assert result["level"] == "info"
        assert result["message"] == "GET /api/v1/health HTTP/1.1"
        assert result["fields"]["remote_addr"] == "192.168.1.10"
        assert result["fields"]["remote_user"] == "frank"
        assert result["fields"]["status"] == 200
        assert result["fields"]["body_bytes"] == "123"
        assert result["fields"]["referer"] == "https://example.com"
        assert result["fields"]["user_agent"] == "Mozilla/5.0"

    def test_parse_nginx_404_warn(self):
        parser = NginxLogParser()
        line = '10.0.0.1 - - [15/Jan/2024:14:33:15 +0000] "GET /missing/resource HTTP/1.1" 404 456 "-" "curl/7.68.0"'
        result = parser.parse(line)
        assert result is not None
        assert result["level"] == "warn"
        assert result["fields"]["remote_user"] == "-"
        assert result["fields"]["status"] == 404

    def test_parse_nginx_500_error(self):
        parser = NginxLogParser()
        line = '172.16.0.5 - - [15/Jan/2024:14:34:20 +0000] "POST /api/v1/checkout HTTP/1.1" 500 789 "-" "PostmanRuntime/7.26.8"'
        result = parser.parse(line)
        assert result is not None
        assert result["level"] == "error"
        assert result["fields"]["status"] == 500

    def test_parse_non_nginx_line(self):
        parser = NginxLogParser()
        assert parser.parse("2024-01-15T10:30:45 [auth-service] ERROR") is None


class TestLogAggregatorWithFixtures:
    """Integration and robustness tests for LogAggregator using fixture files."""

    def test_process_json_fixture(self):
        aggregator = LogAggregator()
        fixture_path = FIXTURES_DIR / "json_logs.log"
        count = aggregator.process_file(str(fixture_path))
        assert count == 4
        summary = aggregator.get_summary()
        assert summary["total_entries"] == 4
        assert summary["by_service"]["auth-service"] == 1
        assert summary["by_service"]["checkout-api"] == 1
        assert summary["by_service"]["user-service"] == 1
        assert summary["by_service"]["cache-service"] == 1

    def test_process_plain_text_fixture(self):
        aggregator = LogAggregator()
        fixture_path = FIXTURES_DIR / "plain_text.log"
        count = aggregator.process_file(str(fixture_path))
        assert count == 4
        summary = aggregator.get_summary()
        assert summary["total_entries"] == 4

    def test_process_nginx_fixture(self):
        aggregator = LogAggregator()
        fixture_path = FIXTURES_DIR / "nginx_access.log"
        count = aggregator.process_file(str(fixture_path))
        assert count == 3
        summary = aggregator.get_summary()
        assert summary["total_entries"] == 3
        assert summary["by_service"]["nginx"] == 3
        assert summary["by_level"]["info"] == 1
        assert summary["by_level"]["warn"] == 1
        assert summary["by_level"]["error"] == 1

    def test_process_malformed_fixture_robustness(self):
        """Acceptance Criterion 2: Ensure parsing does not crash on malformed/unsupported lines."""
        aggregator = LogAggregator()
        fixture_path = FIXTURES_DIR / "malformed.log"
        # Must execute without raising exceptions or crashing
        count = aggregator.process_file(str(fixture_path))
        assert isinstance(count, int)
        summary = aggregator.get_summary()
        assert isinstance(summary["total_entries"], int)

    def test_cli_exports_and_methods(self):
        """Acceptance Criterion 5: Ensure existing log aggregation functions remain compatible."""
        aggregator = LogAggregator()
        aggregator.process_file(str(FIXTURES_DIR / "json_logs.log"))
        aggregator.process_file(str(FIXTURES_DIR / "nginx_access.log"))

        # Test search
        results = aggregator.search("login")
        assert len(results) >= 1

        # Test breakdown and timeline
        breakdown = aggregator.get_service_breakdown()
        assert "nginx" in breakdown
        assert "auth-service" in breakdown

        timeline = aggregator.get_error_timeline()
        assert isinstance(timeline, list)

        # Test exports to temporary files
        with tempfile.TemporaryDirectory() as tmpdir:
            json_out = os.path.join(tmpdir, "out.json")
            csv_out = os.path.join(tmpdir, "out.csv")
            html_out = os.path.join(tmpdir, "out.html")

            aggregator.export_json(json_out)
            assert os.path.exists(json_out)

            aggregator.export_csv(csv_out)
            assert os.path.exists(csv_out)

            aggregator.generate_html_report(html_out)
            assert os.path.exists(html_out)
