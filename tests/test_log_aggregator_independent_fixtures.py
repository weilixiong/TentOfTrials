#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "log_aggregator"


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8").strip()


def test_json_fixture():
    entry = JSONLogParser().parse(read_fixture("json_structured.log"))

    assert entry is not None
    assert entry["format"] == "json"
    assert entry["timestamp"] == "2026-07-06T10:15:30Z"
    assert entry["level"] == "ERROR"
    assert entry["service"] == "billing"
    assert entry["message"] == "payment failed"
    assert entry["fields"]["request_id"] == "req-123"


def test_plain_text_fixture():
    entry = TextLogParser().parse(read_fixture("plain_text.log"))

    assert entry is not None
    assert entry["format"] == "text"
    assert entry["timestamp"] is not None
    assert entry["level"] == "warn"
    assert entry["service"] == "auth"
    assert "token refresh delayed" in entry["message"]


def test_nginx_fixture_direct_parser():
    entry = NginxLogParser().parse(read_fixture("nginx_access.log"))

    assert entry is not None
    assert entry["format"] == "nginx"
    assert entry["timestamp"] is not None
    assert entry["level"] == "error"
    assert entry["service"] == "nginx"
    assert entry["fields"]["remote_addr"] == "203.0.113.9"
    assert entry["fields"]["request"] == "GET /health HTTP/1.1"
    assert entry["fields"]["status"] == 503
    assert entry["fields"]["body_bytes"] == "17"


def test_malformed_json_does_not_crash_json_parser():
    entry = JSONLogParser().parse(read_fixture("malformed.log"))
    assert entry is None


def test_aggregator_routes_nginx_before_generic_text_parser():
    line = read_fixture("nginx_access.log")

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "access.log"
        log_path.write_text(line + "\n", encoding="utf-8")

        aggregator = LogAggregator()
        count = aggregator.process_file(str(log_path))

    assert count == 1
    assert len(aggregator.entries) == 1
    assert aggregator.entries[0]["format"] == "nginx"
    assert aggregator.service_counts["nginx"] == 1
    assert aggregator.level_counts["error"] == 1


def run_all():
    tests = [
        test_json_fixture,
        test_plain_text_fixture,
        test_nginx_fixture_direct_parser,
        test_malformed_json_does_not_crash_json_parser,
        test_aggregator_routes_nginx_before_generic_text_parser,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print("ALL LOG AGGREGATOR FIXTURE TESTS PASSED")


if __name__ == "__main__":
    run_all()
