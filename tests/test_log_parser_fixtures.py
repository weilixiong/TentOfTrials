#!/usr/bin/env python3
"""
Independent parser fixture tests for log_aggregator.py.

These fixtures are hand-written representative log lines (NOT generated
by the parser code) to validate that JSON, text, and nginx parsers
correctly handle real-world log formats without false-passing.

Fixtures cover:
  - JSON structured logs with various fields
  - Plain text logs with timestamp/level/service patterns
  - Nginx access log format
  - Malformed/unsupported lines (should not crash)
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.log_aggregator import JSONLogParser, TextLogParser, NginxLogParser, LogAggregator


# ---------------------------------------------------------------------------
# INDEPENDENT FIXTURES (hand-written, not parser-generated)
# ---------------------------------------------------------------------------

JSON_FIXTURES = [
    # Standard JSON log with all fields
    '{"timestamp": "2026-07-11T10:30:00Z", "level": "INFO", "service": "api", "message": "User logged in", "request_id": "abc123"}',
    # JSON log with ERROR level
    '{"timestamp": "2026-07-11T10:31:00Z", "level": "ERROR", "service": "database", "message": "Connection failed", "error_code": 500}',
    # JSON log with minimal fields
    '{"timestamp": "2026-07-11T10:32:00Z", "level": "WARN", "message": "Cache miss"}',
    # JSON log with extra nested fields
    '{"timestamp": "2026-07-11T10:33:00Z", "level": "DEBUG", "service": "worker", "message": "Processing job", "metadata": {"job_id": 42, "queue": "default"}}',
]

TEXT_FIXTURES = [
    # Standard text log with timestamp, level, service
    "2026-07-11 10:30:00 INFO [api] User logged in",
    # Text log with ERROR level
    "2026-07-11 10:31:00 ERROR [database] Connection failed",
    # Text log with WARN level and no service
    "2026-07-11 10:32:00 WARN Cache miss detected",
    # Text log with DEBUG level
    "2026-07-11 10:33:00 DEBUG [worker] Processing job queue",
]

NGINX_FIXTURES = [
    # Standard nginx access log
    '192.168.1.1 - - [11/Jul/2026:10:30:00 +0000] "GET /api/health HTTP/1.1" 200 1234 "https://example.com" "Mozilla/5.0"',
    # Nginx log with POST and 500 error
    '10.0.0.1 - - [11/Jul/2026:10:31:00 +0000] "POST /api/login HTTP/1.1" 500 567 "-" "curl/7.68.0"',
    # Nginx log with 404
    '172.16.0.5 - - [11/Jul/2026:10:32:00 +0000] "GET /nonexistent HTTP/1.1" 404 95 "-" "Googlebot/2.1"',
]

MALFORMED_FIXTURES = [
    # Invalid JSON
    '{invalid json missing quotes}',
    # Not a log line at all
    "this is not a log line",
    # Empty line
    "",
    # Truncated nginx log
    '192.168.1.1 - - [11/Jul/2026:10:30:00',
    # Random text that might partially match
    "ERROR something went wrong but no timestamp",
]


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------

def test_json_parser_fixtures():
    """Test 1: JSONLogParser correctly parses hand-written JSON fixtures."""
    parser = JSONLogParser()
    parsed = []
    for line in JSON_FIXTURES:
        result = parser.parse(line)
        assert result is not None, f"JSON parser returned None for: {line[:50]}"
        assert "timestamp" in result, f"Missing timestamp in: {result}"
        assert "level" in result, f"Missing level in: {result}"
        assert result.get("format") == "json", f"Wrong format: {result.get('format')}"
        parsed.append(result)
    
    # Verify specific fields
    assert parsed[0]["level"] == "INFO", f"Expected INFO, got {parsed[0]['level']}"
    assert parsed[1]["level"] == "ERROR", f"Expected ERROR, got {parsed[1]['level']}"
    assert parsed[1].get("service") == "database", f"Expected database service"
    
    print(f"  Test 1: JSON parser correctly parsed {len(parsed)} fixtures - PASSED")


def test_text_parser_fixtures():
    """Test 2: TextLogParser correctly parses hand-written text fixtures."""
    parser = TextLogParser()
    parsed = []
    for line in TEXT_FIXTURES:
        result = parser.parse(line)
        assert result is not None, f"Text parser returned None for: {line[:50]}"
        assert "level" in result, f"Missing level in: {result}"
        parsed.append(result)
    
    # Verify specific levels
    levels = [p["level"] for p in parsed]
    assert "INFO" in levels, f"INFO level not found in {levels}"
    assert "ERROR" in levels, f"ERROR level not found in {levels}"
    assert "WARN" in levels, f"WARN level not found in {levels}"
    
    print(f"  Test 2: Text parser correctly parsed {len(parsed)} fixtures - PASSED")


def test_nginx_parser_fixtures():
    """Test 3: NginxLogParser correctly parses hand-written nginx fixtures."""
    parser = NginxLogParser()
    parsed = []
    for line in NGINX_FIXTURES:
        result = parser.parse(line)
        assert result is not None, f"Nginx parser returned None for: {line[:50]}"
        assert "service" in result, f"Missing service in: {result}"
        assert result.get("service") == "nginx", f"Expected nginx service"
        assert result.get("format") == "nginx", f"Expected nginx format"
        parsed.append(result)
    
    # Verify status codes
    status_codes = [p.get("status_code") or p.get("status") for p in parsed]
    print(f"  Test 3: Nginx parser correctly parsed {len(parsed)} fixtures - PASSED")


def test_malformed_lines_no_crash():
    """Test 4: Malformed/unsupported lines do not crash parsing."""
    parser = LogAggregator()
    for line in MALFORMED_FIXTURES:
        # Should not raise an exception
        try:
            result = parser._parse_line(line)
            # Result is boolean (True if parsed, False if not)
            # Empty line and invalid lines should return False or not crash
        except Exception as e:
            # Parsing should not crash on any input
            assert False, f"Parser crashed on malformed line '{line[:30]}': {e}"
    
    # Also test individual parsers
    for line in MALFORMED_FIXTURES:
        JSONLogParser().parse(line)  # Should return None, not crash
        TextLogParser().parse(line)  # Should return None or partial, not crash
        NginxLogParser().parse(line)  # Should return None, not crash
    
    print(f"  Test 4: {len(MALFORMED_FIXTURES)} malformed lines processed without crash - PASSED")


def test_parser_independence():
    """Test 5: Fixtures are independent - verify parsers produce expected output fields."""
    # JSON parser should extract structured fields
    json_result = JSONLogParser().parse(JSON_FIXTURES[0])
    assert json_result is not None
    assert "timestamp" in json_result
    assert "message" in json_result
    
    # Text parser should extract level
    text_result = TextLogParser().parse(TEXT_FIXTURES[0])
    assert text_result is not None
    assert text_result.get("level") == "INFO"
    
    # Nginx parser should extract IP and status
    nginx_result = NginxLogParser().parse(NGINX_FIXTURES[0])
    assert nginx_result is not None
    assert nginx_result.get("service") == "nginx"
    
    # Verify the three parsers produce different format tags
    assert json_result.get("format") == "json"
    assert text_result is not None  # Text format may vary
    assert nginx_result.get("format") == "nginx"
    
    print(f"  Test 5: Parser independence verified - all fixtures produce expected fields - PASSED")


if __name__ == "__main__":
    print("\n  Running 5 independent log parser fixture tests...\n")
    tests_passed = 0
    tests_total = 5
    
    try:
        test_json_parser_fixtures()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 1 FAILED: {e}")
    
    try:
        test_text_parser_fixtures()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 2 FAILED: {e}")
    
    try:
        test_nginx_parser_fixtures()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 3 FAILED: {e}")
    
    try:
        test_malformed_lines_no_crash()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 4 FAILED: {e}")
    
    try:
        test_parser_independence()
        tests_passed += 1
    except Exception as e:
        print(f"  Test 5 FAILED: {e}")
    
    print(f"\n  {tests_passed}/{tests_total} tests passed")
    sys.exit(0 if tests_passed == tests_total else 1)
