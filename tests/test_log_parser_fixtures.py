"""Regression tests backed by hand-written fixtures independent of parser code."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "logs"
SPEC = importlib.util.spec_from_file_location(
    "log_aggregator", ROOT / "tools" / "log_aggregator.py"
)
log_aggregator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(log_aggregator)


def fixture_lines(name):
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def test_json_parser_uses_hand_written_field_variants_and_rejects_non_objects():
    lines = fixture_lines("json_lines.log")
    parser = log_aggregator.JSONLogParser()

    first = parser.parse(lines[0])
    second = parser.parse(lines[1])

    assert first["timestamp"] == "2026-10-24T09:15:30Z"
    assert first["level"] == "ERROR"
    assert first["service"] == "payments"
    assert first["message"] == "charge declined"
    assert first["fields"]["request_id"] == "req-7"
    assert second["timestamp"] == 1792833391
    assert second["level"] == "warning"
    assert second["service"] == "worker"
    assert second["message"] == "retry scheduled"
    assert parser.parse(lines[2]) is None
    assert parser.parse(lines[3]) is None


def test_text_parser_extracts_timestamp_level_service_and_raw_message():
    lines = fixture_lines("plain_text.log")
    parser = log_aggregator.TextLogParser()

    billing = parser.parse(lines[0])
    scheduler = parser.parse(lines[1])
    gateway = parser.parse(lines[2])

    expected = int(datetime(2026, 10, 24, 11, 22, 33, tzinfo=timezone.utc).timestamp())
    assert billing["timestamp"] == expected
    assert billing["level"] == "error"
    assert billing["service"] == "billing"
    assert billing["message"] == lines[0]
    assert billing["fields"] == {"raw": lines[0]}
    assert scheduler["level"] == "info"
    assert scheduler["service"] == "scheduler"
    assert gateway["level"] == "warn"
    assert gateway["service"] is None
    assert parser.parse("") is None


def test_nginx_parser_covers_success_client_error_and_server_error():
    lines = fixture_lines("nginx_access.log")
    parser = log_aggregator.NginxLogParser()
    entries = [parser.parse(line) for line in lines]

    assert all(entries)
    assert [entry["level"] for entry in entries] == ["info", "error", "warn"]
    assert [entry["fields"]["status"] for entry in entries] == [200, 503, 404]
    assert entries[0]["timestamp"] == int(
        datetime(2026, 10, 24, 12, 34, 56, tzinfo=timezone.utc).timestamp()
    )
    assert entries[0]["service"] == "nginx"
    assert entries[0]["message"] == "GET /health HTTP/1.1"
    assert entries[0]["fields"]["remote_addr"] == "203.0.113.10"
    assert entries[0]["fields"]["remote_user"] == "alice"
    assert entries[1]["fields"]["referer"] == "https://example.test/cart"
    assert parser.parse("this is not an access log") is None


def test_aggregator_routes_nginx_fixture_to_nginx_parser(tmp_path):
    source = FIXTURES / "nginx_access.log"
    copied = tmp_path / "access.log"
    copied.write_bytes(source.read_bytes())

    aggregator = log_aggregator.LogAggregator()
    assert aggregator.process_file(str(copied)) == 3
    assert [entry["format"] for entry in aggregator.entries] == ["nginx"] * 3
    assert aggregator.service_counts == {"nginx": 3}
    assert aggregator.level_counts == {"info": 1, "error": 1, "warn": 1}
