#!/usr/bin/env python3
"""
Independent parser fixture tests for log_aggregator.py

These fixtures are HAND-WRITTEN representative log lines, NOT generated
by the parser itself. This prevents the false-pass issue where test data
and parser logic share the same assumptions.

Each fixture set covers: valid JSON, plain text, nginx-style logs, and
one malformed edge case that should not crash parsing.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

# ── JSON FIXTURES ──────────────────────────────────────────────
JSON_FIXTURES = [
    # Standard structured log with explicit timestamp, level, service
    (
        '{"timestamp": "2024-11-15T08:30:00Z", "level": "ERROR", "service": "auth-api", "message": "Token validation failed for user 4821"}',
        {"timestamp": "2024-11-15T08:30:00Z", "level": "ERROR", "service": "auth-api", "message": "Token validation failed for user 4821", "format": "json"}
    ),
    # Using alternate field names (time, severity, logger)
    (
        '{"time": "2024-11-15T09:00:00", "severity": "WARN", "logger": "payment-worker", "msg": "Retry limit approaching for invoice INV-993"}',
        {"timestamp": "2024-11-15T09:00:00", "level": "WARN", "service": "payment-worker", "message": "Retry limit approaching for invoice INV-993", "format": "json"}
    ),
    # Minimal JSON — only message, everything else defaulted
    (
        '{"message": "Health check completed"}',
        {"timestamp": None, "level": "info", "service": None, "message": "Health check completed", "format": "json"}
    ),
]

# ── PLAIN TEXT FIXTURES ────────────────────────────────────────
TEXT_FIXTURES = [
    # ISO 8601 timestamp with ERROR level
    (
        "2024-11-15T10:15:30Z ERROR [database] Connection pool exhausted (active=50, max=50)",
        {"level": "error", "service": "database", "format": "text"}
    ),
    # Standard timestamp with WARNING level
    (
        "2024-11-15 11:00:00 WARNING [cache] Cache miss rate above threshold: 34.2%",
        {"level": "warn", "service": "cache", "format": "text"}
    ),
    # INFO level with no explicit service bracket
    (
        "2024-11-15T12:00:00Z INFO Scheduler triggered daily report generation",
        {"level": "info", "format": "text"}
    ),
]

# ── NGINX FIXTURES ────────────────────────────────────────────
NGINX_FIXTURES = [
    # Normal successful request (200)
    (
        '192.168.1.10 - - [15/Nov/2024:10:30:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"',
        {"level": "info", "service": "nginx", "format": "nginx"}
    ),
    # 404 (warn)
    (
        '10.0.0.5 - admin [15/Nov/2024:10:31:00 +0000] "POST /api/delete HTTP/1.1" 404 45 "https://example.com" "curl/7.68"',
        {"level": "warn", "service": "nginx", "format": "nginx"}
    ),
    # 500 (error)
    (
        '172.16.0.1 - - [15/Nov/2024:10:32:00 +0000] "GET /api/internal-error HTTP/1.1" 500 89 "-" "python-requests/2.28"',
        {"level": "error", "service": "nginx", "format": "nginx"}
    ),
]

# ── MALFORMED / UNSUPPORTED INPUT ──────────────────────────────
MALFORMED_INPUT = [
    "",                              # empty line
    "   \t  ",                       # whitespace only
    "not a valid log line at all",   # gibberish
    "{broken json",                  # invalid JSON
    "404 - - [broken/nginx/format",  # incomplete nginx line
]

# ── TESTS ──────────────────────────────────────────────────────
json_parser = JSONLogParser()
text_parser = TextLogParser()
nginx_parser = NginxLogParser()

passed = 0
failed = 0

def check(name, actual, expected_fields):
    """Check that all expected fields are present and correct."""
    global passed, failed
    if actual is None:
        print(f"  ✗ {name}: parser returned None")
        failed += 1
        return
    for key, expected in expected_fields.items():
        actual_val = actual.get(key)
        if actual_val != expected:
            print(f"  ✗ {name}: field '{key}' expected '{expected}', got '{actual_val}'")
            failed += 1
            return
    passed += 1

# JSON tests
for i, (line, expected) in enumerate(JSON_FIXTURES):
    result = json_parser.parse(line)
    check(f"JSON fixture {i+1}", result, expected)

# Text tests
for i, (line, expected) in enumerate(TEXT_FIXTURES):
    result = text_parser.parse(line)
    check(f"Text fixture {i+1}", result, expected)

# Nginx tests
for i, (line, expected) in enumerate(NGINX_FIXTURES):
    result = nginx_parser.parse(line)
    check(f"Nginx fixture {i+1}", result, expected)

# Malformed input: parsers should return None, NOT crash
for i, line in enumerate(MALFORMED_INPUT):
    for parser in [json_parser, text_parser, nginx_parser]:
        try:
            result = parser.parse(line)
            # All parsers should either return None or handle gracefully
        except Exception as e:
            print(f"  ✗ Malformed line {i+1} crashed parser {parser.__class__.__name__}: {e}")
            failed += 1
            break

print(f"\n{'─' * 50}")
print(f"Results: {passed} passed, {failed} failed")
if failed > 0:
    print("❌ SOME TESTS FAILED")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED")