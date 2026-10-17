#!/usr/bin/env python3
"""
Independent parser fixture validation for TentOfTrials log parsers.

This script validates the JSON, text, and nginx log parsers against
hand-written fixture data. It verifies that each parser correctly extracts:
  - timestamp
  - level
  - service/format
  - key fields (message, remote_addr, status, etc.)

Malformed lines are tested to ensure they don't crash the parser.

Usage:
    python3 validate_fixtures.py [--fixtures-dir DIR]

Exit code 0 = all validations passed, 1 = failures detected.
"""

import argparse
import json
import sys
from pathlib import Path

# Find the tools directory containing log_aggregator.py
# Search relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLS_CANDIDATES = [
    SCRIPT_DIR.parent / "tools",  # fixtures/ inside repo root
    SCRIPT_DIR / "tools",          # fixtures/ inside tools/
    SCRIPT_DIR,                    # fixtures/ IS tools/
    Path("/home/redman8326/tentoftrials/tools"),  # local dev clone
]

TOOLS_DIR = None
for candidate in TOOLS_CANDIDATES:
    if (candidate / "log_aggregator.py").exists():
        TOOLS_DIR = candidate
        break

if TOOLS_DIR is None:
    print("ERROR: Could not find log_aggregator.py in any expected location.")
    print("Searched:")
    for c in TOOLS_CANDIDATES:
        print(f"  {c}")
    sys.exit(1)

sys.path.insert(0, str(TOOLS_DIR))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser, LogAggregator


# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------

class FixtureTestCase:
    """A single validation case for a parser fixture."""
    def __init__(self, name, expected_format, expected_level=None,
                 expected_service=None, expected_timestamp=None,
                 expected_message=None, expected_fields=None,
                 should_parse=True, line_index=0):
        self.name = name
        self.expected_format = expected_format
        self.expected_level = expected_level
        self.expected_service = expected_service
        self.expected_timestamp = expected_timestamp
        self.expected_message = expected_message
        self.expected_fields = expected_fields or {}
        self.should_parse = should_parse
        self.line_index = line_index

    def validate(self, entry, raw_line):
        """Validate a parsed entry against expectations. Returns list of errors."""
        errors = []

        if self.should_parse:
            if entry is None:
                errors.append(f"  FAIL: line did not parse: {raw_line[:80]}")
                return errors

            if entry.get('format') != self.expected_format:
                errors.append(f"  FAIL: format={entry.get('format')}, expected={self.expected_format}")

            if self.expected_level and entry.get('level') != self.expected_level:
                errors.append(f"  FAIL: level={entry.get('level')}, expected={self.expected_level}")

            if self.expected_service and entry.get('service') != self.expected_service:
                errors.append(f"  FAIL: service={entry.get('service')}, expected={self.expected_service}")

            if self.expected_timestamp and entry.get('timestamp') != self.expected_timestamp:
                errors.append(f"  FAIL: timestamp={entry.get('timestamp')}, expected={self.expected_timestamp}")

            if self.expected_message and entry.get('message') != self.expected_message:
                errors.append(f"  FAIL: message={entry.get('message')!r}, expected={self.expected_message!r}")

            for field_name, expected_value in self.expected_fields.items():
                actual_value = entry.get('fields', {}).get(field_name)
                if actual_value != expected_value:
                    errors.append(f"  FAIL: fields.{field_name}={actual_value!r}, expected={expected_value!r}")
        else:
            if entry is not None:
                errors.append(f"  FAIL: line should not parse but did: {raw_line[:80]}")

        return errors


# ---------------------------------------------------------------------------
# JSON parser test cases
# ---------------------------------------------------------------------------

JSON_TEST_CASES = [
    # Line 0: standard JSON with timestamp/level/service/message
    FixtureTestCase(
        name="json_standard",
        expected_format="json",
        expected_level="INFO",
        expected_service="auth",
        expected_timestamp="2024-01-15T10:30:00Z",
        expected_message="User login successful for user_id=12345",
        line_index=0,
    ),
    # Line 1: JSON with time/severity/logger/msg fields
    FixtureTestCase(
        name="json_alt_fields",
        expected_format="json",
        expected_level="ERROR",
        expected_service="payment",
        expected_timestamp="2024-01-15T10:31:00Z",
        expected_message="Transaction failed for order_id=98765: insufficient_funds",
        line_index=1,
    ),
    # Line 2: JSON with @timestamp and app/event
    FixtureTestCase(
        name="json_at_timestamp",
        expected_format="json",
        expected_level="WARN",
        expected_service="api",
        expected_timestamp="2024-01-15T10:32:00Z",
        expected_message="Rate limit exceeded for client_ip=192.168.1.100",
        line_index=2,
    ),
    # Line 3: JSON with DEBUG level
    FixtureTestCase(
        name="json_debug",
        expected_format="json",
        expected_level="DEBUG",
        expected_service="cache",
        expected_timestamp="2024-01-15T10:33:00Z",
        expected_message="Cache hit for key=user:profile:12345",
        line_index=3,
    ),
    # Line 4: JSON with extra nested fields
    FixtureTestCase(
        name="json_nested_fields",
        expected_format="json",
        expected_level="ERROR",
        expected_service="auth",
        expected_timestamp="2024-01-15T10:34:00Z",
        expected_message="Authentication failed for user_id=99999: invalid_token",
        expected_fields={"metadata": {"ip": "10.0.0.1", "user_agent": "Mozilla/5.0"}},
        line_index=4,
    ),
    # Line 5: JSON with time/severity/logger/msg + metadata
    FixtureTestCase(
        name="json_with_metadata",
        expected_format="json",
        expected_level="INFO",
        expected_service="notification",
        expected_timestamp="2024-01-15T10:35:00Z",
        expected_message="Email sent to user@example.com",
        expected_fields={"metadata": {"template": "welcome", "priority": "normal"}},
        line_index=5,
    ),
]

# JSON malformed lines that should return None
JSON_MALFORMED_CASES = [
    ("json_malformed_truncated", 0),
    ("json_malformed_incomplete", 1),
    ("json_malformed_not_json", 2),
    ("json_malformed_array", 3),
]


# ---------------------------------------------------------------------------
# Text parser test cases
# ---------------------------------------------------------------------------

TEXT_TEST_CASES = [
    # Line 0: ISO 8601 timestamp
    FixtureTestCase(
        name="text_iso8601",
        expected_format="text",
        expected_level="info",
        expected_service="auth",
        expected_message="2024-01-15T10:30:00 INFO [auth] User login successful for user_id=12345",
        line_index=0,
    ),
    # Line 1: Standard timestamp
    FixtureTestCase(
        name="text_standard_ts",
        expected_format="text",
        expected_level="error",
        expected_service="payment",
        expected_message="2024-01-15 10:31:00 ERROR [payment] Transaction failed for order_id=98765: insufficient_funds",
        line_index=1,
    ),
    # Line 2: Syslog-style timestamp
    FixtureTestCase(
        name="text_syslog",
        expected_format="text",
        expected_level="warn",
        expected_service="api",
        expected_message="Jan 15 10:32:00 WARN [api] Rate limit exceeded for client_ip=192.168.1.100",
        line_index=2,
    ),
    # Line 3: DEBUG level
    FixtureTestCase(
        name="text_debug",
        expected_format="text",
        expected_level="debug",
        expected_service="cache",
        expected_message="2024-01-15T10:33:00 DEBUG [cache] Cache hit for key=user:profile:12345",
        line_index=3,
    ),
    # Line 4: ERROR level
    FixtureTestCase(
        name="text_error",
        expected_format="text",
        expected_level="error",
        expected_service="auth",
        expected_message="2024-01-15T10:34:00 ERROR [auth] Authentication failed for user_id=99999: invalid_token",
        line_index=4,
    ),
    # Line 5: Syslog INFO
    FixtureTestCase(
        name="text_syslog_info",
        expected_format="text",
        expected_level="info",
        expected_service="notification",
        expected_message="Jan 15 10:35:00 INFO [notification] Email sent to user@example.com",
        line_index=5,
    ),
]

# Text malformed lines
TEXT_MALFORMED_CASES = [
    ("text_malformed_garbage", 0),
    ("text_malformed_no_level", 1),
]


# ---------------------------------------------------------------------------
# Nginx parser test cases
# ---------------------------------------------------------------------------

NGINX_TEST_CASES = [
    # Line 0: 200 OK
    FixtureTestCase(
        name="nginx_200",
        expected_format="nginx",
        expected_level="info",
        expected_service="nginx",
        expected_message="GET /api/users HTTP/1.1",
        expected_fields={
            "remote_addr": "192.168.1.100",
            "remote_user": "frank",
            "status": 200,
            "body_bytes": "1234",
            "referer": "https://example.com",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        line_index=0,
    ),
    # Line 1: 401 Unauthorized (warn)
    FixtureTestCase(
        name="nginx_401",
        expected_format="nginx",
        expected_level="warn",
        expected_service="nginx",
        expected_message="POST /api/login HTTP/1.1",
        expected_fields={
            "remote_addr": "192.168.1.101",
            "remote_user": "-",
            "status": 401,
            "body_bytes": "567",
            "referer": "-",
            "user_agent": "curl/7.68.0",
        },
        line_index=1,
    ),
    # Line 2: 503 Service Unavailable (error)
    FixtureTestCase(
        name="nginx_503",
        expected_format="nginx",
        expected_level="error",
        expected_service="nginx",
        expected_message="GET /api/orders HTTP/1.1",
        expected_fields={
            "remote_addr": "192.168.1.102",
            "remote_user": "jane",
            "status": 503,
            "body_bytes": "89",
            "referer": "-",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        },
        line_index=2,
    ),
    # Line 3: 404 Not Found (warn)
    FixtureTestCase(
        name="nginx_404",
        expected_format="nginx",
        expected_level="warn",
        expected_service="nginx",
        expected_message="DELETE /api/session HTTP/1.1",
        expected_fields={
            "remote_addr": "192.168.1.103",
            "remote_user": "-",
            "status": 404,
            "body_bytes": "234",
            "referer": "https://example.com/dashboard",
            "user_agent": "PostmanRuntime/7.32.3",
        },
        line_index=3,
    ),
    # Line 4: 500 Internal Server Error (error)
    FixtureTestCase(
        name="nginx_500",
        expected_format="nginx",
        expected_level="error",
        expected_service="nginx",
        expected_message="PUT /api/users/123 HTTP/1.1",
        expected_fields={
            "remote_addr": "10.0.0.50",
            "remote_user": "admin",
            "status": 500,
            "body_bytes": "45",
            "referer": "https://example.com/admin",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
        },
        line_index=4,
    ),
]

# Nginx malformed lines that should return None
NGINX_MALFORMED_CASES = [
    ("nginx_malformed_incomplete", 0),
    ("nginx_malformed_not_nginx", 1),
    ("nginx_malformed_no_status", 2),
]


# ---------------------------------------------------------------------------
# Validation runner
# ---------------------------------------------------------------------------

def load_lines(filepath):
    """Load non-empty lines from a fixture file."""
    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n').rstrip('\r')
            if stripped:
                lines.append(stripped)
    return lines


def run_json_validation(fixtures_dir):
    """Run JSON parser validation against fixtures."""
    print("\n=== JSON Parser Validation ===")
    parser = JSONLogParser()
    errors = []
    passed = 0

    valid_file = fixtures_dir / "json" / "valid_entries.jsonl"
    lines = load_lines(valid_file)

    for tc in JSON_TEST_CASES:
        raw_line = lines[tc.line_index]
        entry = parser.parse(raw_line)
        tc_errors = tc.validate(entry, raw_line)
        if tc_errors:
            errors.extend(tc_errors)
        else:
            passed += 1
            print(f"  PASS: {tc.name}")

    # Test malformed lines
    malformed_file = fixtures_dir / "json" / "malformed_entries.jsonl"
    malformed_lines = load_lines(malformed_file)

    for name, line_idx in JSON_MALFORMED_CASES:
        raw_line = malformed_lines[line_idx]
        entry = parser.parse(raw_line)
        if entry is not None:
            errors.append(f"  FAIL: {name} should not parse but did: {raw_line[:80]}")
        else:
            passed += 1
            print(f"  PASS: {name} (correctly rejected)")

    return passed, errors


def run_text_validation(fixtures_dir):
    """Run text parser validation against fixtures."""
    print("\n=== Text Parser Validation ===")
    parser = TextLogParser()
    errors = []
    passed = 0

    valid_file = fixtures_dir / "text" / "valid_entries.txt"
    lines = load_lines(valid_file)

    for tc in TEXT_TEST_CASES:
        raw_line = lines[tc.line_index]
        entry = parser.parse(raw_line)
        tc_errors = tc.validate(entry, raw_line)
        if tc_errors:
            errors.extend(tc_errors)
        else:
            passed += 1
            print(f"  PASS: {tc.name}")

    # Test malformed lines - these should still parse as text (text parser is permissive)
    # but should not crash
    malformed_file = fixtures_dir / "text" / "malformed_entries.txt"
    malformed_lines = load_lines(malformed_file)

    for name, line_idx in TEXT_MALFORMED_CASES:
        raw_line = malformed_lines[line_idx]
        try:
            entry = parser.parse(raw_line)
            # Text parser is permissive - it should return something or None, but not crash
            passed += 1
            print(f"  PASS: {name} (no crash, returned {'entry' if entry else 'None'})")
        except Exception as e:
            errors.append(f"  FAIL: {name} crashed with: {e}")

    return passed, errors


def run_nginx_validation(fixtures_dir):
    """Run nginx parser validation against fixtures."""
    print("\n=== Nginx Parser Validation ===")
    parser = NginxLogParser()
    errors = []
    passed = 0

    valid_file = fixtures_dir / "nginx" / "valid_entries.log"
    lines = load_lines(valid_file)

    for tc in NGINX_TEST_CASES:
        raw_line = lines[tc.line_index]
        entry = parser.parse(raw_line)
        tc_errors = tc.validate(entry, raw_line)
        if tc_errors:
            errors.extend(tc_errors)
        else:
            passed += 1
            print(f"  PASS: {tc.name}")

    # Test malformed lines
    malformed_file = fixtures_dir / "nginx" / "malformed_entries.log"
    malformed_lines = load_lines(malformed_file)

    for name, line_idx in NGINX_MALFORMED_CASES:
        raw_line = malformed_lines[line_idx]
        entry = parser.parse(raw_line)
        if entry is not None:
            errors.append(f"  FAIL: {name} should not parse but did: {raw_line[:80]}")
        else:
            passed += 1
            print(f"  PASS: {name} (correctly rejected)")

    return passed, errors


def run_aggregator_validation(fixtures_dir):
    """Run full aggregator validation - ensures all parsers work together."""
    print("\n=== LogAggregator Integration Validation ===")
    errors = []
    passed = 0

    aggregator = LogAggregator()

    # Process each valid fixture file
    for fmt, filename in [
        ("json", "valid_entries.jsonl"),
        ("text", "valid_entries.txt"),
        ("nginx", "valid_entries.log"),
    ]:
        filepath = fixtures_dir / fmt / filename
        count = aggregator.process_file(str(filepath))
        expected = {
            "json": 6,
            "text": 6,
            "nginx": 5,
        }[fmt]

        if count == expected:
            passed += 1
            print(f"  PASS: {fmt} file processed {count} entries")
        else:
            errors.append(f"  FAIL: {fmt} file processed {count} entries, expected {expected}")

    # Verify summary
    summary = aggregator.get_summary()
    if summary['total_entries'] >= 17:
        passed += 1
        print(f"  PASS: aggregator total_entries={summary['total_entries']}")
    else:
        errors.append(f"  FAIL: aggregator total_entries={summary['total_entries']}, expected >= 17")

    # Verify all entries have required keys
    required_keys = {'timestamp', 'level', 'service', 'message', 'format'}
    all_valid = True
    for i, entry in enumerate(aggregator.entries):
        missing = required_keys - set(entry.keys())
        if missing:
            errors.append(f"  FAIL: entry {i} missing keys: {missing}")
            all_valid = False
    if all_valid:
        passed += 1
        print(f"  PASS: all {len(aggregator.entries)} entries have required keys")

    return passed, errors


def main():
    parser = argparse.ArgumentParser(description="Validate log parser fixtures")
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing fixture subdirectories (json/, text/, nginx/)",
    )
    args = parser.parse_args()

    fixtures_dir = args.fixtures_dir.resolve()

    print(f"Fixtures directory: {fixtures_dir}")
    print("=" * 60)

    total_passed = 0
    all_errors = []

    passed, errors = run_json_validation(fixtures_dir)
    total_passed += passed
    all_errors.extend(errors)

    passed, errors = run_text_validation(fixtures_dir)
    total_passed += passed
    all_errors.extend(errors)

    passed, errors = run_nginx_validation(fixtures_dir)
    total_passed += passed
    all_errors.extend(errors)

    passed, errors = run_aggregator_validation(fixtures_dir)
    total_passed += passed
    all_errors.extend(errors)

    print("\n" + "=" * 60)
    print(f"Results: {total_passed} passed, {len(all_errors)} failed")

    if all_errors:
        print("\nFailures:")
        for err in all_errors:
            print(err)
        return 1
    else:
        print("\nAll validations passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())