#!/usr/bin/env python3
"""Independent parser fixtures and validation for log_aggregator.py"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

JSON_FIXTURES = [
    {"line": '{"timestamp": "2026-06-15T14:30:00", "level": "ERROR", "service": "api-gateway", "message": "Connection timeout to upstream service"}',
     "expect": {"timestamp": "2026-06-15T14:30:00", "level": "ERROR", "service": "api-gateway", "format": "json"}},
    {"line": '{"time": "2026-06-15T10:05:00", "severity": "WARN", "logger": "auth-service", "msg": "Rate limit approaching for user 12345"}',
     "expect": {"timestamp": "2026-06-15T10:05:00", "level": "WARN", "service": "auth-service", "format": "json"}},
    {"line": '{"@timestamp": "2026-06-15T08:00:00", "lvl": "INFO", "app": "worker", "event": "Job completed successfully"}',
     "expect": {"timestamp": "2026-06-15T08:00:00", "level": "INFO", "service": "worker", "format": "json"}},
]

TEXT_FIXTURES = [
    {"line": "2026-06-15 14:30:00 [database] ERROR: Connection pool exhausted after 30 retries", "expect_level": "error", "expect_service": "database"},
    {"line": "Jun 15 14:30:01 webserver WARNING: High memory usage detected (92%)", "expect_level": "warn", "expect_service": None},
    {"line": "2026-06-15 10:00:00 CACHE DEBUG: Miss for key user_session_abc123", "expect_level": "debug", "expect_service": None},
    {"line": "2026-06-15 12:00:00 INFO: System health check passed", "expect_level": "info", "expect_service": None},
    {"line": "2026-06-15 16:45:00 [scheduler] CRITICAL: Job queue full, dropping oldest entries", "expect_level": "error", "expect_service": "scheduler"},
]

NGINX_FIXTURES = [
    {"line": '192.168.1.1 - - [15/Jun/2026:14:30:00 +0000] "GET /api/v1/health HTTP/1.1" 200 1234 "-" "curl/7.88.1"', "expect_level": "info", "expect_service": "nginx", "expect_status": 200},
    {"line": '10.0.0.5 - admin [15/Jun/2026:14:31:00 +0000] "POST /api/v1/orders HTTP/1.1" 500 89 "-" "Mozilla/5.0"', "expect_level": "error", "expect_service": "nginx", "expect_status": 500},
    {"line": '172.16.0.100 - - [15/Jun/2026:14:32:00 +0000] "DELETE /api/v1/sessions/abc123 HTTP/1.1" 404 45 "-" "Python-requests/2.31"', "expect_level": "warn", "expect_service": "nginx", "expect_status": 404},
]

MALFORMED_FIXTURES = [
    {"line": "", "parser": "text"},
    {"line": '{"timestamp": "2026-01-01", level: broken}', "parser": "json"},
    {"line": "192.168.1.1 - - [invalid", "parser": "nginx"},
    {"line": "\x00\x01\x02\x03\xff\xfe\xfd\xfc", "parser": "text"},
    {"line": "用户登录成功 [user_id=42]", "parser": "text"},
]

def validate_json_parser():
    parser = JSONLogParser(); errors = []
    for i, fixture in enumerate(JSON_FIXTURES):
        result = parser.parse(fixture["line"])
        if result is None:
            errors.append(f"  JSON #{i}: parse returned None for: {fixture['line'][:60]}..."); continue
        for key, expected in fixture["expect"].items():
            got = result.get(key)
            if got != expected:
                errors.append(f"  JSON #{i}: {key} expected={expected!r}, got={got!r}")
    for i, fixture in enumerate(MALFORMED_FIXTURES):
        if fixture["parser"] != "json": continue
        try:
            parser.parse(fixture["line"])
        except Exception as e:
            errors.append(f"  JSON malformed #{i}: crashed with {type(e).__name__}: {e}")
    return errors

def validate_text_parser():
    parser = TextLogParser(); errors = []
    for i, fixture in enumerate(TEXT_FIXTURES):
        result = parser.parse(fixture["line"])
        if result is None:
            errors.append(f"  TEXT #{i}: parse returned None for: {fixture['line'][:60]}..."); continue
        level = result.get("level", "unknown").lower()
        if level != fixture["expect_level"]:
            errors.append(f"  TEXT #{i}: level expected={fixture['expect_level']!r}, got={level!r}")
        svc = result.get("service")
        if svc != fixture["expect_service"]:
            errors.append(f"  TEXT #{i}: service expected={fixture['expect_service']!r}, got={svc!r}")
    for i, fixture in enumerate(MALFORMED_FIXTURES):
        if fixture["parser"] != "text": continue
        try:
            parser.parse(fixture["line"])
        except Exception as e:
            errors.append(f"  TEXT malformed #{i}: crashed with {type(e).__name__}: {e}")
    return errors

def validate_nginx_parser():
    parser = NginxLogParser(); errors = []
    for i, fixture in enumerate(NGINX_FIXTURES):
        result = parser.parse(fixture["line"])
        if result is None:
            errors.append(f"  NGINX #{i}: parse returned None for: {fixture['line'][:60]}..."); continue
        level = result.get("level", "").lower()
        if level != fixture["expect_level"]:
            errors.append(f"  NGINX #{i}: level expected={fixture['expect_level']!r}, got={level!r}")
        svc = result.get("service")
        if svc != fixture["expect_service"]:
            errors.append(f"  NGINX #{i}: service expected={fixture['expect_service']!r}, got={svc!r}")
        status = result.get("fields", {}).get("status")
        if status != fixture["expect_status"]:
            errors.append(f"  NGINX #{i}: status expected={fixture['expect_status']!r}, got={status!r}")
    for i, fixture in enumerate(MALFORMED_FIXTURES):
        if fixture["parser"] != "nginx": continue
        try:
            parser.parse(fixture["line"])
        except Exception as e:
            errors.append(f"  NGINX malformed #{i}: crashed with {type(e).__name__}: {e}")
    return errors

def main():
    print("=" * 60)
    print("Log Parser Validation -- Independent Fixtures")
    print("=" * 60)
    all_errors = []
    all_errors.extend(validate_json_parser())
    all_errors.extend(validate_text_parser())
    all_errors.extend(validate_nginx_parser())
    total_tests = len(JSON_FIXTURES) + len(TEXT_FIXTURES) + len(NGINX_FIXTURES) + len(MALFORMED_FIXTURES)
    total_errors = len(all_errors)
    print(f"\nResults:\n  Total tests: {total_tests}\n  Errors: {total_errors}")
    if all_errors:
        print(f"\nErrors:"); [print(e) for e in all_errors]
        return 1
    else:
        print(f"\nAll fixtures pass!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
