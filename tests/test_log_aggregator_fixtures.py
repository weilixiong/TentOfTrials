from pathlib import Path
import sys

import pytest

# Allow importing the existing production module from tests/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from log_aggregator import (
    JSONLogParser,
    TextLogParser,
    NginxLogParser,
    LogAggregator,
)


FIXTURES = Path(__file__).parent / "fixtures" / "log_aggregator"


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def test_json_fixtures():
    parser = JSONLogParser()
    lines = read_fixture("json.log")

    expected = [
        {
            "timestamp": 1788862530,
            "level": "ERROR",
            "service": "payments",
            "message": "Database connection failed",
            "request_id": "req-7f3a",
            "region": "ap-south-1",
        },
        {
            "timestamp": 1788862590,
            "level": "WARN",
            "service": "api-gateway",
            "message": "Upstream response exceeded latency threshold",
            "request_id": "req-91bc",
        },
        {
            "timestamp": 1788862650,
            "level": "INFO",
            "service": "worker",
            "message": "Job completed",
            "job_id": "job-2048",
        },
    ]

    assert len(lines) == len(expected)

    for line, wanted in zip(lines, expected):
        result = parser.parse(line)

        assert result is not None
        assert result["timestamp"] == wanted["timestamp"]
        assert result["level"] == wanted["level"]
        assert result["service"] == wanted["service"]
        assert result["message"] == wanted["message"]
        assert result["format"] == "json"

        for field, value in wanted.items():
            if field not in {
                "timestamp",
                "level",
                "service",
                "message",
            }:
                assert result["fields"][field] == value


def test_plain_text_fixtures():
    parser = TextLogParser()
    lines = read_fixture("plain_text.log")

    expected = [
        {
            "timestamp": 1788862560,
            "level": "warn",
            "service": "payments",
            "message": "2026-09-08 10:16:00 [payments] WARN: Slow response detected",
        },
        {
            "timestamp": 1788862620,
            "level": "error",
            "service": "api-gateway",
            "message": "2026-09-08 10:17:00 [api-gateway] ERROR: Upstream request failed",
        },
        {
            "timestamp": 1788862680,
            "level": "info",
            "service": "worker",
            "message": "2026-09-08 10:18:00 [worker] INFO: Job completed successfully",
        },
    ]

    assert len(lines) == len(expected)

    for line, wanted in zip(lines, expected):
        result = parser.parse(line)

        assert result is not None
        assert result["timestamp"] == wanted["timestamp"]
        assert result["level"] == wanted["level"]
        assert result["service"] == wanted["service"]
        assert result["message"] == wanted["message"]
        assert result["fields"]["raw"] == wanted["message"]
        assert result["format"] == "text"


def test_nginx_fixtures():
    parser = NginxLogParser()
    lines = read_fixture("nginx.log")

    expected = [
        {
            "timestamp": 1788862620,
            "level": "error",
            "status": 500,
            "remote_addr": "203.0.113.10",
            "request": "GET /api/orders HTTP/1.1",
            "body_bytes": "123",
            "referer": "-",
            "user_agent": "TestClient/1.0",
        },
        {
            "timestamp": 1788862680,
            "level": "warn",
            "status": 401,
            "remote_addr": "198.51.100.42",
            "request": "POST /api/login HTTP/1.1",
            "body_bytes": "87",
            "referer": "https://example.test/",
            "user_agent": "TestClient/1.0",
        },
        {
            "timestamp": 1788862740,
            "level": "info",
            "status": 200,
            "remote_addr": "192.0.2.25",
            "request": "GET /health HTTP/1.1",
            "body_bytes": "42",
            "referer": "-",
            "user_agent": "HealthCheck/1.0",
        },
    ]

    assert len(lines) == len(expected)

    for line, wanted in zip(lines, expected):
        result = parser.parse(line)

        assert result is not None
        assert result["timestamp"] == wanted["timestamp"]
        assert result["level"] == wanted["level"]
        assert result["service"] == "nginx"
        assert result["format"] == "nginx"

        fields = result["fields"]
        assert fields["status"] == wanted["status"]
        assert fields["remote_addr"] == wanted["remote_addr"]
        assert fields["request"] == wanted["request"]
        assert fields["body_bytes"] == wanted["body_bytes"]
        assert fields["referer"] == wanted["referer"]
        assert fields["user_agent"] == wanted["user_agent"]

def test_nginx_fixtures_through_aggregator():
    aggregator = LogAggregator()
    count = aggregator.process_file(str(FIXTURES / "nginx.log"))

    assert count == 3
    assert len(aggregator.entries) == 3

    expected = [
        (1788862620, "error", 500, "GET /api/orders HTTP/1.1"),
        (1788862680, "warn", 401, "POST /api/login HTTP/1.1"),
        (1788862740, "info", 200, "GET /health HTTP/1.1"),
    ]

    for entry, (timestamp, level, status, request) in zip(
        aggregator.entries, expected
    ):
        assert entry["format"] == "nginx"
        assert entry["service"] == "nginx"
        assert entry["timestamp"] == timestamp
        assert entry["level"] == level
        assert entry["fields"]["status"] == status
        assert entry["fields"]["request"] == request


@pytest.mark.parametrize(
    "line",
    [
        "%%% totally malformed log %%%",
        "not a structured record",
        "",
    ],
)
def test_malformed_or_unsupported_input_does_not_crash(line):
    aggregator = LogAggregator()

    # The requirement here is robustness: malformed input must not
    # raise an exception while being processed.
    try:
        result = aggregator._parse_line(line)
    except Exception as exc:
        pytest.fail(f"Parser crashed on malformed input: {exc}")

    if line:
        assert result is True
        assert aggregator.entries