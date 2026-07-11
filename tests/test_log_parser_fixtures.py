"""Independent test fixtures for log_aggregator parsers.

These fixtures use hand-written representative log lines — NOT data generated
by the parser itself — to avoid false passes when real log formats drift.
"""
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestJSONLogParser:
    """Test JSON log parser with independent fixtures."""

    def setup_method(self):
        self.parser = JSONLogParser()
        with open(os.path.join(FIXTURES_DIR, 'json_logs.txt')) as f:
            self.lines = f.readlines()

    def test_parses_standard_json_log(self):
        """Standard JSON with timestamp/level/service/message keys."""
        result = self.parser.parse(self.lines[0])
        assert result is not None
        assert result['format'] == 'json'
        assert result['service'] == 'backend'
        assert result['level'] == 'info'
        assert 'Server started' in result['message']

    def test_parses_elasticsearch_format(self):
        """JSON with @timestamp/severity/logger/msg keys (Elasticsearch style)."""
        result = self.parser.parse(self.lines[1])
        assert result is not None
        assert result['service'] == 'auth'
        assert result['level'] == 'error'
        assert 'Failed login' in result['message']

    def test_parses_alternative_keys(self):
        """JSON with time/lvl/app/event keys."""
        result = self.parser.parse(self.lines[2])
        assert result is not None
        assert result['service'] == 'market'
        assert result['level'] == 'warn'
        assert 'Rate limit' in result['message']

    def test_returns_none_for_invalid_json(self):
        """Non-JSON lines should return None."""
        result = self.parser.parse(self.lines[4])
        assert result is None

    def test_all_valid_lines_parse(self):
        """All 4 valid JSON lines should parse successfully."""
        valid_lines = [l for l in self.lines if l.strip() and not l.startswith('{invalid')]
        parsed = [self.parser.parse(l) for l in valid_lines if self.parser.parse(l)]
        assert len(parsed) == 4


class TestTextLogParser:
    """Test text log parser with independent fixtures."""

    def setup_method(self):
        self.parser = TextLogParser()
        with open(os.path.join(FIXTURES_DIR, 'text_logs.txt')) as f:
            self.lines = f.readlines()

    def test_parses_text_log_line(self):
        """Text log line should produce a result with format='text'."""
        result = self.parser.parse(self.lines[0])
        assert result is not None
        assert result['format'] == 'text'
        assert 'Server started' in result['message']

    def test_empty_line_returns_none(self):
        """Empty lines should return None."""
        # Line 4 is empty
        result = self.parser.parse('\n')
        assert result is None

    def test_all_non_empty_lines_parse(self):
        """All non-empty text lines should produce results."""
        results = [self.parser.parse(l) for l in self.lines if l.strip()]
        assert all(r is not None for r in results)
        assert len(results) == 4

    def test_preserves_raw_line(self):
        """Text parser should preserve the raw line in fields."""
        result = self.parser.parse(self.lines[0])
        assert 'raw' in result['fields']
        assert result['fields']['raw'].strip() == self.lines[0].strip()


class TestNginxLogParser:
    """Test Nginx log parser with independent fixtures."""

    def setup_method(self):
        self.parser = NginxLogParser()
        with open(os.path.join(FIXTURES_DIR, 'nginx_logs.txt')) as f:
            self.lines = f.readlines()

    def test_parses_standard_nginx_log(self):
        """Standard nginx access log with GET request."""
        result = self.parser.parse(self.lines[0])
        assert result is not None
        assert result['format'] == 'nginx'
        assert result['service'] == 'nginx'

    def test_parses_post_request(self):
        """POST request with 401 status."""
        result = self.parser.parse(self.lines[1])
        assert result is not None
        assert 'POST' in str(result.get('fields', {}))

    def test_parses_429_rate_limit(self):
        """429 status code (rate limited)."""
        result = self.parser.parse(self.lines[2])
        assert result is not None

    def test_parses_304_not_modified(self):
        """304 status code (not modified)."""
        result = self.parser.parse(self.lines[3])
        assert result is not None

    def test_all_lines_parse(self):
        """All 4 nginx lines should parse successfully."""
        results = [self.parser.parse(l) for l in self.lines]
        assert all(r is not None for r in results)
        assert len(results) == 4

    def test_invalid_nginx_line_returns_none(self):
        """Non-nginx format should return None."""
        result = self.parser.parse('this is not an nginx log line\n')
        assert result is None
